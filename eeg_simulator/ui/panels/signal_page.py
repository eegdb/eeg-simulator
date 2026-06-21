"""实时信号页面 - NavigationView 布局"""

import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
                             QLabel, QDoubleSpinBox, QCheckBox, QPushButton,
                             QFrame, QSizePolicy, QSplitter, QComboBox)
from PyQt6.QtCore import Qt, pyqtSignal

from ..themes import get_color
from ..widgets.navigation_view import NavigationPage
from ..widgets.head_layout import HeatmapOverlayWidget
from ...utils import tr


def _add_equal_width_cells(parent_layout, cell_widgets_list):
    """将每组控件放入等宽单元格并加入横向布局。"""
    for widgets in cell_widgets_list:
        cell = QWidget()
        cell_layout = QHBoxLayout(cell)
        cell_layout.setContentsMargins(0, 0, 0, 0)
        cell_layout.setSpacing(6)
        for widget in widgets:
            cell_layout.addWidget(widget)
        cell_layout.addStretch()
        parent_layout.addWidget(cell, 1)

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

        controls_row = QHBoxLayout()
        controls_row.setSpacing(12)
        panel_expanding = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        # ========== 滤波参数（仅高通 / 低通 / 陷波）==========
        self.filter_group = QGroupBox(tr('filter_settings'))
        filter_layout = QHBoxLayout(self.filter_group)
        
        self.highpass_label = QLabel(tr('label_highpass'))
        self.highpass_spin = QDoubleSpinBox()
        self.highpass_spin.setRange(0, 100)
        self.highpass_spin.setValue(0.5)
        self.highpass_spin.setDecimals(1)
        self.highpass_spin.setFixedWidth(52)
        self.highpass_spin.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        
        self.lowpass_label = QLabel(tr('label_lowpass'))
        self.lowpass_spin = QDoubleSpinBox()
        self.lowpass_spin.setRange(0, 500)
        self.lowpass_spin.setValue(100)
        self.lowpass_spin.setDecimals(1)
        self.lowpass_spin.setFixedWidth(52)
        self.lowpass_spin.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        
        self.notch_cb = QCheckBox(tr('label_notch_filter'))
        self.notch_cb.setChecked(True)
        self.notch_freq_combo = QComboBox()
        self.notch_freq_combo.setObjectName('notch_freq_combo')
        self.notch_freq_combo.addItem('50', 50.0)
        self.notch_freq_combo.setItemData(0, '50 Hz', Qt.ItemDataRole.ToolTipRole)
        self.notch_freq_combo.addItem('60', 60.0)
        self.notch_freq_combo.setItemData(1, '60 Hz', Qt.ItemDataRole.ToolTipRole)
        self.notch_freq_combo.setToolTip(tr('label_notch_filter'))
        self.notch_freq_combo.setEnabled(True)
        self.notch_freq_combo.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self.notch_freq_combo.setFixedWidth(40)
        self.notch_freq_combo.setStyleSheet("""
            QComboBox#notch_freq_combo {
                min-width: 40px;
                max-width: 40px;
                padding: 2px 2px 2px 4px;
            }
            QComboBox#notch_freq_combo::drop-down {
                width: 12px;
            }
        """)
        _add_equal_width_cells(filter_layout, [
            [self.highpass_label, self.highpass_spin],
            [self.lowpass_label, self.lowpass_spin],
            [self.notch_cb, self.notch_freq_combo],
        ])
        self.filter_group.setSizePolicy(panel_expanding)
        controls_row.addWidget(self.filter_group, 1)

        # ========== 波形显示 ==========
        self.waveform_group = QGroupBox(tr('group_waveform_view'))
        waveform_layout = QHBoxLayout(self.waveform_group)
        self.waveform_autoscale_cb = QCheckBox(tr('label_waveform_autoscale'))
        self.waveform_autoscale_cb.setToolTip(tr('tooltip_waveform_autoscale'))
        self.waveform_autoscale_cb.setChecked(True)
        self.time_window_label = QLabel(tr('label_time_window'))
        self.time_window_spin = QDoubleSpinBox()
        self.time_window_spin.setRange(1, 60)
        self.time_window_spin.setValue(10)
        self.time_window_spin.setSuffix(' s')
        self.time_window_spin.setDecimals(0)
        _add_equal_width_cells(waveform_layout, [
            [self.waveform_autoscale_cb],
            [self.time_window_label, self.time_window_spin],
        ])
        self.waveform_group.setSizePolicy(panel_expanding)
        controls_row.addWidget(self.waveform_group, 1)

        # ========== 分析侧栏（热力图 / FFT 开关）==========
        self.side_view_group = QGroupBox(tr('group_side_analysis'))
        side_view_layout = QHBoxLayout(self.side_view_group)
        self.show_heatmap_cb = QCheckBox(tr('label_show_heatmap'))
        self.show_heatmap_cb.setChecked(False)
        self.show_fft_cb = QCheckBox(tr('label_show_fft'))
        self.show_fft_cb.setChecked(False)
        _add_equal_width_cells(side_view_layout, [
            [self.show_heatmap_cb],
            [self.show_fft_cb],
        ])
        self.side_view_group.setSizePolicy(panel_expanding)
        controls_row.addWidget(self.side_view_group, 1)

        layout.addLayout(controls_row)
        
        # 连接信号
        self.highpass_spin.valueChanged.connect(self.filter_changed.emit)
        self.lowpass_spin.valueChanged.connect(self.filter_changed.emit)
        self.notch_cb.stateChanged.connect(self.filter_changed.emit)
        self.notch_freq_combo.currentIndexChanged.connect(self.filter_changed.emit)
        self.notch_cb.stateChanged.connect(
            lambda _: self.notch_freq_combo.setEnabled(self.notch_cb.isChecked())
        )
        self.show_heatmap_cb.stateChanged.connect(self._update_side_panels_visibility)
        self.show_fft_cb.stateChanged.connect(self._update_side_panels_visibility)
        
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
        
        # 右侧：地形图 + FFT（固定宽度，可单独开关）
        self.right_panel = QWidget()
        self.right_panel.setFixedWidth(280)
        right_layout = QVBoxLayout(self.right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)
        
        # 地形图（固定大小）
        self.heatmap_group = QGroupBox(tr('panel_head_layout'))
        self.heatmap_group.setFixedWidth(270)
        heatmap_layout = QVBoxLayout(self.heatmap_group)
        heatmap_layout.setContentsMargins(4, 4, 4, 4)
        heatmap_layout.setSpacing(4)

        band_layout = QHBoxLayout()
        self.heatmap_band_label = QLabel(tr('label_heatmap_band'))
        band_layout.addWidget(self.heatmap_band_label)
        self.heatmap_band_combo = QComboBox()
        self.heatmap_band_combo.setToolTip(tr('tooltip_heatmap_band'))
        self._populate_heatmap_band_combo()
        band_layout.addWidget(self.heatmap_band_combo, 1)
        heatmap_layout.addLayout(band_layout)
        self.heatmap_band_combo.currentIndexChanged.connect(self._on_heatmap_band_changed)
        
        self.heatmap_widget = HeatmapOverlayWidget()
        self.heatmap_widget.setFixedSize(250, 250)  # 固定大小
        heatmap_layout.addWidget(self.heatmap_widget, alignment=Qt.AlignmentFlag.AlignCenter)
        right_layout.addWidget(self.heatmap_group)
        
        # FFT 频谱图
        self.fft_group = QGroupBox(tr('label_fft_spectrum'))
        self.fft_group.setFixedWidth(270)
        fft_layout = QVBoxLayout(self.fft_group)
        fft_layout.setContentsMargins(4, 4, 4, 4)
        fft_layout.setSpacing(4)
        
        # FFT 导联选择
        fft_select_layout = QHBoxLayout()
        self.fft_channel_label = QLabel(tr('label_fft_channel'))
        fft_select_layout.addWidget(self.fft_channel_label)
        self.fft_channel_combo = QComboBox()
        self.fft_channel_combo.setToolTip(tr('tooltip_fft_channel'))
        fft_select_layout.addWidget(self.fft_channel_combo, 1)
        fft_layout.addLayout(fft_select_layout)
        
        # FFT 波形图
        self.fft_plot = pg.PlotWidget()
        self.fft_plot.setBackground(get_color('bg_card'))
        self.fft_plot.setMinimumHeight(150)
        self.fft_plot.setMaximumHeight(200)
        self.fft_plot.setLabel('bottom', tr('label_frequency'))
        self.fft_plot.setLabel('left', tr('label_power'))
        self.fft_plot.showGrid(x=True, y=True, alpha=0.3)
        self.fft_curve = self.fft_plot.plot(pen=pg.mkPen(color=get_color('accent'), width=2))
        fft_layout.addWidget(self.fft_plot)
        
        right_layout.addWidget(self.fft_group, 1)
        self.viz_splitter = viz_splitter
        viz_splitter.addWidget(self.right_panel)
        # 设置分割器拉伸因子：左侧可伸缩，右侧固定
        viz_splitter.setStretchFactor(0, 1)
        viz_splitter.setStretchFactor(1, 0)

        viz_layout.addWidget(viz_splitter)
        layout.addWidget(self.viz_group, 1)
        self._update_side_panels_visibility()
    
    def update_plots(self, channels):
        """根据通道列表更新图表"""
        saved_y_ranges = {}
        if not self.is_waveform_autoscale():
            for ch_name, plot in self.plot_items.items():
                y_min, y_max = plot.viewRange()[1]
                saved_y_ranges[ch_name] = (y_min, y_max)

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
            
            if not self.is_waveform_autoscale() and ch_name in saved_y_ranges:
                y_min, y_max = saved_y_ranges[ch_name]
                plot.setYRange(y_min, y_max, padding=0)
            
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

    def is_heatmap_enabled(self) -> bool:
        return self.show_heatmap_cb.isChecked()

    def _populate_heatmap_band_combo(self, select_key=None):
        """填充热力图频带下拉列表"""
        if select_key is None and hasattr(self, 'heatmap_band_combo'):
            select_key = self.get_heatmap_band()
        self.heatmap_band_combo.blockSignals(True)
        self.heatmap_band_combo.clear()
        for key in ('broadband', 'delta', 'theta', 'alpha', 'beta', 'gamma'):
            self.heatmap_band_combo.addItem(tr(f'band_{key}'), key)
        if select_key:
            idx = self.heatmap_band_combo.findData(select_key)
            if idx >= 0:
                self.heatmap_band_combo.setCurrentIndex(idx)
        self.heatmap_band_combo.blockSignals(False)

    def get_heatmap_band(self) -> str:
        if not hasattr(self, 'heatmap_band_combo'):
            return 'alpha'
        key = self.heatmap_band_combo.currentData()
        return key if key else 'alpha'

    def _on_heatmap_band_changed(self, _index=None):
        """切换频带后立即刷新地形图"""
        if not self.is_heatmap_enabled():
            return
        sim = self.parent_simulator
        if sim.simulation_time > 0 or sim.is_running:
            sim.simulation._update_heatmap_from_simulation()

    def is_fft_enabled(self) -> bool:
        return self.show_fft_cb.isChecked()

    def is_waveform_autoscale(self) -> bool:
        return self.waveform_autoscale_cb.isChecked()

    def _set_y_range_from_data(self, plot, data):
        y_min = float(np.min(data))
        y_max = float(np.max(data))
        if y_min == y_max:
            margin = max(abs(y_min) * 0.1, 1e-6) if y_min != 0 else 1.0
            y_min -= margin
            y_max += margin
        else:
            pad = (y_max - y_min) * 0.08
            y_min -= pad
            y_max += pad
        plot.setYRange(y_min, y_max, padding=0)

    def update_waveform_plots(self, t_display, channel_data: dict):
        """更新各通道波形；开启自动占满时按数据动态缩放 Y 轴"""
        for ch_name, data in channel_data.items():
            curve = self.plot_curves.get(ch_name)
            if curve is None:
                continue
            curve.setData(t_display, data)
            plot = self.plot_items.get(ch_name)
            if plot is None or len(data) == 0:
                continue
            if len(t_display) > 1:
                plot.setXRange(float(t_display[0]), float(t_display[-1]), padding=0)
            elif len(t_display) == 1:
                plot.setXRange(float(t_display[0]) - 0.5, float(t_display[0]) + 0.5, padding=0)
            if not self.is_waveform_autoscale():
                continue
            self._set_y_range_from_data(plot, data)

    def _update_side_panels_visibility(self):
        """根据开关显示/隐藏热力图与 FFT 面板"""
        show_heatmap = self.is_heatmap_enabled()
        show_fft = self.is_fft_enabled()
        show_side = show_heatmap or show_fft

        self.right_panel.setVisible(show_side)
        self.heatmap_group.setVisible(show_heatmap)
        self.fft_group.setVisible(show_fft)

        if show_heatmap and hasattr(self.parent_simulator, 'ui'):
            self.parent_simulator.ui._sync_heatmap_montage()
        if not show_fft and hasattr(self, 'fft_curve'):
            self.fft_curve.setData([], [])
    
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
        """更新FFT频谱显示"""
        if not self.is_fft_enabled():
            return
        if hasattr(self, 'fft_curve') and self.fft_curve is not None:
            self.fft_curve.setData(freqs, power)
    
    def update_info(self, sr=None, ch_count=None, buffer_size=None):
        """更新信息显示（标签存在时才更新）"""
        if sr is not None and hasattr(self, 'sr_info_label'):
            self.sr_info_label.setText(f"🔊 {int(sr)} Hz")
        if ch_count is not None and hasattr(self, 'ch_info_label'):
            self.ch_info_label.setText(f"📡 {ch_count} ch")
        if buffer_size is not None and hasattr(self, 'buffer_info_label'):
            self.buffer_info_label.setText(f"📊 {buffer_size} points")
    
    def get_filter_params(self):
        """获取滤波参数"""
        return {
            'highpass': self.highpass_spin.value(),
            'lowpass': self.lowpass_spin.value(),
            'notch': self.notch_cb.isChecked(),
            'notch_freq': float(self.notch_freq_combo.currentData()),
            'time_window': self.time_window_spin.value(),
            'show_heatmap': self.is_heatmap_enabled(),
            'show_fft': self.is_fft_enabled(),
            'heatmap_band': self.get_heatmap_band(),
            'waveform_autoscale': self.is_waveform_autoscale(),
        }

    def apply_filter_params(self, params: dict):
        """从项目数据恢复滤波参数"""
        if not params:
            return
        if 'highpass' in params:
            self.highpass_spin.setValue(float(params['highpass']))
        if 'lowpass' in params:
            self.lowpass_spin.setValue(float(params['lowpass']))
        if 'notch' in params:
            self.notch_cb.setChecked(bool(params['notch']))
        if 'notch_freq' in params:
            freq = float(params['notch_freq'])
            idx = self.notch_freq_combo.findData(freq)
            if idx >= 0:
                self.notch_freq_combo.setCurrentIndex(idx)
        if 'time_window' in params:
            self.time_window_spin.setValue(float(params['time_window']))
        if 'show_heatmap' in params:
            self.show_heatmap_cb.setChecked(bool(params['show_heatmap']))
        if 'show_fft' in params:
            self.show_fft_cb.setChecked(bool(params['show_fft']))
        if 'heatmap_band' in params:
            self._populate_heatmap_band_combo(str(params['heatmap_band']))
        if 'waveform_autoscale' in params:
            self.waveform_autoscale_cb.setChecked(bool(params['waveform_autoscale']))
        self.notch_freq_combo.setEnabled(self.notch_cb.isChecked())
        self._update_side_panels_visibility()


    def update_heatmap(self, channel_activities, channel_names=None):
        """更新热力图（montage 模式）"""
        if not self.is_heatmap_enabled():
            return
        if hasattr(self, 'heatmap_widget'):
            self.heatmap_widget.update_heatmap(channel_activities, channel_names)

    def update_heatmap_result(self, result: dict):
        """更新热力图（自动选择 forward 原生或 montage 模式）"""
        if not self.is_heatmap_enabled() or not hasattr(self, 'heatmap_widget'):
            return
        if result.get('mode') == 'forward' and result.get('info') is not None:
            self.heatmap_widget.update_heatmap_forward(
                result['powers'], result['info']
            )
        else:
            self.heatmap_widget.update_heatmap(
                result.get('powers'), result.get('names')
            )
        self.heatmap_widget.repaint()
    
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
        self.filter_group.setTitle(tr('filter_settings'))
        self.waveform_group.setTitle(tr('group_waveform_view'))
        self.side_view_group.setTitle(tr('group_side_analysis'))
        self.viz_group.setTitle(tr('panel_realtime_signal'))
        self.heatmap_group.setTitle(tr('panel_head_layout'))
        self.fft_group.setTitle(tr('label_fft_spectrum'))
        
        # 更新滤波标签
        self.highpass_label.setText(tr('label_highpass'))
        self.lowpass_label.setText(tr('label_lowpass'))
        self.notch_cb.setText(tr('label_notch_filter'))
        self.time_window_label.setText(tr('label_time_window'))
        self.show_heatmap_cb.setText(tr('label_show_heatmap'))
        self.show_fft_cb.setText(tr('label_show_fft'))
        self.heatmap_band_label.setText(tr('label_heatmap_band'))
        self.heatmap_band_combo.setToolTip(tr('tooltip_heatmap_band'))
        self._populate_heatmap_band_combo()
        self.waveform_autoscale_cb.setText(tr('label_waveform_autoscale'))
        self.waveform_autoscale_cb.setToolTip(tr('tooltip_waveform_autoscale'))
        
        # 更新 FFT 标签
        self.fft_channel_label.setText(tr('label_fft_channel'))
        self.fft_channel_combo.setToolTip(tr('tooltip_fft_channel'))
        self.fft_plot.setLabel('bottom', tr('label_frequency'))
        self.fft_plot.setLabel('left', tr('label_power'))
