"""运行所有单元测试"""

import subprocess
import sys
import os
import unittest

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入测试模块
from tests.test_models import (
    TestDipole, TestSignalGenerator, TestCouplingModel,
    TestPatchCouplingEngine, TestPatchSerialization, TestWaveformParser,
)
from tests.test_utils import TestTranslator, TestConfigManager, TestLogger
from tests.test_signal_engine import TestSignalEngine


def run_unittest_suite():
    """运行 unittest 测试套件"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestDipole))
    suite.addTests(loader.loadTestsFromTestCase(TestSignalGenerator))
    suite.addTests(loader.loadTestsFromTestCase(TestCouplingModel))
    suite.addTests(loader.loadTestsFromTestCase(TestPatchCouplingEngine))
    suite.addTests(loader.loadTestsFromTestCase(TestPatchSerialization))
    suite.addTests(loader.loadTestsFromTestCase(TestWaveformParser))
    suite.addTests(loader.loadTestsFromTestCase(TestTranslator))
    suite.addTests(loader.loadTestsFromTestCase(TestConfigManager))
    suite.addTests(loader.loadTestsFromTestCase(TestLogger))
    suite.addTests(loader.loadTestsFromTestCase(TestSignalEngine))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


def run_pytest_modules():
    """运行 pytest 模块（output_sink 等）"""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cmd = [sys.executable, '-m', 'pytest', 'tests/test_output_sink.py', '-q']
    return subprocess.call(cmd, cwd=root)


def run_all_tests():
    """运行所有测试"""
    code = run_unittest_suite()
    if code != 0:
        return code
    return run_pytest_modules()


if __name__ == '__main__':
    sys.exit(run_all_tests())
