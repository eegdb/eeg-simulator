"""耦合模型管理对话框 - 管理 Patch 之间的耦合关系"""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QComboBox,
                             QDoubleSpinBox, QGroupBox, QFrame,
                             QListWidget, QListWidgetItem, QMessageBox,
                             QWidget, QFormLayout, QScrollArea, QSizePolicy)
from PyQt6.QtCore import Qt, pyqtSignal

from ...utils import tr, get_logger
from ...models import CouplingModel
from ..themes import get_color

logger = get_logger(__name__)


def _save_btn_style():
    """保存按钮"""
    return f"""
        QPushButton {{
            background-color: {get_color('accent')};
            color: {get_color('text_inverse')};
            border: none;
            border-radius: 4px;
            padding: 8px 24px;
            font-size: 13px;
            font-weight: bold;
            min-height: 34px;
        }}
        QPushButton:hover {{
            background-color: {get_color('accent_hover')};
        }}
        QPushButton:disabled {{
            background-color: {get_color('bg_input')};
            color: {get_color('text_muted')};
        }}
    """


def _danger_btn_style():
    return f"""
        QPushButton {{
            background-color: {get_color('red')};
            color: {get_color('text_inverse')};
            border: none;
            border-radius: 6px;
            padding: 8px 16px;
            font-weight: bold;
            min-height: 36px;
        }}
        QPushButton:hover {{
            background-color: {get_color('red')};
        }}
        QPushButton:disabled {{
            background-color: {get_color('bg_input')};
            color: {get_color('text_muted')};
        }}
    """


def _secondary_btn_style():
    return f"""
        QPushButton {{
            background-color: {get_color('bg_input')};
            color: {get_color('text_main')};
            border: 1px solid {get_color('border')};
            border-radius: 6px;
            padding: 8px 16px;
            font-weight: bold;
            min-height: 36px;
        }}
        QPushButton:hover {{
            background-color: {get_color('border')};
        }}
    """


