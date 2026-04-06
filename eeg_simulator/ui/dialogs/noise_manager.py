"""噪声管理对话框 - 支持每种噪声类型多个实例"""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGroupBox,
                             QPushButton, QLabel, QDoubleSpinBox, QListWidget,
                             QListWidgetItem, QFrame, QScrollArea, QWidget,
                             QComboBox, QFormLayout, QSplitter, QMessageBox)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from ...utils import tr
from ..themes import get_color


class NoiseInstance:
    """噪声实例"""
    def __init__(self, noise_type, name, amplitude=1.0, unit='μV', **kwargs):
        self.noise_type = noise_type
        self.name = name
        self.amplitude = amplitude
        self.unit = unit
        # 各种噪声类型的参数
        self.line_freq = kwargs.get('line_freq', None)  # 工频噪声频率
        self.cutoff_freq = kwargs.get('cutoff_freq', None)  # 截止频率
        self.exponent = kwargs.get('exponent', None)  # 1/f噪声指数
        self.heart_rate = kwargs.get('heart_rate', None)  # 心率(ECG)
        self.blink_rate = kwargs.get('blink_rate', None)  # 眨眼频率(EOG)
        self.id = id(self)  # 唯一标识


class NoiseManagerDialog(QDialog):
    """噪声管理对话框"""
    
    noise_config_changed = pyqtSignal(list)  # 噪声配置改变信号
    
    def __init__(self, existing_configs=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr('dlg_noise_manager_title'))
        self.setMinimumSize(700, 600)
        
        # 噪声实例列表
        self.noise_instances = []
        
        self.init_ui()
        
        # 加载已有配置
        if existing_configs:
            self.load_existing_configs(existing_configs)
    
    def init_ui(self):
        """初始化UI"""
        main_layout = QHBoxLayout(self)
        main_layout.setSpacing(15)
        
        # 左侧：已添加的噪声列表
        left_panel = self._create_list_panel()
        main_layout.addWidget(left_panel, 1)
        
        # 右侧：添加新噪声
        right_panel = self._create_add_panel()
        main_layout.addWidget(right_panel, 1)
    
    def _create_list_panel(self):
        """创建左侧列表面板"""
        panel = QGroupBox(tr('panel_active_noises'))
        layout = QVBoxLayout(panel)
        
        # 统计信息
        self.stats_label = QLabel(tr('label_noise_count', 0))
        from ..themes import get_color
        self.stats_label.setStyleSheet(f"color: {get_color('text_muted')}; font-size: 11px;")
        layout.addWidget(self.stats_label)
        
        # 噪声实例列表
        self.noise_list = QListWidget()
        self.noise_list.setAlternatingRowColors(False)
        self.noise_list.setStyleSheet(f"""
            QListWidget {{
                background-color: {get_color('bg_input')};
                color: {get_color('text_main')};
                border: 1px solid {get_color('border')};
                border-radius: 4px;
            }}
            QListWidget::item {{
                padding: 8px;
                border-bottom: 1px solid {get_color('border')};
            }}
            QListWidget::item:selected {{
                background-color: {get_color('accent')};
                color: {get_color('text_inverse')};
            }}
            QListWidget::item:hover {{
                background-color: {get_color('bg_hover')};
            }}
        """)
        self.noise_list.itemClicked.connect(self.on_item_selected)
        layout.addWidget(self.noise_list)
        
        # 操作按钮
        btn_layout = QHBoxLayout()
        
        remove_btn = QPushButton(tr('btn_remove_noise'))
        remove_btn.setObjectName("StopBtn")
        remove_btn.clicked.connect(self.remove_selected_noise)
        btn_layout.addWidget(remove_btn)
        
        clear_btn = QPushButton(tr('btn_clear_all'))
        clear_btn.setObjectName("StopBtn")
        clear_btn.clicked.connect(self.clear_all_noises)
        btn_layout.addWidget(clear_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        # 说明
        hint = QLabel(tr('hint_noise_list'))
        hint.setStyleSheet(f"color: {get_color('text_muted')}; font-size: 10px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        
        return panel
    
    def _create_add_panel(self):
        """创建右侧添加面板"""
        panel = QGroupBox(tr('panel_add_noise'))
        layout = QVBoxLayout(panel)
        
        # 噪声类型选择
        type_group = QGroupBox(tr('label_noise_type'))
        type_layout = QVBoxLayout(type_group)
        
        self.noise_type_combo = QComboBox()
        self.noise_type_combo.addItem(tr('noise_white'), 'white')
        self.noise_type_combo.addItem(tr('noise_pink'), 'pink')
        self.noise_type_combo.addItem(tr('noise_1f'), '1f')
        self.noise_type_combo.addItem(tr('noise_brown'), 'brown')
        self.noise_type_combo.addItem(tr('noise_line'), 'line')
        self.noise_type_combo.addItem(tr('noise_eog'), 'eog')
        self.noise_type_combo.addItem(tr('noise_emg'), 'emg')
        self.noise_type_combo.addItem(tr('noise_ecg'), 'ecg')
        self.noise_type_combo.currentIndexChanged.connect(self.on_noise_type_changed)
        type_layout.addWidget(self.noise_type_combo)
        
        # 噪声描述
        self.desc_label = QLabel(tr('desc_white_noise'))
        self.desc_label.setStyleSheet(f"color: {get_color('text_muted')}; font-size: 10px;")
        self.desc_label.setWordWrap(True)
        type_layout.addWidget(self.desc_label)
        
        layout.addWidget(type_group)
        
        # 参数设置
        params_group = QGroupBox(tr('label_noise_params'))
        self.params_stack = QWidget()
        self.params_layout = QFormLayout(self.params_stack)
        self.params_layout.setContentsMargins(0, 0, 0, 0)
        
        # 幅度（所有噪声类型通用）
        self.amp_spin = QDoubleSpinBox()
        self.amp_spin.setRange(0, 10000)
        self.amp_spin.setDecimals(2)
        self.amp_spin.setValue(1.0)
        self.amp_spin.setSuffix(" μV")
        self.params_layout.addRow(tr('label_amplitude'), self.amp_spin)
        
        # 工频频率
        self.line_freq_combo = QComboBox()
        self.line_freq_combo.addItem("50 Hz", 50)
        self.line_freq_combo.addItem("60 Hz", 60)
        self.params_layout.addRow(tr('label_line_frequency'), self.line_freq_combo)
        
        # 截止频率（白噪声、EOG、EMG、ECG）
        self.cutoff_freq_spin = QDoubleSpinBox()
        self.cutoff_freq_spin.setRange(0.1, 1000)
        self.cutoff_freq_spin.setDecimals(1)
        self.cutoff_freq_spin.setValue(100.0)
        self.cutoff_freq_spin.setSuffix(" Hz")
        self.params_layout.addRow(tr('label_cutoff_freq'), self.cutoff_freq_spin)
        
        # 指数（1/f噪声）
        self.exponent_spin = QDoubleSpinBox()
        self.exponent_spin.setRange(0.1, 3.0)
        self.exponent_spin.setDecimals(2)
        self.exponent_spin.setValue(1.0)
        self.params_layout.addRow(tr('label_exponent'), self.exponent_spin)
        
        # 心率（ECG）
        self.heart_rate_spin = QDoubleSpinBox()
        self.heart_rate_spin.setRange(30, 200)
        self.heart_rate_spin.setDecimals(0)
        self.heart_rate_spin.setValue(60)
        self.heart_rate_spin.setSuffix(" BPM")
        self.params_layout.addRow(tr('label_heart_rate'), self.heart_rate_spin)
        
        # 眨眼频率（EOG）
        self.blink_rate_spin = QDoubleSpinBox()
        self.blink_rate_spin.setRange(0, 10)
        self.blink_rate_spin.setDecimals(1)
        self.blink_rate_spin.setValue(0.5)
        self.blink_rate_spin.setSuffix(" Hz")
        self.params_layout.addRow(tr('label_blink_rate'), self.blink_rate_spin)
        
        params_group_layout = QVBoxLayout(params_group)
        params_group_layout.addWidget(self.params_stack)
        
        # 设置默认值
        self.set_default_params('white')
        
        layout.addWidget(params_group)
        
        layout.addStretch()
        
        # 添加按钮
        self.add_btn = QPushButton(tr('btn_add_noise'))
        self.add_btn.setObjectName("PrimaryBtn")
        self.add_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {get_color('accent')};
                color: {get_color('text_inverse')};
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: bold;
                border: none;
            }}
            QPushButton:hover {{
                background-color: {get_color('accent_hover')};
            }}
        """)
        self.add_btn.clicked.connect(self.add_noise_instance)
        layout.addWidget(self.add_btn)
        
        # 底部按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton(tr('cancel'))
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {get_color('bg_input')};
                color: {get_color('text_main')};
                border: 1px solid {get_color('border')};
                border-radius: 6px;
                padding: 8px 16px;
            }}
            QPushButton:hover {{
                background-color: {get_color('border')};
            }}
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        ok_btn = QPushButton(tr('ok'))
        ok_btn.setObjectName("PrimaryBtn")
        ok_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {get_color('accent')};
                color: {get_color('text_inverse')};
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
                border: none;
            }}
            QPushButton:hover {{
                background-color: {get_color('accent_hover')};
            }}
        """)
        ok_btn.clicked.connect(self.on_ok)
        btn_layout.addWidget(ok_btn)
        
        layout.addLayout(btn_layout)
        
        return panel
    
    def on_noise_type_changed(self, index):
        """噪声类型改变"""
        noise_type = self.noise_type_combo.currentData()
        
        # 更新描述
        descriptions = {
            'white': tr('desc_white_noise'),
            'pink': tr('desc_pink_noise'),
            '1f': tr('desc_1f_noise'),
            'brown': tr('desc_brown_noise'),
            'line': tr('desc_line_noise'),
            'eog': tr('desc_eog_noise'),
            'emg': tr('desc_emg_noise'),
            'ecg': tr('desc_ecg_noise'),
        }
        self.desc_label.setText(descriptions.get(noise_type, ''))
        
        # 设置默认参数
        self.set_default_params(noise_type)
        
        # 根据噪声类型显示/隐藏参数
        self._update_param_visibility(noise_type)
    
    def _update_param_visibility(self, noise_type):
        """根据噪声类型更新参数可见性"""
        # 定义每种噪声类型的参数可见性
        param_visibility = {
            'white': ['amplitude', 'cutoff_freq'],
            'pink': ['amplitude'],
            '1f': ['amplitude', 'exponent'],
            'brown': ['amplitude'],
            'line': ['amplitude', 'line_freq'],
            'eog': ['amplitude', 'cutoff_freq', 'blink_rate'],
            'emg': ['amplitude', 'cutoff_freq'],
            'ecg': ['amplitude', 'heart_rate'],
        }
        
        visible_params = param_visibility.get(noise_type, ['amplitude'])
        
        # 隐藏所有参数标签和控件
        for i in range(self.params_layout.rowCount()):
            label = self.params_layout.itemAt(i, QFormLayout.ItemRole.LabelRole)
            field = self.params_layout.itemAt(i, QFormLayout.ItemRole.FieldRole)
            if label and label.widget():
                label.widget().setVisible(False)
            if field and field.widget():
                field.widget().setVisible(False)
        
        # 显示需要的参数
        param_map = {
            'amplitude': self.amp_spin,
            'line_freq': self.line_freq_combo,
            'cutoff_freq': self.cutoff_freq_spin,
            'exponent': self.exponent_spin,
            'heart_rate': self.heart_rate_spin,
            'blink_rate': self.blink_rate_spin,
        }
        
        for param_name in visible_params:
            widget = param_map.get(param_name)
            if widget:
                # 找到对应的标签
                for i in range(self.params_layout.rowCount()):
                    field = self.params_layout.itemAt(i, QFormLayout.ItemRole.FieldRole)
                    if field and field.widget() == widget:
                        label = self.params_layout.itemAt(i, QFormLayout.ItemRole.LabelRole)
                        if label and label.widget():
                            label.widget().setVisible(True)
                        widget.setVisible(True)
                        break
    
    def set_default_params(self, noise_type):
        """设置默认参数"""
        # 振幅默认值
        amp_defaults = {
            'white': 1.0,
            'pink': 1.0,
            '1f': 2.0,
            'brown': 5.0,
            'line': 10.0,
            'eog': 50.0,
            'emg': 20.0,
            'ecg': 30.0,
        }
        self.amp_spin.setValue(amp_defaults.get(noise_type, 1.0))
        
        # 其他参数默认值
        self.line_freq_combo.setCurrentIndex(0)  # 50Hz
        self.cutoff_freq_spin.setValue(100.0)
        self.exponent_spin.setValue(1.0)
        self.heart_rate_spin.setValue(60)
        self.blink_rate_spin.setValue(0.5)
    
    def load_existing_configs(self, configs):
        """加载已有的噪声配置"""
        for config in configs:
            instance = NoiseInstance(
                noise_type=config['type'],
                name=config['name'],
                amplitude=config['amplitude'],
                unit=config.get('unit', 'μV'),
                line_freq=config.get('line_freq', None),
                cutoff_freq=config.get('cutoff_freq', None),
                exponent=config.get('exponent', None),
                heart_rate=config.get('heart_rate', None),
                blink_rate=config.get('blink_rate', None),
            )
            self.noise_instances.append(instance)
        
        self.refresh_noise_list()
    
    def add_noise_instance(self):
        """添加噪声实例"""
        noise_type = self.noise_type_combo.currentData()
        name = self.noise_type_combo.currentText()
        amplitude = self.amp_spin.value()
        
        # 收集所有参数
        kwargs = {
            'cutoff_freq': self.cutoff_freq_spin.value() if self.cutoff_freq_spin.isVisible() else None,
            'exponent': self.exponent_spin.value() if self.exponent_spin.isVisible() else None,
            'line_freq': self.line_freq_combo.currentData() if self.line_freq_combo.isVisible() else None,
            'heart_rate': self.heart_rate_spin.value() if self.heart_rate_spin.isVisible() else None,
            'blink_rate': self.blink_rate_spin.value() if self.blink_rate_spin.isVisible() else None,
        }
        
        # 移除None值
        kwargs = {k: v for k, v in kwargs.items() if v is not None}
        
        instance = NoiseInstance(noise_type, name, amplitude, 'μV', **kwargs)
        self.noise_instances.append(instance)
        
        self.refresh_noise_list()
    
    def refresh_noise_list(self):
        """刷新噪声列表"""
        self.noise_list.clear()
        
        for i, inst in enumerate(self.noise_instances):
            # 收集参数信息
            params = []
            if inst.line_freq is not None:
                params.append(f"{inst.line_freq}Hz")
            if inst.cutoff_freq is not None:
                params.append(f"cutoff={inst.cutoff_freq:.1f}Hz")
            if inst.exponent is not None:
                params.append(f"exp={inst.exponent:.2f}")
            if inst.heart_rate is not None:
                params.append(f"HR={inst.heart_rate:.0f}bpm")
            if inst.blink_rate is not None:
                params.append(f"blink={inst.blink_rate:.1f}Hz")
            
            param_info = f" ({', '.join(params)})" if params else ""
            text = f"#{i+1} {inst.name} | {inst.amplitude:.2f}{inst.unit}{param_info}"
            
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, inst.id)
            self.noise_list.addItem(item)
            # 设置提示，鼠标悬停时显示完整信息
            item.setToolTip(text)
        
        # 更新统计
        self.stats_label.setText(tr('label_noise_count', len(self.noise_instances)))
    
    def on_item_selected(self, item):
        """选中列表项 - 将噪声信息显示到右侧面板"""
        # 获取选中的实例ID
        instance_id = item.data(Qt.ItemDataRole.UserRole)
        
        # 查找对应的噪声实例
        selected_instance = None
        for inst in self.noise_instances:
            if inst.id == instance_id:
                selected_instance = inst
                break
        
        if selected_instance is None:
            return
        
        # 更新右侧面板以显示选中的噪声信息
        self._load_instance_to_panel(selected_instance)
    
    def _load_instance_to_panel(self, instance):
        """将噪声实例加载到右侧面板"""
        # 设置噪声类型
        index = self.noise_type_combo.findData(instance.noise_type)
        if index >= 0:
            self.noise_type_combo.setCurrentIndex(index)
        
        # 设置幅度
        self.amp_spin.setValue(instance.amplitude)
        
        # 设置其他参数
        if instance.line_freq is not None:
            line_index = self.line_freq_combo.findData(instance.line_freq)
            if line_index >= 0:
                self.line_freq_combo.setCurrentIndex(line_index)
        
        if instance.cutoff_freq is not None:
            self.cutoff_freq_spin.setValue(instance.cutoff_freq)
        
        if instance.exponent is not None:
            self.exponent_spin.setValue(instance.exponent)
        
        if instance.heart_rate is not None:
            self.heart_rate_spin.setValue(instance.heart_rate)
        
        if instance.blink_rate is not None:
            self.blink_rate_spin.setValue(instance.blink_rate)
        
        # 更新参数可见性
        self._update_param_visibility(instance.noise_type)
        
        # 更新描述
        descriptions = {
            'white': tr('desc_white_noise'),
            'pink': tr('desc_pink_noise'),
            '1f': tr('desc_1f_noise'),
            'brown': tr('desc_brown_noise'),
            'line': tr('desc_line_noise'),
            'eog': tr('desc_eog_noise'),
            'emg': tr('desc_emg_noise'),
            'ecg': tr('desc_ecg_noise'),
        }
        self.desc_label.setText(descriptions.get(instance.noise_type, ''))
    
    def remove_selected_noise(self):
        """删除选中的噪声"""
        current_row = self.noise_list.currentRow()
        if current_row >= 0 and current_row < len(self.noise_instances):
            self.noise_instances.pop(current_row)
            self.refresh_noise_list()
    
    def clear_all_noises(self):
        """清空所有噪声"""
        if self.noise_instances:
            reply = QMessageBox.question(
                self, tr('confirm'),
                tr('msg_confirm_clear_noises', len(self.noise_instances)),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.noise_instances.clear()
                self.refresh_noise_list()
    
    def on_ok(self):
        """确认按钮"""
        # 转换为字典列表
        configs = []
        for inst in self.noise_instances:
            config = {
                'type': inst.noise_type,
                'name': inst.name,
                'amplitude': inst.amplitude,
                'unit': inst.unit,
            }
            # 添加各种参数（如果不为None）
            if inst.line_freq:
                config['line_freq'] = inst.line_freq
            if inst.cutoff_freq:
                config['cutoff_freq'] = inst.cutoff_freq
            if inst.exponent:
                config['exponent'] = inst.exponent
            if inst.heart_rate:
                config['heart_rate'] = inst.heart_rate
            if inst.blink_rate:
                config['blink_rate'] = inst.blink_rate
            configs.append(config)
        
        self.noise_config_changed.emit(configs)
        self.accept()
    
    def get_noise_configs(self):
        """获取所有噪声配置"""
        configs = []
        for inst in self.noise_instances:
            config = {
                'type': inst.noise_type,
                'name': inst.name,
                'amplitude': inst.amplitude,
                'unit': inst.unit,
            }
            # 添加各种参数（如果不为None）
            if inst.line_freq:
                config['line_freq'] = inst.line_freq
            if inst.cutoff_freq:
                config['cutoff_freq'] = inst.cutoff_freq
            if inst.exponent:
                config['exponent'] = inst.exponent
            if inst.heart_rate:
                config['heart_rate'] = inst.heart_rate
            if inst.blink_rate:
                config['blink_rate'] = inst.blink_rate
            configs.append(config)
        return configs
