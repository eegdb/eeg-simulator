"""头部电极布局预览组件 - 使用 MNE 的 plot 方法"""

import io
import matplotlib
matplotlib.use('Agg')  # 使用非交互式后端
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas

import mne
import numpy as np

from PyQt6.QtWidgets import (QWidget, QComboBox, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QFileDialog, QMessageBox, QCheckBox)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QImage

from ..styles import COLORS
from ...utils import tr, get_logger
from ...utils.mne_loader import resolve_standard_montage

logger = get_logger(__name__)

# 10-10 中与 T7/T8/P7/P8 同位置的旧 10-20 命名，地形图只保留一套
_LEGACY_OVERLAP_CHANNELS = frozenset({'T3', 'T4', 'T5', 'T6'})
_POS_TOL_M = 1e-4


def _unique_channels_for_topomap(montage, ch_names):
    """去掉空间位置重叠的通道（优先保留新命名，如 T7 而非 T3）"""
    positions = montage.get_positions()['ch_pos']
    ordered = sorted(
        ch_names,
        key=lambda n: (n in _LEGACY_OVERLAP_CHANNELS, n),
    )
    seen = []
    unique = []
    for name in ordered:
        if name not in positions:
            continue
        pos = np.asarray(positions[name], dtype=float)
        if any(np.linalg.norm(pos - p) < _POS_TOL_M for p in seen):
            continue
        seen.append(pos)
        unique.append(name)
    return unique


def _montage_pick(montage, ch_names):
    """从 montage 中取出子集（兼容不同 MNE 版本）"""
    try:
        return montage.pick(ch_names)
    except AttributeError:
        pos = montage.get_positions()
        ch_pos = {n: pos['ch_pos'][n] for n in ch_names if n in pos['ch_pos']}
        return mne.channels.make_dig_montage(
            ch_pos=ch_pos, coord_frame=pos.get('coord_frame', 'head')
        )


