"""信号生成、耦合、投影、噪声与实时滤波。"""

import copy

import numpy as np

from ...models.coupling import PatchCouplingEngine
from ...utils import tr, get_logger

logger = get_logger(__name__)

# 热力图频带定义：(fmin, fmax)；fmax=None 表示至 min(Nyquist, 100 Hz)
HEATMAP_BAND_RANGES = {
    'broadband': (0.5, None),
    'delta': (0.5, 4.0),
    'theta': (4.0, 8.0),
    'alpha': (8.0, 13.0),
    'beta': (13.0, 30.0),
    'gamma': (30.0, 100.0),
}
# 窄频带功率低于全频带峰值此比例时，地形图显示为空白（避免 10 Hz 源在 Beta 仍出现 Alpha 形）
HEATMAP_BAND_MIN_BB_RATIO = 0.01


class SimulatorSignal:
    """SimulatorSignal 服务。"""

    def __init__(self, simulator):
        self._sim = simulator
        self._heatmap_forward_cache_key = None
        self._heatmap_forward_series = None
        self._analysis_filter_cache = {}

    def _generate_patch_signals_batch(self, t, n_samples):
        """批量生成Patch信号 - 保持相位连续性"""
        patch_signals = {}
        dt = 1.0 / self._sim.sampling_rate

        for patch_id, patch in self._sim.patches.items():
            # 初始化该patch的信号状态
            if patch_id not in self._sim._signal_states:
                self._sim._signal_states[patch_id] = {'phase': 0.0}

            state = self._sim._signal_states[patch_id]

            # 使用连续性信号生成方法
            signals = self._sim.signal_engine.generate_continuous_waveform(
                patch, n_samples, dt, state
            )
            patch_signals[patch_id] = signals
        return patch_signals

    def _apply_coupling_batch(self, patch_signals, t, n_samples):
        """批量应用耦合"""
        dt = 1.0 / self._sim.sampling_rate
        coupled_signals = {}
        mne_factors = (
            self._get_mne_coupling_factors()
            if self._sim._use_mne_coupling and self._sim._mne_coupling_engine is not None
            else None
        )

        for i in range(n_samples):
            current_signals = {pid: signals[i] for pid, signals in patch_signals.items()}

            if mne_factors is not None:
                current_signals = PatchCouplingEngine.apply_mne_factors(
                    current_signals, mne_factors
                )
            elif self._sim._coupling_models:
                current_time = t[i] if i < len(t) else self._sim.simulation_time + i * dt
                current_signals = self._sim._coupling_engine.compute_coupled_signals(current_signals, current_time)

            for pid, signal in current_signals.items():
                if pid not in coupled_signals:
                    coupled_signals[pid] = []
                coupled_signals[pid].append(signal)

        # 转换为numpy数组
        for pid in coupled_signals:
            coupled_signals[pid] = np.array(coupled_signals[pid])

        return coupled_signals

    def _patches_geometry_signature(self):
        """Patch 偶极子几何签名，用于 MNE 耦合权重缓存失效"""
        parts = []
        for patch_id in sorted(self._sim.patches.keys()):
            patch = self._sim.patches[patch_id]
            verts = tuple(sorted(
                (d.hemi, d.vertno) for d in patch.dipoles
                if getattr(d, 'vertno', None) is not None and getattr(d, 'hemi', None)
            ))
            parts.append((patch_id, verts))
        return tuple(parts)

    def invalidate_mne_coupling_cache(self):
        """清除 MNE 耦合几何权重缓存"""
        self._sim._mne_coupling_factor_cache = None
        self._sim._mne_coupling_factor_cache_key = None

    def _get_mne_coupling_factors(self):
        """预计算 MNE 耦合因子（几何权重 × 强度），每帧只算一次"""
        if self._sim._mne_coupling_engine is None or not self._sim._coupling_models:
            return []

        coupling_page = getattr(self._sim, 'signal_sources_page', None)
        k = coupling_page.knn_spin.value() if coupling_page is not None else 3
        decay_length = coupling_page.decay_spin.value() if coupling_page is not None else 0.02
        coupling_sig = tuple(
            (cid, c.source_patch_id, c.target_patch_id, c.type, c.strength, c.delay)
            for cid, c in sorted(self._sim._coupling_models.items())
        )
        cache_key = (k, decay_length, self._patches_geometry_signature(), coupling_sig)

        if self._sim._mne_coupling_factor_cache_key == cache_key and self._sim._mne_coupling_factor_cache is not None:
            return self._sim._mne_coupling_factor_cache

        factors = []
        for coupling_id, coupling in self._sim._coupling_models.items():
            source_id = coupling.source_patch_id
            target_id = coupling.target_patch_id

            if source_id not in self._sim.patches or target_id not in self._sim.patches:
                continue

            source_patch = self._sim.patches[source_id]
            target_patch = self._sim.patches[target_id]

            source_dipoles = [
                {'hemi': d.hemi, 'vertno': d.vertno, 'position': d.position}
                for d in source_patch.dipoles
                if getattr(d, 'hemi', None) is not None and getattr(d, 'vertno', None) is not None
            ]
            target_dipoles = [
                {'hemi': d.hemi, 'vertno': d.vertno, 'position': d.position}
                for d in target_patch.dipoles
                if getattr(d, 'hemi', None) is not None and getattr(d, 'vertno', None) is not None
            ]

            if not source_dipoles or not target_dipoles:
                continue

            mne_coupling = self._sim._mne_coupling_engine.compute_inter_patch_coupling(
                source_id, target_id,
                {'dipoles': source_dipoles},
                {'dipoles': target_dipoles},
                k=k, decay_length=decay_length,
            )
            factors.append((source_id, target_id, mne_coupling * coupling.strength, coupling))

        self._sim._mne_coupling_factor_cache = factors
        self._sim._mne_coupling_factor_cache_key = cache_key
        return factors

    def _apply_mne_coupling(self, patch_signals):
        """应用MNE耦合（单样本，保留供外部调用）"""
        factors = self._get_mne_coupling_factors()
        if not factors:
            return patch_signals
        return PatchCouplingEngine.apply_mne_factors(patch_signals, factors)

    def _build_patch_data(self, patch_signals, n_samples):
        """组装 MNE 仿真所需的 patch 数据"""
        patch_data = {}
        for patch_id, patch in self._sim.patches.items():
            signals = patch_signals.get(patch_id, np.zeros(n_samples))
            patch_data[patch_id] = {
                'signals': signals,
                'dipoles': patch.dipoles,
                'amplitude_scale': getattr(patch, 'amplitude_scale', 1e-9),
            }
        return patch_data

    def _project_to_electrodes_batch(
        self,
        patch_signals,
        n_samples,
        start_time=None,
        return_all_data: bool = False,
    ):
        """批量投影到电极"""
        if self._sim._mne_simulator is not None and self._sim._mne_simulator.is_ready():
            patch_data = self._build_patch_data(patch_signals, n_samples)

            try:
                all_data = self._sim._mne_simulator.simulate(
                    patch_data,
                    self._sim.simulation_time if start_time is None else start_time,
                    n_samples,
                )
                # 只返回选中的通道，使用通道名称映射
                eeg_data = {}
                missing_channels = []  # 记录MNE投影失败的通道
                logged = getattr(self._sim, '_logged_missing_channels', None)
                if logged is None:
                    logged = set()
                    self._sim._logged_missing_channels = logged

                for ch_name in self._sim.selected_channels:
                    mapped_name = self._sim.eeg_channel_mapping.get(ch_name)
                    if mapped_name is None:
                        mapped_name = ch_name
                        if ch_name not in logged:
                            logged.add(ch_name)
                            logger.warning(
                                f"通道 {ch_name} 未建立 EEG 映射（当前 montage 可能不含该导联），"
                                f"将使用简化投影"
                            )
                        missing_channels.append(ch_name)
                        continue

                    if mapped_name in all_data:
                        eeg_data[ch_name] = all_data[mapped_name]
                    elif ch_name in all_data:
                        eeg_data[ch_name] = all_data[ch_name]
                    else:
                        missing_channels.append(ch_name)
                        if ch_name not in logged:
                            logged.add(ch_name)
                            logger.warning(
                                f"通道 {ch_name} (映射: {mapped_name}) "
                                f"未在MNE前向模型输出中找到，将使用简化投影"
                            )

                # 对未找到的通道使用简化投影
                if missing_channels:
                    simplified_data = self._simplified_projection_for_channels(
                        patch_signals, n_samples, missing_channels
                    )
                    eeg_data.update(simplified_data)

                if not eeg_data:
                    logger.warning(f"没有匹配的通道! 选中: {self._sim.selected_channels}, "
                                 f"可用: {list(all_data.keys())[:10]}...")
                    # 完全回退到简化投影
                    fallback = self._simplified_projection_batch(patch_signals, n_samples)
                    return (fallback, None) if return_all_data else fallback

                return (eeg_data, all_data) if return_all_data else eeg_data
            except Exception as e:
                logger.error(f"MNE投影失败: {e}")

        # 简化投影
        fallback = self._simplified_projection_batch(patch_signals, n_samples)
        return (fallback, None) if return_all_data else fallback

    def _simplified_projection_batch(self, patch_signals, n_samples):
        """简化投影 - 用于EEG通道"""
        n_channels = len(self._sim.selected_channels) if self._sim.selected_channels else 1
        n_sources = len(patch_signals)

        eeg_data = {}

        # 计算每个Patch的振幅缩放因子并应用到信号
        scaled_signals = {}
        for patch_id, signals in patch_signals.items():
            patch = self._sim.patches.get(patch_id)
            if patch:
                amp_scale = getattr(patch, 'amplitude_scale', 1e-9)
                scaled_signals[patch_id] = signals * amp_scale
            else:
                scaled_signals[patch_id] = signals * 1e-9

        signal_array = np.array(list(scaled_signals.values())) if scaled_signals else np.zeros((1, n_samples))

        channel_weights = self._simplified_channel_scales()

        for i, ch in enumerate(self._sim.selected_channels or ['Cz']):
            if n_sources > 0:
                scale = channel_weights.get(ch, channel_weights['default'])
                weights = self._deterministic_projection_weights(ch, i, n_sources, scale)
                projected = np.dot(weights, signal_array) * 1e6
                eeg_data[ch] = projected
            else:
                eeg_data[ch] = np.zeros(n_samples)

        return eeg_data

    def _simplified_projection_for_channels(self, patch_signals, n_samples, channel_names):
        """为指定通道使用简化投影

        当MNE投影无法找到某些通道时使用此方法作为回退

        Args:
            patch_signals: Patch信号字典
            n_samples: 样本数
            channel_names: 需要生成数据的通道名称列表

        Returns:
            dict: {通道名: 信号数组}
        """
        n_sources = len(patch_signals)
        eeg_data = {}

        # 计算每个Patch的振幅缩放因子并应用到信号
        scaled_signals = {}
        for patch_id, signals in patch_signals.items():
            patch = self._sim.patches.get(patch_id)
            if patch:
                amp_scale = getattr(patch, 'amplitude_scale', 1e-9)
                scaled_signals[patch_id] = signals * amp_scale
            else:
                scaled_signals[patch_id] = signals * 1e-9

        signal_array = np.array(list(scaled_signals.values())) if scaled_signals else np.zeros((1, n_samples))

        channel_weights = self._simplified_channel_scales()

        for i, ch in enumerate(channel_names):
            if n_sources > 0:
                scale = channel_weights.get(ch, channel_weights['default'])
                weights = self._deterministic_projection_weights(ch, i, n_sources, scale)
                projected = np.dot(weights, signal_array) * 1e6
                eeg_data[ch] = projected
            else:
                eeg_data[ch] = np.zeros(n_samples)


        return eeg_data

    @staticmethod
    def _simplified_channel_scales():
        """10-20 通道简化投影强度系数"""
        return {
            'Fp1': 0.4, 'Fpz': 0.4, 'Fp2': 0.4,
            'F7': 0.5, 'F3': 0.6, 'Fz': 0.7, 'F4': 0.6, 'F8': 0.5,
            'F1': 0.6, 'F2': 0.6, 'F5': 0.5, 'F6': 0.5,
            'T7': 0.5, 'C3': 0.8, 'Cz': 0.9, 'C4': 0.8, 'T8': 0.5,
            'C1': 0.8, 'C2': 0.8, 'C5': 0.7, 'C6': 0.7,
            'P7': 0.5, 'P3': 0.7, 'Pz': 0.8, 'P4': 0.7, 'P8': 0.5,
            'P1': 0.7, 'P2': 0.7, 'P5': 0.6, 'P6': 0.6,
            'O1': 0.5, 'Oz': 0.6, 'O2': 0.5, 'PO1': 0.5, 'PO2': 0.5,
            'FT7': 0.5, 'FT8': 0.5, 'TP7': 0.5, 'TP8': 0.5,
            'CP1': 0.7, 'CP2': 0.7, 'CP3': 0.7, 'CP4': 0.7,
            'CP5': 0.6, 'CP6': 0.6, 'CPz': 0.8,
            'FC1': 0.6, 'FC2': 0.6, 'FC3': 0.6, 'FC4': 0.6,
            'FC5': 0.5, 'FC6': 0.5, 'FCz': 0.7,
            'default': 0.5,
        }

    @staticmethod
    def _deterministic_projection_weights(ch, ch_index, n_sources, scale):
        """按通道名生成确定性投影权重（不污染全局 RNG）"""
        rng = np.random.RandomState(abs(hash(ch)) % (2**31))
        weights = rng.randn(n_sources) * 0.1 + 0.5
        weights[ch_index % n_sources] *= 1.5
        return weights / (np.sum(np.abs(weights)) + 1e-10) * scale

    def _add_noise_batch(self, eeg_data, t, n_samples):
        """批量添加噪声 - 保持噪声连续性"""
        dt = 1.0 / self._sim.sampling_rate

        for ch_name, signal in eeg_data.items():
            # 初始化该通道的噪声状态
            if ch_name not in self._sim._noise_states:
                self._sim._noise_states[ch_name] = {}

            total_noise = np.zeros(n_samples)
            for noise_config in self._sim.noise_configs:
                noise_type = noise_config.get('type', 'white')

                # 为该噪声类型初始化状态
                if noise_type not in self._sim._noise_states[ch_name]:
                    self._sim._noise_states[ch_name][noise_type] = {}

                noise_state = self._sim._noise_states[ch_name][noise_type]

                # 使用连续噪声生成
                noise = self._sim.signal_engine.generate_continuous_noise(
                    noise_config, n_samples, dt, noise_state
                )
                total_noise += noise

            # 噪声单位是 μV，需要转换为 V（因为 eeg_data 是 V 级别）
            eeg_data[ch_name] = signal + total_noise * 1e-6
        return eeg_data

    def invalidate_heatmap_forward_cache(self):
        """仿真步进后清除热力图全通道投影缓存（频带切换时复用）"""
        self._heatmap_forward_cache_key = None
        self._heatmap_forward_series = None

    def _update_buffers_batch(self, t, patch_signals, eeg_data, n_samples):
        """批量更新缓冲区 - 对新数据实时滤波后再存入"""
        self.invalidate_heatmap_forward_cache()
        take = min(n_samples, self._sim.buffer_size)

        # 更新时间缓冲区
        if take >= self._sim.buffer_size:
            self._sim.time_buffer[:] = t[-self._sim.buffer_size:]
        else:
            self._sim.time_buffer[:-take] = self._sim.time_buffer[take:]
            self._sim.time_buffer[-take:] = t[-take:]

        # 更新EEG缓冲区 - 只对新数据进行滤波
        output_batch = {}
        for ch_name, signal in eeg_data.items():
            if ch_name not in self._sim.eeg_buffer:
                self._sim.eeg_buffer[ch_name] = np.zeros(self._sim.buffer_size)

            # 转换为uV
            signal_uV = signal * 1e6

            # 只对新数据(n_samples个点)进行实时滤波
            if n_samples > 0:
                signal_uV = self._apply_filter(signal_uV, ch_name)

            # 存入缓冲区
            if take >= self._sim.buffer_size:
                self._sim.eeg_buffer[ch_name][:] = signal_uV[-self._sim.buffer_size:]
            else:
                buf = self._sim.eeg_buffer[ch_name]
                buf[:-take] = buf[take:]
                buf[-take:] = signal_uV[-take:]
            if ch_name in self._sim.selected_channels:
                output_batch[ch_name] = signal_uV.copy()

        if self._sim._output_sink and output_batch:
            self._sim._output_sink.write_batch(output_batch)

    def _init_filter_states(self):
        """初始化实时滤波状态和系数

        根据当前滤波参数计算滤波器系数和初始状态，
        为每个通道创建独立的滤波状态。
        """
        from scipy import signal as sp_signal

        # 获取当前滤波参数
        filter_params = self._sim.signal_page.get_filter_params()
        highpass = filter_params.get('highpass', 0)
        lowpass = filter_params.get('lowpass', 0)
        notch = filter_params.get('notch', False)
        notch_freq = filter_params.get('notch_freq', 50.0)

        # 获取滤波阶数配置
        hp_order = self._sim.config.get('filter_highpass_order', 4)
        lp_order = self._sim.config.get('filter_lowpass_order', 4)
        notch_order = self._sim.config.get('filter_notch_order', 2)

        # 计算滤波器系数
        coeffs = {}

        # 高通滤波系数
        if highpass > 0:
            coeffs['hp'] = sp_signal.butter(hp_order, highpass, 'high', 
                                             fs=self._sim.sampling_rate, output='sos')

        # 低通滤波系数
        if lowpass > 0 and lowpass < self._sim.sampling_rate / 2:
            coeffs['lp'] = sp_signal.butter(lp_order, lowpass, 'low', 
                                             fs=self._sim.sampling_rate, output='sos')

        # 陷波滤波系数
        if notch:
            q_value = 15 * notch_order
            b, a = sp_signal.iirnotch(notch_freq, q_value, fs=self._sim.sampling_rate)
            coeffs['notch'] = (b, a)

        self._sim._filter_coeffs = coeffs

        # 为每个通道初始化滤波状态
        self._sim._filter_states = {}
        for ch_name in self._sim.selected_channels:
            states = {}

            # SOS滤波初始状态 (高通)
            if 'hp' in coeffs:
                states['hp'] = sp_signal.sosfilt_zi(coeffs['hp']) * 0

            # SOS滤波初始状态 (低通)
            if 'lp' in coeffs:
                states['lp'] = sp_signal.sosfilt_zi(coeffs['lp']) * 0

            # 陷波滤波初始状态
            if 'notch' in coeffs:
                b, a = coeffs['notch']
                states['notch'] = sp_signal.lfilter_zi(b, a) * 0

            self._sim._filter_states[ch_name] = states

        logger.info(
            f"实时滤波器已初始化: HP={highpass}Hz, LP={lowpass}Hz, "
            f"Notch={notch} ({notch_freq}Hz)"
        )

    def warm_up_display_buffer(self):
        """预填充显示缓冲区并预热滤波器，避免启动后短暂显示直线波形。"""
        n = self._sim.buffer_size
        if n <= 0 or not self._sim.selected_channels:
            return

        sr = self._sim.sampling_rate
        dt = 1.0 / sr
        t = np.linspace(0, n * dt, n, endpoint=False)

        patch_signals = self._generate_patch_signals_batch(t, n)
        patch_signals = self._apply_coupling_batch(patch_signals, t, n)
        eeg_data = self._project_to_electrodes_batch(patch_signals, n)
        if self._sim.noise_configs:
            eeg_data = self._add_noise_batch(eeg_data, t, n)

        self._sim.time_buffer[:n] = t

        for ch_name in self._sim.selected_channels:
            if ch_name not in self._sim.eeg_buffer:
                self._sim.eeg_buffer[ch_name] = np.zeros(n)
            raw = eeg_data.get(ch_name)
            if raw is None:
                self._sim.eeg_buffer[ch_name][:] = 0
                continue
            signal_uV = raw * 1e6
            signal_uV = self._apply_filter(signal_uV, ch_name)
            self._sim.eeg_buffer[ch_name][:] = signal_uV

        self._sim.simulation_time = n * dt
        logger.debug(f"显示缓冲区已预热: {n} 点, t={self._sim.simulation_time:.2f}s")

    def _apply_filter(self, data, ch_name):
        """应用实时有状态滤波

        使用保存的滤波器状态进行单向实时滤波，避免边界效应。

        Args:
            data: 输入信号数据（一维数组）
            ch_name: 通道名称，用于获取对应的滤波状态

        Returns:
            滤波后的数据
        """
        try:
            from scipy import signal as sp_signal

            # 如果没有初始化滤波状态，直接返回原数据
            if not self._sim._filter_coeffs or ch_name not in self._sim._filter_states:
                return data

            coeffs = self._sim._filter_coeffs
            states = self._sim._filter_states[ch_name]

            # 高通滤波 (有状态)
            if 'hp' in coeffs and 'hp' in states:
                data, states['hp'] = sp_signal.sosfilt(coeffs['hp'], data, zi=states['hp'])

            # 低通滤波 (有状态)
            if 'lp' in coeffs and 'lp' in states:
                data, states['lp'] = sp_signal.sosfilt(coeffs['lp'], data, zi=states['lp'])

            # 陷波滤波 (有状态)
            if 'notch' in coeffs and 'notch' in states:
                b, a = coeffs['notch']
                data, states['notch'] = sp_signal.lfilter(b, a, data, zi=states['notch'])

            return data

        except Exception as e:
            logger.warning(f"滤波应用失败 ({ch_name}): {e}")
            return data

    def _clear_display_buffers(self):
        """清空实时显示缓冲区，避免滤波参数变更后新旧结果混杂。"""
        n = self._sim.buffer_size
        if self._sim.time_buffer.size:
            sr = max(float(self._sim.sampling_rate), 1.0)
            last_time = max(
                float(getattr(self._sim, 'simulation_time', 0.0)) - 1.0 / sr,
                0.0,
            )
            first_time = last_time - (n - 1) / sr
            self._sim.time_buffer[:] = first_time + np.arange(n) / sr
        for ch_name in self._sim.selected_channels:
            if ch_name not in self._sim.eeg_buffer:
                self._sim.eeg_buffer[ch_name] = np.zeros(n)
            else:
                self._sim.eeg_buffer[ch_name].fill(0)

    def _on_filter_changed(self):
        """滤波参数改变时重新初始化滤波器并清空显示缓冲"""
        logger.info("滤波参数已改变，重新初始化滤波器")
        if self._sim.is_running:
            self._init_filter_states()
            self._clear_display_buffers()
            self._sim.simulation._update_plots()
        else:
            self._sim._filter_states.clear()
            self._sim._filter_coeffs.clear()
            self._clear_display_buffers()

    def _update_fft_spectrum(self, n_samples):
        """更新FFT频谱显示"""
        try:
            # 获取当前选中的FFT通道
            fft_channel = self._sim.signal_page.fft_channel_combo.currentText()
            if not fft_channel or fft_channel not in self._sim.eeg_buffer:
                return

            # 获取数据
            fft_samples = min(n_samples, 2048)
            data = self._sim.eeg_buffer[fft_channel][-fft_samples:]
            if len(data) < 256:  # 需要足够的数据点
                return

            freqs, fft_power = self._compute_channel_psd(data, self._sim.sampling_rate)

            # 显示0到采样率一半的频段（奈奎斯特频率）
            max_freq = self._sim.sampling_rate / 2
            freq_mask = (freqs >= 0) & (freqs <= max_freq)
            freqs_display = freqs[freq_mask]
            power_display = fft_power[freq_mask]

            # 对数缩放以便更好显示
            power_display = np.log10(power_display + 1e-10)

            # 更新FFT曲线
            self._sim.signal_page.update_fft(freqs_display, power_display)

        except Exception as e:
            logger.debug(f"FFT更新失败: {e}")

    @staticmethod
    def _compute_channel_psd(data: np.ndarray, sampling_rate: float):
        """计算单通道加窗功率谱密度"""
        data = np.asarray(data, dtype=float)
        window = np.hamming(len(data))
        data_windowed = data * window
        n = len(data)
        fft_vals = np.fft.rfft(data_windowed)
        fft_power = np.abs(fft_vals) ** 2 / max(n, 1)
        freqs = np.fft.rfftfreq(n, 1.0 / sampling_rate)
        return freqs, fft_power

    @staticmethod
    def _band_mean_power(freqs: np.ndarray, power: np.ndarray, fmin: float, fmax: float) -> float:
        """频带内平均功率"""
        mask = (freqs >= fmin) & (freqs <= fmax)
        if not np.any(mask):
            return 0.0
        return float(np.mean(power[mask]))

    def _resolve_heatmap_band(self, band_key: str) -> tuple[float, float]:
        """解析热力图频带上下限"""
        fmin, fmax = HEATMAP_BAND_RANGES.get(band_key, HEATMAP_BAND_RANGES['alpha'])
        nyquist = self._sim.sampling_rate / 2.0
        if fmax is None:
            fmax = min(nyquist, 100.0)
        else:
            fmax = min(fmax, nyquist)
        fmin = max(fmin, 0.0)
        return fmin, fmax

    def _filter_window_offline(self, data_uV: np.ndarray) -> np.ndarray:
        """对分析窗口做零相位滤波（不修改实时滤波状态）"""
        from scipy import signal as sp_signal

        if not self._sim._filter_coeffs:
            return data_uV
        data = np.asarray(data_uV, dtype=float)
        coeffs = self._sim._filter_coeffs
        if 'hp' in coeffs:
            data = sp_signal.sosfiltfilt(coeffs['hp'], data)
        if 'lp' in coeffs:
            data = sp_signal.sosfiltfilt(coeffs['lp'], data)
        if 'notch' in coeffs:
            b, a = coeffs['notch']
            data = sp_signal.filtfilt(b, a, data)
        return data

    def _capture_coupling_state(self) -> dict:
        snapshots = {}
        for coupling_id, coupling in self._sim._coupling_models.items():
            history = getattr(coupling, '_history', None)
            snapshots[coupling_id] = {
                'history': None if history is None else history.copy(),
                'write_idx': getattr(coupling, '_write_idx', 0),
            }
        return snapshots

    def _restore_coupling_state(self, snapshots: dict) -> None:
        for coupling_id, snapshot in snapshots.items():
            coupling = self._sim._coupling_models.get(coupling_id)
            if coupling is None:
                continue
            history = snapshot.get('history')
            coupling._history = None if history is None else history.copy()
            coupling._write_idx = snapshot.get('write_idx', 0)

    def _get_forward_series_for_heatmap(self, n_samples: int):
        """为热力图分析生成全通道前向投影时间序列"""
        if not (
            self._sim.simulation_time > 0
            and self._sim._mne_simulator
            and self._sim._mne_simulator.is_ready()
            and self._sim.patches
        ):
            return None

        sr = self._sim.sampling_rate
        dt = 1.0 / sr
        min_samples = max(64, int(sr * 0.5))
        n_samples = int(min(max(n_samples, min_samples), self._sim.buffer_size))
        t_end = self._sim.simulation_time
        t_start = max(0.0, t_end - n_samples * dt)
        cache_key = (round(t_end, 4), n_samples)
        if self._heatmap_forward_cache_key == cache_key and self._heatmap_forward_series is not None:
            return self._heatmap_forward_series
        t = np.linspace(t_start, t_end, n_samples, endpoint=False)
        signal_state_snapshot = copy.deepcopy(self._sim._signal_states)
        coupling_state_snapshot = self._capture_coupling_state()
        try:
            patch_signals = self._generate_patch_signals_batch(t, n_samples)
            patch_signals = self._apply_coupling_batch(patch_signals, t, n_samples)
            patch_data = self._build_patch_data(patch_signals, n_samples)
            forward_series = self._sim._mne_simulator.simulate(
                patch_data, t_start, n_samples
            )
            self._heatmap_forward_cache_key = cache_key
            self._heatmap_forward_series = forward_series
            return forward_series
        except Exception as e:
            logger.debug(f"热力图全通道投影失败: {e}")
            return None
        finally:
            self._sim._signal_states.clear()
            self._sim._signal_states.update(signal_state_snapshot)
            self._restore_coupling_state(coupling_state_snapshot)

    def _bandpass_for_analysis(self, data_uV: np.ndarray, sr: float, fmin: float, fmax: float) -> np.ndarray:
        """零相位带通（分析窗口专用，不改变实时滤波状态）"""
        from scipy import signal as sp_signal

        data = np.asarray(data_uV, dtype=float)
        if data.size < 16:
            return data
        nyquist = sr / 2.0
        if fmax is None:
            fmax = min(nyquist, 100.0)
        fmax = min(fmax, nyquist * 0.999)
        fmin = max(fmin, 0.05)
        if fmax <= fmin:
            return np.zeros_like(data)
        low = fmin / nyquist
        high = fmax / nyquist
        cache_key = (round(float(sr), 6), round(float(fmin), 6), None if fmax is None else round(float(fmax), 6))
        sos = self._analysis_filter_cache.get(cache_key)
        if sos is None:
            if high >= 1.0:
                sos = sp_signal.butter(4, low, btype='highpass', output='sos')
            else:
                sos = sp_signal.butter(4, [low, high], btype='bandpass', output='sos')
            self._analysis_filter_cache[cache_key] = sos
        return sp_signal.sosfiltfilt(sos, data)

    def _total_power_from_uV_series(self, series_uV: np.ndarray) -> float:
        data = np.asarray(series_uV, dtype=float)
        if data.size == 0:
            return 0.0
        return float(np.mean(data ** 2))

    def _band_power_from_uV_series(self, series_uV, sr, fmin, fmax) -> float:
        data = self._filter_window_offline(np.asarray(series_uV, dtype=float))
        return self._band_power_from_filtered_uV_series(data, sr, fmin, fmax)

    def _band_power_from_filtered_uV_series(self, series_uV, sr, fmin, fmax) -> float:
        data = np.asarray(series_uV, dtype=float)
        if fmax is None or (fmin, fmax) == HEATMAP_BAND_RANGES['broadband']:
            return self._total_power_from_uV_series(data)
        band_data = self._bandpass_for_analysis(data, sr, fmin, fmax)
        return self._total_power_from_uV_series(band_data)

    def _band_power_from_voltage_series(self, series_v, sr, fmin, fmax) -> float:
        series_uV = np.asarray(series_v, dtype=float) * 1e6
        return self._band_power_from_uV_series(series_uV, sr, fmin, fmax)

    def _compute_channel_heatmap_power_arrays(
        self,
        channel_names,
        n_samples: int,
        sr: float,
        fmin: float,
        fmax: float,
    ) -> tuple[list[str], np.ndarray, np.ndarray]:
        min_samples = max(64, int(sr * 0.5))
        names = []
        powers = []
        broadband = []
        for ch_name in channel_names:
            buf = self._sim.eeg_buffer.get(ch_name)
            if buf is None or len(buf) == 0:
                continue
            take = min(n_samples, len(buf))
            if take < min_samples:
                continue
            data = self._filter_window_offline(buf[-take:])
            names.append(ch_name)
            powers.append(self._band_power_from_filtered_uV_series(data, sr, fmin, fmax))
            broadband.append(self._total_power_from_uV_series(data))
        return (
            names,
            np.asarray(powers, dtype=float),
            np.asarray(broadband, dtype=float),
        )

    def compute_heatmap_band_powers_for_topomap(self, n_samples: int) -> dict:
        """计算频带功率地形图数据（0–1 归一化）。

        有前向模型时优先使用其原生 EEG 电极位置，避免 10-10 名称
        重映射到稀疏传感器造成的左右假不对称。
        """
        band_key = self._sim.signal_page.get_heatmap_band()
        fmin, fmax = self._resolve_heatmap_band(band_key)
        sr = self._sim.sampling_rate
        min_samples = max(64, int(sr * 0.5))
        n_samples = int(min(max(n_samples, min_samples), self._sim.buffer_size))

        montage = None
        if hasattr(self._sim, 'electrode_channels_page'):
            montage = self._sim.electrode_channels_page.get_current_montage()

        if montage is None:
            names, powers, broadband = self._compute_channel_heatmap_power_arrays(
                list(self._sim.selected_channels or []), n_samples, sr, fmin, fmax
            )
            return {
                'mode': 'montage',
                'powers': self._normalize_heatmap_powers(
                    powers, band_key, broadband=broadband
                )['powers'],
                'names': names,
                'band': band_key,
            }

        selected_names = list(self._sim.selected_channels or [])
        if not selected_names:
            selected_names = [ch for ch in montage.ch_names if ch in self._sim.eeg_buffer]
        names, powers, broadband = self._compute_channel_heatmap_power_arrays(
            selected_names, n_samples, sr, fmin, fmax
        )
        return self._normalize_heatmap_powers(
            powers, band_key, names=names, broadband=broadband
        )

    def compute_heatmap_band_powers_from_forward_series(self, forward_series: dict) -> dict:
        """使用已经生成好的全通道 forward 数据计算热力图，避免 UI 刷新时二次 forward。"""
        if not forward_series or self._sim._mne_simulator is None:
            return {'mode': 'montage', 'powers': np.asarray([]), 'names': [], 'band': 'alpha'}

        import mne

        band_key = self._sim.signal_page.get_heatmap_band()
        fmin, fmax = self._resolve_heatmap_band(band_key)
        sr = self._sim.sampling_rate
        info = self._sim._mne_simulator.info
        picks = mne.pick_types(info, meg=False, eeg=True, exclude=[])
        powers = []
        broadband = []
        for pick in picks:
            name = info['ch_names'][pick]
            if name in forward_series:
                series_uV = np.asarray(forward_series[name], dtype=float) * 1e6
                series_uV = self._filter_window_offline(series_uV)
                powers.append(self._band_power_from_filtered_uV_series(series_uV, sr, fmin, fmax))
                broadband.append(self._total_power_from_uV_series(series_uV))
            else:
                powers.append(0.0)
                broadband.append(0.0)
        return self._normalize_heatmap_powers(
            np.asarray(powers, dtype=float),
            band_key,
            mode='forward',
            info=info,
            broadband=np.asarray(broadband, dtype=float),
        )

    def compute_heatmap_band_powers(self, channel_names, n_samples: int) -> np.ndarray:
        """按所选频带计算各通道功率（0–1 归一化），用于地形图"""
        band_key = self._sim.signal_page.get_heatmap_band()
        fmin, fmax = self._resolve_heatmap_band(band_key)
        min_samples = max(64, int(self._sim.sampling_rate * 0.5))

        powers = []
        broadband = []
        for ch_name in channel_names:
            buf = self._sim.eeg_buffer.get(ch_name)
            if buf is None or len(buf) == 0:
                powers.append(0.0)
                broadband.append(0.0)
                continue
            take = min(n_samples, len(buf))
            if take < min_samples:
                powers.append(0.0)
                broadband.append(0.0)
                continue
            data = self._filter_window_offline(buf[-take:])
            powers.append(
                self._band_power_from_filtered_uV_series(
                    data, self._sim.sampling_rate, fmin, fmax
                )
            )
            broadband.append(self._total_power_from_uV_series(data))

        powers = np.asarray(powers, dtype=float)
        broadband = np.asarray(broadband, dtype=float)
        return self._normalize_heatmap_powers(
            powers, band_key, broadband=broadband
        )['powers']

    def _normalize_heatmap_powers(
        self,
        powers: np.ndarray,
        band_key: str,
        names=None,
        mode: str = 'montage',
        info=None,
        broadband: np.ndarray | None = None,
    ) -> dict:
        """归一化频带功率供地形图显示（按频带独立缩放）"""
        powers = np.asarray(powers, dtype=float)
        max_power = float(np.max(powers)) if powers.size else 0.0
        if (
            band_key != 'broadband'
            and broadband is not None
            and broadband.size
        ):
            max_bb = float(np.max(broadband))
            if max_bb > 0 and max_power / max_bb < HEATMAP_BAND_MIN_BB_RATIO:
                display = np.zeros_like(powers)
            elif max_bb > 0:
                display = np.clip(powers / max_bb, 0.0, 1.0)
            elif max_power > 0:
                display = powers / max_power
            else:
                display = powers
        elif max_power > 0:
            display = powers / max_power
        else:
            display = powers
        result = {
            'mode': mode,
            'powers': display,
            'band': band_key,
        }
        if names is not None:
            result['names'] = names
        if info is not None:
            result['info'] = info
        return result