class CouplingManagerDialog(QDialog):
    """耦合模型管理对话框"""

    coupling_changed = pyqtSignal()

    def __init__(self, parent_simulator, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr('dlg_coupling_manager_title'))
        self.setMinimumSize(820, 680)
        self.resize(860, 760)

        self.parent_simulator = parent_simulator
        self.patches = parent_simulator.patches
        self.coupling_models = parent_simulator.patch_ops.coupling_models
        self.current_edit_id = None

        self.init_ui()
        self.refresh_coupling_list()

    def init_ui(self):
        """初始化UI"""
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        left_panel = self._create_list_panel()
        main_layout.addWidget(left_panel, 1)

        right_panel = self._create_form_panel()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(right_panel)
        main_layout.addWidget(scroll, 1)

    def _create_list_panel(self):
        """创建左侧耦合列表面板"""
        panel = QGroupBox(tr('panel_coupling_list'))
        layout = QVBoxLayout(panel)

        self.stats_label = QLabel(tr('coupling_stats', 0))
        self.stats_label.setStyleSheet("color: #4CAF50; font-weight: bold; font-size: 14px;")
        layout.addWidget(self.stats_label)

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

        btn_layout = QHBoxLayout()
        self.delete_btn = QPushButton(tr('delete'))
        self.delete_btn.setStyleSheet(_danger_btn_style())
        self.delete_btn.setEnabled(False)
        self.delete_btn.clicked.connect(self._on_delete_coupling)
        btn_layout.addWidget(self.delete_btn)

        self.clear_all_btn = QPushButton(tr('btn_clear_all'))
        self.clear_all_btn.setStyleSheet(_secondary_btn_style())
        self.clear_all_btn.clicked.connect(self._on_clear_all)
        btn_layout.addWidget(self.clear_all_btn)

        layout.addLayout(btn_layout)
        return panel

    def _create_form_panel(self):
        """创建右侧统一表单（新建 / 编辑共用）"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)

        self.form_group = QGroupBox(tr('panel_create_edit_coupling'))
        form_outer = QVBoxLayout(self.form_group)

        self.mode_label = QLabel()
        self.mode_label.setStyleSheet(
            f"color: {get_color('text_muted')}; font-size: 13px; padding-bottom: 6px;"
        )
        form_outer.addWidget(self.mode_label)

        form_layout = QFormLayout()
        self.source_combo = QComboBox()
        self.target_combo = QComboBox()
        self.type_combo = QComboBox()
        self.strength_spin = QDoubleSpinBox()
        self.delay_spin = QDoubleSpinBox()
        self.type_hint = QLabel()
        self.type_hint.setWordWrap(True)

        self.form_refs = self._add_coupling_form_rows(
            form_layout,
            self.source_combo,
            self.target_combo,
            self.type_combo,
            self.strength_spin,
            self.delay_spin,
            self.type_hint,
        )
        self._wire_type_dependent_fields(self.form_refs)
        form_outer.addLayout(form_layout)

        btn_row = QHBoxLayout()
        self.new_btn = QPushButton(tr('btn_new_coupling'))
        self.new_btn.setStyleSheet(_secondary_btn_style())
        self.new_btn.clicked.connect(self._on_new_coupling)
        btn_row.addWidget(self.new_btn)
        btn_row.addStretch()
        self.save_btn = QPushButton(tr('btn_save'))
        self.save_btn.setStyleSheet(_save_btn_style())
        self.save_btn.setMinimumHeight(36)
        self.save_btn.setAutoDefault(False)
        self.save_btn.clicked.connect(self._on_save_coupling)
        btn_row.addWidget(self.save_btn)
        form_outer.addLayout(btn_row)

        layout.addWidget(self.form_group)
        layout.addStretch()

        self._reset_form_to_create()
        return panel

    def _configure_type_combo(self, combo: QComboBox):
        combo.clear()
        combo.addItem(tr('coupling_linear'), 'linear')
        combo.addItem(tr('coupling_nonlinear'), 'nonlinear')
        combo.addItem(tr('coupling_delayed'), 'delayed')

    def _configure_strength_spin(self, spin: QDoubleSpinBox):
        spin.setRange(-100, 100)
        spin.setDecimals(3)
        spin.setSingleStep(0.1)

    def _configure_delay_spin(self, spin: QDoubleSpinBox):
        spin.setRange(0, 1)
        spin.setDecimals(4)
        spin.setSingleStep(0.001)
        spin.setSuffix(' s')

    def _add_coupling_form_rows(
        self,
        form: QFormLayout,
        source_combo: QComboBox,
        target_combo: QComboBox,
        type_combo: QComboBox,
        strength_spin: QDoubleSpinBox,
        delay_spin: QDoubleSpinBox,
        type_hint: QLabel,
    ):
        """表单字段"""
        self._configure_type_combo(type_combo)
        self._configure_strength_spin(strength_spin)
        self._configure_delay_spin(delay_spin)
        type_hint.setStyleSheet(
            f"color: {get_color('accent')}; font-size: 12px; padding: 0 0 8px 0;"
        )
        type_hint.setWordWrap(True)
        type_hint.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        type_hint.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        form.addRow(tr('label_source_patch'), source_combo)
        form.addRow(tr('label_target_patch'), target_combo)
        form.addRow(tr('label_type'), type_combo)
        form.addRow(type_hint)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        params_group = QGroupBox(tr('coupling_params_linear'))
        params_layout = QFormLayout(params_group)
        params_layout.addRow(tr('label_strength_linear'), strength_spin)
        params_layout.addRow(tr('label_delay'), delay_spin)
        form.addRow(params_group)

        return {
            'type_combo': type_combo,
            'type_hint': type_hint,
            'params_group': params_group,
            'strength_label': params_layout.labelForField(strength_spin),
            'delay_label': params_layout.labelForField(delay_spin),
            'strength_spin': strength_spin,
            'delay_spin': delay_spin,
        }

    def _wire_type_dependent_fields(self, form_refs: dict):
        type_combo = form_refs['type_combo']
        type_combo.currentIndexChanged.connect(
            lambda _index: self._update_type_dependent_fields(form_refs)
        )
        self._update_type_dependent_fields(form_refs)

    def _update_type_dependent_fields(self, form_refs: dict):
        type_combo = form_refs['type_combo']
        type_hint = form_refs['type_hint']
        params_group = form_refs['params_group']
        strength_label = form_refs['strength_label']
        delay_label = form_refs['delay_label']
        delay_spin = form_refs['delay_spin']

        coupling_type = type_combo.currentData() or CouplingModel.TYPE_LINEAR
        hints = {
            CouplingModel.TYPE_LINEAR: tr('coupling_type_hint_linear'),
            CouplingModel.TYPE_NONLINEAR: tr('coupling_type_hint_nonlinear'),
            CouplingModel.TYPE_DELAYED: tr('coupling_type_hint_delayed'),
        }
        param_titles = {
            CouplingModel.TYPE_LINEAR: tr('coupling_params_linear'),
            CouplingModel.TYPE_NONLINEAR: tr('coupling_params_nonlinear'),
            CouplingModel.TYPE_DELAYED: tr('coupling_params_delayed'),
        }
        strength_labels = {
            CouplingModel.TYPE_LINEAR: tr('label_strength_linear'),
            CouplingModel.TYPE_NONLINEAR: tr('label_strength_nonlinear'),
            CouplingModel.TYPE_DELAYED: tr('label_strength_delayed'),
        }

        type_hint.setText(hints.get(coupling_type, ''))
        type_hint.adjustSize()
        params_group.setTitle(param_titles.get(coupling_type, tr('coupling_params_linear')))
        strength_label.setText(strength_labels.get(coupling_type, tr('label_strength')))

        is_delayed = coupling_type == CouplingModel.TYPE_DELAYED
        delay_label.setVisible(is_delayed)
        delay_spin.setVisible(is_delayed)
        delay_spin.setEnabled(is_delayed)
        delay_spin.setToolTip('' if is_delayed else tr('coupling_delay_na'))

    def _set_combo_by_patch_id(self, combo: QComboBox, patch_id: str):
        index = combo.findData(patch_id)
        combo.setCurrentIndex(index if index >= 0 else -1)

    def _update_mode_label(self):
        if self.current_edit_id:
            self.mode_label.setText(tr('coupling_mode_edit', self.current_edit_id))
        else:
            self.mode_label.setText(tr('coupling_mode_create'))

    def _reset_form_to_create(self):
        """重置为新建模式"""
        self.current_edit_id = None
        self._populate_patch_combo(self.source_combo)
        self._populate_patch_combo(self.target_combo)
        self.source_combo.setEnabled(True)
        self.target_combo.setEnabled(True)
        self.source_combo.setCurrentIndex(0 if self.source_combo.count() else -1)
        self.target_combo.setCurrentIndex(
            1 if self.target_combo.count() > 1 else (0 if self.target_combo.count() else -1)
        )
        self.type_combo.setCurrentIndex(0)
        self.strength_spin.setValue(0.5)
        self.delay_spin.setValue(0.0)
        self._update_type_dependent_fields(self.form_refs)
        self._update_mode_label()

    def _load_coupling_into_form(self, coupling_id: str, coupling: CouplingModel):
        """加载选中耦合到表单（编辑模式）"""
        self.current_edit_id = coupling_id
        self._populate_patch_combo(self.source_combo)
        self._populate_patch_combo(self.target_combo)
        self._set_combo_by_patch_id(self.source_combo, coupling.source_patch_id)
        self._set_combo_by_patch_id(self.target_combo, coupling.target_patch_id)
        self.source_combo.setEnabled(False)
        self.target_combo.setEnabled(False)

        self.strength_spin.setValue(coupling.strength)
        self.delay_spin.setValue(coupling.delay)

        type_index = self.type_combo.findData(coupling.type)
        if type_index >= 0:
            self.type_combo.setCurrentIndex(type_index)
        self._update_type_dependent_fields(self.form_refs)
        self._update_mode_label()

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
        if select_id is None:
            select_id = self.current_edit_id

        self.coupling_list.blockSignals(True)
        self.coupling_list.clear()

        for coupling_id, coupling in self.coupling_models.items():
            source_patch = self.patches.get(coupling.source_patch_id)
            target_patch = self.patches.get(coupling.target_patch_id)

            source_name = source_patch.name if source_patch else coupling.source_patch_id
            target_name = target_patch.name if target_patch else coupling.target_patch_id

            type_text = tr(f'coupling_{coupling.type}')
            display_text = (
                f"{source_name} → {target_name}\n"
                f"  {type_text}, strength={coupling.strength:.3f}, delay={coupling.delay:.4f}s"
            )

            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, coupling_id)
            item.setToolTip(f"ID: {coupling_id}")
            self.coupling_list.addItem(item)
            if select_id and coupling_id == select_id:
                item.setSelected(True)
                self.coupling_list.setCurrentItem(item)

        self.coupling_list.blockSignals(False)

        count = len(self.coupling_models)
        self.stats_label.setText(tr('coupling_stats', count))

        if select_id and select_id in self.coupling_models:
            self._load_coupling_into_form(select_id, self.coupling_models[select_id])
            self.delete_btn.setEnabled(True)
        elif count == 0:
            self.coupling_list.clearSelection()
            self._reset_form_to_create()
            self.delete_btn.setEnabled(False)

    def _on_new_coupling(self):
        """切换到新建模式"""
        self.coupling_list.blockSignals(True)
        self.coupling_list.clearSelection()
        self.coupling_list.blockSignals(False)
        self.delete_btn.setEnabled(False)
        self._reset_form_to_create()

    def _on_coupling_selected(self):
        """选中列表项时加载到表单"""
        items = self.coupling_list.selectedItems()
        if not items:
            self.delete_btn.setEnabled(False)
            self._reset_form_to_create()
            return

        coupling_id = items[0].data(Qt.ItemDataRole.UserRole)
        coupling = self.coupling_models.get(coupling_id)
        if coupling:
            self.delete_btn.setEnabled(True)
            self._load_coupling_into_form(coupling_id, coupling)

    def _on_save_coupling(self):
        """保存：新建或更新"""
        if self.current_edit_id:
            self._save_existing_coupling()
        else:
            self._save_new_coupling()

    def _save_new_coupling(self):
        source_id = self.source_combo.currentData()
        target_id = self.target_combo.currentData()

        if not source_id or not target_id:
            QMessageBox.warning(self, tr('warning'), tr('msg_select_source_target'))
            return

        if source_id == target_id:
            QMessageBox.warning(self, tr('warning'), tr('msg_same_source_target'))
            return

        for coupling in self.coupling_models.values():
            if coupling.source_patch_id == source_id and coupling.target_patch_id == target_id:
                QMessageBox.warning(self, tr('warning'), tr('msg_coupling_exists'))
                return

        new_id = self.parent_simulator.patch_ops.add_coupling_model(
            source_patch_id=source_id,
            target_patch_id=target_id,
            type=self.type_combo.currentData(),
            strength=self.strength_spin.value(),
            delay=self.delay_spin.value(),
        )

        if new_id:
            logger.info(f"Created coupling: {new_id}")
            self.refresh_coupling_list(select_id=new_id)
            self.coupling_changed.emit()
            QMessageBox.information(self, tr('success'), tr('msg_coupling_created', new_id))

    def _save_existing_coupling(self):
        coupling_id = self.current_edit_id
        if self.parent_simulator.patch_ops.modify_coupling_model(
            coupling_id,
            strength=self.strength_spin.value(),
            delay=self.delay_spin.value(),
            type=self.type_combo.currentData(),
        ):
            logger.info(f"Updated coupling: {coupling_id}")
            self.refresh_coupling_list(select_id=coupling_id)
            self.coupling_changed.emit()
            QMessageBox.information(self, tr('success'), tr('msg_coupling_updated', coupling_id))

    def _on_delete_coupling(self):
        items = self.coupling_list.selectedItems()
        if not items:
            return

        coupling_id = items[0].data(Qt.ItemDataRole.UserRole)
        reply = QMessageBox.question(
            self, tr('confirm'),
            tr('msg_confirm_delete_coupling', coupling_id),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.parent_simulator.patch_ops.delete_coupling_model(coupling_id)
            self._on_new_coupling()
            self.refresh_coupling_list()
            self.coupling_changed.emit()
            logger.info(f"Deleted coupling: {coupling_id}")

    def _on_clear_all(self):
        if not self.coupling_models:
            return

        reply = QMessageBox.question(
            self, tr('confirm'),
            tr('msg_confirm_clear_couplings', len(self.coupling_models)),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.parent_simulator.patch_ops.clear_coupling_models()
            self._on_new_coupling()
            self.refresh_coupling_list()
            self.coupling_changed.emit()
            logger.info("Cleared all couplings")
