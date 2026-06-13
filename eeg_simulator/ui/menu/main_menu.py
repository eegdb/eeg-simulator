"""主菜单栏"""

from PyQt6.QtWidgets import (QMenuBar, QMenu, QMessageBox, QFileDialog,
                             QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
                             QPushButton, QWidget, QCheckBox, QSpinBox, QLineEdit)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QKeySequence, QAction

from ..styles import COLORS
from ...utils import tr, get_config, get_logger_manager


class SettingsDialog(QDialog):
    """设置对话框"""
    
    settings_changed = pyqtSignal(dict)
    
    def __init__(self, current_settings=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr('settings_title'))
        self.setMinimumSize(400, 300)
        
        self.settings = current_settings or {}
        
        layout = QVBoxLayout(self)
        
        # 语言设置
        lang_group = QWidget()
        lang_layout = QHBoxLayout(lang_group)
        lang_layout.addWidget(QLabel(tr('settings_language')))
        
        self.lang_combo = QComboBox()
        self.lang_combo.addItem("中文 (简体)", "zh_CN")
        self.lang_combo.addItem("English", "en")
        self.lang_combo.setCurrentIndex(0 if self.settings.get('language', 'zh_CN') == 'zh_CN' else 1)
        lang_layout.addWidget(self.lang_combo)
        lang_layout.addStretch()
        layout.addWidget(lang_group)
        
        # 主题设置
        theme_group = QWidget()
        theme_layout = QHBoxLayout(theme_group)
        theme_layout.addWidget(QLabel(tr('settings_theme')))
        
        self.theme_combo = QComboBox()
        self.theme_combo.addItem(tr('settings_dark_mode'), "dark")
        self.theme_combo.addItem(tr('settings_light_mode'), "light")
        current_theme = self.settings.get('theme', 'dark')
        self.theme_combo.setCurrentIndex(0 if current_theme == 'dark' else 1)
        theme_layout.addWidget(self.theme_combo)
        theme_layout.addStretch()
        layout.addWidget(theme_group)
        
        # 界面设置
        ui_group = QWidget()
        ui_layout = QVBoxLayout(ui_group)
        
        # 日志级别设置
        log_layout = QHBoxLayout()
        log_layout.addWidget(QLabel(tr('settings_log_level')))
        
        self.log_level_combo = QComboBox()
        self.log_level_combo.addItem(tr('settings_log_level_debug'), 'DEBUG')
        self.log_level_combo.addItem(tr('settings_log_level_info'), 'INFO')
        self.log_level_combo.addItem(tr('settings_log_level_warning'), 'WARNING')
        self.log_level_combo.addItem(tr('settings_log_level_error'), 'ERROR')
        
        # 默认 DEBUG，从设置中读取
        current_level = self.settings.get('log_level', 'DEBUG')
        level_index = {'DEBUG': 0, 'INFO': 1, 'WARNING': 2, 'ERROR': 3}.get(current_level, 0)
        self.log_level_combo.setCurrentIndex(level_index)
        
        log_layout.addWidget(self.log_level_combo)
        log_layout.addStretch()
        ui_layout.addLayout(log_layout)
        
        layout.addWidget(ui_group)
        
        # 仿真设置
        sim_group = QWidget()
        sim_layout = QVBoxLayout(sim_group)
        
        default_sr_layout = QHBoxLayout()
        default_sr_layout.addWidget(QLabel(tr('settings_default_sr')))
        self.default_sr = QSpinBox()
        self.default_sr.setRange(100, 10000)
        self.default_sr.setValue(self.settings.get('default_sampling_rate', 1000))
        self.default_sr.setSuffix(" Hz")
        default_sr_layout.addWidget(self.default_sr)
        default_sr_layout.addStretch()
        sim_layout.addLayout(default_sr_layout)
        
        # 热力图刷新频率设置
        heatmap_refresh_layout = QHBoxLayout()
        heatmap_refresh_layout.addWidget(QLabel(tr('settings_heatmap_refresh')))
        self.heatmap_refresh_spin = QSpinBox()
        self.heatmap_refresh_spin.setRange(50, 5000)  # 50ms 到 5s
        self.heatmap_refresh_spin.setValue(self.settings.get('heatmap_refresh_interval', 1000))
        self.heatmap_refresh_spin.setSuffix(" ms")
        self.heatmap_refresh_spin.setSingleStep(50)
        self.heatmap_refresh_spin.setToolTip(tr('settings_heatmap_refresh_tooltip'))
        heatmap_refresh_layout.addWidget(self.heatmap_refresh_spin)
        heatmap_refresh_layout.addStretch()
        sim_layout.addLayout(heatmap_refresh_layout)
        
        # 滤波阶数设置
        filter_order_layout = QHBoxLayout()
        filter_order_layout.addWidget(QLabel(tr('settings_filter_order')))
        
        self.filter_hp_order = QSpinBox()
        self.filter_hp_order.setRange(1, 10)
        self.filter_hp_order.setValue(self.settings.get('filter_highpass_order', 4))
        filter_order_layout.addWidget(QLabel(tr('settings_highpass_order')))
        filter_order_layout.addWidget(self.filter_hp_order)
        
        self.filter_lp_order = QSpinBox()
        self.filter_lp_order.setRange(1, 10)
        self.filter_lp_order.setValue(self.settings.get('filter_lowpass_order', 4))
        filter_order_layout.addWidget(QLabel(tr('settings_lowpass_order')))
        filter_order_layout.addWidget(self.filter_lp_order)
        
        self.filter_notch_order = QSpinBox()
        self.filter_notch_order.setRange(1, 10)
        self.filter_notch_order.setValue(self.settings.get('filter_notch_order', 2))
        filter_order_layout.addWidget(QLabel(tr('settings_notch_order')))
        filter_order_layout.addWidget(self.filter_notch_order)
        
        filter_order_layout.addStretch()
        sim_layout.addLayout(filter_order_layout)
        
        layout.addWidget(sim_group)
        
        # 项目设置
        project_group = QWidget()
        project_layout = QVBoxLayout(project_group)
        
        # 默认项目目录
        default_dir_layout = QHBoxLayout()
        default_dir_layout.addWidget(QLabel(tr('settings_default_project_dir')))
        
        self.default_dir_input = QLineEdit()
        self.default_dir_input.setText(self.settings.get('default_project_dir', ''))
        self.default_dir_input.setReadOnly(True)
        default_dir_layout.addWidget(self.default_dir_input, 1)
        
        browse_btn = QPushButton(tr('btn_browse'))
        browse_btn.clicked.connect(self._on_browse_dir)
        default_dir_layout.addWidget(browse_btn)
        
        project_layout.addLayout(default_dir_layout)
        layout.addWidget(project_group)
        
        layout.addStretch()
        
        # 按钮
        btn_layout = QHBoxLayout()
        
        save_btn = QPushButton(tr('save'))
        save_btn.setObjectName("PrimaryBtn")
        save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(save_btn)
        
        cancel_btn = QPushButton(tr('cancel'))
        cancel_btn.setObjectName("StopBtn")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        layout.addLayout(btn_layout)
    
    def _on_browse_dir(self):
        """浏览选择默认项目目录"""
        current_dir = self.default_dir_input.text()
        if not current_dir:
            current_dir = ""
        
        dir_path = QFileDialog.getExistingDirectory(
            self, tr('dlg_select_default_dir'), current_dir
        )
        if dir_path:
            self.default_dir_input.setText(dir_path)
    
    def _on_save(self):
        """保存设置"""
        self.settings = {
            'language': self.lang_combo.currentData(),
            'theme': self.theme_combo.currentData(),
            'dark_mode': self.theme_combo.currentData() == 'dark',
            'default_sampling_rate': self.default_sr.value(),
            'default_project_dir': self.default_dir_input.text(),
            'log_level': self.log_level_combo.currentData(),
            'heatmap_refresh_interval': self.heatmap_refresh_spin.value(),
            'filter_highpass_order': self.filter_hp_order.value(),
            'filter_lowpass_order': self.filter_lp_order.value(),
            'filter_notch_order': self.filter_notch_order.value(),
        }
        self.settings_changed.emit(self.settings)
        self.accept()


