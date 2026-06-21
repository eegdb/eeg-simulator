"""UI 初始化、状态栏、主题与语言。"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QStatusBar,
)
from PyQt6.QtCore import QTimer

from ...ui.styles import COLORS
from ...ui.themes import generate_stylesheet, get_color, set_theme
from ...ui.widgets import NavigationView
from ...ui.panels import SourceConfigPage, ElectrodeChannelsPage, OutputPage, SignalPage
from ...ui.menu import MainMenuBar
from ...utils import tr, get_logger
from ...utils.project_manager import ProjectManager

logger = get_logger(__name__)


class SimulatorUI:
    """SimulatorUI 服务。"""

    def __init__(self, simulator):
        self._sim = simulator

    def init_ui(self):
        """初始化UI - NavigationView 布局"""
        # 设置菜单栏
        self._sim.menu_bar = MainMenuBar(self._sim, self._sim.config)
        self._sim.setMenuBar(self._sim.menu_bar)

        # 连接菜单信号
        self._sim.menu_bar.new_project_requested.connect(self._sim.project._on_new_project)
        self._sim.menu_bar.open_project_requested.connect(self._sim.project._on_open_project)
        self._sim.menu_bar.save_project_requested.connect(self._sim.project._on_save_project)
        self._sim.menu_bar.save_project_as_requested.connect(self._sim.project._on_save_project_as)
        self._sim.menu_bar.settings_changed.connect(self._on_settings_changed)
        self._sim.menu_bar.language_changed.connect(self._on_language_changed)

        # 创建中央部件
        central_widget = QWidget()
        self._sim.setCentralWidget(central_widget)

        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ========== NavigationView 导航视图 ==========
        self._sim.nav_view = NavigationView()

        # 创建各个页面
        self._sim.source_page = SourceConfigPage(self._sim)
        self._sim.electrode_channels_page = ElectrodeChannelsPage(self._sim)
        self._sim.output_page = OutputPage(self._sim)
        self._sim.signal_page = SignalPage(self._sim)

        # 连接滤波参数改变信号
        self._sim.signal_page.filter_changed.connect(self._sim.signal._on_filter_changed)
        self._sim.signal_page.time_window_spin.valueChanged.connect(self._sim.buffers._on_time_window_changed)

        # 添加页面到导航视图
        self._sim.nav_view.add_page('source', '🧠', tr('nav_source_config'), self._sim.source_page)
        self._sim.nav_view.add_page('electrode_channels', '📍', tr('nav_electrode_channels'), self._sim.electrode_channels_page)
        self._sim.nav_view.add_page('output', '⚙️', tr('nav_output'), self._sim.output_page)
        self._sim.nav_view.add_page('signal', '∿', tr('nav_signal'), self._sim.signal_page)

        # 设置默认页面
        self._sim.nav_view.set_current_page('source')

        main_layout.addWidget(self._sim.nav_view, 1)

        # 定时器
        self._sim.timer = QTimer()
        self._sim.timer.timeout.connect(self._sim.simulation.update_simulation)

        # 状态栏
        self._create_status_bar()

        # 连接输出页面的采样率变化
        self._sim.output_page.sr_spin.valueChanged.connect(self._sim.buffers._on_sr_changed_from_page)

        # 初始化实时信号页面的热力图布局（与源配置页 montage 一致）
        self._sim.source_page.sync_montage_to_electrode_page()
        self._sync_heatmap_montage()

    def _sync_heatmap_montage(self):
        """同步电极布局到实时信号页面的热力图"""
        try:
            montage = self._sim.electrode_channels_page.get_current_montage()
            if montage:
                self._sim.signal_page.set_montage(montage)
                key = self._sim.electrode_channels_page.get_montage_key()
                logger.info(f"热力图布局已同步: {key} ({len(montage.ch_names)} 通道)")
        except Exception as e:
            logger.warning(f"同步热力图布局失败: {e}")

    def _create_status_bar(self):
        """创建状态栏"""
        self._sim.status_bar = QStatusBar()
        self._sim.status_bar.setStyleSheet(f"""
            QStatusBar {{
                background-color: {COLORS['bg_card']};
                color: {COLORS['text_main']};
                border-top: 1px solid {COLORS['border']};
                padding: 4px 12px;
                font-size: 12px;
            }}
            QStatusBar::item {{
                border: none;
            }}
        """)
        self._sim.setStatusBar(self._sim.status_bar)

        # 项目名
        self._sim.status_project = QLabel(f"📁 {tr('project_untitled')}")
        self._sim.status_project.setStyleSheet(f"color: {COLORS['text_muted']};")
        self._sim.status_bar.addWidget(self._sim.status_project)

        # 分隔线
        for _ in range(4):
            sep = QFrame()
            sep.setFrameShape(QFrame.Shape.VLine)
            sep.setStyleSheet(f"color: {COLORS['border']};")
            self._sim.status_bar.addWidget(sep)

        # 运行状态
        self._sim.status_run = QLabel("○ " + tr('status_ready'))
        self._sim.status_run.setStyleSheet(f"color: {COLORS['text_muted']};")
        self._sim.status_bar.addWidget(self._sim.status_run)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet(f"color: {COLORS['border']};")
        self._sim.status_bar.addWidget(sep)

        # 采样率
        self._sim.status_sr = QLabel(f"🔊 {self._sim.sampling_rate} Hz")
        self._sim.status_sr.setStyleSheet(f"color: {COLORS['text_muted']};")
        self._sim.status_bar.addWidget(self._sim.status_sr)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet(f"color: {COLORS['border']};")
        self._sim.status_bar.addWidget(sep)

        # 导联数
        self._sim.status_channels = QLabel("📡 0 ch")
        self._sim.status_channels.setStyleSheet(f"color: {COLORS['text_muted']};")
        self._sim.status_bar.addWidget(self._sim.status_channels)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet(f"color: {COLORS['border']};")
        self._sim.status_bar.addWidget(sep)

        # 运行时间
        self._sim.status_time = QLabel("⏱️ 00:00:00")
        self._sim.status_time.setStyleSheet(f"color: {COLORS['text_muted']};")
        self._sim.status_bar.addWidget(self._sim.status_time)

        # 右侧固定内容
        self._sim.status_output = QLabel("🌐 LSL")
        self._sim.status_output.setStyleSheet(f"color: {COLORS['text_muted']};")
        self._sim.status_bar.addPermanentWidget(self._sim.status_output)

        # 更新时间计时器
        self._sim.status_timer = QTimer()
        self._sim.status_timer.timeout.connect(self._update_status_time)
        self._sim._run_start_time = None

    def _update_status_bar(self):
        """更新状态栏"""
        if not hasattr(self._sim, 'status_project'):
            return

        # 项目名
        if self._sim.current_project_path:
            project_name = ProjectManager.get_project_name(self._sim.current_project_path)
            self._sim.status_project.setText(f"📁 {project_name}")
            self._sim.status_project.setStyleSheet(f"color: {COLORS['text_main']};")
        else:
            self._sim.status_project.setText(f"📁 {tr('project_untitled')}")
            self._sim.status_project.setStyleSheet(f"color: {COLORS['text_muted']};")

        # 采样率
        if hasattr(self._sim, 'status_sr'):
            self._sim.status_sr.setText(f"🔊 {int(self._sim.sampling_rate)} Hz")

        # 导联数
        if hasattr(self._sim, 'status_channels'):
            channel_count = len(self._sim.selected_channels)
            self._sim.status_channels.setText(f"📡 {channel_count} ch")

        # 输出格式
        if hasattr(self._sim, 'status_output') and hasattr(self._sim.output_page, 'output_combo'):
            output_format = self._sim.output_page.output_combo.currentData()
            if output_format == 'lsl':
                self._sim.status_output.setText("🌐 LSL")
            elif output_format == 'edf':
                self._sim.status_output.setText("📄 EDF")
            elif output_format == 'fif':
                self._sim.status_output.setText("📄 FIFF")

    def _update_status_time(self):
        """更新运行时间"""
        if self._sim._run_start_time and self._sim.is_running:
            elapsed = int(self._sim.simulation_time)
            hours = elapsed // 3600
            minutes = (elapsed % 3600) // 60
            seconds = elapsed % 60
            time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            self._sim.status_time.setText(f"⏱️ {time_str}")
            self._sim.output_page.time_label.setText(f"⏱️ {time_str}")

    def _on_settings_changed(self, settings):
        """设置改变"""
        # 应用日志级别
        if settings.get('log_level'):
            from ...utils import get_logger_manager
            get_logger_manager().set_console_level(settings['log_level'])

        # 应用主题
        if settings.get('theme'):
            self._apply_theme(settings['theme'])

        # 保存设置到配置
        if settings.get('language'):
            self._sim.config.set('language', settings['language'])
        if settings.get('theme'):
            self._sim.config.set('theme', settings['theme'])
        if settings.get('default_sampling_rate'):
            self._sim.config.set('default_sampling_rate', settings['default_sampling_rate'])
        if settings.get('heatmap_refresh_interval') is not None:
            self._sim.config.set('heatmap_refresh_interval', settings['heatmap_refresh_interval'])
            self._sim.heatmap_refresh_interval = settings['heatmap_refresh_interval'] / 1000.0  # 转换为秒
        if settings.get('filter_highpass_order') is not None:
            self._sim.config.set('filter_highpass_order', settings['filter_highpass_order'])
        if settings.get('filter_lowpass_order') is not None:
            self._sim.config.set('filter_lowpass_order', settings['filter_lowpass_order'])
        if settings.get('filter_notch_order') is not None:
            self._sim.config.set('filter_notch_order', settings['filter_notch_order'])

    def _on_language_changed(self, lang):
        """语言切换"""
        # 保存语言设置
        self._sim.config.set_language(lang)

        # 应用语言
        self._sim.translator.set_language(lang)

        # 更新窗口标题
        self._sim.project._update_window_title()

        # 更新导航栏文本
        self._sim.nav_view.update_texts({
            'source': tr('nav_source_config'),
            'electrode_channels': tr('nav_electrode_channels'),
            'signal': tr('nav_signal'),
            'output': tr('nav_output'),
        })

        # 更新菜单栏
        self._update_menu_texts()

        # 更新所有页面文本
        self._sim.source_page.update_texts()
        self._sim.electrode_channels_page.update_texts()
        self._sim.signal_page.update_texts()
        self._sim.output_page.update_texts()

        # 更新状态栏
        self._update_status_bar()
        if self._sim.is_running:
            self._sim.status_run.setText("● " + tr('status_running'))
        elif self._sim.simulation_time > 0:
            self._sim.status_run.setText("○ " + tr('status_stopped'))
        else:
            self._sim.status_run.setText("○ " + tr('status_ready'))

        logger.info(f"语言已切换: {lang}")

    def _update_menu_texts(self):
        """更新菜单文本"""
        # 文件菜单
        self._sim.menu_bar.file_menu.setTitle(tr('menu_file'))
        self._sim.menu_bar.new_action.setText(tr('menu_new_project'))
        self._sim.menu_bar.open_action.setText(tr('menu_open_project'))
        self._sim.menu_bar.save_action.setText(tr('menu_save_project'))
        self._sim.menu_bar.save_as_action.setText(tr('menu_save_project_as'))
        self._sim.menu_bar.exit_action.setText(tr('menu_exit'))

        # 设置菜单
        self._sim.menu_bar.settings_menu.setTitle(tr('menu_settings'))
        self._sim.menu_bar.settings_action.setText(tr('menu_settings_general'))

        # 帮助菜单
        self._sim.menu_bar.help_menu.setTitle(tr('menu_help'))
        self._sim.menu_bar.docs_action.setText(tr('menu_docs'))
        self._sim.menu_bar.about_action.setText(tr('menu_about'))

    def _apply_theme(self, theme_name):
        """应用主题"""
        from PyQt6.QtWidgets import QApplication

        # 保存主题设置
        self._sim.config.set_theme(theme_name)

        # 应用主题
        set_theme(theme_name)

        # 生成新样式表
        new_stylesheet = generate_stylesheet()

        # 应用到整个应用程序
        app = QApplication.instance()
        if app:
            app.setStyleSheet(new_stylesheet)

        # 更新导航栏主题
        self._sim.nav_view.update_theme()

        # 更新所有页面主题
        self._sim.source_page.update_theme()
        self._sim.electrode_channels_page.update_theme()
        self._sim.signal_page.update_theme()
        self._sim.output_page.update_theme()

        # 强制刷新所有页面以应用新主题
        for page in [self._sim.source_page, self._sim.electrode_channels_page, 
                     self._sim.signal_page, self._sim.output_page]:
            page.update()

        # 更新状态栏主题
        self._update_status_bar_theme()

        logger.info(f"主题已切换: {theme_name}")

    def _update_status_bar_theme(self):
        """更新状态栏主题"""
        bg_color = get_color('bg_card')
        text_color = get_color('text_main')
        text_muted = get_color('text_muted')
        border_color = get_color('border')

        # 更新状态栏样式
        self._sim.status_bar.setStyleSheet(f"""
            QStatusBar {{
                background-color: {bg_color};
                color: {text_color};
                border-top: 1px solid {border_color};
                padding: 4px 12px;
                font-size: 12px;
            }}
            QStatusBar::item {{
                border: none;
            }}
        """)

        # 更新状态栏各标签颜色
        for widget in [self._sim.status_project, self._sim.status_run, self._sim.status_sr, 
                       self._sim.status_channels, self._sim.status_time, self._sim.status_output]:
            widget.setStyleSheet(f"color: {text_muted};")
