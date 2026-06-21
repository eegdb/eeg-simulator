"""信号生成、耦合、投影、噪声与实时滤波。"""

import numpy as np

from ...models.coupling import PatchCouplingEngine
from ...utils import tr, get_logger

logger = get_logger(__name__)


class SimulatorSignal:
    """SimulatorSignal 服务。"""

    def __init__(self, simulator):
        self._sim = simulator

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
                current_time = self._sim.simulation_time + i * dt
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

        k = self._sim.source_page.knn_spin.value() if hasattr(self._sim, 'source_page') else 3
        decay_length = self._sim.source_page.decay_spin.value() if hasattr(self._sim, 'source_page') else 0.02
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

    def _project_to_electrodes_batch(self, patch_signals, n_samples):
        """批量投影到电极"""
        if self._sim._mne_simulator is not None and self._sim._mne_simulator.is_ready():
            patch_data = {}
            for patch_id, patch in self._sim.patches.items():
                signals = patch_signals.get(patch_id, np.zeros(n_samples))
                patch_data[patch_id] = {
                    'signals': signals,
                    'dipoles': patch.dipoles,
                    'amplitude_scale': getattr(patch, 'amplitude_scale', 1e-9)
                }

            try:
                all_data = self._sim._mne_simulator.simulate(patch_data, self._sim.simulation_time, n_samples)
                # 只返回选中的通道，使用通道名称映射
                eeg_data = {}
                missing_channels = []  # 记录MNE投影失败的通道

                for ch_name in self._sim.selected_channels:
                    # 检查是否有通道映射 (标准10-20命名 -> MNE前向模型命名)
                    mapped_name = self._sim.eeg_channel_mapping.get(ch_name, ch_name)

                    if mapped_name in all_data:
                        eeg_data[ch_name] = all_data[mapped_name]  # 使用标准命名作为key
                    elif ch_name in all_data:
                        # 通道名直接匹配（无需映射）
                        eeg_data[ch_name] = all_data[ch_name]
                    else:
                        missing_channels.append(ch_name)
                        logged = getattr(self._sim, '_logged_missing_channels', None)
                        if logged is None:
                            logged = set()
                            self._sim._logged_missing_channels = logged
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
                    return self._simplified_projection_batch(patch_signals, n_samples)

                return eeg_data
            except Exception as e:
                logger.error(f"MNE投影失败: {e}")

        # 简化投影
        return self._simplified_projection_batch(patch_signals, n_samples)

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

    def _update_buffers_batch(self, t, patch_signals, eeg_data, n_samples):
        """批量更新缓冲区 - 对新数据实时滤波后再存入"""
        # 更新时间缓冲区
        self._sim.time_buffer = np.roll(self._sim.time_buffer, -n_samples)
        self._sim.time_buffer[-n_samples:] = t

        # 更新EEG缓冲区 - 只对新数据进行滤波
        for ch_name, signal in eeg_data.items():
            if ch_name not in self._sim.eeg_buffer:
                self._sim.eeg_buffer[ch_name] = np.zeros(self._sim.buffer_size)

            # 转换为uV
            signal_uV = signal * 1e6

            # 只对新数据(n_samples个点)进行实时滤波
            if n_samples > 0:
                signal_uV = self._apply_filter(signal_uV, ch_name)

            # 存入缓冲区
            self._sim.eeg_buffer[ch_name] = np.roll(self._sim.eeg_buffer[ch_name], -n_samples)
            self._sim.eeg_buffer[ch_name][-n_samples:] = signal_uV

        if self._sim._output_sink and n_samples > 0:
            batch = {
                ch: self._sim.eeg_buffer[ch][-n_samples:].copy()
                for ch in self._sim.selected_channels
                if ch in self._sim.eeg_buffer
            }
            if batch:
                self._sim._output_sink.write_batch(batch)

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

    def _on_filter_changed(self):
        """滤波参数改变时重新初始化滤波器"""
        logger.info("滤波参数已改变，重新初始化滤波器")
        # 重新初始化滤波器状态和系数
        if self._sim.is_running:
            self._init_filter_states()
        else:
            # 如果仿真未运行，清空滤波状态，下次启动时重新初始化
            self._sim._filter_states.clear()
            self._sim._filter_coeffs.clear()

    def _update_fft_spectrum(self, n_samples):
        """更新FFT频谱显示"""
        try:
            # 获取当前选中的FFT通道
            fft_channel = self._sim.signal_page.fft_channel_combo.currentText()
            if not fft_channel or fft_channel not in self._sim.eeg_buffer:
                return

            # 获取数据
            data = self._sim.eeg_buffer[fft_channel][-n_samples:]
            if len(data) < 256:  # 需要足够的数据点
                return

            # 计算FFT
            from scipy import fft
            # 使用Hamming窗
            window = np.hamming(len(data))
            data_windowed = data * window

            # FFT计算
            fft_vals = fft.fft(data_windowed)
            fft_power = np.abs(fft_vals[:len(fft_vals)//2]) ** 2
            freqs = fft.fftfreq(len(data), 1/self._sim.sampling_rate)[:len(fft_power)]

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