class MainMenuBar(QMenuBar):
    """主菜单栏"""
    
    # 信号
    new_project_requested = pyqtSignal()
    open_project_requested = pyqtSignal()
    save_project_requested = pyqtSignal()
    save_project_as_requested = pyqtSignal()
    settings_changed = pyqtSignal(dict)
    language_changed = pyqtSignal(str)
    about_requested = pyqtSignal()
    
    def __init__(self, parent=None, config=None):
        super().__init__(parent)
        
        self.config = config
        
        # 从配置管理器加载设置
        if config:
            self.settings = config.get_all()
        else:
            self.settings = {
                'language': 'zh_CN',
                'dark_mode': True,
                'animations': True,
                'default_sampling_rate': 1000,
                'log_level': 'DEBUG',
            }
        
        self._create_menus()
    
    def _create_menus(self):
        """创建菜单"""
        # 文件菜单
        self.file_menu = self.addMenu(tr('menu_file'))
        
        self.new_action = QAction(tr('menu_new_project'), self)
        self.new_action.setShortcut(QKeySequence.StandardKey.New)
        self.new_action.triggered.connect(self._on_new_project)
        self.file_menu.addAction(self.new_action)
        
        self.open_action = QAction(tr('menu_open_project'), self)
        self.open_action.setShortcut(QKeySequence.StandardKey.Open)
        self.open_action.triggered.connect(self._on_open_project)
        self.file_menu.addAction(self.open_action)
        
        self.save_action = QAction(tr('menu_save_project'), self)
        self.save_action.setShortcut(QKeySequence.StandardKey.Save)
        self.save_action.triggered.connect(self._on_save_project)
        self.file_menu.addAction(self.save_action)
        
        self.save_as_action = QAction(tr('menu_save_project_as'), self)
        self.save_as_action.setShortcut(QKeySequence.StandardKey.SaveAs)
        self.save_as_action.triggered.connect(self._on_save_project_as)
        self.file_menu.addAction(self.save_as_action)
        
        self.file_menu.addSeparator()
        
        self.exit_action = QAction(tr('menu_exit'), self)
        self.exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        self.exit_action.triggered.connect(self._on_exit)
        self.file_menu.addAction(self.exit_action)
        
        # 设置菜单
        self.settings_menu = self.addMenu(tr('menu_settings'))
        
        self.settings_action = QAction(tr('menu_settings_general'), self)
        self.settings_action.triggered.connect(self._on_settings)
        self.settings_menu.addAction(self.settings_action)
        
        # 帮助菜单
        self.help_menu = self.addMenu(tr('menu_help'))
        
        self.docs_action = QAction(tr('menu_docs'), self)
        self.docs_action.setShortcut(QKeySequence.StandardKey.HelpContents)
        self.docs_action.triggered.connect(self._on_docs)
        self.help_menu.addAction(self.docs_action)
        
        self.help_menu.addSeparator()
        
        self.about_action = QAction(tr('menu_about'), self)
        self.about_action.triggered.connect(self._on_about)
        self.help_menu.addAction(self.about_action)
    
    def _on_new_project(self):
        """新建项目"""
        self.new_project_requested.emit()
    
    def _on_open_project(self):
        """打开项目"""
        self.open_project_requested.emit()
    
    def _on_save_project(self):
        """保存项目"""
        self.save_project_requested.emit()
    
    def _on_save_project_as(self):
        """另存为"""
        self.save_project_as_requested.emit()
    
    def _on_exit(self):
        """退出"""
        if self.parent():
            self.parent().close()
    
    def _on_settings(self):
        """打开设置"""
        dialog = SettingsDialog(self.settings, self)
        dialog.settings_changed.connect(self._on_settings_changed)
        dialog.exec()
    
    def _on_settings_changed(self, settings):
        """设置改变"""
        # 如果语言改变，立即应用
        if settings.get('language') != getattr(self, '_last_language', None):
            self._on_language_changed(settings['language'])
            self._last_language = settings['language']
        
        # 如果日志级别改变，立即应用
        if settings.get('log_level'):
            log_manager = get_logger_manager()
            log_manager.set_console_level(settings['log_level'])
        
        self.settings = settings
        self.settings_changed.emit(settings)
    
    def _on_language_changed(self, lang):
        """语言切换"""
        from eeg_simulator.utils import get_translator
        
        self.settings['language'] = lang
        
        # 立即应用语言到翻译器
        translator = get_translator()
        translator.set_language(lang)
        
        self.language_changed.emit(lang)
    
    def _on_docs(self):
        """打开文档"""
        import webbrowser
        webbrowser.open("https://github.com/eegdb/eeg-simulator")
    
    def _on_about(self):
        """关于对话框"""
        QMessageBox.about(
            self, tr('dlg_about_title'),
            f"""<h2>EEG Simulator 0.1.0</h2>
            <p>{tr('app_name')}</p>
            <p>&copy; 2024 EEG Simulator Team</p>
            """
        )
    
    def update_settings(self, settings):
        """更新设置"""
        self.settings.update(settings)
