"""信号生成引擎 - 处理各种信号类型的生成"""

import numpy as np

from ..models import SignalGenerator, Patch
from ..utils import get_logger

logger = get_logger(__name__)


class SignalEngine:
    """信号生成引擎"""
    
    def __init__(self, sampling_rate=1000):
        self.sampling_rate = sampling_rate
        logger.debug(f"信号引擎初始化，采样率: {sampling_rate}Hz")
        
    def generate(self, signal_type, params, t):
        """生成信号
        
        Args:
            signal_type: 信号类型
            params: 参数字典
            t: 时间点
            
        Returns:
            float: 信号值
        """
        if signal_type == SignalGenerator.TYPE_SINE:
            return self._sine(params, t)
        elif signal_type == SignalGenerator.TYPE_NOISE:
            return self._noise(params)
        elif signal_type == SignalGenerator.TYPE_IMPULSE:
            return self._impulse(params, t)
        elif signal_type == SignalGenerator.TYPE_SAWTOOTH:
            return self._sawtooth(params, t)
        elif signal_type == SignalGenerator.TYPE_SQUARE:
            return self._square(params, t)
        else:
            return 0.0
            
    def _sine(self, params, t):
        """正弦波"""
        freq = params.get('frequency', 10)
        amp = params.get('amplitude', 1)
        phase = params.get('phase', 0)
        return amp * np.sin(2 * np.pi * freq * t + phase)
        
    def generate_noise(self, noise_config, n_samples):
        """生成噪声信号
        
        Args:
            noise_config: 噪声配置字典，包含 type 和 amplitude 等参数
            n_samples: 样本数
            
        Returns:
            numpy.ndarray: 噪声信号数组
        """
        noise_type = noise_config.get('type', 'white')
        amp = noise_config.get('amplitude', 1.0)
        
        if noise_type == 'white':
            return self._generate_white_noise(n_samples, amp, noise_config)
        elif noise_type == 'pink':
            # 粉红噪声：1/f 频谱
            return self._generate_pink_noise(n_samples, amp)
        elif noise_type == 'brown':
            # 布朗噪声：1/f^2 频谱
            return self._generate_brown_noise(n_samples, amp)
        elif noise_type == 'line':
            # 工频噪声
            freq = noise_config.get('line_freq', 50)
            return amp * np.sin(2 * np.pi * freq * np.arange(n_samples) / self.sampling_rate)
        elif noise_type == 'ecg':
            # 心电伪迹
            heart_rate = noise_config.get('heart_rate', 60)
            return self._generate_ecg_noise(n_samples, amp, heart_rate)
        elif noise_type == 'eog':
            # 眼电伪迹
            blink_rate = noise_config.get('blink_rate', 0.5)
            return self._generate_eog_noise(n_samples, amp, blink_rate)
        elif noise_type == 'emg':
            # 肌电伪迹
            return self._generate_emg_noise(n_samples, amp, noise_config)
        else:
            # 默认白噪声
            return amp * np.random.randn(n_samples)
    
    def _generate_white_noise(self, n_samples, amp, noise_config):
        """生成白噪声，支持截止频率"""
        noise = amp * np.random.randn(n_samples)
        # 应用低通滤波（如果设置了截止频率）
        cutoff_freq = noise_config.get('cutoff_freq')
        if cutoff_freq and cutoff_freq > 0 and cutoff_freq < self.sampling_rate / 2:
            from scipy import signal as sp_signal
            sos = sp_signal.butter(4, cutoff_freq, 'low', fs=self.sampling_rate, output='sos')
            noise = sp_signal.sosfiltfilt(sos, noise)
        return noise
    
    def _generate_ecg_noise(self, n_samples, amp, heart_rate=60):
        """生成心电伪迹 (ECG)
        
        使用简化的 ECG 模型生成心电信号，包含 P、QRS、T 波。
        参考真实心电图波形特征。
        
        Args:
            n_samples: 样本数
            amp: 幅度 (μV)，指 R 波峰值幅度
            heart_rate: 心率 (BPM)，默认 60
            
        Returns:
            numpy.ndarray: ECG 噪声信号
        """
        dt = 1.0 / self.sampling_rate
        t = np.arange(n_samples) * dt
        
        # 计算心跳周期
        beat_interval = 60.0 / heart_rate  # 秒/beat
        
        # 在每个时间点计算相对于心跳周期的位置 (0-1)
        phase = (t % beat_interval) / beat_interval
        
        # 初始化信号
        ecg = np.zeros(n_samples)
        
        # 定义各波在心跳周期中的相对位置（基于标准ECG）
        # P波: 约 10-15% 周期位置
        # PR间期: 约 12-20% 周期
        # QRS: 约 15-20% 周期 (宽度约 80-100ms)
        # T波: 约 35-50% 周期
        
        # P 波 (心房去极化) - 小圆丘状正向波
        p_center = 0.12  # P波中心位置
        p_width = 0.10   # P波宽度 (占周期的比例)
        p_amp = 0.15     # P波幅度 (相对于R波)
        p_mask = np.abs(phase - p_center) < p_width / 2
        # 使用钟形曲线模拟
        p_shape = np.exp(-((phase[p_mask] - p_center) / (p_width/4)) ** 2)
        ecg[p_mask] += p_amp * amp * p_shape
        
        # PR 段 (等电位线，P波后的小平台)
        # 不需要额外添加，保持为零
        
        # QRS 复合波 (心室去极化) - 最关键的特征
        qrs_center = 0.19  # QRS中心位置
        qrs_width = 0.08   # QRS宽度 (约 80-100ms 对于60bpm)
        
        # Q 波 (小负向凹陷)
        q_center = qrs_center - 0.025
        q_width = 0.025
        q_mask = np.abs(phase - q_center) < q_width / 2
        if np.any(q_mask):
            q_shape = np.exp(-((phase[q_mask] - q_center) / (q_width/4)) ** 2)
            ecg[q_mask] -= 0.20 * amp * q_shape  # Q波幅度约为R波的20%
        
        # R 波 (高大的尖峰) - ECG最显著的特征
        r_center = qrs_center
        r_width = 0.020   # R波很窄 (约 20ms)
        r_mask = np.abs(phase - r_center) < r_width / 2
        if np.any(r_mask):
            # 使用更尖锐的高斯函数
            r_shape = np.exp(-((phase[r_mask] - r_center) / (r_width/3)) ** 2)
            ecg[r_mask] += amp * r_shape  # 主波，使用设置的幅度
        
        # S 波 (负向波)
        s_center = qrs_center + 0.025
        s_width = 0.030
        s_mask = np.abs(phase - s_center) < s_width / 2
        if np.any(s_mask):
            s_shape = np.exp(-((phase[s_mask] - s_center) / (s_width/4)) ** 2)
            ecg[s_mask] -= 0.35 * amp * s_shape  # S波通常比Q波深
        
        # ST 段 (等电位线，S波后)
        
        # T 波 (心室复极化) - 圆丘状正向波，比P波宽且高
        t_center = 0.42   # T波位置 (在QRS后)
        t_width = 0.15    # T波较宽
        t_amp = 0.25      # T波幅度约为R波的25%
        t_mask = np.abs(phase - t_center) < t_width / 2
        if np.any(t_mask):
            # 使用不对称的钟形曲线 (上升慢，下降快)
            t_offset = phase[t_mask] - t_center
            t_shape = np.exp(-0.5 * ((t_offset) / (t_width/5)) ** 2)
            ecg[t_mask] += t_amp * amp * t_shape
        
        # U 波 (可选，有时可见) - 很小，通常忽略
        
        # 添加少量高频噪声 (模拟肌电干扰)
        ecg += 0.03 * amp * np.random.randn(n_samples)
        
        # 添加非常轻微的基线漂移 (模拟呼吸影响)
        # 呼吸频率约 0.15-0.3 Hz
        resp_freq = 0.20
        ecg += 0.05 * amp * np.sin(2 * np.pi * resp_freq * t)
        
        return ecg
    
    def _generate_continuous_ecg_noise(self, n_samples, amp, heart_rate, dt, state):
        """生成连续心电伪迹 - 保持心跳周期连续性"""
        ecg = np.zeros(n_samples)
        
        # 计算心跳周期
        beat_interval = 60.0 / heart_rate  # 秒/beat
        
        # 获取当前心跳周期位置（从上次继续）
        current_t_in_beat = state.get('ecg_t_in_beat', 0.0)
        
        for i in range(n_samples):
            # 计算当前周期位置 (0-1)
            phase = current_t_in_beat / beat_interval
            
            # P 波
            p_center = 0.12
            p_width = 0.10
            p_amp = 0.15
            if abs(phase - p_center) < p_width / 2:
                p_shape = np.exp(-((phase - p_center) / (p_width/4)) ** 2)
                ecg[i] += p_amp * amp * p_shape
            
            # Q 波
            q_center = 0.19 - 0.025
            q_width = 0.025
            if abs(phase - q_center) < q_width / 2:
                q_shape = np.exp(-((phase - q_center) / (q_width/4)) ** 2)
                ecg[i] -= 0.20 * amp * q_shape
            
            # R 波
            r_center = 0.19
            r_width = 0.020
            if abs(phase - r_center) < r_width / 2:
                r_shape = np.exp(-((phase - r_center) / (r_width/3)) ** 2)
                ecg[i] += amp * r_shape
            
            # S 波
            s_center = 0.19 + 0.025
            s_width = 0.030
            if abs(phase - s_center) < s_width / 2:
                s_shape = np.exp(-((phase - s_center) / (s_width/4)) ** 2)
                ecg[i] -= 0.35 * amp * s_shape
            
            # T 波
            t_center = 0.42
            t_width = 0.15
            t_amp = 0.25
            if abs(phase - t_center) < t_width / 2:
                t_shape = np.exp(-0.5 * ((phase - t_center) / (t_width/5)) ** 2)
                ecg[i] += t_amp * amp * t_shape
            
            # 添加少量高频噪声
            ecg[i] += 0.03 * amp * np.random.randn()
            
            # 添加基线漂移
            resp_freq = 0.20
            ecg[i] += 0.05 * amp * np.sin(2 * np.pi * resp_freq * current_t_in_beat)
            
            # 更新时间
            current_t_in_beat += dt
            if current_t_in_beat >= beat_interval:
                current_t_in_beat = 0.0
        
        # 保存状态
        state['ecg_t_in_beat'] = current_t_in_beat
        
        return ecg
    
    def _generate_eog_noise(self, n_samples, amp, blink_rate=0.5):
        """生成眼电伪迹 (EOG)
        
        模拟眨眼产生的瞬态干扰，表现为低频脉冲信号。
        
        Args:
            n_samples: 样本数
            amp: 幅度 (μV)，眨眼伪迹通常较大 (50-200 μV)
            blink_rate: 眨眼频率 (Hz)，默认 0.5 (约每2秒眨眼一次)
            
        Returns:
            numpy.ndarray: EOG 噪声信号
        """
        dt = 1.0 / self.sampling_rate
        t = np.arange(n_samples) * dt
        
        eog = np.zeros(n_samples)
        
        if blink_rate <= 0:
            return eog
        
        # 眨眼间隔
        blink_interval = 1.0 / blink_rate
        
        # 生成每个眨眼事件
        blink_times = np.arange(0, t[-1] + blink_interval, blink_interval)
        
        for blink_t in blink_times:
            # 眨眼波形：快速上升然后缓慢下降的双相脉冲
            blink_idx = int(blink_t * self.sampling_rate)
            if blink_idx >= n_samples:
                break
            
            # 眨眼持续时间约 100-400 ms
            blink_duration = 0.3  # 秒
            blink_samples = int(blink_duration * self.sampling_rate)
            
            if blink_idx + blink_samples > n_samples:
                blink_samples = n_samples - blink_idx
            
            if blink_samples > 0:
                # 创建眨眼波形 (双相脉冲)
                blink_t_local = np.arange(blink_samples) / self.sampling_rate
                
                # 第一阶段：快速上升 (0-50ms)
                rise_time = 0.05
                rise_samples = int(rise_time * self.sampling_rate)
                if rise_samples > blink_samples:
                    rise_samples = blink_samples
                
                # 第二阶段：缓慢下降
                # 使用高斯差分近似双相脉冲
                sigma1 = 0.04
                sigma2 = 0.08
                
                for i in range(blink_samples):
                    ti = blink_t_local[i]
                    # 双相波形：正相 followed by 负相
                    val = (np.exp(-((ti - 0.08) / sigma1) ** 2) - 
                           0.6 * np.exp(-((ti - 0.18) / sigma2) ** 2))
                    
                    if blink_idx + i < n_samples:
                        eog[blink_idx + i] += amp * val
        
        # 添加缓慢的眼动基线漂移 (0.1-0.5 Hz)
        eog += 0.2 * amp * np.sin(2 * np.pi * 0.2 * t + np.random.uniform(0, 2*np.pi))
        
        # 添加低幅度白噪声
        eog += 0.05 * amp * np.random.randn(n_samples)
        
        return eog
    
    def _generate_continuous_eog_noise(self, n_samples, amp, blink_rate, dt, state):
        """生成连续眼电伪迹 - 保持眨眼周期连续性"""
        eog = np.zeros(n_samples)
        
        if blink_rate <= 0:
            return eog
        
        # 眨眼间隔
        blink_interval = 1.0 / blink_rate
        blink_duration = 0.3  # 秒
        
        # 获取当前状态
        # 如果是第一次调用（状态为空），随机初始化 time_since_last_blink
        # 这样第一个块就能有机会立即触发眨眼
        if 'eog_time_since_last_blink' not in state:
            # 随机初始化，确保第一个块就能触发眨眼
            time_since_last_blink = np.random.uniform(0, blink_interval)
            in_blink = False
            blink_progress = 0.0
            baseline_phase = np.random.uniform(0, 2*np.pi)
        else:
            time_since_last_blink = state['eog_time_since_last_blink']
            in_blink = state.get('eog_in_blink', False)
            blink_progress = state.get('eog_blink_progress', 0.0)
            baseline_phase = state.get('eog_baseline_phase', 0.0)
        
        # 基线漂移参数
        baseline_freq = 0.2
        
        for i in range(n_samples):
            sample = 0.0
            
            # 检查是否开始新的眨眼
            if not in_blink and time_since_last_blink >= blink_interval:
                in_blink = True
                blink_progress = 0.0
                time_since_last_blink = 0.0
            
            # 生成眨眼波形
            if in_blink:
                ti = blink_progress
                sigma1 = 0.04
                sigma2 = 0.08
                val = (np.exp(-((ti - 0.08) / sigma1) ** 2) - 
                       0.6 * np.exp(-((ti - 0.18) / sigma2) ** 2))
                sample += amp * val
                
                # 更新眨眼进度
                blink_progress += dt
                if blink_progress >= blink_duration:
                    in_blink = False
                    blink_progress = 0.0
            else:
                time_since_last_blink += dt
            
            # 添加基线漂移
            sample += 0.2 * amp * np.sin(2 * np.pi * baseline_freq * baseline_phase)
            baseline_phase += dt
            
            # 添加低幅度白噪声
            sample += 0.05 * amp * np.random.randn()
            
            eog[i] = sample
        
        # 保存状态
        state['eog_time_since_last_blink'] = time_since_last_blink
        state['eog_in_blink'] = in_blink
        state['eog_blink_progress'] = blink_progress
        state['eog_baseline_phase'] = baseline_phase
        
        return eog
    
    def _generate_emg_noise(self, n_samples, amp, noise_config):
        """生成肌电伪迹 (EMG)
        
        模拟肌肉活动产生的高频、非周期性噪声。
        
        Args:
            n_samples: 样本数
            amp: 幅度 (μV)
            noise_config: 噪声配置字典
            
        Returns:
            numpy.ndarray: EMG 噪声信号
        """
        dt = 1.0 / self.sampling_rate
        t = np.arange(n_samples) * dt
        
        emg = np.zeros(n_samples)
        
        # EMG 特性：高频成分 (20-200 Hz)，爆发性活动
        # 生成多个频带的随机信号
        
        # 低频成分 (10-30 Hz) - 较大的运动单位
        for _ in range(3):
            freq = np.random.uniform(10, 30)
            phase = np.random.uniform(0, 2 * np.pi)
            envelope = np.random.uniform(0.5, 1.0)
            emg += 0.3 * amp * envelope * np.sin(2 * np.pi * freq * t + phase)
        
        # 中频成分 (30-100 Hz) - 主要 EMG 能量
        for _ in range(5):
            freq = np.random.uniform(30, 100)
            phase = np.random.uniform(0, 2 * np.pi)
            envelope = np.random.uniform(0.3, 1.0)
            # 添加随机包络变化（爆发性）
            burst = 1 + 0.5 * np.sin(2 * np.pi * np.random.uniform(2, 8) * t)
            emg += 0.4 * amp * envelope * burst * np.sin(2 * np.pi * freq * t + phase)
        
        # 高频成分 (100-200 Hz) - 快速运动单位
        for _ in range(3):
            freq = np.random.uniform(100, min(200, self.sampling_rate / 2 - 1))
            phase = np.random.uniform(0, 2 * np.pi)
            envelope = np.random.uniform(0.2, 0.6)
            emg += 0.2 * amp * envelope * np.sin(2 * np.pi * freq * t + phase)
        
        # 添加随机噪声基底
        emg += 0.15 * amp * np.random.randn(n_samples)
        
        # 模拟爆发性活动（肌肉收缩期）
        n_bursts = max(1, int(t[-1] / 2))  # 平均每2秒一个爆发
        for _ in range(n_bursts):
            burst_start = np.random.uniform(0, max(0.1, t[-1] - 0.5))
            burst_duration = np.random.uniform(0.1, 0.5)  # 100-500 ms
            burst_start_idx = int(burst_start * self.sampling_rate)
            burst_end_idx = min(n_samples, burst_start_idx + int(burst_duration * self.sampling_rate))
            
            if burst_start_idx < burst_end_idx:
                # 创建包络
                burst_len = burst_end_idx - burst_start_idx
                envelope = np.sin(np.pi * np.arange(burst_len) / burst_len) ** 2
                emg[burst_start_idx:burst_end_idx] += amp * envelope * np.random.randn(burst_len)
        
        # 应用截止频率滤波（如果设置）
        cutoff_freq = noise_config.get('cutoff_freq')
        if cutoff_freq and cutoff_freq > 0 and cutoff_freq < self.sampling_rate / 2:
            from scipy import signal as sp_signal
            sos = sp_signal.butter(4, cutoff_freq, 'low', fs=self.sampling_rate, output='sos')
            emg = sp_signal.sosfiltfilt(sos, emg)
        
        return emg
    
    def _generate_continuous_emg_noise(self, n_samples, amp, noise_config, dt, state):
        """生成连续肌电伪迹 - 保持多频带信号相位连续性"""
        emg = np.zeros(n_samples)
        
        # 获取或初始化相位状态
        if 'emg_phases' not in state:
            # 初始化各频带相位
            state['emg_phases'] = {
                'low': [np.random.uniform(0, 2 * np.pi) for _ in range(3)],
                'mid': [np.random.uniform(0, 2 * np.pi) for _ in range(5)],
                'high': [np.random.uniform(0, 2 * np.pi) for _ in range(3)]
            }
            # 初始化爆发状态
            state['emg_burst_active'] = False
            state['emg_burst_samples_remaining'] = 0
            state['emg_burst_envelope_pos'] = 0
        
        phases = state['emg_phases']
        
        # 低频成分 (10-30 Hz) - 保持相位连续性
        low_freqs = [12.5, 17.3, 23.8]  # 使用固定频率保持连续性
        for i, freq in enumerate(low_freqs):
            envelope = 0.75
            phase_increment = 2 * np.pi * freq * dt
            for j in range(n_samples):
                emg[j] += 0.3 * amp * envelope * np.sin(phases['low'][i])
                phases['low'][i] += phase_increment
        
        # 中频成分 (30-100 Hz)
        mid_freqs = [38.5, 52.3, 67.7, 78.4, 91.2]
        for i, freq in enumerate(mid_freqs):
            envelope = 0.65
            phase_increment = 2 * np.pi * freq * dt
            for j in range(n_samples):
                burst = 1 + 0.5 * np.sin(2 * np.pi * 5.0 * j * dt)  # 固定5Hz包络
                emg[j] += 0.4 * amp * envelope * burst * np.sin(phases['mid'][i])
                phases['mid'][i] += phase_increment
        
        # 高频成分 (100-200 Hz)
        high_freqs = [112.5, 138.7, 165.3]
        for i, freq in enumerate(high_freqs):
            envelope = 0.4
            phase_increment = 2 * np.pi * freq * dt
            for j in range(n_samples):
                emg[j] += 0.2 * amp * envelope * np.sin(phases['high'][i])
                phases['high'][i] += phase_increment
        
        # 添加随机噪声基底
        emg += 0.15 * amp * np.random.randn(n_samples)
        
        # 模拟爆发性活动（保持连续性）
        burst_active = state['emg_burst_active']
        burst_samples_remaining = state['emg_burst_samples_remaining']
        burst_envelope_pos = state['emg_burst_envelope_pos']
        
        # 如果不在爆发中，随机决定是否开始新的爆发
        if not burst_active:
            # 平均每2秒一个爆发，概率基于采样间隔
            if np.random.random() < (dt / 2.0):
                burst_active = True
                burst_duration = np.random.uniform(0.1, 0.5)  # 100-500 ms
                burst_samples_remaining = int(burst_duration / dt)
                burst_envelope_pos = 0
        
        # 生成爆发信号
        if burst_active and burst_samples_remaining > 0:
            burst_len = min(n_samples, burst_samples_remaining)
            for i in range(burst_len):
                # 正弦包络
                envelope = np.sin(np.pi * burst_envelope_pos / (burst_samples_remaining + burst_len)) ** 2
                emg[i] += amp * envelope * np.random.randn()
                burst_envelope_pos += 1
            
            burst_samples_remaining -= burst_len
            if burst_samples_remaining <= 0:
                burst_active = False
        
        # 保存状态
        state['emg_burst_active'] = burst_active
        state['emg_burst_samples_remaining'] = burst_samples_remaining
        state['emg_burst_envelope_pos'] = burst_envelope_pos
        
        # 应用截止频率滤波（如果设置）
        cutoff_freq = noise_config.get('cutoff_freq')
        if cutoff_freq and cutoff_freq > 0 and cutoff_freq < self.sampling_rate / 2:
            from scipy import signal as sp_signal
            sos = sp_signal.butter(4, cutoff_freq, 'low', fs=self.sampling_rate, output='sos')
            emg = sp_signal.sosfilt(sos, emg)  # 使用sosfilt保持连续性
        
        return emg
    
    def _generate_pink_noise(self, n_samples, amp):
        """生成粉红噪声"""
        # 使用简单的近似方法
        white = np.random.randn(n_samples)
        # 简单的积分滤波
        pink = np.cumsum(white)
        pink = pink / np.std(pink) * amp if np.std(pink) > 0 else white * amp
        return pink
    
    def _generate_continuous_pink_noise(self, n_samples, amp, state):
        """生成连续粉红噪声 - 使用简化AR(1)模型保持连续性"""
        # AR(1)模型：x[n] = a * x[n-1] + white[n]
        # 选择a接近1来产生长程相关性（类似1/f）
        a = 0.995  # 非常接近1，产生强相关性
        
        # 获取上次最后一个值
        if 'pink_last_value' not in state:
            state['pink_last_value'] = 0.0
        
        last_value = state['pink_last_value']
        
        pink = np.zeros(n_samples)
        
        for i in range(n_samples):
            white = np.random.randn() * amp * 0.1  # 小幅度白噪声
            sample = a * last_value + white
            pink[i] = sample
            last_value = sample
        
        # 保存状态
        state['pink_last_value'] = last_value
        
        return pink
    
    def _generate_brown_noise(self, n_samples, amp):
        """生成布朗噪声"""
        white = np.random.randn(n_samples)
        # 双重积分
        brown = np.cumsum(np.cumsum(white))
        brown = brown / np.std(brown) * amp if np.std(brown) > 0 else white * amp
        return brown
    
    def _generate_continuous_brown_noise(self, n_samples, amp, state):
        """生成连续布朗噪声 - 使用双重累积和保持连续性"""
        # 生成白噪声
        white = np.random.randn(n_samples)
        
        # 获取或初始化积分状态
        if 'brown_first_sum' not in state:
            state['brown_first_sum'] = 0.0
            state['brown_second_sum'] = 0.0
        
        last_first = state['brown_first_sum']
        last_second = state['brown_second_sum']
        
        # 第一次积分
        first_int = np.cumsum(white) + last_first
        # 第二次积分
        brown = np.cumsum(first_int) + last_second
        
        # 保存最后一个值供下次使用
        state['brown_first_sum'] = float(first_int[-1]) if len(first_int) > 0 else last_first
        state['brown_second_sum'] = float(brown[-1]) if len(brown) > 0 else last_second
        
        # 使用全局缩放因子
        total_samples_estimate = 5000
        scale = total_samples_estimate  # 双重积分方差增长更快
        if scale > 0:
            brown_scaled = brown / scale * amp
        else:
            brown_scaled = brown * 0
        
        return brown_scaled
    
    def _generate_continuous_line_noise(self, n_samples, amp, freq, dt, state):
        """生成连续工频噪声 - 保持相位连续性"""
        # 获取当前相位
        phase = state.get('line_phase', 0.0)
        phase_increment = 2 * np.pi * freq * dt
        
        noise = np.zeros(n_samples)
        for i in range(n_samples):
            noise[i] = amp * np.sin(phase)
            phase += phase_increment
        
        # 保存相位（保持在0-2π范围内）
        state['line_phase'] = phase % (2 * np.pi)
        return noise
    
    def generate_continuous_noise(self, noise_config, n_samples, dt, state):
        """生成连续噪声信号 - 保持时间连续性
        
        Args:
            noise_config: 噪声配置字典
            n_samples: 生成样本数
            dt: 采样时间间隔（秒）
            state: 状态字典，用于存储和恢复噪声状态（会被更新）
            
        Returns:
            np.ndarray: 噪声信号数组
        """
        noise_type = noise_config.get('type', 'white')
        amp = noise_config.get('amplitude', 1.0)
        
        if noise_type == 'white':
            # 白噪声本来就是完全随机的，不需要连续性
            cutoff_freq = noise_config.get('cutoff_freq')
            if cutoff_freq and cutoff_freq > 0 and cutoff_freq < self.sampling_rate / 2:
                # 如果需要滤波，使用有状态滤波器
                return self._generate_continuous_filtered_white_noise(
                    n_samples, amp, cutoff_freq, dt, state
                )
            return amp * np.random.randn(n_samples)
            
        elif noise_type == 'pink':
            # 粉红噪声是随机过程，不需要跨批次时域连续性
            # 使用独立生成保持统计特性
            return self._generate_pink_noise(n_samples, amp)
            
        elif noise_type == 'brown':
            # 布朗噪声是随机过程，不需要跨批次时域连续性
            return self._generate_brown_noise(n_samples, amp)
            
        elif noise_type == 'line':
            freq = noise_config.get('line_freq', 50)
            return self._generate_continuous_line_noise(n_samples, amp, freq, dt, state)
            
        elif noise_type == 'ecg':
            heart_rate = noise_config.get('heart_rate', 60)
            return self._generate_continuous_ecg_noise(n_samples, amp, heart_rate, dt, state)
            
        elif noise_type == 'eog':
            blink_rate = noise_config.get('blink_rate', 0.5)
            return self._generate_continuous_eog_noise(n_samples, amp, blink_rate, dt, state)
            
        elif noise_type == 'emg':
            return self._generate_continuous_emg_noise(n_samples, amp, noise_config, dt, state)
            
        else:
            return amp * np.random.randn(n_samples)
    
    def _generate_continuous_filtered_white_noise(self, n_samples, amp, cutoff_freq, dt, state):
        """生成连续滤波白噪声 - 使用有状态滤波器保持连续性"""
        from scipy import signal as sp_signal
        
        # 生成白噪声
        noise = amp * np.random.randn(n_samples)
        
        # 获取或初始化滤波器状态
        if 'white_noise_filter_zi' not in state:
            sos = sp_signal.butter(4, cutoff_freq, 'low', fs=self.sampling_rate, output='sos')
            zi = sp_signal.sosfilt_zi(sos)
            state['white_noise_sos'] = sos
            state['white_noise_filter_zi'] = zi * 0
        
        # 有状态滤波
        sos = state['white_noise_sos']
        zi = state['white_noise_filter_zi']
        filtered_noise, zf = sp_signal.sosfilt(sos, noise, zi=zi)
        state['white_noise_filter_zi'] = zf
        
        return filtered_noise
        
    def _noise(self, params):
        """高斯噪声（单个样本）"""
        amp = params.get('amplitude', 1)
        return amp * np.random.randn()
        
    def _impulse(self, params, t):
        """脉冲信号"""
        freq = params.get('frequency', 1)
        amp = params.get('amplitude', 1)
        width = params.get('width', 0.1)
        period = 1.0 / freq
        if (t % period) < (period * width):
            return amp
        return 0.0
        
    def _sawtooth(self, params, t):
        """锯齿波"""
        freq = params.get('frequency', 10)
        amp = params.get('amplitude', 1)
        period = 1.0 / freq
        phase = (t % period) / period
        return amp * (2 * phase - 1)
        
    def _square(self, params, t):
        """方波"""
        freq = params.get('frequency', 10)
        amp = params.get('amplitude', 1)
        duty = params.get('duty_cycle', 0.5)
        period = 1.0 / freq
        phase = (t % period) / period
        return amp if phase < duty else -amp
    
    def generate_dipole_waveform(self, dipole, t, patch=None):
        """生成偶极子的波形信号
        
        Args:
            dipole: Dipole 对象
            t: 时间点
            patch: 所属的 Patch 对象（如果有），如果为 None 则使用默认正弦波
            
        Returns:
            float: 信号值
        """
        # 如果有 Patch，使用 Patch 的波形设置
        if patch is not None:
            waveform_type = patch.waveform_type
            params = patch.waveform_params
        else:
            # 默认正弦波参数
            waveform_type = Patch.WAVEFORM_SIN
            params = {
                'amplitude': 10.0,
                'frequency': 10.0,
                'phase': 0.0,
                'offset': 0.0,
                'onset': 0.0,
                'duration': 0.0
            }
        
        # 获取波形参数中的频率和振幅
        freq = params.get('frequency', 10.0)
        amp = params.get('amplitude', 10.0)
        
        if waveform_type == Patch.WAVEFORM_SIN:
            # 获取波形参数
            phase = params.get('phase', 0.0)
            offset = params.get('offset', 0.0)
            onset = params.get('onset', 0.0)
            duration = params.get('duration', 0.0)
            
            # 检查时间窗口
            if t < onset:
                return 0.0
            if duration > 0 and t > onset + duration:
                return 0.0
            
            # 计算有效时间（相对于 onset）
            t_eff = t - onset
            
            # 生成正弦波
            signal = amp * np.sin(2 * np.pi * freq * t_eff + np.radians(phase))
            return signal + offset
            
        elif waveform_type == Patch.WAVEFORM_COS:
            # 获取波形参数
            phase = params.get('phase', 0.0)
            offset = params.get('offset', 0.0)
            onset = params.get('onset', 0.0)
            duration = params.get('duration', 0.0)
            
            # 检查时间窗口
            if t < onset:
                return 0.0
            if duration > 0 and t > onset + duration:
                return 0.0
            
            # 计算有效时间（相对于 onset）
            t_eff = t - onset
            
            # 生成余弦波
            signal = amp * np.cos(2 * np.pi * freq * t_eff + np.radians(phase))
            return signal + offset
            
        elif waveform_type == Patch.WAVEFORM_ERP:
            # ERP: 高斯脉冲
            latency = params.get('latency', 0.1)
            width = params.get('width', 0.05)
            polarity = params.get('polarity', 'positive')
            
            # 周期性 ERP
            period = 1.0 / freq if freq > 0 else 1.0
            t_in_period = t % period
            
            # 高斯函数
            sigma = width / 2.355  # FWHM to sigma
            signal = amp * np.exp(-0.5 * ((t_in_period - latency) / sigma) ** 2)
            
            # 应用极性
            if polarity == 'negative':
                signal = -signal
            
            return signal
            
        elif waveform_type == Patch.WAVEFORM_GAUSSIAN:
            # 高斯调制正弦波
            sigma = params.get('sigma', 0.1)
            center = params.get('center', 0.5)
            period = 1.0 / freq if freq > 0 else 1.0
            t_in_period = t % period
            envelope = np.exp(-0.5 * ((t_in_period - center * period) / (sigma * period)) ** 2)
            return amp * envelope * np.sin(2 * np.pi * freq * t)
            
        elif waveform_type == Patch.WAVEFORM_GAMMA:
            # Gamma 函数调制
            alpha = params.get('alpha', 2.0)
            beta = params.get('beta', 0.1)
            period = 1.0 / freq if freq > 0 else 1.0
            t_in_period = t % period
            # Gamma-like envelope
            if t_in_period > 0:
                envelope = (t_in_period ** alpha) * np.exp(-t_in_period / beta)
                return amp * envelope * np.sin(2 * np.pi * freq * t)
            return 0.0
            
        elif waveform_type == Patch.WAVEFORM_OSCILLATION:
            # Oscillation: Gaussian 包络调制的振荡
            osc_freq = params.get('freq', 10.0)
            phase = params.get('phase', 0.0)
            osc_amp = params.get('amp', 20.0)
            center = params.get('center', 0.5)
            width = params.get('width', 0.1)
            
            # Gaussian 包络
            envelope = np.exp(-(t - center)**2 / (2 * width**2))
            return osc_amp * envelope * np.sin(2 * np.pi * osc_freq * t + np.radians(phase))
            
        elif waveform_type == Patch.WAVEFORM_CUSTOM:
            # 自定义波形 - 从预定义数组中采样
            data = params.get('data', [])
            if len(data) > 0:
                # 周期性循环播放
                period = 1.0 / freq if freq > 0 else 1.0
                t_in_period = t % period
                # 计算索引
                idx = int((t_in_period / period) * len(data)) % len(data)
                return amp * data[idx]
            return 0.0
            
        else:
            # 默认正弦波
            return amp * np.sin(2 * np.pi * freq * t)
    
    def generate_patch_waveform(self, patch, t):
        """生成 Patch 的波形信号（单点，向后兼容）
        
        Args:
            patch: Patch 对象
            t: 时间点
            
        Returns:
            float: 信号值
        """
        # 调用批量生成方法，取第一个值
        result = self.generate_patch_waveform_batch(patch, t, 1)
        return result[0] if len(result) > 0 else 0.0
    
    def generate_patch_waveform_batch(self, patch, start_time, n_samples):
        """批量生成 Patch 的波形信号
        
        按照输出采样率批量生成信号，提高性能。
        
        Args:
            patch: Patch 对象
            start_time: 起始时间（秒）
            n_samples: 生成样本数
            
        Returns:
            np.ndarray: 信号数组 (n_samples,)
        """
        # 直接使用 Patch 的波形设置
        waveform_type = patch.waveform_type
        params = patch.waveform_params
        
        # 获取波形参数中的频率和振幅
        freq = params.get('frequency', 10.0)
        amp = params.get('amplitude', 10.0)
        
        # 调试日志
        logger.debug(f"Patch {patch.id}: waveform={waveform_type}, amp={amp}, freq={freq}, params={params}")
        
        # 生成时间数组
        dt = 1.0 / self.sampling_rate
        t_array = start_time + np.arange(n_samples) * dt
        
        if waveform_type == Patch.WAVEFORM_SIN:
            phase = params.get('phase', 0.0)
            offset = params.get('offset', 0.0)
            onset = params.get('onset', 0.0)
            duration = params.get('duration', 0.0)
            
            # 计算有效时间窗口
            if duration > 0:
                end_time = onset + duration
                mask = (t_array >= onset) & (t_array <= end_time)
            else:
                mask = t_array >= onset
            
            signals = np.zeros(n_samples)
            t_eff = t_array[mask] - onset
            signals[mask] = amp * np.sin(2 * np.pi * freq * t_eff + np.radians(phase))
            return signals + offset
            
        elif waveform_type == Patch.WAVEFORM_COS:
            phase = params.get('phase', 0.0)
            offset = params.get('offset', 0.0)
            onset = params.get('onset', 0.0)
            duration = params.get('duration', 0.0)
            
            if duration > 0:
                end_time = onset + duration
                mask = (t_array >= onset) & (t_array <= end_time)
            else:
                mask = t_array >= onset
            
            signals = np.zeros(n_samples)
            t_eff = t_array[mask] - onset
            signals[mask] = amp * np.cos(2 * np.pi * freq * t_eff + np.radians(phase))
            return signals + offset
            
        elif waveform_type == Patch.WAVEFORM_ERP:
            latency = params.get('latency', 0.1)
            width = params.get('width', 0.05)
            polarity = params.get('polarity', 'positive')
            
            period = 1.0 / freq if freq > 0 else 1.0
            t_in_period = t_array % period
            
            sigma = width / 2.355
            signals = amp * np.exp(-0.5 * ((t_in_period - latency) / sigma) ** 2)
            
            if polarity == 'negative':
                signals = -signals
            
            return signals
            
        elif waveform_type == Patch.WAVEFORM_GAUSSIAN:
            sigma = params.get('sigma', 0.1)
            center = params.get('center', 0.5)
            period = 1.0 / freq if freq > 0 else 1.0
            t_in_period = t_array % period
            envelope = np.exp(-0.5 * ((t_in_period - center * period) / (sigma * period)) ** 2)
            return amp * envelope * np.sin(2 * np.pi * freq * t_array)
            
        elif waveform_type == Patch.WAVEFORM_GAMMA:
            alpha = params.get('alpha', 2.0)
            beta = params.get('beta', 0.1)
            period = 1.0 / freq if freq > 0 else 1.0
            t_in_period = t_array % period
            
            signals = np.zeros(n_samples)
            mask = t_in_period > 0
            envelope = (t_in_period[mask] ** alpha) * np.exp(-t_in_period[mask] / beta)
            signals[mask] = amp * envelope * np.sin(2 * np.pi * freq * t_array[mask])
            return signals
            
        elif waveform_type == Patch.WAVEFORM_OSCILLATION:
            osc_freq = params.get('freq', 10.0)
            phase = params.get('phase', 0.0)
            osc_amp = params.get('amp', 20.0)
            center = params.get('center', 0.5)
            width = params.get('width', 0.1)
            
            envelope = np.exp(-(t_array - center)**2 / (2 * width**2))
            return osc_amp * envelope * np.sin(2 * np.pi * osc_freq * t_array + np.radians(phase))
            
        elif waveform_type == Patch.WAVEFORM_CUSTOM:
            data = params.get('data', [])
            if len(data) > 0:
                period = 1.0 / freq if freq > 0 else 1.0
                t_in_period = t_array % period
                indices = ((t_in_period / period) * len(data)).astype(int) % len(data)
                return amp * np.array(data)[indices]
            return np.zeros(n_samples)
            
        else:
            return amp * np.sin(2 * np.pi * freq * t_array)
    
    def generate_continuous_waveform(self, patch, n_samples, dt, state):
        """生成连续波形信号 - 保持相位连续性
        
        通过维护相位状态，确保每次生成的信号与前一次连续衔接。
        适用于正弦、余弦等周期性信号。
        
        Args:
            patch: Patch 对象
            n_samples: 生成样本数
            dt: 采样时间间隔（秒）
            state: 状态字典，包含 'phase' 当前相位（会被更新）
            
        Returns:
            np.ndarray: 信号数组 (n_samples,)
        """
        waveform_type = patch.waveform_type
        params = patch.waveform_params
        
        freq = params.get('frequency', 10.0)
        amp = params.get('amplitude', 10.0)
        
        signals = np.zeros(n_samples)
        
        if waveform_type == Patch.WAVEFORM_SIN:
            phase_offset = np.radians(params.get('phase', 0.0))
            offset = params.get('offset', 0.0)
            
            # 使用状态中的相位，加上初始相位偏移
            current_phase = state.get('phase', 0.0) + phase_offset
            phase_increment = 2 * np.pi * freq * dt
            
            # 生成连续的正弦波
            for i in range(n_samples):
                signals[i] = amp * np.sin(current_phase)
                current_phase += phase_increment
            
            # 更新状态，保持在 0-2π 范围内以避免数值溢出
            state['phase'] = (current_phase - phase_offset) % (2 * np.pi)
            return signals + offset
            
        elif waveform_type == Patch.WAVEFORM_COS:
            phase_offset = np.radians(params.get('phase', 0.0))
            offset = params.get('offset', 0.0)
            
            current_phase = state.get('phase', 0.0) + phase_offset
            phase_increment = 2 * np.pi * freq * dt
            
            for i in range(n_samples):
                signals[i] = amp * np.cos(current_phase)
                current_phase += phase_increment
            
            state['phase'] = (current_phase - phase_offset) % (2 * np.pi)
            return signals + offset
            
        elif waveform_type == Patch.WAVEFORM_ERP:
            # ERP信号本身基于全局时间，不需要维护相位状态
            # 但为了保持一致性，我们仍然记录周期位置
            latency = params.get('latency', 0.1)
            width = params.get('width', 0.05)
            polarity = params.get('polarity', 'positive')
            
            period = 1.0 / freq if freq > 0 else 1.0
            
            # 从状态中获取当前周期位置
            current_t_in_period = state.get('t_in_period', 0.0)
            
            for i in range(n_samples):
                sigma = width / 2.355
                val = amp * np.exp(-0.5 * ((current_t_in_period - latency) / sigma) ** 2)
                signals[i] = -val if polarity == 'negative' else val
                
                # 更新周期位置
                current_t_in_period += dt
                if current_t_in_period >= period:
                    current_t_in_period = 0.0
            
            state['t_in_period'] = current_t_in_period
            return signals
            
        elif waveform_type == Patch.WAVEFORM_GAUSSIAN:
            # 高斯调制信号 - 维护载波相位
            sigma = params.get('sigma', 0.1)
            center = params.get('center', 0.5)
            period = 1.0 / freq if freq > 0 else 1.0
            
            current_phase = state.get('phase', 0.0)
            current_t_in_period = state.get('t_in_period', 0.0)
            phase_increment = 2 * np.pi * freq * dt
            
            for i in range(n_samples):
                envelope = np.exp(-0.5 * ((current_t_in_period - center * period) / (sigma * period)) ** 2)
                signals[i] = amp * envelope * np.sin(current_phase)
                
                current_phase += phase_increment
                current_t_in_period += dt
                if current_t_in_period >= period:
                    current_t_in_period = 0.0
            
            state['phase'] = current_phase % (2 * np.pi)
            state['t_in_period'] = current_t_in_period
            return signals
            
        elif waveform_type == Patch.WAVEFORM_GAMMA:
            alpha = params.get('alpha', 2.0)
            beta = params.get('beta', 0.1)
            period = 1.0 / freq if freq > 0 else 1.0
            
            current_phase = state.get('phase', 0.0)
            current_t_in_period = state.get('t_in_period', 0.0)
            phase_increment = 2 * np.pi * freq * dt
            
            for i in range(n_samples):
                if current_t_in_period > 0:
                    envelope = (current_t_in_period ** alpha) * np.exp(-current_t_in_period / beta)
                    signals[i] = amp * envelope * np.sin(current_phase)
                else:
                    signals[i] = 0.0
                
                current_phase += phase_increment
                current_t_in_period += dt
                if current_t_in_period >= period:
                    current_t_in_period = 0.0
            
            state['phase'] = current_phase % (2 * np.pi)
            state['t_in_period'] = current_t_in_period
            return signals
            
        elif waveform_type == Patch.WAVEFORM_OSCILLATION:
            osc_freq = params.get('freq', 10.0)
            osc_amp = params.get('amp', 20.0)
            phase_offset = np.radians(params.get('phase', 0.0))
            center = params.get('center', 0.5)
            width = params.get('width', 0.1)
            
            # 基于全局仿真时间的振荡信号
            # 使用状态记录当前仿真时间
            current_sim_time = state.get('sim_time', 0.0)
            osc_phase = state.get('osc_phase', 0.0)
            osc_phase_increment = 2 * np.pi * osc_freq * dt
            
            for i in range(n_samples):
                envelope = np.exp(-(current_sim_time - center)**2 / (2 * width**2))
                signals[i] = osc_amp * envelope * np.sin(osc_phase + phase_offset)
                
                current_sim_time += dt
                osc_phase += osc_phase_increment
            
            state['sim_time'] = current_sim_time
            state['osc_phase'] = osc_phase % (2 * np.pi)
            return signals
            
        elif waveform_type == Patch.WAVEFORM_CUSTOM:
            data = params.get('data', [])
            if len(data) > 0:
                period = 1.0 / freq if freq > 0 else 1.0
                
                current_t_in_period = state.get('t_in_period', 0.0)
                data_len = len(data)
                
                for i in range(n_samples):
                    idx = int((current_t_in_period / period) * data_len) % data_len
                    signals[i] = amp * data[idx]
                    
                    current_t_in_period += dt
                    if current_t_in_period >= period:
                        current_t_in_period = 0.0
                
                state['t_in_period'] = current_t_in_period
                return signals
            return np.zeros(n_samples)
            
        else:
            # 默认正弦波 - 保持连续性
            current_phase = state.get('phase', 0.0)
            phase_increment = 2 * np.pi * freq * dt
            
            for i in range(n_samples):
                signals[i] = amp * np.sin(current_phase)
                current_phase += phase_increment
            
            state['phase'] = current_phase % (2 * np.pi)
            return signals
