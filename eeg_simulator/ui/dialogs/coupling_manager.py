"""耦合模型管理对话框 - 管理 Patch 之间的耦合关系"""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, 
                             QLabel, QPushButton, QComboBox,
                             QDoubleSpinBox, QGroupBox, QFrame,
                             QListWidget, QListWidgetItem, QMessageBox,
                             QSplitter, QWidget, QFormLayout, QScrollArea,
                             QDialogButtonBox)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from ...utils import tr, get_logger
from ...models import CouplingModel

logger = get_logger(__name__)


class CouplingManagerDialog(QDialog):
    """耦合模型管理对话框"""
    
    coupling_changed = pyqtSignal()  # 耦合模型发生变化时发出信号
    
    def __init__(self, parent_simulator, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr('dlg_coupling_manager_title'))
        self.setMinimumSize(800, 600)
        
        self.parent_simulator = parent_simulator
        self.patches = parent_simulator.patches
        self.coupling_models = parent_simulator.patch_ops.coupling_models
        
        self.init_ui()
        self.refresh_coupling_list()
    
    def init_ui(self):
        """初始化UI"""
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)
        
        # 左侧面板 - 耦合列表
        left_panel = self._create_list_panel()
        main_layout.addWidget(left_panel, 1)
        
        # 右侧面板 - 创建/编辑
        right_panel = self._create_edit_panel()
        main_layout.addWidget(right_panel, 1)
    
    def _create_list_panel(self):
        """创建左侧耦合列表面板"""
        panel = QGroupBox(tr('panel_coupling_list'))
        layout = QVBoxLayout(panel)
        
        # 统计信息
        self.stats_label = QLabel(tr('coupling_stats', 0))
        self.stats_label.setStyleSheet("color: #4CAF50; font-weight: bold; font-size: 14px;")
        layout.addWidget(self.stats_label)
        
        # 耦合列表
        self.coupling_list = QListWidget()
        self.coupling_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.coupling_list.itemSelectionChanged.connect(self._on_coupling_selected)
        self.coupling_list.setStyleSheet("""
            QListWidget {
                background-color: #2d2d2d;
                border: 1px solid #444;
                border-radius: 4px;
                padding: 5px;
            }
            QListWidget::item {
                padding: 10px;
                border-bottom: 1px solid #444;
                color: #ffffff;
            }
            QListWidget::item:selected {
                background-color: #4CAF50;
                color: white;
            }
            QListWidget::item:hover:!selected {
                background-color: #3d3d3d;
            }
        """)
        layout.addWidget(self.coupling_list)
        
        # 删除按钮
        btn_layout = QHBoxLayout()
        self.delete_btn = QPushButton(tr('delete'))
        self.delete_btn.setObjectName("StopBtn")
        self.delete_btn.setEnabled(False)
        self.delete_btn.clicked.connect(self._on_delete_coupling)
        btn_layout.addWidget(self.delete_btn)
        
        self.clear_all_btn = QPushButton(tr('btn_clear_all'))
        self.clear_all_btn.clicked.connect(self._on_clear_all)
        btn_layout.addWidget(self.clear_all_btn)
        
        layout.addLayout(btn_layout)
        
        return panel
    
    def _create_edit_panel(self):
        """创建右侧编辑面板"""
        panel = QGroupBox(tr('panel_create_edit_coupling'))
        layout = QVBoxLayout(panel)
        
        # 创建新耦合区域
        create_group = QGroupBox(tr('group_create_coupling'))
        create_layout = QFormLayout(create_group)
        
        # 源 Patch 选择
        self.source_combo = QComboBox()
        self._populate_patch_combo(self.source_combo)
        create_layout.addRow(tr('label_source_patch'), self.source_combo)
        
        # 目标 Patch 选择
        self.target_combo = QComboBox()
        self._populate_patch_combo(self.target_combo)
        create_layout.addRow(tr('label_target_patch'), self.target_combo)
        
        # 耦合类型
        self.type_combo = QComboBox()
        self.type_combo.addItem(tr('coupling_linear'), 'linear')
        self.type_combo.addItem(tr('coupling_nonlinear'), 'nonlinear')
        self.type_combo.addItem(tr('coupling_delayed'), 'delayed')
        create_layout.addRow(tr('label_type'), self.type_combo)
        
        # 耦合强度
        self.strength_spin = QDoubleSpinBox()
        self.strength_spin.setRange(-100, 100)
        self.strength_spin.setDecimals(3)
        self.strength_spin.setSingleStep(0.1)
        self.strength_spin.setValue(0.5)
        create_layout.addRow(tr('label_strength'), self.strength_spin)
        
        # 延迟
        self.delay_spin = QDoubleSpinBox()
        self.delay_spin.setRange(0, 1)
        self.delay_spin.setDecimals(4)
        self.delay_spin.setSingleStep(0.001)
        self.delay_spin.setSuffix(' s')
        self.delay_spin.setValue(0.0)
        create_layout.addRow(tr('label_delay'), self.delay_spin)
        
        # 添加按钮
        self.add_btn = QPushButton(tr('btn_add_coupling'))
        self.add_btn.setObjectName("PrimaryBtn")
        self.add_btn.clicked.connect(self._on_add_coupling)
        create_layout.addRow(self.add_btn)
        
        layout.addWidget(create_group)
        
        # 编辑区域（选中现有耦合时使用）
        self.edit_group = QGroupBox(tr('group_edit_coupling'))
        self.edit_group.setEnabled(False)
        edit_layout = QFormLayout(self.edit_group)
        
        # 显示当前选中的耦合信息
        self.edit_info_label = QLabel(tr('label_no_selection'))
        self.edit_info_label.setStyleSheet("color: gray;")
        edit_layout.addRow(self.edit_info_label)
        
        # 编辑强度
        self.edit_strength_spin = QDoubleSpinBox()
        self.edit_strength_spin.setRange(-100, 100)
        self.edit_strength_spin.setDecimals(3)
        self.edit_strength_spin.setSingleStep(0.1)
        self.edit_strength_spin.valueChanged.connect(self._on_edit_strength_changed)
        edit_layout.addRow(tr('label_strength'), self.edit_strength_spin)
        
        # 编辑延迟
        self.edit_delay_spin = QDoubleSpinBox()
        self.edit_delay_spin.setRange(0, 1)
        self.edit_delay_spin.setDecimals(4)
        self.edit_delay_spin.setSingleStep(0.001)
        self.edit_delay_spin.setSuffix(' s')
        self.edit_delay_spin.valueChanged.connect(self._on_edit_delay_changed)
        edit_layout.addRow(tr('label_delay'), self.edit_delay_spin)
        
        # 编辑类型
        self.edit_type_combo = QComboBox()
        self.edit_type_combo.addItem(tr('coupling_linear'), 'linear')
        self.edit_type_combo.addItem(tr('coupling_nonlinear'), 'nonlinear')
        self.edit_type_combo.addItem(tr('coupling_delayed'), 'delayed')
        self.edit_type_combo.currentIndexChanged.connect(self._on_edit_type_changed)
        edit_layout.addRow(tr('label_type'), self.edit_type_combo)
        
        layout.addWidget(self.edit_group)
        layout.addStretch()
        
        # 关闭按钮
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)
        
        return panel
    
    def _populate_patch_combo(self, combo: QComboBox, exclude_patch_id: str = None):
        """填充 Patch 下拉框"""
        combo.clear()
        for patch_id, patch in self.patches.items():
            if patch_id == exclude_patch_id:
                continue
            display_name = patch.name or patch_id
            dipole_count = patch.get_dipole_count()
            combo.addItem(f"{display_name} ({dipole_count} dipoles)", patch_id)
    
    def refresh_coupling_list(self, select_id=None):
        """刷新耦合列表"""
        if select_id is None and hasattr(self, 'current_edit_id'):
            select_id = getattr(self, 'current_edit_id', None)

        self.coupling_list.clear()
        
        for coupling_id, coupling in self.coupling_models.items():
            # 获取 Patch 名称
            source_patch = self.patches.get(coupling.source_patch_id)
            target_patch = self.patches.get(coupling.target_patch_id)
            
            source_name = source_patch.name if source_patch else coupling.source_patch_id
            target_name = target_patch.name if target_patch else coupling.target_patch_id
            
            # 创建显示文本
            type_text = tr(f'coupling_{coupling.type}')
            display_text = f"{source_name} → {target_name}\n  {type_text}, strength={coupling.strength:.3f}, delay={coupling.delay:.4f}s"
            
            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, coupling_id)
            item.setToolTip(f"ID: {coupling_id}")
            self.coupling_list.addItem(item)
            if select_id and coupling_id == select_id:
                item.setSelected(True)
                self.coupling_list.setCurrentItem(item)
        
        # 更新统计
        count = len(self.coupling_models)
        self.stats_label.setText(tr('coupling_stats', count))
        
        # 如果没有耦合，禁用编辑区域
        if count == 0:
            self.edit_group.setEnabled(False)
            self.edit_info_label.setText(tr('label_no_coupling_selected'))
    
    def _on_coupling_selected(self):
        """选中耦合模型时"""
        items = self.coupling_list.selectedItems()
        if not items:
            self.delete_btn.setEnabled(False)
            self.edit_group.setEnabled(False)
            self.edit_info_label.setText(tr('label_no_coupling_selected'))
            return
        
        item = items[0]
        coupling_id = item.data(Qt.ItemDataRole.UserRole)
        coupling = self.coupling_models.get(coupling_id)
        
        if coupling:
            self.delete_btn.setEnabled(True)
            self.edit_group.setEnabled(True)
            
            # 更新编辑区域
            source_patch = self.patches.get(coupling.source_patch_id)
            target_patch = self.patches.get(coupling.target_patch_id)
            source_name = source_patch.name if source_patch else coupling.source_patch_id
            target_name = target_patch.name if target_patch else coupling.target_patch_id
            
            self.edit_info_label.setText(
                f"{coupling_id}\n{source_name} → {target_name}"
            )
            self.edit_info_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
            
            # 设置当前值
            self.edit_strength_spin.blockSignals(True)
            self.edit_strength_spin.setValue(coupling.strength)
            self.edit_strength_spin.blockSignals(False)
            
            self.edit_delay_spin.blockSignals(True)
            self.edit_delay_spin.setValue(coupling.delay)
            self.edit_delay_spin.blockSignals(False)
            
            self.edit_type_combo.blockSignals(True)
            type_index = self.edit_type_combo.findData(coupling.type)
            if type_index >= 0:
                self.edit_type_combo.setCurrentIndex(type_index)
            self.edit_type_combo.blockSignals(False)
            
            self.current_edit_id = coupling_id
    
    def _on_add_coupling(self):
        """添加新的耦合模型"""
        source_id = self.source_combo.currentData()
        target_id = self.target_combo.currentData()
        
        if not source_id or not target_id:
            QMessageBox.warning(self, tr('warning'), tr('msg_select_source_target'))
            return
        
        if source_id == target_id:
            QMessageBox.warning(self, tr('warning'), tr('msg_same_source_target'))
            return
        
        # 检查是否已存在相同的耦合
        for coupling in self.coupling_models.values():
            if (coupling.source_patch_id == source_id and 
                coupling.target_patch_id == target_id):
                QMessageBox.warning(self, tr('warning'), tr('msg_coupling_exists'))
                return
        
        coupling_type = self.type_combo.currentData()
        strength = self.strength_spin.value()
        delay = self.delay_spin.value()
        
        new_id = self.parent_simulator.patch_ops.add_coupling_model(
            source_patch_id=source_id,
            target_patch_id=target_id,
            type=coupling_type,
            strength=strength,
            delay=delay
        )
        
        if new_id:
            logger.info(f"Created coupling: {new_id}")
            self.refresh_coupling_list()
            self.coupling_changed.emit()
            QMessageBox.information(self, tr('success'), tr('msg_coupling_created', new_id))
    
    def _on_delete_coupling(self):
        """删除选中的耦合模型"""
        items = self.coupling_list.selectedItems()
        if not items:
            return
        
        item = items[0]
        coupling_id = item.data(Qt.ItemDataRole.UserRole)
        
        reply = QMessageBox.question(
            self, tr('confirm'),
            tr('msg_confirm_delete_coupling', coupling_id),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.parent_simulator.patch_ops.delete_coupling_model(coupling_id)
            self.refresh_coupling_list()
            self.coupling_changed.emit()
            logger.info(f"Deleted coupling: {coupling_id}")
    
    def _on_clear_all(self):
        """清除所有耦合模型"""
        if not self.coupling_models:
            return
        
        reply = QMessageBox.question(
            self, tr('confirm'),
            tr('msg_confirm_clear_couplings', len(self.coupling_models)),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.parent_simulator.patch_ops.clear_coupling_models()
            self.refresh_coupling_list()
            self.coupling_changed.emit()
            logger.info("Cleared all couplings")
    
    def _on_edit_strength_changed(self, value):
        """编辑强度改变"""
        if hasattr(self, 'current_edit_id') and self.current_edit_id:
            if self.parent_simulator.patch_ops.modify_coupling_model(
                self.current_edit_id, strength=value
            ):
                self.refresh_coupling_list(select_id=self.current_edit_id)
                self.coupling_changed.emit()
    
    def _on_edit_delay_changed(self, value):
        """编辑延迟改变"""
        if hasattr(self, 'current_edit_id') and self.current_edit_id:
            if self.parent_simulator.patch_ops.modify_coupling_model(
                self.current_edit_id, delay=value
            ):
                self.refresh_coupling_list(select_id=self.current_edit_id)
                self.coupling_changed.emit()
    
    def _on_edit_type_changed(self, index):
        """编辑类型改变"""
        if hasattr(self, 'current_edit_id') and self.current_edit_id:
            new_type = self.edit_type_combo.currentData()
            if self.parent_simulator.patch_ops.modify_coupling_model(
                self.current_edit_id, type=new_type
            ):
                self.refresh_coupling_list(select_id=self.current_edit_id)
                self.coupling_changed.emit()
