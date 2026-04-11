"""脑电仿真器主类 - NavigationView 布局版本"""

import os
import sys
import time
from typing import Optional, Dict

import numpy as np
import mne

from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QFileDialog,
                             QMessageBox, QStatusBar, QFrame, QStackedWidget)
from PyQt6.QtCore import QTimer, Qt

from ..models import Patch, CouplingModel, PatchCouplingEngine, MNECouplingEngine, Dipole
from ..ui.styles import COLORS
from ..ui.themes import set_theme, generate_stylesheet, get_color
from ..ui.widgets import NavigationView
from ..ui.panels import SourceConfigPage, ElectrodeChannelsPage, OutputPage, SignalPage
from ..ui.menu import MainMenuBar
from ..ui.dialogs import NewProjectDialog
from ..utils import get_config, get_translator, tr, get_logger
from ..utils.project_manager import ProjectManager
from .signal_engine import SignalEngine
from .mne_simulator import MNESimulator

logger = get_logger(__name__)


class EEGSimulator(QMainWindow):
    """脑电仿真器主窗口 - NavigationView 布局"""

    def __init__(self):
        super().__init__()
        
        logger.info("=" * 60)
        logger.info("EEG Simulator (NavigationView) 初始化开始")
        logger.info(f"Python版本: {sys.version}")
        logger.info(f"MNE版本: {mne.__version__}")
        logger.info(f"NumPy版本: {np.__version__}")
        
        # 加载配置
        self.config = get_config()
        self.translator = get_translator()
        logger.info(f"配置加载完成，主题: {self.config.get_theme()}, 语言: {self.config.get_language()}")
        
        # 应用主题
        theme = self.config.get_theme()
        set_theme(theme)
        
        # 应用语言
        lang = self.config.get_language()
        self.translator.set_language(lang)
        
        self.setWindowTitle(tr('app_name'))
        self.setMinimumSize(1400, 900)
        logger.info(f"窗口设置完成，最小尺寸: 1400x900")

        # 数据存储
        self.patches = {}
        self._current_patch_id = None

        # MNE数据
        self.mne_info = None
        self.mne_fwd = None
        
        # BEM模型数据
        self.bem_model = None
        self.bem_conductivity = None
        self.subjects_dir = None
        
        # 项目数据
        self.current_project_path = None

        # 仿真参数
        self.sampling_rate = self.config.get('default_sampling_rate', 1000)
        self.simulation_time = 0.0
        self.is_running = False
        self.buffer_size = 5000
        self.samples_per_update = max(1, int(self.sampling_rate / 30))
        
        # 信号生成状态 - 用于保持相位连续性 {patch_id: {'phase': current_phase}}
        self._signal_states = {}
        
        # 热力图刷新控制
        self._last_heatmap_update_time = 0.0  # 上次热力图更新的仿真时间
        self.heatmap_refresh_interval = self.config.get('heatmap_refresh_interval', 1000) / 1000.0  # 转换为秒

        # 数据缓冲区
        self.time_buffer = np.zeros(self.buffer_size)
        self.signal_buffer = {}
        self.eeg_buffer = {}
        self.export_data = {}
        
        # 实时保存相关
        self.temp_files = {}
        self._samples_per_channel = {}
        
        # 实时滤波状态存储 {channel_name: {'hp': zi_hp, 'lp': zi_lp, 'notch': zi_notch}}
        self._filter_states = {}
        self._filter_coeffs = {}
        
        # 噪声状态存储 {channel_name: {noise_type: state_dict}}
        self._noise_states = {}

        # 选中的导联列表
        self.selected_channels = []
        
        # EEG通道名称映射 (标准10-20命名 -> MNE前向模型命名)
        self.eeg_channel_mapping = {}

        # ID计数器
        self._patch_counter = 0
        self._dipole_counter = 0
        
        # 噪声配置
        self.noise_configs = []

        # 耦合模型存储
        self._coupling_models: Dict[str, CouplingModel] = {}
        self._coupling_counter = 0
        self._coupling_engine = PatchCouplingEngine(self.sampling_rate)
        
        # MNE 耦合引擎
        self._mne_coupling_engine: Optional[MNECouplingEngine] = None
        self._use_mne_coupling = True
        
        # MNE 仿真器
        self._mne_simulator: Optional[MNESimulator] = None

        # 信号引擎
        self.signal_engine = SignalEngine(self.sampling_rate)

        self.init_ui()
        self.init_simulation()

    def init_ui(self):
        """初始化UI - NavigationView 布局"""
        # 设置菜单栏
        self.menu_bar = MainMenuBar(self, self.config)
        self.setMenuBar(self.menu_bar)
        
        # 连接菜单信号
        self.menu_bar.new_project_requested.connect(self._on_new_project)
        self.menu_bar.open_project_requested.connect(self._on_open_project)
        self.menu_bar.save_project_requested.connect(self._on_save_project)
        self.menu_bar.save_project_as_requested.connect(self._on_save_project_as)
        self.menu_bar.settings_changed.connect(self._on_settings_changed)
        self.menu_bar.language_changed.connect(self._on_language_changed)
        
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # ========== NavigationView 导航视图 ==========
        self.nav_view = NavigationView()
        
        # 创建各个页面
        self.source_page = SourceConfigPage(self)
        self.electrode_channels_page = ElectrodeChannelsPage(self)
        self.output_page = OutputPage(self)
        self.signal_page = SignalPage(self)
        
        # 连接滤波参数改变信号
        self.signal_page.filter_changed.connect(self._on_filter_changed)
        
        # 添加页面到导航视图
        self.nav_view.add_page('source', '🧠', tr('nav_source_config'), self.source_page)
        self.nav_view.add_page('electrode_channels', '📍', tr('nav_electrode_channels'), self.electrode_channels_page)
        self.nav_view.add_page('output', '⚙️', tr('nav_output'), self.output_page)
        self.nav_view.add_page('signal', '∿', tr('nav_signal'), self.signal_page)
        
        # 设置默认页面
        self.nav_view.set_current_page('source')
        
        main_layout.addWidget(self.nav_view, 1)
        
        # 定时器
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_simulation)
        
        # 状态栏
        self._create_status_bar()
        
        # 连接输出页面的采样率变化
        self.output_page.sr_spin.valueChanged.connect(self._on_sr_changed_from_page)
        
        # 初始化实时信号页面的热力图布局（与电极布局页面一致）
        self._sync_heatmap_montage()

    def _sync_heatmap_montage(self):
        """同步电极布局到实时信号页面的热力图"""
        try:
            montage = self.electrode_channels_page.get_current_montage()
            if montage:
                self.signal_page.set_montage(montage)
                logger.info(f"热力图布局已同步: {montage}")
        except Exception as e:
            logger.warning(f"同步热力图布局失败: {e}")

    def _create_status_bar(self):
        """创建状态栏"""
        self.status_bar = QStatusBar()
        self.status_bar.setStyleSheet(f"""
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
        self.setStatusBar(self.status_bar)
        
        # 项目名
        self.status_project = QLabel(f"📁 {tr('project_untitled')}")
        self.status_project.setStyleSheet(f"color: {COLORS['text_muted']};")
        self.status_bar.addWidget(self.status_project)
        
        # 分隔线
        for _ in range(4):
            sep = QFrame()
            sep.setFrameShape(QFrame.Shape.VLine)
            sep.setStyleSheet(f"color: {COLORS['border']};")
            self.status_bar.addWidget(sep)
        
        # 运行状态
        self.status_run = QLabel("○ " + tr('status_ready'))
        self.status_run.setStyleSheet(f"color: {COLORS['text_muted']};")
        self.status_bar.addWidget(self.status_run)
        
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet(f"color: {COLORS['border']};")
        self.status_bar.addWidget(sep)
        
        # 采样率
        self.status_sr = QLabel(f"🔊 {self.sampling_rate} Hz")
        self.status_sr.setStyleSheet(f"color: {COLORS['text_muted']};")
        self.status_bar.addWidget(self.status_sr)
        
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet(f"color: {COLORS['border']};")
        self.status_bar.addWidget(sep)
        
        # 导联数
        self.status_channels = QLabel("📡 0 ch")
        self.status_channels.setStyleSheet(f"color: {COLORS['text_muted']};")
        self.status_bar.addWidget(self.status_channels)
        
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet(f"color: {COLORS['border']};")
        self.status_bar.addWidget(sep)
        
        # 运行时间
        self.status_time = QLabel("⏱️ 00:00:00")
        self.status_time.setStyleSheet(f"color: {COLORS['text_muted']};")
        self.status_bar.addWidget(self.status_time)
        
        # 右侧固定内容
        self.status_output = QLabel("🌐 LSL")
        self.status_output.setStyleSheet(f"color: {COLORS['text_muted']};")
        self.status_bar.addPermanentWidget(self.status_output)
        
        # 更新时间计时器
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self._update_status_time)
        self._run_start_time = None

    def _update_status_bar(self):
        """更新状态栏"""
        if not hasattr(self, 'status_project'):
            return
        
        # 项目名
        if self.current_project_path:
            project_name = ProjectManager.get_project_name(self.current_project_path)
            self.status_project.setText(f"📁 {project_name}")
            self.status_project.setStyleSheet(f"color: {COLORS['text_main']};")
        else:
            self.status_project.setText(f"📁 {tr('project_untitled')}")
            self.status_project.setStyleSheet(f"color: {COLORS['text_muted']};")
        
        # 采样率
        if hasattr(self, 'status_sr'):
            self.status_sr.setText(f"🔊 {int(self.sampling_rate)} Hz")
        
        # 导联数
        if hasattr(self, 'status_channels'):
            channel_count = len(self.selected_channels)
            self.status_channels.setText(f"📡 {channel_count} ch")
        
        # 输出格式
        if hasattr(self, 'status_output') and hasattr(self.output_page, 'output_combo'):
            output_format = self.output_page.output_combo.currentData()
            if output_format == 'lsl':
                self.status_output.setText("🌐 LSL")
            elif output_format == 'edf':
                self.status_output.setText("📄 EDF")
            elif output_format == 'fif':
                self.status_output.setText("📄 FIFF")

    def _update_status_time(self):
        """更新运行时间"""
        if self._run_start_time and self.is_running:
            elapsed = int(self.simulation_time)
            hours = elapsed // 3600
            minutes = (elapsed % 3600) // 60
            seconds = elapsed % 60
            time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            self.status_time.setText(f"⏱️ {time_str}")
            self.output_page.time_label.setText(f"⏱️ {time_str}")

    def _on_sr_changed_from_page(self, value):
        """从输出页面改变采样率"""
        self.sampling_rate = value
        self.samples_per_update = max(1, int(self.sampling_rate / 30))
        self.signal_engine.sampling_rate = self.sampling_rate
        self._coupling_engine.set_sampling_rate(self.sampling_rate)
        self._update_status_bar()

    def _on_layout_changed(self, layout_key):
        """电极布局改变时"""
        logger.info(f"切换电极布局: {layout_key}")
        self.electrode_channels_page._update_channel_list()
        
        # 同步电极布局到实时信号页面的热力图
        montage = self.electrode_channels_page.get_current_montage()
        if montage:
            self.signal_page.set_montage(montage)
        self.signal_page.clear_heatmap()
        
        self._update_plot_curves()

    def _update_plot_curves(self):
        """更新图表曲线"""
        if self.is_running:
            self.stop_simulation()
            self.start_simulation()

    def init_simulation(self):
        """初始化仿真"""
        logger.info("仿真系统初始化")
        self._init_signal_buffers()
        self.electrode_channels_page._update_channel_list()
        logger.info("仿真系统初始化完成")

    def _init_signal_buffers(self):
        """初始化信号缓冲区"""
        self.signal_buffer.clear()
        for patch in self.patches.values():
            for dipole in patch.dipoles:
                self.signal_buffer[dipole.id] = np.zeros(self.buffer_size)

    def start_simulation(self):
        """开始仿真"""
        if self.is_running:
            return
        
        logger.info("=" * 40)
        logger.info("开始仿真")
        
        # 检查是否有选中的通道
        if not self.selected_channels:
            QMessageBox.warning(self, tr('warning'), tr('msg_no_channels_selected'))
            return
        
        # 更新状态
        self.is_running = True
        self.simulation_time = 0.0
        self._run_start_time = time.time()
        
        # 重置信号生成状态，确保从初始相位开始
        self._signal_states.clear()
        
        # 重置噪声状态
        self._noise_states.clear()
        
        # 更新UI
        self.status_run.setText("● " + tr('status_running'))
        self.status_run.setStyleSheet(f"color: {COLORS['accent']};")
        self.output_page.update_simulation_status(True)
        
        # 初始化图表
        self.signal_page.update_plots(self.selected_channels)
        
        # 初始化实时滤波状态
        self._init_filter_states()
        
        # 启动定时器
        update_interval = int(1000 / 30)  # 30fps
        self.timer.start(update_interval)
        self.status_timer.start(1000)
        
        logger.info(f"仿真参数: 采样率={self.sampling_rate}Hz")
        logger.info(f"选中通道: {self.selected_channels}")

    def stop_simulation(self):
        """停止仿真"""
        if not self.is_running:
            return
        
        logger.info("停止仿真")
        
        self.is_running = False
        self.timer.stop()
        self.status_timer.stop()
        
        # 清除信号生成状态，下次启动时重新初始化
        self._signal_states.clear()
        
        # 清除噪声状态
        self._noise_states.clear()
        
        # 更新UI
        self.status_run.setText("○ " + tr('status_stopped'))
        self.status_run.setStyleSheet(f"color: {COLORS['text_muted']};")
        self.output_page.update_simulation_status(False)

    def update_simulation(self):
        """更新仿真（定时器回调）"""
        if not self.is_running:
            return
        
        try:
            # 计算时间
            current_time = time.time()
            last_update = getattr(self, '_last_update_time', None)
            
            if last_update is None:
                elapsed = 1.0 / 30
            else:
                elapsed = current_time - last_update
            
            # 限制最大间隔
            elapsed = min(elapsed, 0.1)
            self._last_update_time = current_time
            
            # 计算样本数
            dt = 1.0 / self.sampling_rate
            
            # 计算样本数
            n_samples = int(elapsed * self.sampling_rate)
            if n_samples <= 0:
                return
            
            # 生成时间序列
            t_start = self.simulation_time
            t_end = t_start + n_samples * dt
            t = np.linspace(t_start, t_end, n_samples, endpoint=False)
            
            # 生成各Patch信号
            patch_signals = self._generate_patch_signals_batch(t, n_samples)
            
            # 应用耦合
            patch_signals = self._apply_coupling_batch(patch_signals, t, n_samples)
            
            # 投影到电极
            eeg_data = self._project_to_electrodes_batch(patch_signals, n_samples)
            
            # 添加噪声
            if self.noise_configs:
                eeg_data = self._add_noise_batch(eeg_data, t, n_samples)
            
            # 更新缓冲区
            self._update_buffers_batch(t, patch_signals, eeg_data, n_samples)
            
            # 更新图表
            self._update_plots()
            
            # 更新热力图（根据配置的时间间隔）
            if self.simulation_time - self._last_heatmap_update_time >= self.heatmap_refresh_interval:
                self._update_heatmap_from_simulation()
                self._last_heatmap_update_time = self.simulation_time
            
            # 更新时间
            self.simulation_time = t_end
            
        except Exception as e:
            logger.error(f"仿真更新失败: {e}", exc_info=True)
            self.stop_simulation()
            QMessageBox.critical(self, tr('error'), f"仿真失败: {str(e)}")

    def _generate_patch_signals_batch(self, t, n_samples):
        """批量生成Patch信号 - 保持相位连续性"""
        patch_signals = {}
        dt = 1.0 / self.sampling_rate
        
        for patch_id, patch in self.patches.items():
            # 初始化该patch的信号状态
            if patch_id not in self._signal_states:
                self._signal_states[patch_id] = {'phase': 0.0}
            
            state = self._signal_states[patch_id]
            
            # 使用连续性信号生成方法
            signals = self.signal_engine.generate_continuous_waveform(
                patch, n_samples, dt, state
            )
            patch_signals[patch_id] = signals
        return patch_signals

    def _apply_coupling_batch(self, patch_signals, t, n_samples):
        """批量应用耦合"""
        dt = 1.0 / self.sampling_rate
        coupled_signals = {}
        
        for i in range(n_samples):
            current_signals = {pid: signals[i] for pid, signals in patch_signals.items()}
            
            # 应用MNE耦合
            if self._use_mne_coupling and self._mne_coupling_engine is not None:
                current_signals = self._apply_mne_coupling(current_signals)
            elif self._coupling_models:
                current_time = self.simulation_time + i * dt
                current_signals = self._coupling_engine.compute_coupled_signals(current_signals, current_time)
            
            for pid, signal in current_signals.items():
                if pid not in coupled_signals:
                    coupled_signals[pid] = []
                coupled_signals[pid].append(signal)
        
        # 转换为numpy数组
        for pid in coupled_signals:
            coupled_signals[pid] = np.array(coupled_signals[pid])
        
        return coupled_signals

    def _apply_mne_coupling(self, patch_signals):
        """应用MNE耦合"""
        if self._mne_coupling_engine is None or not self._coupling_models:
            return patch_signals
        
        k = self.source_page.knn_spin.value() if hasattr(self, 'source_page') else 3
        decay_length = self.source_page.decay_spin.value() if hasattr(self, 'source_page') else 0.02
        
        coupled_signals = patch_signals.copy()
        
        for coupling_id, coupling in self._coupling_models.items():
            source_id = coupling.source_patch_id
            target_id = coupling.target_patch_id
            
            if source_id not in self.patches or target_id not in self.patches:
                continue
            
            source_patch = self.patches[source_id]
            target_patch = self.patches[target_id]
            
            source_dipoles = [{'hemi': d.hemi, 'vertno': d.vertno, 'position': d.position}
                            for d in source_patch.dipoles if hasattr(d, 'hemi') and hasattr(d, 'vertno')]
            target_dipoles = [{'hemi': d.hemi, 'vertno': d.vertno, 'position': d.position}
                            for d in target_patch.dipoles if hasattr(d, 'hemi') and hasattr(d, 'vertno')]
            
            if not source_dipoles or not target_dipoles:
                continue
            
            mne_coupling = self._mne_coupling_engine.compute_inter_patch_coupling(
                source_id, target_id,
                {'dipoles': source_dipoles},
                {'dipoles': target_dipoles},
                k=k, decay_length=decay_length
            )
            
            if target_id in coupled_signals and source_id in patch_signals:
                coupled_signals[target_id] += mne_coupling * patch_signals[source_id] * coupling.strength
        
        return coupled_signals

    def _project_to_electrodes_batch(self, patch_signals, n_samples):
        """批量投影到电极"""
        if self._mne_simulator is not None and self._mne_simulator.is_ready():
            patch_data = {}
            for patch_id, patch in self.patches.items():
                signals = patch_signals.get(patch_id, np.zeros(n_samples))
                patch_data[patch_id] = {
                    'signals': signals,
                    'dipoles': patch.dipoles,
                    'amplitude_scale': getattr(patch, 'amplitude_scale', 1e-9)
                }
            
            try:
                all_data = self._mne_simulator.simulate(patch_data, self.simulation_time, n_samples)
                # 只返回选中的通道，使用通道名称映射
                eeg_data = {}
                missing_channels = []  # 记录MNE投影失败的通道
                
                for ch_name in self.selected_channels:
                    # 检查是否有通道映射 (标准10-20命名 -> MNE前向模型命名)
                    mapped_name = self.eeg_channel_mapping.get(ch_name, ch_name)
                    
                    if mapped_name in all_data:
                        eeg_data[ch_name] = all_data[mapped_name]  # 使用标准命名作为key
                    elif ch_name in all_data:
                        # 通道名直接匹配（无需映射）
                        eeg_data[ch_name] = all_data[ch_name]
                    else:
                        # 记录未找到的通道，稍后使用简化投影
                        missing_channels.append(ch_name)
                        logger.debug(f"通道 {ch_name} (映射: {mapped_name}) 未在MNE前向模型中找到匹配，将使用简化投影")
                
                # 对未找到的通道使用简化投影
                if missing_channels:
                    simplified_data = self._simplified_projection_for_channels(
                        patch_signals, n_samples, missing_channels
                    )
                    eeg_data.update(simplified_data)
                
                # 调试：检查投影结果
                if eeg_data:
                    first_ch = list(eeg_data.keys())[0]
                    first_signal = eeg_data[first_ch]
                    logger.debug(f"MNE投影: 选中{len(self.selected_channels)}个, "
                               f"MNE匹配{len(eeg_data) - len(missing_channels)}个, "
                               f"简化投影{len(missing_channels)}个")
                else:
                    logger.warning(f"没有匹配的通道! 选中: {self.selected_channels}, "
                                 f"可用: {list(all_data.keys())[:10]}...")
                    # 完全回退到简化投影
                    return self._simplified_projection_batch(patch_signals, n_samples)
                
                return eeg_data
            except Exception as e:
                logger.error(f"MNE投影失败: {e}")
        
        # 简化投影
        return self._simplified_projection_batch(patch_signals, n_samples)

    def _simplified_projection_batch(self, patch_signals, n_samples):
        """简化投影 - 用于EEG通道"""
        n_channels = len(self.selected_channels) if self.selected_channels else 1
        n_sources = len(patch_signals)
        
        eeg_data = {}
        
        # 计算每个Patch的振幅缩放因子并应用到信号
        scaled_signals = {}
        for patch_id, signals in patch_signals.items():
            patch = self.patches.get(patch_id)
            if patch:
                amp_scale = getattr(patch, 'amplitude_scale', 1e-9)
                scaled_signals[patch_id] = signals * amp_scale
            else:
                scaled_signals[patch_id] = signals * 1e-9
        
        signal_array = np.array(list(scaled_signals.values())) if scaled_signals else np.zeros((1, n_samples))
        
        # 为每个通道生成投影权重
        # 根据通道位置分配不同的权重模式
        for i, ch in enumerate(self.selected_channels or ['Cz']):
            if n_sources > 0:
                # 根据通道名称生成不同的权重模式
                if ch in ['Cz', 'C3', 'C4']:
                    # 中央区域通道 - 较强信号
                    scale = 1.0
                elif ch in ['Fz', 'Pz', 'O1', 'O2']:
                    # 前后区域通道 - 中等信号
                    scale = 0.7
                else:
                    # 其他区域通道 - 较弱信号
                    scale = 0.5
                
                # 使用随机权重但保持一定相关性
                weights = np.random.randn(n_sources) * 0.1 + 0.5
                weights[i % n_sources] *= 2.0  # 强调某些源
                weights = weights / (np.sum(np.abs(weights)) + 1e-10) * scale
                
                # 投影信号并放大到 uV 级别 (信号已经是Am单位，需要转为uV)
                projected = np.dot(weights, signal_array) * 1e6  # 从 Am 转为 uV
                eeg_data[ch] = projected
            else:
                eeg_data[ch] = np.zeros(n_samples)
        
        logger.debug(f"简化投影: {len(eeg_data)}个通道, 首通道{list(eeg_data.keys())[0] if eeg_data else 'None'}="
                   f"[{np.min(list(eeg_data.values())[0]):.2e}, {np.max(list(eeg_data.values())[0]):.2e}]")
        
        return eeg_data

    def _simplified_projection_for_channels(self, patch_signals, n_samples, channel_names):
        """为指定通道使用简化投影
        
        当MNE投影无法找到某些通道时使用此方法作为回退
        
        Args:
            patch_signals: Patch信号字典
            n_samples: 样本数
            channel_names: 需要生成数据的通道名称列表
            
        Returns:
            dict: {通道名: 信号数组}
        """
        n_sources = len(patch_signals)
        eeg_data = {}
        
        # 计算每个Patch的振幅缩放因子并应用到信号
        scaled_signals = {}
        for patch_id, signals in patch_signals.items():
            patch = self.patches.get(patch_id)
            if patch:
                amp_scale = getattr(patch, 'amplitude_scale', 1e-9)
                scaled_signals[patch_id] = signals * amp_scale
            else:
                scaled_signals[patch_id] = signals * 1e-9
        
        signal_array = np.array(list(scaled_signals.values())) if scaled_signals else np.zeros((1, n_samples))
        
        # 预定义的通道权重模式（基于10-20系统位置）
        channel_weights = {
            # 前额
            'Fp1': 0.4, 'Fpz': 0.4, 'Fp2': 0.4,
            # 额叶
            'F7': 0.5, 'F3': 0.6, 'Fz': 0.7, 'F4': 0.6, 'F8': 0.5,
            'F1': 0.6, 'F2': 0.6, 'F5': 0.5, 'F6': 0.5,
            # 中央
            'T7': 0.5, 'C3': 0.8, 'Cz': 0.9, 'C4': 0.8, 'T8': 0.5,
            'C1': 0.8, 'C2': 0.8, 'C5': 0.7, 'C6': 0.7,
            # 顶叶
            'P7': 0.5, 'P3': 0.7, 'Pz': 0.8, 'P4': 0.7, 'P8': 0.5,
            'P1': 0.7, 'P2': 0.7, 'P5': 0.6, 'P6': 0.6,
            # 枕叶
            'O1': 0.5, 'Oz': 0.6, 'O2': 0.5, 'PO1': 0.5, 'PO2': 0.5,
            # 颞叶
            'FT7': 0.5, 'FT8': 0.5, 'TP7': 0.5, 'TP8': 0.5,
            # 中央顶叶
            'CP1': 0.7, 'CP2': 0.7, 'CP3': 0.7, 'CP4': 0.7, 'CP5': 0.6, 'CP6': 0.6, 'CPz': 0.8,
            # 额中央
            'FC1': 0.6, 'FC2': 0.6, 'FC3': 0.6, 'FC4': 0.6, 'FC5': 0.5, 'FC6': 0.5, 'FCz': 0.7,
            # 默认
            'default': 0.5
        }
        
        for i, ch in enumerate(channel_names):
            if n_sources > 0:
                # 获取该通道的权重系数
                scale = channel_weights.get(ch, channel_weights['default'])
                
                # 使用通道名生成确定性随机种子，保持同一通道的信号一致性
                seed = hash(ch) % 10000
                np.random.seed(seed)
                
                # 生成权重
                weights = np.random.randn(n_sources) * 0.1 + 0.5
                weights[i % n_sources] *= 1.5  # 轻微强调某些源
                weights = weights / (np.sum(np.abs(weights)) + 1e-10) * scale
                
                # 投影信号并放大到 uV 级别 (信号已经是Am单位，需要转为uV)
                projected = np.dot(weights, signal_array) * 1e6
                eeg_data[ch] = projected
                
                # 重置随机种子
                np.random.seed(None)
            else:
                eeg_data[ch] = np.zeros(n_samples)
        
        
        return eeg_data

    def _add_noise_batch(self, eeg_data, t, n_samples):
        """批量添加噪声 - 保持噪声连续性"""
        dt = 1.0 / self.sampling_rate
        
        for ch_name, signal in eeg_data.items():
            # 初始化该通道的噪声状态
            if ch_name not in self._noise_states:
                self._noise_states[ch_name] = {}
            
            total_noise = np.zeros(n_samples)
            for noise_config in self.noise_configs:
                noise_type = noise_config.get('type', 'white')
                
                # 为该噪声类型初始化状态
                if noise_type not in self._noise_states[ch_name]:
                    self._noise_states[ch_name][noise_type] = {}
                
                noise_state = self._noise_states[ch_name][noise_type]
                
                # 使用连续噪声生成
                noise = self.signal_engine.generate_continuous_noise(
                    noise_config, n_samples, dt, noise_state
                )
                total_noise += noise
            
            # 噪声单位是 μV，需要转换为 V（因为 eeg_data 是 V 级别）
            eeg_data[ch_name] = signal + total_noise * 1e-6
        return eeg_data

    def _update_buffers_batch(self, t, patch_signals, eeg_data, n_samples):
        """批量更新缓冲区 - 对新数据实时滤波后再存入"""
        # 更新时间缓冲区
        self.time_buffer = np.roll(self.time_buffer, -n_samples)
        self.time_buffer[-n_samples:] = t
        
        # 更新EEG缓冲区 - 只对新数据进行滤波
        for ch_name, signal in eeg_data.items():
            if ch_name not in self.eeg_buffer:
                self.eeg_buffer[ch_name] = np.zeros(self.buffer_size)
            
            # 转换为uV
            signal_uV = signal * 1e6
            
            # 只对新数据(n_samples个点)进行实时滤波
            if n_samples > 0:
                signal_uV = self._apply_filter(signal_uV, ch_name)
            
            # 存入缓冲区
            self.eeg_buffer[ch_name] = np.roll(self.eeg_buffer[ch_name], -n_samples)
            self.eeg_buffer[ch_name][-n_samples:] = signal_uV
        
        # 调试：检查缓冲区状态
        if self.selected_channels:
            first_ch = self.selected_channels[0]
            if first_ch in self.eeg_buffer:
                buf = self.eeg_buffer[first_ch]
                logger.debug(f"缓冲区更新: {first_ch}范围=[{np.min(buf):.2f}, {np.max(buf):.2f}]μV")

    def _update_plots(self):
        """更新波形图 - 缓冲区已包含滤波后的数据，直接显示"""
        time_window = self.signal_page.time_window_spin.value()
        n_samples = int(time_window * self.sampling_rate)
        
        t_display = self.time_buffer[-n_samples:] if len(self.time_buffer) >= n_samples else self.time_buffer
        
        for ch_name in self.selected_channels:
            if ch_name in self.eeg_buffer and ch_name in self.signal_page.plot_curves:
                # 缓冲区中已是滤波后的数据，直接显示
                data = self.eeg_buffer[ch_name][-n_samples:].copy()
                self.signal_page.plot_curves[ch_name].setData(t_display, data)
        
        # 更新FFT频谱
        self._update_fft_spectrum(n_samples)
    
    def _init_filter_states(self):
        """初始化实时滤波状态和系数
        
        根据当前滤波参数计算滤波器系数和初始状态，
        为每个通道创建独立的滤波状态。
        """
        from scipy import signal as sp_signal
        
        # 获取当前滤波参数
        filter_params = self.signal_page.get_filter_params()
        highpass = filter_params.get('highpass', 0)
        lowpass = filter_params.get('lowpass', 0)
        notch = filter_params.get('notch', False)
        
        # 获取滤波阶数配置
        hp_order = self.config.get('filter_highpass_order', 4)
        lp_order = self.config.get('filter_lowpass_order', 4)
        notch_order = self.config.get('filter_notch_order', 2)
        
        # 计算滤波器系数
        coeffs = {}
        
        # 高通滤波系数
        if highpass > 0:
            coeffs['hp'] = sp_signal.butter(hp_order, highpass, 'high', 
                                             fs=self.sampling_rate, output='sos')
        
        # 低通滤波系数
        if lowpass > 0 and lowpass < self.sampling_rate / 2:
            coeffs['lp'] = sp_signal.butter(lp_order, lowpass, 'low', 
                                             fs=self.sampling_rate, output='sos')
        
        # 陷波滤波系数
        if notch:
            q_value = 15 * notch_order
            b, a = sp_signal.iirnotch(50, q_value, fs=self.sampling_rate)
            coeffs['notch'] = (b, a)
        
        self._filter_coeffs = coeffs
        
        # 为每个通道初始化滤波状态
        self._filter_states = {}
        for ch_name in self.selected_channels:
            states = {}
            
            # SOS滤波初始状态 (高通)
            if 'hp' in coeffs:
                states['hp'] = sp_signal.sosfilt_zi(coeffs['hp']) * 0
            
            # SOS滤波初始状态 (低通)
            if 'lp' in coeffs:
                states['lp'] = sp_signal.sosfilt_zi(coeffs['lp']) * 0
            
            # 陷波滤波初始状态
            if 'notch' in coeffs:
                b, a = coeffs['notch']
                states['notch'] = sp_signal.lfilter_zi(b, a) * 0
            
            self._filter_states[ch_name] = states
        
        logger.info(f"实时滤波器已初始化: HP={highpass}Hz, LP={lowpass}Hz, Notch={notch}")
    
    def _apply_filter(self, data, ch_name):
        """应用实时有状态滤波
        
        使用保存的滤波器状态进行单向实时滤波，避免边界效应。
        
        Args:
            data: 输入信号数据（一维数组）
            ch_name: 通道名称，用于获取对应的滤波状态
        
        Returns:
            滤波后的数据
        """
        try:
            from scipy import signal as sp_signal
            
            # 如果没有初始化滤波状态，直接返回原数据
            if not self._filter_coeffs or ch_name not in self._filter_states:
                return data
            
            coeffs = self._filter_coeffs
            states = self._filter_states[ch_name]
            
            # 高通滤波 (有状态)
            if 'hp' in coeffs and 'hp' in states:
                data, states['hp'] = sp_signal.sosfilt(coeffs['hp'], data, zi=states['hp'])
            
            # 低通滤波 (有状态)
            if 'lp' in coeffs and 'lp' in states:
                data, states['lp'] = sp_signal.sosfilt(coeffs['lp'], data, zi=states['lp'])
            
            # 陷波滤波 (有状态)
            if 'notch' in coeffs and 'notch' in states:
                b, a = coeffs['notch']
                data, states['notch'] = sp_signal.lfilter(b, a, data, zi=states['notch'])
            
            return data
            
        except Exception as e:
            logger.warning(f"滤波应用失败 ({ch_name}): {e}")
            return data

    def _on_filter_changed(self):
        """滤波参数改变时重新初始化滤波器"""
        logger.info("滤波参数已改变，重新初始化滤波器")
        # 重新初始化滤波器状态和系数
        if self.is_running:
            self._init_filter_states()
        else:
            # 如果仿真未运行，清空滤波状态，下次启动时重新初始化
            self._filter_states.clear()
            self._filter_coeffs.clear()

    def _update_fft_spectrum(self, n_samples):
        """更新FFT频谱显示"""
        try:
            # 获取当前选中的FFT通道
            fft_channel = self.signal_page.fft_channel_combo.currentText()
            if not fft_channel or fft_channel not in self.eeg_buffer:
                return
            
            # 获取数据
            data = self.eeg_buffer[fft_channel][-n_samples:]
            if len(data) < 256:  # 需要足够的数据点
                return
            
            # 计算FFT
            from scipy import fft
            # 使用Hamming窗
            window = np.hamming(len(data))
            data_windowed = data * window
            
            # FFT计算
            fft_vals = fft.fft(data_windowed)
            fft_power = np.abs(fft_vals[:len(fft_vals)//2]) ** 2
            freqs = fft.fftfreq(len(data), 1/self.sampling_rate)[:len(fft_power)]
            
            # 显示0到采样率一半的频段（奈奎斯特频率）
            max_freq = self.sampling_rate / 2
            freq_mask = (freqs >= 0) & (freqs <= max_freq)
            freqs_display = freqs[freq_mask]
            power_display = fft_power[freq_mask]
            
            # 对数缩放以便更好显示
            power_display = np.log10(power_display + 1e-10)
            
            # 更新FFT曲线
            self.signal_page.update_fft(freqs_display, power_display)
            
        except Exception as e:
            logger.debug(f"FFT更新失败: {e}")

    def _update_heatmap_from_simulation(self):
        """根据仿真结果更新热力图"""
        if not self.selected_channels:
            return
        
        # 计算当前各导联的信号幅值
        activities = []
        for ch_name in self.selected_channels:
            if ch_name in self.eeg_buffer:
                # 使用当前值的绝对值作为活动强度
                activity = np.abs(self.eeg_buffer[ch_name][-1])
                activities.append(activity)
            else:
                activities.append(0)
        
        # 归一化到 0-1 范围
        if activities:
            max_act = max(activities) if max(activities) > 0 else 1
            activities = [a / max_act for a in activities]
        
        # 更新热力图（通过signal_page）
        self.signal_page.update_heatmap(np.array(activities))

    def init_mne_coupling_engine(self, src, labels=None):
        """初始化MNE耦合引擎"""
        if src is None:
            logger.warning("无法初始化MNE耦合引擎: 源空间为空")
            return
        
        try:
            k = self.source_page.knn_spin.value() if hasattr(self, 'source_page') else 3
            decay_length = self.source_page.decay_spin.value() if hasattr(self, 'source_page') else 0.02
            
            self._mne_coupling_engine = MNECouplingEngine(
                src=src, labels=labels, sampling_rate=self.sampling_rate
            )
            logger.info("MNE耦合引擎初始化成功")
        except Exception as e:
            logger.error(f"MNE耦合引擎初始化失败: {e}")
            self._mne_coupling_engine = None
        
        if self.mne_fwd is not None:
            try:
                self._mne_simulator = MNESimulator(fwd=self.mne_fwd, src=src, sampling_rate=self.sampling_rate)
                logger.info("MNE仿真器初始化成功")
                # 更新通道映射
                self._update_eeg_channel_mapping(self.mne_fwd)
            except Exception as e:
                logger.error(f"MNE仿真器初始化失败: {e}")
                self._mne_simulator = None

    def load_mne_data(self, file_path):
        """加载MNE数据"""
        try:
            logger.info(f"加载MNE数据: {file_path}")
            
            if 'fwd' in file_path.lower():
                fwd = mne.read_forward_solution(file_path)
                self.mne_fwd = fwd
                self.mne_info = fwd['info']
                
                self._mne_simulator = MNESimulator(fwd)
                self.signal_page.set_montage_from_info(self.mne_info)
                self.electrode_channels_page._update_channel_list()
                
                # 更新通道映射（标准10-20命名 -> MNE前向模型命名）
                self._update_eeg_channel_mapping(fwd)
                
                logger.info(f"正向模型加载成功: {len(fwd['info']['ch_names'])} 通道")
            else:
                raw = mne.io.read_raw_fif(file_path, preload=True)
                self.mne_info = raw.info
                logger.info(f"原始数据加载成功: {len(raw.info['ch_names'])} 通道")
                
        except Exception as e:
            logger.error(f"MNE数据加载失败: {e}", exc_info=True)
            raise

    def _update_eeg_channel_mapping(self, fwd):
        """根据前向模型创建通道名称映射
        
        将标准10-20命名（如Cz, Pz等）映射到MNE前向模型的通道命名（如EEG 001等）
        同时添加直接名称匹配作为回退
        """
        try:
            import numpy as np
            from collections import defaultdict
            
            info = fwd['info']
            ch_names = info['ch_names']
            
            # 获取标准10-20 montage
            montage_1020 = mne.channels.make_standard_montage('standard_1020')
            montage_positions = montage_1020.get_positions()['ch_pos']
            
            # 创建反向映射: 标准命名 -> MNE通道
            mne_by_distance = defaultdict(list)  # std_name -> [(mne_ch, distance), ...]
            
            for i, mne_ch in enumerate(ch_names):
                loc = np.array(info['chs'][i]['loc'][:3])
                
                # 找到最近的标准电极
                min_dist = float('inf')
                closest_std = None
                
                for std_name, std_pos in montage_positions.items():
                    dist = np.linalg.norm(loc - std_pos)
                    if dist < min_dist:
                        min_dist = dist
                        closest_std = std_name
                
                if min_dist < 0.07 and closest_std:  # 7cm阈值
                    mne_by_distance[closest_std].append((mne_ch, min_dist))
            
            # 为每个标准命名选择距离最近的MNE通道
            self.eeg_channel_mapping = {}
            for std_name, candidates in mne_by_distance.items():
                best_match = min(candidates, key=lambda x: x[1])
                self.eeg_channel_mapping[std_name] = best_match[0]
            
            # 添加直接名称匹配：如果MNE通道名本身就是标准命名，直接映射
            for ch_name in ch_names:
                if ch_name in montage_positions and ch_name not in self.eeg_channel_mapping:
                    self.eeg_channel_mapping[ch_name] = ch_name
            
            logger.info(f"EEG通道映射创建成功: {len(self.eeg_channel_mapping)} 个通道")
            # 记录一些映射示例
            sample_items = list(self.eeg_channel_mapping.items())[:5]
            for std_name, mne_ch in sample_items:
                logger.debug(f"  {std_name} -> {mne_ch}")
                
        except Exception as e:
            logger.error(f"创建通道映射失败: {e}")
            self.eeg_channel_mapping = {}

    # ========== 项目管理 ==========
    
    def _on_new_project(self):
        """新建项目"""
        from datetime import datetime
        from pathlib import Path
        
        dialog = NewProjectDialog(parent=self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        
        project_info = dialog.get_project_info()
        project_name = project_info['name']
        
        default_dir = self.config.get('default_project_dir', str(Path.home() / 'EEGProjects'))
        Path(default_dir).mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        folder_name = f"{project_name}_{timestamp}"
        project_path = os.path.join(default_dir, folder_name)
        
        if ProjectManager.create_project(project_path, project_name):
            self.current_project_path = project_path
            self._clear_all_data()
            self._update_window_title()
            QMessageBox.information(self, tr('success'), tr('msg_project_created', project_name))

    def _on_open_project(self):
        """打开项目"""
        project_dir = QFileDialog.getExistingDirectory(self, tr('dlg_open_project'), "")
        if not project_dir:
            return
        
        if not ProjectManager.is_valid_project(project_dir):
            QMessageBox.warning(self, tr('error'), tr('msg_invalid_project'))
            return
        
        self._load_project_data(project_dir)

    def _on_save_project(self):
        """保存项目"""
        if not self.current_project_path:
            self._create_new_project_with_current_data()
        else:
            self._save_to_project(self.current_project_path)

    def _create_new_project_with_current_data(self):
        """创建新项目并保存当前数据"""
        from datetime import datetime
        from pathlib import Path
        
        dialog = NewProjectDialog(parent=self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        
        project_info = dialog.get_project_info()
        project_name = project_info['name']
        
        default_dir = self.config.get('default_project_dir', str(Path.home() / 'EEGProjects'))
        Path(default_dir).mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        folder_name = f"{project_name}_{timestamp}"
        project_path = os.path.join(default_dir, folder_name)
        
        if ProjectManager.create_project(project_path, project_name):
            self.current_project_path = project_path
            self._save_to_project(project_path)
            self._update_status_bar()

    def _on_save_project_as(self):
        """另存为"""
        project_dir = QFileDialog.getExistingDirectory(self, tr('dlg_save_project'), "")
        if not project_dir:
            return
        
        project_name = tr('project_untitled')
        if self.current_project_path:
            project_name = ProjectManager.get_project_name(self.current_project_path)
        
        project_path = os.path.join(project_dir, project_name)
        
        if not ProjectManager.is_valid_project(project_path):
            ProjectManager.create_project(project_path, project_name)
        
        self.current_project_path = project_path
        self._save_to_project(project_path)

    def _save_to_project(self, project_path):
        """保存数据到项目"""
        logger.info(f"开始保存项目到: {project_path}")
        
        patches_data = {patch_id: patch.to_dict() for patch_id, patch in self.patches.items()}
        couplings_data = {cid: c.to_dict() for cid, c in self._coupling_models.items()}
        
        # 获取 Source Space 信息
        src_info = {}
        if hasattr(self, 'source_page') and self.source_page:
            src_info = {
                "src_filename": self.source_page.src_combo.currentData() if hasattr(self.source_page, 'src_combo') else None,
                "subject": self.source_page.subject,
                "src_labels": self.source_page.src_labels,
                "label_source_map": self.source_page.label_source_map
            }
        
        project_data = {
            "patches": patches_data,
            "couplings": couplings_data,
            "noise": self.noise_configs,
            "bem": {"conductivity": self.bem_conductivity} if self.bem_conductivity else {},
            "config": {"sampling_rate": self.sampling_rate},
            "selected_channels": getattr(self, 'selected_channels', []),
            "source_space": src_info
        }
        
        if ProjectManager.save_project(project_path, project_data):
            self._update_window_title()
            logger.info(f"项目保存成功: {project_path}")
            QMessageBox.information(self, tr('success'), tr('msg_project_saved'))
        else:
            logger.error(f"项目保存失败: {project_path}")
            QMessageBox.critical(self, tr('error'), tr('msg_project_save_failed'))

    def _load_project_data(self, project_path):
        """加载项目数据"""
        logger.info(f"开始加载项目: {project_path}")
        
        data = ProjectManager.load_project(project_path)
        if data is None:
            QMessageBox.critical(self, tr('error'), tr('msg_project_load_failed'))
            return
        
        self.current_project_path = project_path
        self._clear_all_data()
        
        # 加载Patch
        patches_data = data.get("patches", {})
        if isinstance(patches_data, dict):
            for patch_id, p_data in patches_data.items():
                patch = Patch.from_dict(p_data)
                self.patches[patch_id] = patch
        
        # 加载耦合模型（兼容字典和列表格式）
        couplings_data = data.get("couplings", {})
        if isinstance(couplings_data, dict):
            for cid, c_data in couplings_data.items():
                try:
                    coupling = CouplingModel.from_dict(c_data)
                    self._coupling_models[cid] = coupling
                    self._coupling_engine.add_coupling(coupling)
                except Exception as e:
                    logger.warning(f"Failed to load coupling {cid}: {e}")
        elif isinstance(couplings_data, list):
            for c_data in couplings_data:
                try:
                    coupling = CouplingModel.from_dict(c_data)
                    if coupling.id:
                        self._coupling_models[coupling.id] = coupling
                        self._coupling_engine.add_coupling(coupling)
                except Exception as e:
                    logger.warning(f"Failed to load coupling: {e}")
        
        # 加载其他数据
        self.noise_configs = data.get("noise", [])
        self.bem_conductivity = data.get("bem", {}).get("conductivity")
        self.sampling_rate = data.get("config", {}).get("sampling_rate", 1000)
        self.selected_channels = data.get("selected_channels", [])
        
        # 加载 Source Space 信息
        src_info = data.get("source_space", {})
        if src_info and hasattr(self, 'source_page') and self.source_page:
            # 恢复 Source Space 选择
            src_filename = src_info.get("src_filename")
            if src_filename and hasattr(self.source_page, 'src_combo'):
                # 找到对应的索引并设置
                for i in range(self.source_page.src_combo.count()):
                    if self.source_page.src_combo.itemData(i) == src_filename:
                        self.source_page.src_combo.setCurrentIndex(i)
                        break
            # 恢复其他信息
            self.source_page.subject = src_info.get("subject")
            self.source_page.src_labels = src_info.get("src_labels", {'lh': {}, 'rh': {}})
            self.source_page.label_source_map = src_info.get("label_source_map", {'lh': {}, 'rh': {}})
            # 更新 Source Space 信息显示
            if hasattr(self.source_page, 'src_info_label'):
                if src_filename:
                    self.source_page.src_info_label.setText(f"Config: {src_filename}")
                    self.source_page.src_info_label.setStyleSheet(f"color: {get_color('accent')}; font-size: 12px;")
                else:
                    self.source_page.src_info_label.setText(tr('not_loaded'))
                    self.source_page.src_info_label.setStyleSheet(f"color: {get_color('text_muted')}; font-size: 12px;")
            # 尝试自动重新加载 Source Space
            if src_filename and self.source_page.subject:
                self._reload_source_space(src_filename, self.source_page.subject)
        
        self._init_signal_buffers()
        self._update_ui_from_data()
        self._update_window_title()
        self._update_status_bar()
        
        QMessageBox.information(self, tr('success'), 
            tr('msg_project_loaded', ProjectManager.get_project_name(project_path)))

    def _reload_source_space(self, src_filename, subject):
        """重新加载 Source Space（用于项目加载时）"""
        import mne
        import os
        
        try:
            data_path = mne.datasets.sample.data_path()
            subjects_dir = os.path.join(data_path, 'subjects')
            src_path = os.path.join(subjects_dir, subject, 'bem', src_filename)
            
            if os.path.exists(src_path):
                self.source_page.loaded_src = mne.read_source_spaces(src_path)
                self.subjects_dir = subjects_dir
                self.init_mne_coupling_engine(self.source_page.loaded_src, self.source_page.src_labels)
                logger.info(f"自动重新加载 Source Space: {src_filename}")
                
                # 尝试加载对应的前向模型
                fwd_mapping = {
                    'sample-oct-6-src.fif': 'sample_audvis-eeg-oct-6-fwd.fif',
                    'sample-all-src.fif': 'sample_audvis-eeg-oct-6-fwd.fif',
                    'sample-oct-6-orig-src.fif': 'sample_audvis-eeg-oct-6-fwd.fif',
                    'sample-fsaverage-ico-5-src.fif': 'sample_audvis-eeg-ico-5-fwd.fif',
                }
                fwd_filename = fwd_mapping.get(src_filename)
                if fwd_filename:
                    fwd_path = os.path.join(data_path, 'MEG', 'sample', fwd_filename)
                    if os.path.exists(fwd_path):
                        try:
                            self.load_mne_data(fwd_path)
                            logger.info(f"自动加载前向模型: {fwd_filename}")
                        except Exception as e:
                            logger.warning(f"自动加载前向模型失败: {e}")
            else:
                logger.warning(f"Source Space 文件不存在: {src_path}")
        except Exception as e:
            logger.warning(f"自动重新加载 Source Space 失败: {e}")

    def _clear_all_data(self):
        """清除所有数据"""
        logger.info("清除所有数据")
        self.patches.clear()
        self._current_patch_id = None
        self.signal_buffer.clear()
        self.noise_configs = []
        self._coupling_models.clear()
        self._coupling_engine.clear()
        self.bem_model = None
        self.bem_conductivity = None
        self._update_ui_from_data()

    def _update_ui_from_data(self):
        """从数据更新UI"""
        # 更新源配置页面
        if hasattr(self, 'source_page'):
            # 同步噪声配置
            if hasattr(self, 'noise_configs'):
                self.source_page.active_noise_configs = self.noise_configs
            self.source_page._update_patch_stats()
            self.source_page._update_coupling_stats()
            self.source_page._update_noise_stats()
        
        # 更新输出页面
        if hasattr(self, 'output_page'):
            self.output_page.sr_spin.setValue(self.sampling_rate)
        
        # 更新电极通道页面
        if hasattr(self, 'electrode_channels_page'):
            self.electrode_channels_page._update_channel_list()
            # 如果有选中的通道，更新选中状态
            if hasattr(self, 'selected_channels') and self.selected_channels:
                self.electrode_channels_page.set_selected_channels(self.selected_channels)

    def _update_window_title(self):
        """更新窗口标题"""
        if self.current_project_path:
            project_name = ProjectManager.get_project_name(self.current_project_path)
            self.setWindowTitle(f"{tr('app_name')} - {project_name}")
        else:
            self.setWindowTitle(tr('app_name'))

    def _on_settings_changed(self, settings):
        """设置改变"""
        # 应用日志级别
        if settings.get('log_level'):
            from ..utils import get_logger_manager
            get_logger_manager().set_console_level(settings['log_level'])
        
        # 应用主题
        if settings.get('theme'):
            self._apply_theme(settings['theme'])
        
        # 保存设置到配置
        if settings.get('language'):
            self.config.set('language', settings['language'])
        if settings.get('theme'):
            self.config.set('theme', settings['theme'])
        if settings.get('default_sampling_rate'):
            self.config.set('default_sampling_rate', settings['default_sampling_rate'])
        if settings.get('heatmap_refresh_interval') is not None:
            self.config.set('heatmap_refresh_interval', settings['heatmap_refresh_interval'])
            self.heatmap_refresh_interval = settings['heatmap_refresh_interval'] / 1000.0  # 转换为秒
        if settings.get('filter_highpass_order') is not None:
            self.config.set('filter_highpass_order', settings['filter_highpass_order'])
        if settings.get('filter_lowpass_order') is not None:
            self.config.set('filter_lowpass_order', settings['filter_lowpass_order'])
        if settings.get('filter_notch_order') is not None:
            self.config.set('filter_notch_order', settings['filter_notch_order'])

    def _on_language_changed(self, lang):
        """语言切换"""
        # 保存语言设置
        self.config.set_language(lang)
        
        # 应用语言
        self.translator.set_language(lang)
        
        # 更新窗口标题
        self._update_window_title()
        
        # 更新导航栏文本
        self.nav_view.update_texts({
            'source': tr('nav_source_config'),
            'electrode_channels': tr('nav_electrode_channels'),
            'signal': tr('nav_signal'),
            'output': tr('nav_output'),
        })
        
        # 更新菜单栏
        self._update_menu_texts()
        
        # 更新所有页面文本
        self.source_page.update_texts()
        self.electrode_channels_page.update_texts()
        self.signal_page.update_texts()
        self.output_page.update_texts()
        
        logger.info(f"语言已切换: {lang}")
    
    def _update_menu_texts(self):
        """更新菜单文本"""
        # 文件菜单
        self.menu_bar.file_menu.setTitle(tr('menu_file'))
        self.menu_bar.new_action.setText(tr('menu_new_project'))
        self.menu_bar.open_action.setText(tr('menu_open_project'))
        self.menu_bar.save_action.setText(tr('menu_save_project'))
        self.menu_bar.save_as_action.setText(tr('menu_save_project_as'))
        self.menu_bar.exit_action.setText(tr('menu_exit'))
        
        # 设置菜单
        self.menu_bar.settings_menu.setTitle(tr('menu_settings'))
        self.menu_bar.settings_action.setText(tr('menu_settings_general'))
        
        # 帮助菜单
        self.menu_bar.help_menu.setTitle(tr('menu_help'))
        self.menu_bar.docs_action.setText(tr('menu_docs'))
        self.menu_bar.about_action.setText(tr('menu_about'))
    
    def _apply_theme(self, theme_name):
        """应用主题"""
        from ..ui.themes import set_theme, generate_stylesheet
        from PyQt6.QtWidgets import QApplication
        
        # 保存主题设置
        self.config.set_theme(theme_name)
        
        # 应用主题
        set_theme(theme_name)
        
        # 生成新样式表
        new_stylesheet = generate_stylesheet()
        
        # 应用到整个应用程序
        app = QApplication.instance()
        if app:
            app.setStyleSheet(new_stylesheet)
        
        # 更新导航栏主题
        self.nav_view.update_theme()
        
        # 更新所有页面主题
        self.source_page.update_theme()
        self.electrode_channels_page.update_theme()
        self.signal_page.update_theme()
        self.output_page.update_theme()
        
        # 强制刷新所有页面以应用新主题
        for page in [self.source_page, self.electrode_channels_page, 
                     self.signal_page, self.output_page]:
            page.update()
        
        # 更新状态栏主题
        self._update_status_bar_theme()
        
        logger.info(f"主题已切换: {theme_name}")
    
    def _update_status_bar_theme(self):
        """更新状态栏主题"""
        from ..ui.themes import get_color
        bg_color = get_color('bg_card')
        text_color = get_color('text_main')
        text_muted = get_color('text_muted')
        border_color = get_color('border')
        
        # 更新状态栏样式
        self.status_bar.setStyleSheet(f"""
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
        for widget in [self.status_project, self.status_run, self.status_sr, 
                       self.status_channels, self.status_time, self.status_output]:
            widget.setStyleSheet(f"color: {text_muted};")

    # ========== Patch和Dipole管理 ==========
    
    def create_patch(self, position, orientation, radius=0.0, label_name=None, hemi=None, 
                     name=None, waveform_type='sin', waveform_params=None, vertno=None, src_idx=None,
                     anchor_dipole=None):
        """创建Patch
        
        Args:
            anchor_dipole: 可选，已存在的中心偶极子。如果提供，则直接使用该偶极子而不是创建新的。
        """
        self._patch_counter += 1
        patch_id = f"patch_{self._patch_counter}"
        
        patch = Patch(id=patch_id, label_name=label_name, hemi=hemi, name=name,
                     waveform_type=waveform_type, waveform_params=waveform_params)
        
        # 如果提供了已存在的中心偶极子，直接使用；否则创建新的
        if anchor_dipole is not None:
            patch.add_dipole(anchor_dipole)
            patch.set_anchor(anchor_dipole)
            logger.info(f"创建Patch: {patch_id}, 使用已有中心偶极子: {anchor_dipole.id}")
        else:
            self._dipole_counter += 1
            new_dipole = Dipole(id=f"dipole_{self._dipole_counter}", position=position,
                               orientation=orientation, hemi=hemi, vertno=vertno, src_idx=src_idx)
            patch.add_dipole(new_dipole)
            patch.set_anchor(new_dipole)
            self.signal_buffer[new_dipole.id] = np.zeros(self.buffer_size)
            logger.info(f"创建Patch: {patch_id}, 新建中心偶极子: {new_dipole.id}")
        
        patch.set_radius(radius)
        self.patches[patch_id] = patch
        self._current_patch_id = patch_id
        
        return patch_id

    def delete_patch(self, patch_id):
        """删除Patch"""
        if patch_id not in self.patches:
            return
        
        patch = self.patches[patch_id]
        for dipole in patch.dipoles:
            if dipole.id in self.signal_buffer:
                del self.signal_buffer[dipole.id]
        
        del self.patches[patch_id]
        if self._current_patch_id == patch_id:
            self._current_patch_id = None
        
        logger.info(f"删除Patch: {patch_id}")

    def modify_patch(self, patch_id, name=None, waveform_type=None, waveform_params=None, radius=None):
        """修改 Patch
        
        Args:
            patch_id: Patch ID
            name: 新名称（可选）
            waveform_type: 新波形类型（可选）
            waveform_params: 新波形参数（可选）
            radius: 新半径（可选）
        """
        if patch_id not in self.patches:
            return
        
        patch = self.patches[patch_id]
        if name is not None:
            patch.name = name
        if waveform_type is not None:
            patch.waveform_type = waveform_type
        if waveform_params is not None:
            patch.waveform_params = waveform_params
        if radius is not None:
            patch.radius = radius
        
        logger.info(f"修改Patch: {patch_id}")

    def create_dipole(self, position, orientation, hemi=None, vertno=None, src_idx=None):
        """创建偶极子（不放入任何 Patch，用于 PatchManager 中临时创建）
        
        Args:
            position: [x, y, z] 位置坐标，单位米，RAS坐标系
            orientation: [nx, ny, nz] 方向向量
            hemi: 半球标识 'lh'(左), 'rh'(右)，可选
            vertno: 顶点编号，可选
            src_idx: 源空间索引，可选
            
        Returns:
            Dipole: 创建的偶极子对象
        """
        self._dipole_counter += 1
        dipole_id = f"dipole_{self._dipole_counter}"
        
        from ..models import Dipole
        dipole = Dipole(
            id=dipole_id,
            position=position,
            orientation=orientation,
            hemi=hemi,
            vertno=vertno,
            src_idx=src_idx
        )
        
        logger.info(f"创建偶极子: {dipole_id}, 位置: ({position[0]:.4f}, {position[1]:.4f}, {position[2]:.4f})")
        return dipole

    def find_dipoles_in_radius(self, center_position, radius, src=None, label_source_map=None, hemi=None):
        """查找半径内的顶点"""
        nearby_vertices = []
        
        if src is None:
            src = getattr(self.source_page, 'loaded_src', None)
        
        if src is None:
            return nearby_vertices
        
        center_pos = np.array(center_position)
        
        for src_idx, s in enumerate(src):
            if s['type'] != 'surf':
                continue
            
            current_hemi = 'lh' if src_idx == 0 else 'rh'
            if hemi is not None and current_hemi != hemi:
                continue
            
            for vertno in s['vertno']:
                pos = s['rr'][vertno]
                dist = np.linalg.norm(pos - center_pos)
                
                if dist <= radius:
                    orientation = s['nn'][vertno] if 'nn' in s else [0, 0, 1]
                    nearby_vertices.append({
                        'vertno': vertno, 'position': pos.tolist(),
                        'orientation': orientation.tolist() if isinstance(orientation, np.ndarray) else list(orientation),
                        'hemi': current_hemi, 'src_idx': src_idx, 'distance': float(dist)
                    })
        
        nearby_vertices.sort(key=lambda x: x['distance'])
        return nearby_vertices

    # ========== 属性访问 ==========
    
    @property
    def coupling_models(self):
        """获取耦合模型字典"""
        return self._coupling_models
    
    @property
    def dipole_definitions(self):
        """获取所有偶极子（兼容旧代码）"""
        result = {}
        for patch in self.patches.values():
            for dipole in patch.dipoles:
                result[dipole.id] = dipole
        return result

    def set_noise_configs(self, configs):
        """设置噪声配置"""
        self.noise_configs = configs

    def add_coupling_model(self, source_patch_id, target_patch_id, type='linear', strength=0.5, delay=0):
        """添加耦合模型"""
        if source_patch_id not in self.patches or target_patch_id not in self.patches:
            return None
        if source_patch_id == target_patch_id:
            return None
        
        self._coupling_counter += 1
        coupling_id = f"coupling_{self._coupling_counter}"
        
        coupling = CouplingModel(id=coupling_id, source_patch_id=source_patch_id,
                                target_patch_id=target_patch_id, type=type,
                                strength=strength, delay=delay, sampling_rate=self.sampling_rate)
        
        self._coupling_models[coupling_id] = coupling
        self._coupling_engine.add_coupling(coupling)
        
        logger.info(f"创建耦合模型: {coupling_id}")
        return coupling_id

    def delete_coupling_model(self, coupling_id):
        """删除耦合模型"""
        if coupling_id in self._coupling_models:
            del self._coupling_models[coupling_id]
            self._coupling_engine.remove_coupling(coupling_id)
            logger.info(f"删除耦合模型: {coupling_id}")
