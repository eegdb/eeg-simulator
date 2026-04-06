"""实时信号页面 - NavigationView 布局"""

import pyqtgraph as pg
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
                             QLabel, QDoubleSpinBox, QCheckBox, QPushButton,
                             QFrame, QSizePolicy, QSplitter, QComboBox)
from PyQt6.QtCore import Qt, pyqtSignal

from ..themes import get_color
from ..widgets.navigation_view import NavigationPage
from ..widgets.head_layout import HeatmapOverlayWidget
from ...utils import tr


def configure_plot_for_zoom(plot):
    """配置 PlotItem 支持滚轮缩放，禁用拖动"""
    vb = plot.getViewBox()
    
    # 禁用默认鼠标交互
    vb.setMouseEnabled(x=False, y=False)
    
    # 保存原始 wheelEvent
    orig_wheel = vb.wheelEvent
    
    # 定义新的 wheelEvent
    def wheel_event(ev, axis=None):
        # 使用 delta() 而不是 angleDelta()
        delta = ev.delta()
        
        if delta != 0:
            # 获取当前 Y 轴范围
            y_min, y_max = vb.viewRange()[1]
            current_range = max(abs(y_min), abs(y_max))
            
            # delta > 0 (向上滚动) = 放大（范围变小）
            # delta < 0 (向下滚动) = 缩小（范围变大）
            scale_factor = 0.9 if delta > 0 else 1.1
            new_range = current_range * scale_factor
            new_range = max(1, new_range)  # 只限制最小值，不限制最大值
            
            # 以 0 为中心设置 Y 轴范围
            vb.setYRange(-new_range, new_range, padding=0)
            ev.accept()
        else:
            # 调用原始的 X 轴缩放
            orig_wheel(ev, axis)
    
    # 替换 wheelEvent
    vb.wheelEvent = wheel_event
    
    # 禁用拖动
    def drag_event(ev, axis=None):
        ev.ignore()
    vb.mouseDragEvent = drag_event


def create_zoomable_plot(plot_widget, row, col):
    """创建支持滚轮缩放的 PlotItem"""
    # 使用 GraphicsLayout.addPlot 创建 PlotItem
    plot = plot_widget.addPlot(row=row, col=col)
    
    # 配置滚轮缩放
    configure_plot_for_zoom(plot)
    
    return plot


