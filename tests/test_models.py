"""测试 models 模块"""

import unittest
import numpy as np

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eeg_simulator.models import Dipole, SignalGenerator, CouplingModel


class TestDipole(unittest.TestCase):
    """测试 Dipole 类"""

    def test_init(self):
        """测试初始化"""
        dipole = Dipole(
            id="dipole_1",
            position=[0.01, 0.02, 0.03],
            orientation=[1, 0, 0],
            hemi='rh',
            vertno=1234,
            src_idx=0
        )

        self.assertEqual(dipole.id, "dipole_1")
        self.assertEqual(dipole.hemi, "rh")
        self.assertEqual(dipole.vertno, 1234)
        self.assertEqual(dipole.src_idx, 0)
        np.testing.assert_array_almost_equal(dipole.position, np.array([0.01, 0.02, 0.03]))
        np.testing.assert_array_almost_equal(dipole.orientation, np.array([1, 0, 0]))

    def test_orientation_normalization(self):
        """测试方向向量归一化"""
        dipole = Dipole(
            id="dipole_1",
            position=[0, 0, 0],
            orientation=[2, 0, 0],
            hemi='lh'
        )

        norm = np.linalg.norm(dipole.orientation)
        self.assertAlmostEqual(norm, 1.0, places=5)

    def test_optional_attributes(self):
        """测试可选属性"""
        dipole = Dipole(
            id="dipole_1",
            position=[0.0, 0.0, 0.0],
            orientation=[0, 0, 1]
        )

        self.assertIsNone(dipole.hemi)
        self.assertIsNone(dipole.vertno)
        self.assertIsNone(dipole.src_idx)

    def test_repr(self):
        """测试字符串表示"""
        dipole = Dipole(
            id="dipole_1",
            position=[0.01, 0.02, 0.03],
            orientation=[0, 0, 1]
        )

        repr_str = repr(dipole)
        self.assertIn("Dipole", repr_str)
        self.assertIn("dipole_1", repr_str)


class TestSignalGenerator(unittest.TestCase):
    """测试 SignalGenerator 类"""

    def test_init_sine(self):
        """测试正弦信号生成器初始化"""
        signal = SignalGenerator(
            id="signal_1",
            type=SignalGenerator.TYPE_SINE,
            parameters={'frequency': 8, 'amplitude': 7}
        )

        self.assertEqual(signal.id, "signal_1")
        self.assertEqual(signal.type, "sine")
        self.assertEqual(signal.parameters['frequency'], 8)
        self.assertEqual(signal.parameters['amplitude'], 7)

    def test_init_noise(self):
        """测试噪声信号生成器初始化"""
        signal = SignalGenerator(
            id="signal_2",
            type=SignalGenerator.TYPE_NOISE,
            parameters={'amplitude': 1.0}
        )

        self.assertEqual(signal.type, "noise")
        self.assertEqual(signal.parameters['amplitude'], 1.0)

    def test_valid_types(self):
        """测试有效信号类型"""
        self.assertIn('sine', SignalGenerator.VALID_TYPES)
        self.assertIn('noise', SignalGenerator.VALID_TYPES)
        self.assertIn('impulse', SignalGenerator.VALID_TYPES)
        self.assertIn('sawtooth', SignalGenerator.VALID_TYPES)
        self.assertIn('square', SignalGenerator.VALID_TYPES)

    def test_update_parameters(self):
        """测试更新参数"""
        signal = SignalGenerator(
            id="signal_1",
            type=SignalGenerator.TYPE_SINE,
            parameters={'frequency': 8, 'amplitude': 7}
        )

        signal.parameters = {'frequency': 10, 'amplitude': 5}

        self.assertEqual(signal.parameters['frequency'], 10)
        self.assertEqual(signal.parameters['amplitude'], 5)

    def test_repr(self):
        """测试字符串表示"""
        signal = SignalGenerator(
            id="signal_1",
            type="sine",
            parameters={'frequency': 10}
        )

        repr_str = repr(signal)
        self.assertIn("SignalGenerator", repr_str)
        self.assertIn("signal_1", repr_str)


class TestCouplingModel(unittest.TestCase):
    """测试 CouplingModel 类"""

    def test_init_linear(self):
        """测试线性耦合模型初始化"""
        coupling = CouplingModel(
            id="coupling_1",
            source_patch_id="patch_1",
            target_patch_id="patch_2",
            type=CouplingModel.TYPE_LINEAR,
            strength=0.5,
            delay=0.01
        )

        self.assertEqual(coupling.id, "coupling_1")
        self.assertEqual(coupling.source_patch_id, "patch_1")
        self.assertEqual(coupling.target_patch_id, "patch_2")
        self.assertEqual(coupling.type, "linear")
        self.assertEqual(coupling.strength, 0.5)
        self.assertEqual(coupling.delay, 0.01)

    def test_init_nonlinear(self):
        """测试非线性耦合模型初始化"""
        coupling = CouplingModel(
            id="coupling_2",
            source_patch_id="patch_1",
            target_patch_id="patch_2",
            type=CouplingModel.TYPE_NONLINEAR,
            strength=0.3,
            delay=0.005
        )

        self.assertEqual(coupling.type, "nonlinear")

    def test_valid_types(self):
        """测试有效耦合类型"""
        self.assertIn('linear', CouplingModel.VALID_TYPES)
        self.assertIn('nonlinear', CouplingModel.VALID_TYPES)
        self.assertIn('delayed', CouplingModel.VALID_TYPES)

    def test_modify_parameters(self):
        """测试修改参数"""
        coupling = CouplingModel(
            id="coupling_1",
            source_patch_id="patch_1",
            target_patch_id="patch_2",
            type=CouplingModel.TYPE_LINEAR,
            strength=0.5,
            delay=0.01
        )

        coupling.strength = 0.8
        coupling.delay = 0.02
        coupling.type = CouplingModel.TYPE_NONLINEAR

        self.assertEqual(coupling.strength, 0.8)
        self.assertEqual(coupling.delay, 0.02)
        self.assertEqual(coupling.type, "nonlinear")

    def test_delayed_coupling_buffer(self):
        """测试延迟耦合使用历史缓冲区"""
        coupling = CouplingModel(
            id="coupling_3",
            source_patch_id="patch_1",
            target_patch_id="patch_2",
            type=CouplingModel.TYPE_DELAYED,
            strength=1.0,
            delay=0.002,
            sampling_rate=1000
        )

        coupling.apply_coupling(1.0, 0.0, 0.0)
        coupling.apply_coupling(2.0, 0.0, 0.001)
        result = coupling.apply_coupling(3.0, 0.0, 0.002)

        self.assertAlmostEqual(result, 1.0, places=5)

    def test_repr(self):
        """测试字符串表示"""
        coupling = CouplingModel(
            id="coupling_1",
            source_patch_id="patch_1",
            target_patch_id="patch_2",
            type="linear",
            strength=0.5
        )

        repr_str = repr(coupling)
        self.assertIn("Coupling", repr_str)
        self.assertIn("coupling_1", repr_str)


if __name__ == '__main__':
    unittest.main()
