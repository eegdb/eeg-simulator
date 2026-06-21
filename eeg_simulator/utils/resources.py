"""应用图标资源"""

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QPixmap

ICON_FILE = 'app_icon.png'


def get_icon_path() -> Path:
    return Path(__file__).resolve().parent.parent / 'assets' / ICON_FILE


def load_app_icon() -> QIcon:
    path = get_icon_path()
    if not path.is_file():
        return QIcon()

    source = QPixmap(str(path))
    if source.isNull():
        return QIcon()

    icon = QIcon()
    for size in (16, 32, 48, 64, 128, 256, 512):
        icon.addPixmap(
            source.scaled(
                size,
                size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
    return icon
