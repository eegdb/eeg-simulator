"""文件/目录选择对话框（避免 macOS 上全局样式表破坏原生对话框）"""

import sys
from pathlib import Path

from PyQt6.QtWidgets import QFileDialog, QWidget


def _directory_dialog_options() -> QFileDialog.Option:
    options = QFileDialog.Option.ShowDirsOnly
    if sys.platform == 'darwin':
        options |= QFileDialog.Option.DontUseNativeDialog
    return options


def get_existing_directory(
    parent: QWidget,
    title: str,
    start_dir: str = '',
) -> str:
    """选择目录；返回空字符串表示取消"""
    initial = start_dir or str(Path.home())
    path = QFileDialog.getExistingDirectory(
        parent,
        title,
        initial,
        options=_directory_dialog_options(),
    )
    return path or ''