class HeatmapOverlayWidget(QWidget):
    """热力图叠加组件 - 使用 matplotlib 绘制地形图"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._activity_values = None
        self._channel_names = None
        self._montage = None
        self._pixmap = None
        
    def set_montage(self, montage):
        """设置 montage"""
        self._montage = montage
        self._update_plot()
        
    def update_heatmap(self, activity_values, channel_names=None):
        """更新热力图数据
        
        Args:
            activity_values: 各通道活动强度
            channel_names: 与 activity_values 对应的通道名；不传则假定与 montage 顺序一致
        """
        self._activity_values = activity_values
        self._channel_names = list(channel_names) if channel_names else None
        self._update_plot()

    def _prepare_plot_channels_and_data(self):
        """准备无重叠、与数据对齐的通道名和数值"""
        if self._montage is None or self._activity_values is None:
            return None

        activities = np.asarray(self._activity_values, dtype=float)
        positions = self._montage.get_positions()['ch_pos']

        if self._channel_names is not None:
            if len(self._channel_names) != len(activities):
                logger.warning("热力图通道名数量与数据长度不一致")
                return None
            candidates = [n for n in self._channel_names if n in positions]
            if not candidates:
                missing = self._channel_names[:5]
                logger.warning(
                    "热力图通道名与 montage 不匹配（示例: %s），请检查电极布局",
                    missing,
                )
                return None
            name_to_val = dict(zip(self._channel_names, activities))
        else:
            montage_names = list(self._montage.ch_names)
            if len(activities) != len(montage_names):
                return None
            candidates = montage_names
            name_to_val = dict(zip(montage_names, activities))

        unique_names = _unique_channels_for_topomap(self._montage, candidates)
        if len(unique_names) < 3:
            logger.warning(
                "热力图有效通道不足 3 个（当前 %d），无法绘制地形图",
                len(unique_names),
            )
            return None

        data = np.array([name_to_val[n] for n in unique_names], dtype=float)
        return unique_names, data
        
    def _update_plot(self):
        """使用 MNE plot_topomap 绘制热力图"""
        if self._montage is None:
            self._pixmap = None
            self.update()
            return
        
        # 如果没有数据，显示默认头部轮廓
        if self._activity_values is None:
            self.show_default_head()
            return
            
        try:
            plot_data = self._prepare_plot_channels_and_data()
            if plot_data is None:
                self._update_plot_simple()
                return
            ch_names, data = plot_data
            positions = self._montage.get_positions()['ch_pos']
            pos = np.array([positions[name] for name in ch_names])[:, :2]

            widget_size = min(self.width(), self.height())
            dpi = 100
            figsize = max(2, widget_size / dpi) if widget_size > 0 else 4

            fig = plt.figure(figsize=(figsize, figsize), dpi=dpi, facecolor='#1a1a1a')
            ax = fig.add_subplot(111)
            ax.set_facecolor('#1a1a1a')

            mne.viz.plot_topomap(
                data, pos,
                axes=ax,
                show=False,
                contours=8,
                cmap='RdBu_r',
                vlim=(0, 1),
                outlines='head',
                extrapolate='head',
                res=128,
            )
            
            fig.patch.set_alpha(1.0)
            ax.axis('off')

            buf = io.BytesIO()
            fig.savefig(buf, format='png', dpi=dpi,
                       facecolor='#1a1a1a',
                       edgecolor='none',
                       bbox_inches='tight',
                       pad_inches=0)
            buf.seek(0)
            
            # 转换为 QPixmap
            image = QImage.fromData(buf.getvalue())
            self._pixmap = QPixmap.fromImage(image)
            
            # 清理
            plt.close(fig)
            buf.close()
            
            self.update()
            
        except Exception as e:
            logger.warning(f"绘制热力图失败: {e}")
            # 如果失败，尝试使用简化的绘制方法
            self._update_plot_simple()
    
    def _update_plot_simple(self):
        """使用简化的方法绘制等高线地形图"""
        try:
            plot_data = self._prepare_plot_channels_and_data()
            if plot_data is None:
                self._pixmap = None
                self.update()
                return
            ch_names, data = plot_data
            
            # 根据控件大小调整图形尺寸
            widget_size = min(self.width(), self.height())
            dpi = 100
            figsize = max(2, widget_size / dpi) if widget_size > 0 else 4
            
            fig = plt.figure(figsize=(figsize, figsize), dpi=dpi, facecolor='none')
            ax = fig.add_subplot(111)
            
            pos = np.array([
                self._montage.get_positions()['ch_pos'][name] for name in ch_names
            ])[:, :2]
            
            # 使用三角剖分和等高线绘制地形图
            from matplotlib.tri import Triangulation
            tri = Triangulation(pos[:, 0], pos[:, 1])
            
            # 填充等高线（颜色区域）
            levels = np.linspace(0, 1, 15)
            contourf = ax.tricontourf(tri, data, levels=levels, cmap='RdBu_r', vmin=0, vmax=1)
            
            # 绘制等高线（线条）
            contour = ax.tricontour(tri, data, levels=8, colors='black', linewidths=0.5)
            
            # 不添加电极位置标记和标签，保持热力图简洁
            
            # 不绘制头部轮廓圆圈
            
            # 设置坐标轴 - 紧凑布局，根据电极位置精确设置边界
            margin = 0.02
            ax.set_xlim(pos[:, 0].min() - margin, pos[:, 0].max() + margin)
            ax.set_ylim(pos[:, 1].min() - margin, pos[:, 1].max() + margin)
            ax.set_aspect('equal')
            ax.axis('off')
            fig.patch.set_alpha(0)
            ax.set_facecolor('none')
            
            # 保存为 PNG - 使用零边距填充整个空间
            buf = io.BytesIO()
            fig.savefig(buf, format='png', dpi=dpi,
                       facecolor='none',
                       edgecolor='none',
                       bbox_inches='tight',
                       pad_inches=0)
            buf.seek(0)
            
            # 转换为 QPixmap
            image = QImage.fromData(buf.getvalue())
            self._pixmap = QPixmap.fromImage(image)
            
            # 清理
            plt.close(fig)
            buf.close()
            
            self.update()
            
        except Exception as e2:
            logger.warning(f"简化地形图绘制也失败: {e2}")
            self._pixmap = None
    
    def paintEvent(self, event):
        """绘制热力图"""
        from PyQt6.QtGui import QPainter
        
        painter = QPainter(self)
        
        if self._pixmap and not self._pixmap.isNull():
            # 保持正方形比例，居中显示
            scaled = self._pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            # 居中绘制
            x = (self.width() - scaled.width()) // 2
            y = (self.height() - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)
            
    def clear(self):
        """清除热力图"""
        self._activity_values = None
        self._channel_names = None
        self._pixmap = None
        self.update()
    
    def clear_heatmap(self):
        """清除热力图（别名）"""
        self.clear()
    
    def set_from_info(self, info):
        """根据 MNE Info 对象设置布局
        
        Args:
            info: MNE Info 对象，包含通道信息
        """
        import mne
        ch_names = info['ch_names']
        n_channels = len(ch_names)
        
        # 根据通道数量和名称特征推断 montage
        montage_name = None
        
        # 检查是否包含 Biosemi 通道名
        has_biosemi = any(ch.startswith('A') or ch.startswith('B') for ch in ch_names[:10])
        
        if has_biosemi:
            if n_channels <= 16:
                montage_name = 'biosemi16'
            elif n_channels <= 32:
                montage_name = 'biosemi32'
            elif n_channels <= 64:
                montage_name = 'biosemi64'
            elif n_channels <= 128:
                montage_name = 'biosemi128'
            else:
                montage_name = 'biosemi256'
        elif n_channels >= 200:
            montage_name = 'EGI_256'
        elif n_channels >= 100:
            montage_name = 'standard_1005'
        elif n_channels >= 60:
            montage_name = 'standard_1020'
        elif n_channels >= 20:
            montage_name = 'standard_1020'
        else:
            montage_name = 'standard_1020'
        
        try:
            montage = resolve_standard_montage(montage_name)
            self.set_montage(montage)
        except Exception as e:
            logger.warning(f"设置 montage 失败: {e}")
    
    def _draw_head_outline(self, ax):
        """绘制头部轮廓（已禁用 - 无轮廓模式）"""
        # 不绘制头部轮廓、鼻子和耳朵，以节省空间并简化界面
        pass
    
    def show_default_head(self):
        """无仿真数据时显示电极位置预览"""
        if self._montage is None:
            self._pixmap = None
            self.update()
            return
        try:
            widget_size = min(self.width(), self.height())
            dpi = 100
            figsize = max(2, widget_size / dpi) if widget_size > 0 else 4

            fig = plt.figure(figsize=(figsize, figsize), dpi=dpi, facecolor='#1a1a1a')
            ax = fig.add_subplot(111)
            self._montage.plot(
                show_names=False,
                kind='topomap',
                sphere=0.095,
                show=False,
                axes=ax,
            )
            fig.patch.set_alpha(1.0)
            ax.set_facecolor('#1a1a1a')

            buf = io.BytesIO()
            fig.savefig(buf, format='png', dpi=dpi,
                       facecolor='#1a1a1a',
                       edgecolor='none',
                       bbox_inches='tight',
                       pad_inches=0)
            buf.seek(0)
            image = QImage.fromData(buf.getvalue())
            self._pixmap = QPixmap.fromImage(image)
            plt.close(fig)
            buf.close()
            self.update()
        except Exception as e:
            logger.warning(f"绘制默认电极布局失败: {e}")
            self._pixmap = None


class HeadLayoutWidget(QWidget):
    """头部电极布局预览组件 - 使用 MNE 内置 plot"""

    # 常用 MNE 内置 montages（key -> i18n key）
    BUILTIN_MONTAGE_KEYS = [
        'standard_1020', 'standard_1005', 'standard_alphabetic',
        'biosemi16', 'biosemi32', 'biosemi64', 'biosemi128', 'biosemi160', 'biosemi256',
        'easycap-M1', 'easycap-M10', 'EGI_256',
        'GSN-HydroCel-32', 'GSN-HydroCel-64_1.0', 'GSN-HydroCel-128', 'GSN-HydroCel-256',
        'mgh60', 'mgh70', 'artinis-octamon', 'artinis-brite23',
        'brainproducts-RNP-BA-128',
    ]

    MONTAGE_I18N_KEYS = {
        'standard_1020': 'montage_standard_1020',
        'standard_1005': 'montage_standard_1005',
        'standard_alphabetic': 'montage_standard_alphabetic',
        'biosemi16': 'montage_biosemi16',
        'biosemi32': 'montage_biosemi32',
        'biosemi64': 'montage_biosemi64',
        'biosemi128': 'montage_biosemi128',
        'biosemi160': 'montage_biosemi160',
        'biosemi256': 'montage_biosemi256',
        'easycap-M1': 'montage_easycap_M1',
        'easycap-M10': 'montage_easycap_M10',
        'EGI_256': 'montage_EGI_256',
        'GSN-HydroCel-32': 'montage_GSN_HydroCel_32',
        'GSN-HydroCel-64_1.0': 'montage_GSN_HydroCel_64_1_0',
        'GSN-HydroCel-128': 'montage_GSN_HydroCel_128',
        'GSN-HydroCel-256': 'montage_GSN_HydroCel_256',
        'mgh60': 'montage_mgh60',
        'mgh70': 'montage_mgh70',
        'artinis-octamon': 'Artinis Octamon',
        'artinis-brite23': 'Artinis Brite23',
        'brainproducts-RNP-BA-128': 'montage_brainproducts_RNP_BA_128',
    }

    @classmethod
    def montage_display_name(cls, key):
        """获取 montage 的本地化显示名称"""
        i18n_key = cls.MONTAGE_I18N_KEYS.get(key, key)
        if i18n_key.startswith('montage_'):
            return tr(i18n_key)
        return i18n_key

    def get_available_montages(self):
        """获取所有可用布局名称"""
        return {key: self.montage_display_name(key) for key in self.BUILTIN_MONTAGE_KEYS}

    def __init__(self, parent=None, montage_name='standard_1020'):
        super().__init__(parent)
        self.setMinimumSize(250, 250)
        
        self._montage = None
        self._current_name = montage_name
        self._show_labels = True
        self._pixmap = None
        
        # 加载初始 montage
        self.set_montage(montage_name)

    def set_montage(self, montage_name):
        """设置 MNE 内置 montage"""
        try:
            self._montage = resolve_standard_montage(montage_name)
            self._current_name = montage_name
            self._update_plot()
            return True
        except Exception as e:
            logger.warning(f"加载 montage 失败 {montage_name}: {e}")
            return False

    def set_show_labels(self, show):
        """设置是否显示电极标签"""
        self._show_labels = show
        self._update_plot()

    def _update_plot(self):
        """使用 MNE plot 更新图形"""
        if self._montage is None:
            return
        
        try:
            # 根据控件大小动态调整图形尺寸
            widget_size = min(self.width(), self.height())
            dpi = 100
            figsize = max(2, widget_size / dpi) if widget_size > 0 else 4
            
            # 创建新图形
            fig = plt.figure(figsize=(figsize, figsize), dpi=dpi)
            ax = fig.add_subplot(111)
            
            # 使用 MNE 的 plot 方法
            self._montage.plot(
                show_names=self._show_labels,
                kind='topomap',
                sphere=0.095,
                show=False,
                axes=ax
            )
            
            # 调整布局
            fig.tight_layout()
            
            # 保存为 PNG，使用白色背景（MNE默认），零边距
            buf = io.BytesIO()
            fig.savefig(buf, format='png', dpi=dpi,
                       facecolor='white',
                       edgecolor='none',
                       bbox_inches='tight',
                       pad_inches=0)
            buf.seek(0)
            
            # 转换为 QPixmap
            image = QImage.fromData(buf.getvalue())
            self._pixmap = QPixmap.fromImage(image)
            
            # 清理
            plt.close(fig)
            buf.close()
            
            self.update()
            
        except Exception as e:
            logger.warning(f"绘制 montage 失败: {e}")
            import traceback
            traceback.print_exc()

    def paintEvent(self, event):
        """绘制图形"""
        from PyQt6.QtGui import QPainter
        
        painter = QPainter(self)
        
        if self._pixmap and not self._pixmap.isNull():
            # 填充整个空间，不保留空白边距
            scaled = self._pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            painter.drawPixmap(0, 0, scaled)
        else:
            # 绘制占位符
            painter.setPen(Qt.GlobalColor.gray)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, tr('not_loaded'))


class HeadLayoutSelector(QWidget):
    """头部布局选择器 - 包含电极布局和热力图叠加"""
    
    def __init__(self, parent=None, on_layout_changed=None):
        super().__init__(parent)
        self.on_layout_changed = on_layout_changed
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        # 头部组件（电极布局）
        self.head_widget = HeadLayoutWidget()
        
        # 热力图叠加组件
        self.heatmap_widget = HeatmapOverlayWidget()
        self.heatmap_widget.setVisible(False)  # 默认隐藏
        
        # 创建叠加容器
        self.overlay_container = QWidget()
        overlay_layout = QVBoxLayout(self.overlay_container)
        overlay_layout.setContentsMargins(0, 0, 0, 0)
        overlay_layout.addWidget(self.head_widget)
        
        # 将热力图叠加在head_widget上
        self.heatmap_widget.setParent(self.overlay_container)
        self.heatmap_widget.setGeometry(self.head_widget.geometry())
        
        # 布局选择下拉框
        self.combo = QComboBox()
        self._populate_montage_combo()
        
        self.combo.currentIndexChanged.connect(self._on_selection_changed)
        
        # 显示标签复选框
        self.show_labels_cb = QCheckBox(tr('label_show_labels'))
        self.show_labels_cb.setChecked(True)
        self.show_labels_cb.stateChanged.connect(self._on_show_labels_changed)
        
        # 添加到布局
        self.layout_label = QLabel(tr('label_electrode_layout'))
        layout.addWidget(self.layout_label)
        layout.addWidget(self.combo)
        layout.addWidget(self.overlay_container, 1)
        
        # 复选框布局
        checkbox_layout = QHBoxLayout()
        checkbox_layout.addWidget(self.show_labels_cb)
        layout.addLayout(checkbox_layout)
        
        # 同步montage到热力图
        self.heatmap_widget.set_montage(self.head_widget._montage)
        
    def resizeEvent(self, event):
        """窗口大小改变时调整热力图位置"""
        super().resizeEvent(event)
        # 确保热力图覆盖整个容器
        self.heatmap_widget.setGeometry(self.overlay_container.rect())
        
    def _on_selection_changed(self, index):
        """选择改变时"""
        layout_key = self.combo.currentData()
        if layout_key:
            success = self.head_widget.set_montage(layout_key)
            if success:
                # 同步montage到热力图
                self.heatmap_widget.set_montage(self.head_widget._montage)
                if self.on_layout_changed:
                    self.on_layout_changed(layout_key)
    
    def _on_show_labels_changed(self, state):
        """显示标签选项改变时"""
        self.head_widget.set_show_labels(state == Qt.CheckState.Checked.value)
    
    def _populate_montage_combo(self):
        """填充 montage 下拉框"""
        current = self.combo.currentData() if self.combo.count() else None
        self.combo.blockSignals(True)
        self.combo.clear()
        for key, name in self.head_widget.get_available_montages().items():
            self.combo.addItem(name, key)
        if current:
            idx = self.combo.findData(current)
            if idx >= 0:
                self.combo.setCurrentIndex(idx)
        self.combo.blockSignals(False)

    def update_texts(self):
        """更新界面文本（语言切换时调用）"""
        self.layout_label.setText(tr('label_electrode_layout'))
        self.show_labels_cb.setText(tr('label_show_labels'))
        self._populate_montage_combo()
    
    def get_head_widget(self):
        """获取头部组件"""
        return self.head_widget
    
    def set_montage(self, montage_name):
        """设置当前 montage"""
        index = self.combo.findData(montage_name)
        if index >= 0:
            self.combo.setCurrentIndex(index)
    
    def set_from_info(self, info):
        """根据 MNE Info 对象设置布局
        
        Args:
            info: MNE Info 对象，包含通道信息
        """
        ch_names = info['ch_names']
        n_channels = len(ch_names)
        
        # 根据通道数量和名称特征推断 montage
        montage_name = None
        
        # 检查是否包含 Biosemi 通道名
        has_biosemi = any(ch.startswith('A') or ch.startswith('B') for ch in ch_names[:10])
        
        if has_biosemi:
            if n_channels <= 16:
                montage_name = 'biosemi16'
            elif n_channels <= 32:
                montage_name = 'biosemi32'
            elif n_channels <= 64:
                montage_name = 'biosemi64'
            elif n_channels <= 128:
                montage_name = 'biosemi128'
            else:
                montage_name = 'biosemi256'
        elif n_channels >= 200:
            montage_name = 'EGI_256'
        elif n_channels >= 100:
            montage_name = 'standard_1005'
        elif n_channels >= 60:
            # 检查是否是 HydroCel 布局
            has_hydocel = any('E' in ch for ch in ch_names[:10])
            if has_hydocel:
                if n_channels <= 32:
                    montage_name = 'GSN-HydroCel-32'
                elif n_channels <= 64:
                    montage_name = 'GSN-HydroCel-64_1.0'
                elif n_channels <= 128:
                    montage_name = 'GSN-HydroCel-128'
                else:
                    montage_name = 'GSN-HydroCel-256'
            else:
                montage_name = 'easycap-M1'
        else:
            # 默认为 10-20 系统
            montage_name = 'standard_1020'
        
        # 设置 montage
        self.set_montage(montage_name)
    
    def update_heatmap(self, activity_values, channel_names=None):
        """更新热力图数据"""
        if self.view_mode_combo.currentData() == 'heatmap':
            self.heatmap_widget.update_heatmap(activity_values, channel_names)
        
    def clear_heatmap(self):
        """清除热力图"""
        self.heatmap_widget.clear()
