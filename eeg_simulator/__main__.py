"""程序入口"""

import sys
import pyqtgraph as pg

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from .ui.styles import QSS
from .ui.themes import generate_stylesheet, set_theme
from .utils import get_config, get_logger_manager
from .core import EEGSimulator


def main():
    """主函数"""
    # 先加载配置以确定主题和日志级别
    config = get_config()
    theme = config.get_theme()
    set_theme(theme)
    
    # 应用日志级别配置（默认 DEBUG）
    log_manager = get_logger_manager()
    log_level = config.get('log_level', 'DEBUG')
    log_manager.set_console_level(log_level)
    
    app = QApplication(sys.argv)
    
    # 禁用原生菜单栏，让菜单显示在窗口内（Windows风格）
    app.setAttribute(Qt.ApplicationAttribute.AA_DontUseNativeMenuBar, True)
    
    # 使用主题样式表（或默认样式表）
    stylesheet = generate_stylesheet()
    app.setStyleSheet(stylesheet)

    # 设置pyqtgraph - 优化性能配置
    pg.setConfigOptions(
        antialias=False,        # 禁用抗锯齿以提高性能
        useOpenGL=False,        # OpenGL加速（如果显卡支持可设为True）
        enableExperimental=False
    )

    # 创建主窗口
    window = EEGSimulator()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
