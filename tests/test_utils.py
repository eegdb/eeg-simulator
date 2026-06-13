"""测试 utils 模块"""

import unittest
import os
import sys
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eeg_simulator.utils import Translator, tr, ConfigManager


class TestTranslator(unittest.TestCase):
    """测试 Translator 国际化类"""

    def setUp(self):
        """测试前准备"""
        self.translator = Translator()

    def test_default_language(self):
        """测试默认语言"""
        self.assertEqual(self.translator.get_language(), 'zh_CN')

    def test_set_language(self):
        """测试设置语言"""
        result = self.translator.set_language('en')
        self.assertTrue(result)
        self.assertEqual(self.translator.get_language(), 'en')

    def test_set_invalid_language(self):
        """测试设置无效语言"""
        result = self.translator.set_language('invalid_lang')
        self.assertFalse(result)
        self.assertEqual(self.translator.get_language(), 'zh_CN')  # 保持原语言

    def test_translate_zh_cn(self):
        """测试中文翻译"""
        self.translator.set_language('zh_CN')
        
        # 测试存在的关键字
        text = self.translator.translate('app_name')
        self.assertIn('EEG', text)
        
        # 测试不存在的关键字（返回原值）
        text = self.translator.translate('non_existent_key')
        self.assertEqual(text, 'non_existent_key')

    def test_translate_en(self):
        """测试英文翻译"""
        self.translator.set_language('en')
        
        text = self.translator.translate('app_name')
        self.assertIn('EEG', text)

    def test_translate_with_formatting(self):
        """测试带格式化的翻译"""
        self.translator.set_language('zh_CN')
        
        # 测试带参数的翻译
        text = self.translator.translate('label_dipole_count', 5)
        self.assertIn('5', text)

    def test_tr_function(self):
        """测试 tr 快捷函数"""
        # tr 函数应该使用全局实例
        text = tr('app_name')
        self.assertIsInstance(text, str)


class TestConfigManager(unittest.TestCase):
    """测试 ConfigManager 配置管理类"""

    def setUp(self):
        """测试前准备 - 使用临时配置目录"""
        # 创建临时目录
        self.temp_dir = tempfile.mkdtemp()
        self.original_home = Path.home
        
        # 模拟 home 目录
        Path.home = lambda: Path(self.temp_dir)
        
        # 确保每次测试都创建新的 ConfigManager 实例
        import eeg_simulator.utils.config_manager as config_module
        config_module._config_instance = None

    def tearDown(self):
        """测试后清理"""
        # 恢复 home 目录
        Path.home = self.original_home
        
        # 删除临时目录
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
        
        # 重置全局实例
        import eeg_simulator.utils.config_manager as config_module
        config_module._config_instance = None

    def test_load_default_config(self):
        """测试加载默认配置"""
        config = ConfigManager()
        
        self.assertEqual(config.get('language'), 'zh_CN')
        self.assertEqual(config.get('theme'), 'dark')
        self.assertEqual(config.get('default_sampling_rate'), 1000)

    def test_get_with_default(self):
        """测试获取配置（带默认值）"""
        config = ConfigManager()
        
        # 存在的配置
        value = config.get('theme', 'light')
        self.assertEqual(value, 'dark')
        
        # 不存在的配置（返回默认值）
        value = config.get('non_existent', 'default_value')
        self.assertEqual(value, 'default_value')

    def test_set_config(self):
        """测试设置配置"""
        config = ConfigManager()
        
        config.set('theme', 'light')
        self.assertEqual(config.get('theme'), 'light')
        
        # 重新加载验证是否保存
        import eeg_simulator.utils.config_manager as config_module
        config_module._config_instance = None
        config2 = ConfigManager()
        self.assertEqual(config2.get('theme'), 'light')

    def test_set_many(self):
        """测试批量设置配置"""
        config = ConfigManager()
        
        config.set_many({
            'language': 'en',
            'theme': 'light'
        })
        
        self.assertEqual(config.get('language'), 'en')
        self.assertEqual(config.get('theme'), 'light')

    def test_language_methods(self):
        """测试语言相关方法"""
        config = ConfigManager()
        
        # 设置语言
        config.set_language('en')
        self.assertEqual(config.get_language(), 'en')
        
        # 切换回中文
        config.set_language('zh_CN')
        self.assertEqual(config.get_language(), 'zh_CN')

    def test_theme_methods(self):
        """测试主题相关方法"""
        config = ConfigManager()
        
        config.set_theme('light')
        self.assertEqual(config.get_theme(), 'light')
        
        config.set_theme('dark')
        self.assertEqual(config.get_theme(), 'dark')

    def test_get_all(self):
        """测试获取所有配置"""
        config = ConfigManager()
        all_config = config.get_all()
        
        self.assertIn('language', all_config)
        self.assertIn('theme', all_config)

    def test_reset_to_default(self):
        """测试重置为默认配置"""
        config = ConfigManager()
        
        # 修改配置
        config.set('theme', 'light')
        config.set('language', 'en')
        
        # 重置
        config.reset_to_default()
        
        # 验证恢复默认值
        self.assertEqual(config.get('theme'), 'dark')
        self.assertEqual(config.get('language'), 'zh_CN')


if __name__ == '__main__':
    unittest.main()