class SignalPage(NavigationPage):
    """实时信号页面"""
    
    # 信号：滤波参数改变
    filter_changed = pyqtSignal()
    
    def __init__(self, parent_simulator, parent=None):
        self.parent_simulator = parent_simulator
        super().__init__(
            title=tr('nav_signal'),
            subtitle=tr('nav_signal_subtitle'),
            parent=parent
        )
        
        self.plot_items = {}
        self.plot_curves = {}
        
        self._setup_content()
    
    def _setup_content(self):
        """设置页面内容"""
        layout = self.get_content_layout()
        
        # ========== 滤波参数设置 ==========
        filter_group = QGroupBox(tr('filter_settings'))
        filter_layout = QHBoxLayout(filter_group)
        
        # 高通滤波
        filter_layout.addWidget(QLabel(tr('label_highpass')))
        self.highpass_spin = QDoubleSpinBox()
        self.highpass_spin.setRange(0, 100)
        self.highpass_spin.setValue(0.5)
        self.highpass_spin.setSuffix(' Hz')
        self.highpass_spin.setDecimals(1)
        filter_layout.addWidget(self.highpass_spin)
        
        # 低通滤波
        filter_layout.addWidget(QLabel(tr('label_lowpass')))
        self.lowpass_spin = QDoubleSpinBox()
        self.lowpass_spin.setRange(0, 500)
        self.lowpass_spin.setValue(100)
        self.lowpass_spin.setSuffix(' Hz')
        self.lowpass_spin.setDecimals(1)
        filter_layout.addWidget(self.lowpass_spin)
        
        # 工频滤波
        self.notch_cb = QCheckBox(tr('label_notch_filter'))
        self.notch_cb.setChecked(True)
        filter_layout.addWidget(self.notch_cb)
        
        filter_layout.addStretch()
        
        # 时间窗口
        filter_layout.addWidget(QLabel(tr('label_time_window')))
        self.time_window_spin = QDoubleSpinBox()
        self.time_window_spin.setRange(1, 60)
        self.time_window_spin.setValue(10)
        self.time_window_spin.setSuffix(' s')
        self.time_window_spin.setDecimals(0)
        filter_layout.addWidget(self.time_window_spin)
        
        layout.addWidget(filter_group)
        
        # 连接滤波参数改变信号
        self.highpass_spin.valueChanged.connect(self.filter_changed.emit)
        self.lowpass_spin.valueChanged.connect(self.filter_changed.emit)
        self.notch_cb.stateChanged.connect(self.filter_changed.emit)
        
        # ========== 波形显示区域 + 热力图 ==========
        self.viz_group = QGroupBox(tr('panel_realtime_signal'))
        viz_layout = QHBoxLayout(self.viz_group)
        viz_layout.setContentsMargins(8, 12, 8, 12)
        
        # 使用分割器：左侧波形图，右侧热力图
        viz_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 左侧：信号图
        self.plot_widget = pg.GraphicsLayoutWidget()
        self.plot_widget.setBackground(get_color('bg_card'))
        self.plot_widget.setMinimumHeight(400)
        self.plot_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        viz_splitter.addWidget(self.plot_widget)
        
        # 右侧：地形图 + FFT（固定宽度，不随窗口缩放）
        right_panel = QWidget()
        right_panel.setFixedWidth(280)  # 固定宽度
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)
        
        # 地形图（固定大小）
        self.heatmap_group = QGroupBox(tr('panel_head_layout'))
        self.heatmap_group.setFixedWidth(270)
        heatmap_layout = QVBoxLayout(self.heatmap_group)
        heatmap_layout.setContentsMargins(4, 4, 4, 4)
        heatmap_layout.setSpacing(0)
        
        self.heatmap_widget = HeatmapOverlayWidget()
        self.heatmap_widget.setFixedSize(250, 250)  # 固定大小
        heatmap_layout.addWidget(self.heatmap_widget, alignment=Qt.AlignmentFlag.AlignCenter)
        right_layout.addWidget(self.heatmap_group)
        
        # FFT 频谱图
        fft_group = QGroupBox("FFT Spectrum")
        fft_group.setFixedWidth(270)
        fft_layout = QVBoxLayout(fft_group)
        fft_layout.setContentsMargins(4, 4, 4, 4)
        fft_layout.setSpacing(4)
        
        # FFT 导联选择
        fft_select_layout = QHBoxLayout()
        fft_select_layout.addWidget(QLabel("Channel:"))
        self.fft_channel_combo = QComboBox()
        self.fft_channel_combo.setToolTip("Select channel for FFT analysis")
        fft_select_layout.addWidget(self.fft_channel_combo, 1)
        fft_layout.addLayout(fft_select_layout)
        
        # FFT 波形图
        self.fft_plot = pg.PlotWidget()
        self.fft_plot.setBackground(get_color('bg_card'))
        self.fft_plot.setMinimumHeight(150)
        self.fft_plot.setMaximumHeight(200)
        self.fft_plot.setLabel('bottom', 'Frequency (Hz)')
        self.fft_plot.setLabel('left', 'Power')
        self.fft_plot.showGrid(x=True, y=True, alpha=0.3)
        self.fft_curve = self.fft_plot.plot(pen=pg.mkPen(color=get_color('accent'), width=2))
        fft_layout.addWidget(self.fft_plot)
        
        right_layout.addWidget(fft_group, 1)
        viz_splitter.addWidget(right_panel)
        # 设置分割器拉伸因子：左侧可伸缩，右侧固定
        viz_splitter.setStretchFactor(0, 1)  # 左侧（信号图）可伸缩
        viz_splitter.setStretchFactor(1, 0)  # 右侧（热力图+FFT）固定
        
        viz_layout.addWidget(viz_splitter)
        layout.addWidget(self.viz_group, 1)
    
    def update_plots(self, channels):
        """根据通道列表更新图表"""
        self.plot_widget.clear()
        self.plot_items.clear()
        self.plot_curves.clear()
        
        if not channels:
            # 显示提示信息
            placeholder = self.plot_widget.addPlot()
            placeholder.getViewBox().setBackgroundColor(get_color('bg_card'))
            placeholder.showGrid(x=True, y=True, alpha=0.3)
            placeholder.setMouseEnabled(x=False, y=False)
            text = pg.TextItem(
                text=tr('no_channels_hint'),
                color=get_color('text_muted'),
                anchor=(0.5, 0.5)
            )
            placeholder.addItem(text)
            placeholder.setXRange(0, 10)
            placeholder.setYRange(-1, 1)
            placeholder.getAxis('bottom').setTicks([])
            placeholder.getAxis('left').setTicks([])
            return
        
        # 为每个通道创建子图
        n_channels = len(channels)
        for i, ch_name in enumerate(channels):
            # 使用支持滚轮缩放的 PlotItem
            plot = create_zoomable_plot(self.plot_widget, row=i, col=0)
            
            # 设置 ViewBox 背景色
            plot.getViewBox().setBackgroundColor(get_color('bg_card'))
            
            plot.showGrid(x=True, y=True, alpha=0.3)
            plot.setLabel('left', ch_name, color=get_color('text_muted'), size='10px')
            plot.setMenuEnabled(False)
            
            # 隐藏X轴标签，除了最后一个
            if i < n_channels - 1:
                plot.showAxis('bottom', show=False)
            else:
                plot.setLabel('bottom', tr('time_seconds'), color=get_color('text_muted'), size='10px')
            
            # 设置Y轴范围（适合 μV 级别信号）
            plot.setYRange(-5, 5, padding=0.1)
            
            # 创建曲线
            pen = pg.mkPen(color=get_color('accent'), width=1.5)
            curve = plot.plot(pen=pen)
            
            self.plot_items[ch_name] = plot
            self.plot_curves[ch_name] = curve
        
        # 设置图表间距
        self.plot_widget.ci.layout.setSpacing(0)
        self.plot_widget.ci.layout.setHorizontalSpacing(10)
        
        # 设置每行高度相等（1:1比例）- 使用固定拉伸因子
        if n_channels > 0:
            for i in range(n_channels):
                self.plot_widget.ci.layout.setRowStretchFactor(i, 1)
                self.plot_widget.ci.layout.setRowPreferredHeight(i, 100)
        
        # 更新FFT导联选择列表
        self._update_fft_channel_list(channels)
    
    def update_curve_data(self, channel_name, x_data, y_data):
        """更新单个通道的数据"""
        if channel_name in self.plot_curves:
            self.plot_curves[channel_name].setData(x_data, y_data)
    
    def _clear_plots(self):
        """清除图表数据"""
        for curve in self.plot_curves.values():
            curve.clear()
    
    def auto_range(self):
        """自动调整范围"""
        for plot in self.plot_items.values():
            plot.enableAutoRange()
    
    def _update_fft_channel_list(self, channels):
        """更新FFT导联选择列表"""
        current_selection = self.fft_channel_combo.currentText()
        self.fft_channel_combo.clear()
        for ch_name in channels:
            self.fft_channel_combo.addItem(ch_name)
        # 恢复之前的选择，如果还存在
        index = self.fft_channel_combo.findText(current_selection)
        if index >= 0:
            self.fft_channel_combo.setCurrentIndex(index)
        elif self.fft_channel_combo.count() > 0:
            self.fft_channel_combo.setCurrentIndex(0)
    
    def update_fft(self, freqs, power):
        """更新FFT频谱显示
        
        Args:
            freqs: 频率数组 (Hz)
            power: 功率谱密度数组
        """
        if hasattr(self, 'fft_curve') and self.fft_curve is not None:
            self.fft_curve.setData(freqs, power)
    
    def update_info(self, sr=None, ch_count=None, buffer_size=None):
        """更新信息显示"""
        if sr is not None:
            self.sr_info_label.setText(f"🔊 {int(sr)} Hz")
        if ch_count is not None:
            self.ch_info_label.setText(f"📡 {ch_count} ch")
        if buffer_size is not None:
            self.buffer_info_label.setText(f"📊 {buffer_size} points")
    
    def get_filter_params(self):
        """获取滤波参数"""
        return {
            'highpass': self.highpass_spin.value(),
            'lowpass': self.lowpass_spin.value(),
            'notch': self.notch_cb.isChecked(),
            'time_window': self.time_window_spin.value(),
        }


    def update_heatmap(self, channel_activities):
        """更新热力图"""
        if hasattr(self, 'heatmap_widget'):
            self.heatmap_widget.update_heatmap(channel_activities)
    
    def clear_heatmap(self):
        """清除热力图"""
        if hasattr(self, 'heatmap_widget'):
            self.heatmap_widget.clear_heatmap()
    
    def set_montage(self, montage):
        """设置电极布局"""
        if hasattr(self, 'heatmap_widget'):
            self.heatmap_widget.set_montage(montage)
    
    def set_montage_from_info(self, info):
        """从 MNE Info 对象设置电极布局"""
        if hasattr(self, 'heatmap_widget') and hasattr(self.heatmap_widget, 'set_from_info'):
            self.heatmap_widget.set_from_info(info)
    
    def update_theme(self):
        """更新主题颜色"""
        # 调用父类方法更新基础样式（标题、背景等）
        super().update_theme()
        
        from ..themes import get_color
        
        # 更新图表背景
        bg_color = get_color('bg_card')
        self.plot_widget.setBackground(bg_color)
        
        # 更新所有 PlotItem 的 ViewBox 背景
        for plot in self.plot_items.values():
            view_box = plot.getViewBox()
            if view_box:
                view_box.setBackgroundColor(bg_color)
                view_box.update()
        
        # 更新FFT图表背景
        if hasattr(self, 'fft_plot'):
            self.fft_plot.setBackground(bg_color)
            # 更新FFT图表的 ViewBox 背景
            fft_vb = self.fft_plot.getViewBox()
            if fft_vb:
                fft_vb.setBackgroundColor(bg_color)
                fft_vb.update()
        
        # 强制重绘整个图表区域
        self.plot_widget.update()
        if hasattr(self, 'fft_plot'):
            self.fft_plot.update()
    
    def update_texts(self):
        """更新界面文本"""
        from ...utils import tr
        
        # 更新标题
        self.set_title(tr('nav_signal'))
        self.set_subtitle(tr('nav_signal_subtitle'))
        
        # 更新组标题
        self.viz_group.setTitle(tr('panel_realtime_signal'))
        self.heatmap_group.setTitle(tr('panel_head_layout'))
