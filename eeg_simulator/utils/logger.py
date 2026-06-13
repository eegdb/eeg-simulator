"""日志模块 - 统一的日志记录系统

使用方式：
    from .logger import get_logger
    
    logger = get_logger(__name__)
    logger.info("信息日志")
    logger.error("错误日志", exc_info=True)
"""

import os
import sys
import logging
import datetime
from pathlib import Path
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler


# 日志级别映射
LOG_LEVELS = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR,
    'CRITICAL': logging.CRITICAL
}


class ColoredFormatter(logging.Formatter):
    """带颜色的日志格式器（用于控制台输出）"""
    
    # ANSI颜色代码
    COLORS = {
        'DEBUG': '\033[36m',     # 青色
        'INFO': '\033[32m',      # 绿色
        'WARNING': '\033[33m',   # 黄色
        'ERROR': '\033[31m',     # 红色
        'CRITICAL': '\033[35m',  # 紫色
        'RESET': '\033[0m'       # 重置
    }
    
    def format(self, record):
        # 保存原始级别名称
        levelname = record.levelname
        
        # 添加颜色
        if hasattr(sys.stdout, 'isatty') and sys.stdout.isatty():
            color = self.COLORS.get(levelname, self.COLORS['RESET'])
            record.levelname = f"{color}{levelname}{self.COLORS['RESET']}"
        
        result = super().format(record)
        record.levelname = levelname  # 恢复原值
        return result


class LoggerManager:
    """日志管理器 - 单例模式"""
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if LoggerManager._initialized:
            return
        
        LoggerManager._initialized = True
        self.log_dir = None
        self.log_file = None
        self.root_logger = None
        self.console_handler = None
        self.file_handler = None
        
        # 默认日志目录：项目根目录下的 logs 文件夹
        self._setup_log_dir()
        self._setup_root_logger()
    
    def _setup_log_dir(self):
        """设置日志目录"""
        # 获取项目根目录（包含 eeg_simulator 模块的父目录）
        current_file = Path(__file__).resolve()
        project_root = current_file.parent.parent.parent
        
        self.log_dir = project_root / 'logs'
        self.log_dir.mkdir(exist_ok=True)
        
        # 日志文件名：eeg_simulator_YYYYMMDD.log
        today = datetime.datetime.now().strftime('%Y%m%d')
        self.log_file = self.log_dir / f'eeg_simulator_{today}.log'
    
    def _setup_root_logger(self):
        """配置根日志器"""
        self.root_logger = logging.getLogger('eeg_simulator')
        self.root_logger.setLevel(logging.DEBUG)
        
        # 避免重复添加handler
        if self.root_logger.handlers:
            return
        
        # 1. 控制台处理器（带颜色）
        self.console_handler = logging.StreamHandler(sys.stdout)
        self.console_handler.setLevel(logging.DEBUG)
        console_format = ColoredFormatter(
            '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
            datefmt='%H:%M:%S'
        )
        self.console_handler.setFormatter(console_format)
        self.root_logger.addHandler(self.console_handler)
        
        # 2. 文件处理器（按天滚动）
        self.file_handler = TimedRotatingFileHandler(
            self.log_file,
            when='midnight',      # 每天午夜创建新文件
            interval=1,
            backupCount=30,       # 保留30天的日志
            encoding='utf-8'
        )
        self.file_handler.setLevel(logging.DEBUG)
        file_format = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)s | %(filename)s:%(lineno)d | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        self.file_handler.setFormatter(file_format)
        self.root_logger.addHandler(self.file_handler)
        
        # 记录启动信息
        self.root_logger.info("=" * 60)
        self.root_logger.info("EEG Simulator 日志系统启动")
        self.root_logger.info(f"日志文件: {self.log_file}")
        self.root_logger.info(f"Python版本: {sys.version}")
        self.root_logger.info("=" * 60)
    
    def get_logger(self, name):
        """获取指定名称的日志器
        
        Args:
            name: 日志器名称，建议使用 __name__
            
        Returns:
            logging.Logger: 配置好的日志器
        """
        return logging.getLogger(f'eeg_simulator.{name}')
    
    def set_level(self, level):
        """设置日志级别
        
        Args:
            level: 日志级别，如 'DEBUG', 'INFO', 'WARNING', 'ERROR'
        """
        if isinstance(level, str):
            level = LOG_LEVELS.get(level.upper(), logging.INFO)
        self.root_logger.setLevel(level)
    
    def set_console_level(self, level):
        """设置控制台输出级别"""
        if isinstance(level, str):
            level = LOG_LEVELS.get(level.upper(), logging.INFO)
        self.console_handler.setLevel(level)
    
    def set_file_level(self, level):
        """设置文件输出级别"""
        if isinstance(level, str):
            level = LOG_LEVELS.get(level.upper(), logging.DEBUG)
        self.file_handler.setLevel(level)


# 全局日志管理器实例
_logger_manager = None

def get_logger_manager():
    """获取日志管理器实例"""
    global _logger_manager
    if _logger_manager is None:
        _logger_manager = LoggerManager()
    return _logger_manager


def get_logger(name):
    """获取日志器
    
    这是主要的日志获取接口。
    
    Args:
        name: 日志器名称，通常传入 __name__
        
    Returns:
        logging.Logger: 配置好的日志器
        
    Example:
        from .logger import get_logger
        logger = get_logger(__name__)
        logger.info("应用启动")
    """
    manager = get_logger_manager()
    return manager.get_logger(name)


def log_exception(logger, msg="发生异常"):
    """记录异常信息（包含堆栈）
    
    Args:
        logger: 日志器对象
        msg: 错误消息前缀
    """
    logger.error(msg, exc_info=True)


# 便捷函数
def debug(msg, *args, **kwargs):
    """快速记录DEBUG级别日志（使用默认日志器）"""
    get_logger('quick').debug(msg, *args, **kwargs)

def info(msg, *args, **kwargs):
    """快速记录INFO级别日志（使用默认日志器）"""
    get_logger('quick').info(msg, *args, **kwargs)

def warning(msg, *args, **kwargs):
    """快速记录WARNING级别日志（使用默认日志器）"""
    get_logger('quick').warning(msg, *args, **kwargs)

def error(msg, *args, **kwargs):
    """快速记录ERROR级别日志（使用默认日志器）"""
    get_logger('quick').error(msg, *args, **kwargs)

def critical(msg, *args, **kwargs):
    """快速记录CRITICAL级别日志（使用默认日志器）"""
    get_logger('quick').critical(msg, *args, **kwargs)
