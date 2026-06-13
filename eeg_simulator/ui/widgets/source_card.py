"""信号源配置卡片组件"""

from PyQt6.QtWidgets import (QFrame, QVBoxLayout, QHBoxLayout, 
                             QLabel, QLineEdit, QDoubleSpinBox)

from ..styles import COLORS
from ...utils import tr


class SourceCard(QFrame):
    """复刻左侧信号源配置卡片"""

    def __init__(self, name, freq, amp, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self._setup_ui(name, freq, amp)

    def _setup_ui(self, name, freq, amp):
        layout = QVBoxLayout(self)

        # 标题行
        header = QHBoxLayout()
        self.title = QLineEdit(name)
        self.title.setStyleSheet("background:transparent; border:none; font-weight:bold;")
        header.addWidget(self.title)
        layout.addLayout(header)

        # 频率和振幅控制
        grid = QHBoxLayout()
        
        # 频率
        v1 = QVBoxLayout()
        v1.addWidget(QLabel(tr('label_frequency'), objectName="SubTitle"))
        self.freq_spin = QDoubleSpinBox()
        self.freq_spin.setRange(0.1, 1000)
        self.freq_spin.setValue(freq)
        self.freq_spin.setDecimals(2)
        v1.addWidget(self.freq_spin)

        # 振幅
        v2 = QVBoxLayout()
        v2.addWidget(QLabel(tr('label_amplitude'), objectName="SubTitle"))
        self.amp_spin = QDoubleSpinBox()
        self.amp_spin.setRange(0, 10000)
        self.amp_spin.setValue(amp)
        self.amp_spin.setDecimals(2)
        v2.addWidget(self.amp_spin)

        grid.addLayout(v1)
        grid.addLayout(v2)
        layout.addLayout(grid)
