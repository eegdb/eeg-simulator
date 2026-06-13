"""配置管理器 - 使用 SQLite 存储用户配置"""

import os
import sqlite3
import json
from pathlib import Path


class ConfigManager:
    """配置管理器"""
    
    # 默认配置
    DEFAULT_CONFIG = {
        'language': 'en',
        'theme': 'dark',  # 'dark' 或 'light'
        'dark_mode': True,
        'animations': True,
        'default_sampling_rate': 1000,
        'show_electrode_labels': True,
        'last_montage': 'standard_1020',
        'window_size': [1400, 900],
        'default_project_dir': str(Path.home() / 'EEGProjects'),
        'log_level': 'DEBUG',  # DEBUG, INFO, WARNING, ERROR
        'heatmap_refresh_interval': 1000,  # 热力图刷新间隔（毫秒），默认1秒
        'filter_highpass_order': 4,  # 高通滤波阶数
        'filter_lowpass_order': 4,   # 低通滤波阶数
        'filter_notch_order': 2,     # 陷波滤波阶数（实际为品质因数相关的带宽）
    }
    
    def __init__(self):
        # 配置文件路径
        self.config_dir = Path.home() / '.eegs'
        self.config_dir.mkdir(exist_ok=True)
        self.db_path = self.config_dir / 'config.db'
        
        # 初始化数据库
        self._init_db()
        
        # 当前配置缓存
        self._cache = {}
        self._load_all()
    
    def _init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        # 创建配置表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def _load_all(self):
        """加载所有配置到缓存"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute('SELECT key, value FROM config')
        rows = cursor.fetchall()
        
        self._cache = dict(self.DEFAULT_CONFIG)  # 先加载默认值
        for key, value in rows:
            self._cache[key] = self._parse_value(key, value)
        
        conn.close()
    
    def _parse_value(self, key, value):
        """解析数据库值"""
        if value is None:
            return self.DEFAULT_CONFIG.get(key)
        
        # 尝试解析为 JSON
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            # 简单类型转换
            if value.lower() == 'true':
                return True
            elif value.lower() == 'false':
                return False
            elif value.isdigit():
                return int(value)
            try:
                return float(value)
            except ValueError:
                return value
    
    def get(self, key, default=None):
        """获取配置值"""
        return self._cache.get(key, default or self.DEFAULT_CONFIG.get(key))
    
    def set(self, key, value):
        """设置配置值"""
        self._cache[key] = value
        
        # 保存到数据库
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO config (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        ''', (key, json.dumps(value)))
        
        conn.commit()
        conn.close()
    
    def set_many(self, config_dict):
        """批量设置配置"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        for key, value in config_dict.items():
            self._cache[key] = value
            cursor.execute('''
                INSERT OR REPLACE INTO config (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            ''', (key, json.dumps(value)))
        
        conn.commit()
        conn.close()
    
    def get_all(self):
        """获取所有配置"""
        return dict(self._cache)
    
    def reset_to_default(self):
        """重置为默认配置"""
        self._cache = dict(self.DEFAULT_CONFIG)
        
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        # 清空表
        cursor.execute('DELETE FROM config')
        
        # 插入默认值
        for key, value in self.DEFAULT_CONFIG.items():
            cursor.execute('''
                INSERT INTO config (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            ''', (key, json.dumps(value)))
        
        conn.commit()
        conn.close()
    
    def get_theme(self):
        """获取当前主题"""
        return self.get('theme', 'dark')
    
    def set_theme(self, theme):
        """设置主题"""
        self.set('theme', theme)
        self.set('dark_mode', theme == 'dark')
    
    def get_language(self):
        """获取当前语言"""
        return self.get('language', 'en')
    
    def set_language(self, lang):
        """设置语言"""
        self.set('language', lang)


# 全局配置实例
_config_instance = None

def get_config():
    """获取全局配置实例"""
    global _config_instance
    if _config_instance is None:
        _config_instance = ConfigManager()
    return _config_instance
