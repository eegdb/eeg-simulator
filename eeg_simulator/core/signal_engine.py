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
            return amp * np.random.randn(n_samples)
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
        else:
            # 默认白噪声
            return amp * np.random.randn(n_samples)
    
    def _generate_pink_noise(self, n_samples, amp):
        """生成粉红噪声"""
        # 使用简单的近似方法
        white = np.random.randn(n_samples)
        # 简单的积分滤波
        pink = np.cumsum(white)
        pink = pink / np.std(pink) * amp if np.std(pink) > 0 else white * amp
        return pink
    
    def _generate_brown_noise(self, n_samples, amp):
        """生成布朗噪声"""
        white = np.random.randn(n_samples)
        # 双重积分
        brown = np.cumsum(np.cumsum(white))
        brown = brown / np.std(brown) * amp if np.std(brown) > 0 else white * amp
        return brown
        
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
