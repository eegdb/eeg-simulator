"""信号生成器配置卡片"""

from PyQt6.QtWidgets import (QFrame, QVBoxLayout, QHBoxLayout, 
                             QLabel, QDoubleSpinBox, QPushButton)

from ...models import SignalGenerator
from ..themes import get_color
from ...utils import tr


class SignalGeneratorCard(QFrame):
    """信号生成器配置卡片"""
    
    def __init__(self, signal_id: str, signal: SignalGenerator,
                 parent_simulator, parent_panel, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.signal_id = signal_id
        self.signal = signal
        self.parent_simulator = parent_simulator
        self.parent_panel = parent_panel
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"ID: {self.signal_id} ({self.signal.type})", objectName="SubTitle"))

        # 类型显示
        type_label = QLabel(f"{tr('label_type')} {self.signal.type}")
        layout.addWidget(type_label)

        # 参数（简化，假设正弦波）
        if self.signal.type == SignalGenerator.TYPE_SINE:
            # 频率
            freq_layout = QHBoxLayout()
            freq_layout.addWidget(QLabel(tr('label_frequency')))
            self.freq_spin = QDoubleSpinBox()
            self.freq_spin.setRange(0.1, 1000)
            self.freq_spin.setDecimals(2)
            self.freq_spin.setValue(self.signal.parameters.get('frequency', 10))
            self.freq_spin.valueChanged.connect(self._on_modify_signal)
            freq_layout.addWidget(self.freq_spin)
            layout.addLayout(freq_layout)

            # 振幅
            amp_layout = QHBoxLayout()
            amp_layout.addWidget(QLabel(tr('label_amplitude')))
            self.amp_spin = QDoubleSpinBox()
            self.amp_spin.setRange(0, 10000)
            self.amp_spin.setDecimals(2)
            self.amp_spin.setValue(self.signal.parameters.get('amplitude', 1))
            self.amp_spin.valueChanged.connect(self._on_modify_signal)
            amp_layout.addWidget(self.amp_spin)
            layout.addLayout(amp_layout)

        # 删除按钮
        delete_btn = QPushButton(tr('delete'))
        delete_btn.setObjectName("StopBtn")
        delete_btn.clicked.connect(self._on_delete_signal)
        layout.addWidget(delete_btn)

    def _on_modify_signal(self):
        new_params = self.signal.parameters.copy()
        if self.signal.type == SignalGenerator.TYPE_SINE:
            new_params['frequency'] = self.freq_spin.value()
            new_params['amplitude'] = self.amp_spin.value()
        self.parent_simulator.modify_signal_generator(
            self.signal_id,
            parameters=new_params
        )

    def _on_delete_signal(self):
        self.parent_simulator.delete_signal_generator(self.signal_id)
        self.parent_panel.update_signal_list()
