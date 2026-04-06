"""测试 signal_engine 模块"""

import unittest
import numpy as np
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eeg_simulator.core.signal_engine import SignalEngine
from eeg_simulator.models import SignalGenerator


class TestSignalEngine(unittest.TestCase):
    """测试 SignalEngine 信号引擎"""

    def setUp(self):
        """测试前准备"""
        self.engine = SignalEngine(sampling_rate=1000)

    def test_init(self):
        """测试初始化"""
        self.assertEqual(self.engine.sampling_rate, 1000)

    def test_generate_sine(self):
        """测试生成正弦波"""
        params = {'frequency': 10, 'amplitude': 1.0}
        
        t = 0.0
        value = self.engine.generate(SignalGenerator.TYPE_SINE, params, t)
        
        # 在 t=0 时，sin(0) = 0
        self.assertAlmostEqual(value, 0.0, places=5)
        
        # 在 t=0.025s (1/4周期，10Hz的波) 时，sin(2*pi*10*0.025) = sin(pi/2) = 1
        t = 0.025
        value = self.engine.generate(SignalGenerator.TYPE_SINE, params, t)
        self.assertAlmostEqual(value, 1.0, places=2)

    def test_generate_square(self):
        """测试生成方波"""
        params = {'frequency': 10, 'amplitude': 1.0}
        
        # 在 t=0 时，应该是 1（方波的起始，duty_cycle默认0.5）
        t = 0.0
        value = self.engine.generate(SignalGenerator.TYPE_SQUARE, params, t)
        self.assertEqual(value, 1.0)

    def test_generate_sawtooth(self):
        """测试生成锯齿波"""
        params = {'frequency': 10, 'amplitude': 1.0}
        
        t = 0.0
        value = self.engine.generate(SignalGenerator.TYPE_SAWTOOTH, params, t)
        self.assertAlmostEqual(value, -1.0, places=5)  # 锯齿波在 t=0 时是 -amp

    def test_generate_noise(self):
        """测试生成噪声"""
        params = {'amplitude': 1.0}
        
        values = []
        for t in np.arange(0, 1, 0.001):
            value = self.engine.generate(SignalGenerator.TYPE_NOISE, params, t)
            values.append(value)
        
        # 噪声应该在合理范围内
        self.assertTrue(all(-5 < v < 5 for v in values))
        
        # 噪声应该有变化（不是常数）
        self.assertTrue(np.std(values) > 0.1)

    def test_generate_impulse(self):
        """测试生成脉冲信号"""
        params = {'frequency': 1, 'amplitude': 1.0, 'width': 0.1}
        
        # 在 t=0 时，应该返回振幅
        t = 0.0
        value = self.engine.generate(SignalGenerator.TYPE_IMPULSE, params, t)
        self.assertEqual(value, 1.0)

    def test_unknown_signal_type(self):
        """测试未知信号类型"""
        params = {'amplitude': 1.0}
        
        t = 0.0
        value = self.engine.generate('unknown_type', params, t)
        
        # 未知类型应该返回 0
        self.assertEqual(value, 0.0)

    def test_sampling_rate_change(self):
        """测试采样率改变"""
        self.engine.sampling_rate = 500
        self.assertEqual(self.engine.sampling_rate, 500)

    def test_signal_amplitude(self):
        """测试信号振幅参数"""
        params = {'frequency': 10, 'amplitude': 5.0}
        
        # 正弦波的最大值应该接近振幅
        max_val = -np.inf
        for t in np.arange(0, 0.1, 0.0001):
            value = self.engine.generate(SignalGenerator.TYPE_SINE, params, t)
            max_val = max(max_val, value)
        
        # 最大值应该接近 5.0
        self.assertAlmostEqual(max_val, 5.0, places=1)

    def test_signal_phase(self):
        """测试信号相位参数"""
        params = {'frequency': 10, 'amplitude': 1.0, 'phase': np.pi/2}
        
        t = 0.0
        value = self.engine.generate(SignalGenerator.TYPE_SINE, params, t)
        
        # 在 t=0 时，sin(pi/2) = 1
        self.assertAlmostEqual(value, 1.0, places=5)

    def test_sawtooth_cycle(self):
        """测试锯齿波周期"""
        params = {'frequency': 10, 'amplitude': 1.0}  # 周期 0.1s
        
        # 在一个周期内，从 -1 上升到 1
        t0 = self.engine.generate(SignalGenerator.TYPE_SAWTOOTH, params, 0.0)
        t_mid = self.engine.generate(SignalGenerator.TYPE_SAWTOOTH, params, 0.05)  # 半周期
        
        self.assertAlmostEqual(t0, -1.0, places=5)
        self.assertAlmostEqual(t_mid, 0.0, places=5)


if __name__ == '__main__':
    unittest.main()
