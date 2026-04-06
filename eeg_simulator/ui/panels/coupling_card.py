"""耦合模型配置卡片 - 基于 Patch 的耦合"""

from PyQt6.QtWidgets import (QFrame, QVBoxLayout, QHBoxLayout, 
                             QLabel, QDoubleSpinBox, QPushButton,
                             QComboBox)

from ...models import CouplingModel
from ..themes import get_color
from ...utils import tr


class CouplingModelCard(QFrame):
    """耦合模型配置卡片 - Patch 到 Patch 的耦合"""
    
    def __init__(self, coupling_id: str, coupling: CouplingModel,
                 parent_simulator, parent_panel, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.coupling_id = coupling_id
        self.coupling = coupling
        self.parent_simulator = parent_simulator
        self.parent_panel = parent_panel
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        
        # 标题行：ID 和类型
        title_layout = QHBoxLayout()
        title_label = QLabel(f"ID: {self.coupling_id}")
        title_label.setObjectName("SubTitle")
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        
        # 耦合类型选择
        self.type_combo = QComboBox()
        self.type_combo.addItem(tr('coupling_linear'), 'linear')
        self.type_combo.addItem(tr('coupling_nonlinear'), 'nonlinear')
        self.type_combo.addItem(tr('coupling_delayed'), 'delayed')
        
        # 设置当前类型
        type_index = self.type_combo.findData(self.coupling.type)
        if type_index >= 0:
            self.type_combo.setCurrentIndex(type_index)
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        title_layout.addWidget(self.type_combo)
        layout.addLayout(title_layout)

        # 源/目标 Patch 选择
        source_layout = QHBoxLayout()
        source_layout.addWidget(QLabel(tr('label_source_patch')))
        self.source_combo = QComboBox()
        self._populate_patch_combo(self.source_combo, self.coupling.source_patch_id)
        self.source_combo.currentIndexChanged.connect(self._on_source_changed)
        source_layout.addWidget(self.source_combo, 1)
        layout.addLayout(source_layout)
        
        target_layout = QHBoxLayout()
        target_layout.addWidget(QLabel(tr('label_target_patch')))
        self.target_combo = QComboBox()
        self._populate_patch_combo(self.target_combo, self.coupling.target_patch_id)
        self.target_combo.currentIndexChanged.connect(self._on_target_changed)
        target_layout.addWidget(self.target_combo, 1)
        layout.addLayout(target_layout)

        # 强度
        strength_layout = QHBoxLayout()
        strength_layout.addWidget(QLabel(tr('label_strength')))
        self.strength_spin = QDoubleSpinBox()
        self.strength_spin.setRange(-100, 100)
        self.strength_spin.setDecimals(3)
        self.strength_spin.setSingleStep(0.1)
        self.strength_spin.setValue(self.coupling.strength)
        self.strength_spin.valueChanged.connect(self._on_modify_coupling)
        strength_layout.addWidget(self.strength_spin)
        layout.addLayout(strength_layout)

        # 延迟
        delay_layout = QHBoxLayout()
        delay_layout.addWidget(QLabel(tr('label_delay')))
        self.delay_spin = QDoubleSpinBox()
        self.delay_spin.setRange(0, 1)
        self.delay_spin.setDecimals(4)
        self.delay_spin.setSingleStep(0.001)
        self.delay_spin.setSuffix(' s')
        self.delay_spin.setValue(self.coupling.delay)
        self.delay_spin.valueChanged.connect(self._on_modify_coupling)
        delay_layout.addWidget(self.delay_spin)
        layout.addLayout(delay_layout)

        # 删除按钮
        delete_btn = QPushButton(tr('delete'))
        delete_btn.setObjectName("StopBtn")
        delete_btn.clicked.connect(self._on_delete_coupling)
        layout.addWidget(delete_btn)
    
    def _populate_patch_combo(self, combo: QComboBox, current_patch_id: str):
        """填充 Patch 下拉框"""
        combo.clear()
        patches = self.parent_simulator.patches
        
        for patch_id, patch in patches.items():
            # 显示 Patch 名称和偶极子数量
            display_name = patch.name or patch_id
            dipole_count = patch.get_dipole_count()
            combo.addItem(f"{display_name} ({dipole_count} dipoles)", patch_id)
        
        # 设置当前选中
        index = combo.findData(current_patch_id)
        if index >= 0:
            combo.setCurrentIndex(index)
    
    def _on_type_changed(self, index):
        """耦合类型改变"""
        new_type = self.type_combo.currentData()
        self.parent_simulator.modify_coupling_model(
            self.coupling_id,
            type=new_type
        )
    
    def _on_source_changed(self, index):
        """源 Patch 改变"""
        new_source_id = self.source_combo.currentData()
        # 删除旧的耦合，创建新的（因为 source/target 是耦合的关键标识）
        old_coupling = self.coupling
        self.parent_simulator.delete_coupling_model(self.coupling_id)
        
        new_id = self.parent_simulator.add_coupling_model(
            source_patch_id=new_source_id,
            target_patch_id=old_coupling.target_patch_id,
            type=old_coupling.type,
            strength=old_coupling.strength,
            delay=old_coupling.delay
        )
        if new_id:
            self.coupling_id = new_id
            self.coupling = self.parent_simulator.coupling_models.get(new_id)
        self.parent_panel.update_coupling_list()
    
    def _on_target_changed(self, index):
        """目标 Patch 改变"""
        new_target_id = self.target_combo.currentData()
        # 删除旧的耦合，创建新的
        old_coupling = self.coupling
        self.parent_simulator.delete_coupling_model(self.coupling_id)
        
        new_id = self.parent_simulator.add_coupling_model(
            source_patch_id=old_coupling.source_patch_id,
            target_patch_id=new_target_id,
            type=old_coupling.type,
            strength=old_coupling.strength,
            delay=old_coupling.delay
        )
        if new_id:
            self.coupling_id = new_id
            self.coupling = self.parent_simulator.coupling_models.get(new_id)
        self.parent_panel.update_coupling_list()

    def _on_modify_coupling(self):
        """修改耦合参数"""
        self.parent_simulator.modify_coupling_model(
            self.coupling_id,
            strength=self.strength_spin.value(),
            delay=self.delay_spin.value()
        )

    def _on_delete_coupling(self):
        """删除耦合模型"""
        self.parent_simulator.delete_coupling_model(self.coupling_id)
        self.parent_panel.update_coupling_list()
