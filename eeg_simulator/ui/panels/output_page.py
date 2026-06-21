"""输出设置页面 - NavigationView 布局"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
                             QLabel, QComboBox, QDoubleSpinBox, QLineEdit,
                             QPushButton, QFrame)
from PyQt6.QtCore import Qt

from ..themes import get_color


def get_primary_btn_style():
    """获取主按钮样式"""
    return f"""
        QPushButton {{
            background-color: {get_color('accent')};
            color: {get_color('text_inverse')};
            border: none;
            border-radius: 6px;
            padding: 8px 16px;
            font-weight: bold;
            min-height: 36px;
        }}
        QPushButton:hover {{
            background-color: {get_color('accent_hover')};
        }}
    """
from ..widgets.navigation_view import NavigationPage
from ...utils import tr


class OutputPage(NavigationPage):
    """输出设置页面"""
    
    def __init__(self, parent_simulator, parent=None):
        self.parent_simulator = parent_simulator
        super().__init__(
            title=tr('nav_output'),
            subtitle=tr('nav_output_subtitle'),
            parent=parent
        )
        
        self.output_dir = None
        self._filename = ''
        self._device_name = 'EEGSimulator'
        self._setup_content()
    
    def _setup_content(self):
        """设置页面内容"""
        layout = self.get_content_layout()
        
        # ========== 采样率设置 ==========
        self.sr_group = QGroupBox(tr('label_sampling_rate'))
        sr_layout = QVBoxLayout(self.sr_group)
        
        sr_input_layout = QHBoxLayout()
        self.sr_label = QLabel(tr('label_sampling_rate'))
        sr_input_layout.addWidget(self.sr_label)
        
        self.sr_spin = QDoubleSpinBox()
        self.sr_spin.setRange(100, 10000)
        self.sr_spin.setValue(self.parent_simulator.sampling_rate)
        self.sr_spin.setSuffix(' Hz')
        self.sr_spin.valueChanged.connect(self._on_sr_changed)
        sr_input_layout.addWidget(self.sr_spin)
        sr_layout.addLayout(sr_input_layout)
        
        layout.addWidget(self.sr_group)
        
        # ========== 输出格式设置 ==========
        self.format_group = QGroupBox(tr('label_output_format'))
        format_layout = QVBoxLayout(self.format_group)
        
        self.output_combo = QComboBox()
        self.output_combo.addItem('LSL (Lab Streaming Layer)', 'lsl')
        self.output_combo.addItem('EDF (European Data Format)', 'edf')
        self.output_combo.addItem('FIFF (MNE format)', 'fif')
        self.output_combo.currentIndexChanged.connect(self._on_output_format_changed)
        format_layout.addWidget(self.output_combo)
        
        # 输出配置区域
        self.output_config_widget = QWidget()
        self.output_config_layout = QVBoxLayout(self.output_config_widget)
        self.output_config_layout.setContentsMargins(0, 0, 0, 0)
        format_layout.addWidget(self.output_config_widget)
        
        self._init_output_config_ui()
        
        layout.addWidget(self.format_group)
        
        # ========== 输出时长设置 ==========
        self.duration_group = QGroupBox(tr('label_output_duration'))
        duration_layout = QVBoxLayout(self.duration_group)
        
        duration_input_layout = QHBoxLayout()
        self.duration_label = QLabel(tr('label_output_duration'))
        duration_input_layout.addWidget(self.duration_label)
        
        self.duration_spin = QDoubleSpinBox()
        self.duration_spin.setRange(0, 3600)
        self.duration_spin.setDecimals(0)
        self.duration_spin.setSuffix(' s')
        self.duration_spin.setValue(0)
        self.duration_spin.setSpecialValueText(tr('duration_infinite'))
        duration_input_layout.addWidget(self.duration_spin)
        
        duration_layout.addLayout(duration_input_layout)
        layout.addWidget(self.duration_group)
        
        # ========== 仿真控制 ==========
        self.control_group = QGroupBox(tr('simulation_control'))
        control_layout = QVBoxLayout(self.control_group)
        
        # 状态显示
        self.status_frame = QFrame()
        self.status_frame.setStyleSheet(f"""
            background-color: {get_color('bg_input')};
            border-radius: 8px;
            border: 1px solid {get_color('border')};
        """)
        status_inner_layout = QVBoxLayout(self.status_frame)
        status_inner_layout.setContentsMargins(16, 12, 16, 12)
        
        self.status_label = QLabel(tr('status_ready'))
        self.status_label.setStyleSheet(f"font-weight: bold; color: {get_color('text_main')};")
        status_inner_layout.addWidget(self.status_label)
        
        self.time_label = QLabel("⏱️ 00:00:00")
        self.time_label.setStyleSheet(f"font-size: 16px; color: {get_color('accent')};")
        status_inner_layout.addWidget(self.time_label)
        
        control_layout.addWidget(self.status_frame)
        
        # 控制按钮
        btn_layout = QHBoxLayout()
        
        self.sim_control_btn = QPushButton(tr('btn_start_sim'))
        self.sim_control_btn.setStyleSheet(get_primary_btn_style())
        self.sim_control_btn.setMinimumHeight(48)
        self.sim_control_btn.clicked.connect(self._on_sim_control_clicked)
        btn_layout.addWidget(self.sim_control_btn)
        
        control_layout.addLayout(btn_layout)
        layout.addWidget(self.control_group)
        
        layout.addStretch()
    
    def _init_output_config_ui(self):
        """初始化输出配置UI"""
        self._sync_filename_from_ui()
        self._sync_device_name_from_ui()
        self._clear_output_config()
        
        output_format = self.output_combo.currentData()
        
        if output_format in ['edf', 'fif']:
            # 文件输出配置
            file_layout = QVBoxLayout()
            
            # 文件夹选择
            dir_layout = QHBoxLayout()
            self.output_dir_label = QLabel(tr('output_dir_not_set'))
            self.output_dir_label.setWordWrap(True)
            self.output_dir_label.setStyleSheet(f"color: {get_color('text_muted')}; font-size: 12px;")
            dir_layout.addWidget(self.output_dir_label, 1)
            
            self.select_dir_btn = QPushButton(tr('btn_select_dir'))
            self.select_dir_btn.clicked.connect(self._select_output_dir)
            dir_layout.addWidget(self.select_dir_btn)
            file_layout.addLayout(dir_layout)
            
            # 文件名
            name_layout = QHBoxLayout()
            self.filename_label = QLabel(tr('label_filename'))
            name_layout.addWidget(self.filename_label)
            self.filename_input = QLineEdit()
            self.filename_input.setPlaceholderText(tr('placeholder_filename'))
            self.filename_input.setText(self._filename)
            self.filename_input.textChanged.connect(
                lambda text: setattr(self, '_filename', text)
            )
            name_layout.addWidget(self.filename_input)
            file_layout.addLayout(name_layout)
            
            self.output_config_layout.addLayout(file_layout)
            if self.output_dir:
                display_path = (
                    self.output_dir if len(self.output_dir) < 30
                    else '...' + self.output_dir[-27:]
                )
                self.output_dir_label.setText(display_path)
                self.output_dir_label.setStyleSheet(
                    f"color: {get_color('text_main')}; font-size: 12px;"
                )
            
        elif output_format == 'lsl':
            # LSL输出配置
            lsl_layout = QVBoxLayout()
            self.device_name_label = QLabel(tr('label_device_name'))
            lsl_layout.addWidget(self.device_name_label)
            
            self.device_name_input = QLineEdit()
            self.device_name_input.setPlaceholderText(tr('placeholder_device_name'))
            self.device_name_input.setText(self._device_name)
            self.device_name_input.textChanged.connect(
                lambda text: setattr(self, '_device_name', text or 'EEGSimulator')
            )
            lsl_layout.addWidget(self.device_name_input)
            
            self.output_config_layout.addLayout(lsl_layout)
    
    def _clear_output_config(self):
        """清空输出配置区域"""
        for attr in (
            'filename_input', 'filename_label', 'output_dir_label',
            'select_dir_btn', 'device_name_input', 'device_name_label',
        ):
            if hasattr(self, attr):
                delattr(self, attr)

        while self.output_config_layout.count():
            item = self.output_config_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                while item.layout().count():
                    child = item.layout().takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()

    def _sync_filename_from_ui(self):
        widget = getattr(self, 'filename_input', None)
        if widget is not None:
            try:
                self._filename = widget.text()
            except RuntimeError:
                pass

    def _sync_device_name_from_ui(self):
        widget = getattr(self, 'device_name_input', None)
        if widget is not None:
            try:
                self._device_name = widget.text() or 'EEGSimulator'
            except RuntimeError:
                pass
    
    def _on_output_format_changed(self, index):
        """输出格式改变"""
        self._init_output_config_ui()
        if hasattr(self.parent_simulator, '_update_status_bar'):
            self.parent_simulator._update_status_bar()
    
    def _select_output_dir(self):
        """选择输出文件夹"""
        from PyQt6.QtWidgets import QFileDialog
        
        dir_path = QFileDialog.getExistingDirectory(self, tr('dlg_select_output_dir'), "")
        if dir_path:
            self.output_dir = dir_path
            display_path = dir_path if len(dir_path) < 30 else '...' + dir_path[-27:]
            self.output_dir_label.setText(display_path)
            self.output_dir_label.setStyleSheet(f"color: {get_color('text_main')}; font-size: 12px;")
    
    def _on_sr_changed(self, value):
        """采样率改变"""
        if hasattr(self.parent_simulator, '_on_sr_changed_from_page'):
            self.parent_simulator._on_sr_changed_from_page(value)
        else:
            self.parent_simulator.sampling_rate = value
            if hasattr(self.parent_simulator, '_update_status_bar'):
                self.parent_simulator._update_status_bar()
    
    def _on_sim_control_clicked(self):
        """仿真控制按钮点击"""
        if self.parent_simulator.is_running:
            self.parent_simulator.stop_simulation()
            self.sim_control_btn.setText(tr('btn_start_sim'))
            self.sim_control_btn.setStyleSheet(get_primary_btn_style())
            self.status_label.setText(tr('status_stopped'))
            self.status_frame.setStyleSheet(f"""
                background-color: {get_color('bg_input')};
                border-radius: 8px;
                border: 1px solid {get_color('border')};
            """)
        else:
            self.parent_simulator.start_simulation()
            
            # 如果仿真启动成功，自动跳转到实时信号界面
            if self.parent_simulator.is_running:
                if hasattr(self.parent_simulator, 'nav_view'):
                    self.parent_simulator.nav_view.set_current_page('signal')
            
            self.sim_control_btn.setText(tr('btn_stop_sim'))
            self.sim_control_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {get_color('red')}20;
                    color: {get_color('red')};
                    border: 1px solid {get_color('red')}40;
                    border-radius: 6px;
                    padding: 8px 16px;
                    font-weight: bold;
                    min-height: 36px;
                }}
                QPushButton:hover {{
                    background-color: {get_color('red')}30;
                }}
            """)
            self.status_label.setText(tr('status_running'))
            self.status_frame.setStyleSheet(f"""
                background-color: {get_color('accent')}33;
                border-radius: 8px;
                border: 1px solid {get_color('accent')};
            """)
        # 刷新按钮样式
        self.sim_control_btn.style().unpolish(self.sim_control_btn)
        self.sim_control_btn.style().polish(self.sim_control_btn)
    
    def update_simulation_status(self, is_running, elapsed_time_str="00:00:00"):
        """更新仿真状态"""
        if is_running:
            self.sim_control_btn.setText(tr('btn_stop_sim'))
            self.sim_control_btn.setObjectName("StopBtn")
            self.status_label.setText(tr('status_running'))
            self.status_frame.setStyleSheet(f"""
                background-color: rgba(16, 185, 129, 0.2);
                border-radius: 8px;
                border: 1px solid {get_color('accent')};
            """)
        else:
            self.sim_control_btn.setText(tr('btn_start_sim'))
            self.sim_control_btn.setStyleSheet(get_primary_btn_style())
            self.status_label.setText(tr('status_ready'))
            self.status_frame.setStyleSheet(f"""
                background-color: rgba(100, 100, 100, 0.1);
                border-radius: 8px;
                border: 1px solid {get_color('border')};
            """)
        
        self.time_label.setText(f"⏱️ {elapsed_time_str}")
        
        # 刷新按钮样式
        self.sim_control_btn.style().unpolish(self.sim_control_btn)
        self.sim_control_btn.style().polish(self.sim_control_btn)
    
    def get_output_config(self):
        """获取输出配置"""
        self._sync_filename_from_ui()
        self._sync_device_name_from_ui()
        fmt = self.output_combo.currentData()
        return {
            'format': fmt,
            'sampling_rate': self.sr_spin.value(),
            'duration': self.duration_spin.value(),
            'output_dir': self.output_dir,
            'filename': self._filename if fmt in ('edf', 'fif') else '',
            'device_name': self._device_name if fmt == 'lsl' else 'EEGSimulator',
        }


    def update_theme(self):
        """更新主题颜色"""
        # 调用父类方法更新基础样式（标题、背景等）
        super().update_theme()
        
        from ..themes import get_color
        
        # 更新状态框架
        if hasattr(self, 'status_frame'):
            self.status_frame.setStyleSheet(f"""
                background-color: {get_color('bg_input')};
                border-radius: 8px;
                border: 1px solid {get_color('border')};
            """)
        
        # 更新状态标签
        if hasattr(self, 'status_label'):
            self.status_label.setStyleSheet(f"font-weight: bold; color: {get_color('text_main')};")
        
        # 更新时间标签
        if hasattr(self, 'time_label'):
            self.time_label.setStyleSheet(f"font-size: 16px; color: {get_color('accent')};")
        
        # 更新按钮样式
        if hasattr(self, 'sim_control_btn'):
            self.sim_control_btn.setStyleSheet(get_primary_btn_style())
        # 仅在按钮存在时更新（文件输出模式下）
        if hasattr(self, 'select_dir_btn'):
            self.select_dir_btn.setStyleSheet(get_primary_btn_style())
        
        # 更新输出目录标签（如果存在）
        if hasattr(self, 'output_dir_label'):
            # 根据是否已设置目录决定颜色
            if self.output_dir:
                self.output_dir_label.setStyleSheet(f"color: {get_color('text_main')}; font-size: 12px;")
            else:
                self.output_dir_label.setStyleSheet(f"color: {get_color('text_muted')}; font-size: 12px;")
    
    def update_texts(self):
        """更新界面文本"""
        # 更新标题
        self.set_title(tr('nav_output'))
        self.set_subtitle(tr('nav_output_subtitle'))
        
        # 更新组标题
        self.sr_group.setTitle(tr('label_sampling_rate'))
        self.format_group.setTitle(tr('label_output_format'))
        self.duration_group.setTitle(tr('label_output_duration'))
        self.control_group.setTitle(tr('simulation_control'))
        
        # 更新内联标签
        self.sr_label.setText(tr('label_sampling_rate'))
        self.duration_label.setText(tr('label_output_duration'))
        self.duration_spin.setSpecialValueText(tr('duration_infinite'))
        
        # 更新按钮文本
        if self.parent_simulator.is_running:
            self.sim_control_btn.setText(tr('btn_stop_sim'))
        else:
            self.sim_control_btn.setText(tr('btn_start_sim'))
        # 仅在按钮存在时更新（文件输出模式下）
        if hasattr(self, 'select_dir_btn'):
            self.select_dir_btn.setText(tr('btn_select_dir'))
        if hasattr(self, 'filename_label'):
            self.filename_label.setText(tr('label_filename'))
        if hasattr(self, 'filename_input'):
            self.filename_input.setPlaceholderText(tr('placeholder_filename'))
        if hasattr(self, 'device_name_label'):
            self.device_name_label.setText(tr('label_device_name'))
        if hasattr(self, 'device_name_input'):
            self.device_name_input.setPlaceholderText(tr('placeholder_device_name'))
        if hasattr(self, 'output_dir_label') and not self.output_dir:
            self.output_dir_label.setText(tr('output_dir_not_set'))
        
        # 更新状态标签
        if self.parent_simulator.is_running:
            self.status_label.setText(tr('status_running'))
        elif self.parent_simulator.simulation_time > 0:
            self.status_label.setText(tr('status_stopped'))
        else:
            self.status_label.setText(tr('status_ready'))
