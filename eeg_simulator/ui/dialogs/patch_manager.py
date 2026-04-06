"""Patch 管理对话框 - 创建和管理 Patch

Patch 是基于 Label 的偶极子分组，共享相同的波形设置。
"""

import os
import numpy as np
import nibabel as nib
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, 
                             QLabel, QDoubleSpinBox, QPushButton,
                             QGroupBox, QListWidget, QListWidgetItem,
                             QSplitter, QWidget, QFormLayout, QFrame,
                             QMessageBox, QComboBox, QLineEdit, QStackedWidget,
                             QTableWidget, QTableWidgetItem, QHeaderView,
                             QAbstractItemView)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from ...utils import tr, get_logger
from ...models import Patch
from ...ui.themes import get_color

logger = get_logger(__name__)


class PatchManagerDialog(QDialog):
    """Patch 管理对话框"""
    
    patch_created = pyqtSignal(str, dict)  # patch_id, data
    patch_modified = pyqtSignal(str, dict)  # patch_id, data
    patch_deleted = pyqtSignal(str)  # patch_id
    
    def __init__(self, parent_simulator, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr('dlg_patch_manager_title'))
        self.setMinimumSize(1400, 900)
        
        self.parent_simulator = parent_simulator
        self.patches = parent_simulator.patches
        
        # 获取 source_page 的数据 (NavigationView 布局)
        self.src = getattr(parent_simulator.source_page, 'loaded_src', None)
        self.labels = getattr(parent_simulator.source_page, 'src_labels', {'lh': {}, 'rh': {}})
        self.label_source_map = getattr(parent_simulator.source_page, 'label_source_map', {'lh': {}, 'rh': {}})
        self.subject = getattr(parent_simulator.source_page, 'subject', None)
        self.subjects_dir = getattr(parent_simulator, 'subjects_dir', None)
        
        # MRI 数据
        self.t1_data = None
        self.vox_pts = None
        self.current_z = 128
        self.z_max = 255
        
        self.current_patch_id = None
        self.selected_dipole_id = None  # 当前选中的偶极子（用于创建 Patch）
        self._temp_dipoles = {}  # 临时存储创建的偶极子（在 Patch 创建前）
        
        # 加载 MRI 数据
        self._load_mri_data()
        self._collect_dipole_positions()
        
        self.init_ui()
        self.refresh_patch_list()
        # 注意：不再全局刷新偶极子列表，改为根据选择的 Label 按需刷新
    
    def _load_mri_data(self):
        """加载 MRI T1 数据"""
        try:
            if self.subjects_dir and self.subject:
                t1_path = os.path.join(self.subjects_dir, self.subject, 'mri', 'T1.mgz')
                
                if os.path.exists(t1_path):
                    logger.info(f"Loading MRI: {t1_path}")
                    img = nib.load(t1_path)
                    self.t1_data = img.get_fdata()
                    
                    vox2ras = img.header.get_vox2ras_tkr()
                    ras2vox = np.linalg.inv(vox2ras)
                    
                    if self.src:
                        src_pts = np.vstack([s['rr'] for s in self.src]) * 1000
                        src_pts_homo = np.hstack([src_pts, np.ones((len(src_pts), 1))])
                        self.vox_pts = (src_pts_homo @ ras2vox.T)[:, :3]
                    
                    self.z_max = self.t1_data.shape[2] - 1
                    self.current_z = self.z_max // 2
                    
                    logger.info(f"MRI loaded: shape={self.t1_data.shape}")
                else:
                    logger.warning(f"MRI file not found: {t1_path}")
                    self._init_fallback_data()
            else:
                logger.warning("No subjects_dir or subject provided")
                self._init_fallback_data()
        except Exception as e:
            logger.error(f"Error loading MRI: {e}")
            self._init_fallback_data()
    
    def _init_fallback_data(self):
        """初始化备选 MRI 数据"""
        self.t1_data = np.zeros((256, 256, 256), dtype=np.uint8)
        for i in range(256):
            self.t1_data[:, :, i] = i
        self.z_max = 255
        self.current_z = 128
    
    def _collect_dipole_positions(self):
        """收集所有偶极子的位置（用于在 MRI 上显示）"""
        self.dipole_vox_positions = {}  # dipole_id -> (x_vox, y_vox, z_vox)
        
        # 从所有 Patch 中收集偶极子
        all_dipoles = {}
        for patch in self.parent_simulator.patches.values():
            for dipole in patch.dipoles:
                all_dipoles[dipole.id] = dipole
        
        # 加上临时存储的偶极子
        all_dipoles.update(self._temp_dipoles)
        
        for dipole_id, dipole in all_dipoles.items():
            if dipole.vertno is not None and dipole.src_idx is not None and self.vox_pts is not None:
                # 计算该偶极子在 vox_pts 中的索引
                src_idx = dipole.src_idx
                vertno = dipole.vertno
                
                # 计算偏移量
                offset = 0
                for i in range(src_idx):
                    if i < len(self.src):
                        offset += len(self.src[i]['rr'])
                
                vox_idx = offset + vertno
                if vox_idx < len(self.vox_pts):
                    self.dipole_vox_positions[dipole_id] = self.vox_pts[vox_idx]
            else:
                # 手动添加的偶极子：从 RAS 坐标转换
                pos = dipole.position * 1000  # 转换为 mm
                # 简化为伪体素坐标
                self.dipole_vox_positions[dipole_id] = pos + 128  # 简单偏移到 0-256 范围
    
    def _get_dipole_z_vox(self, dipole):
        """获取偶极子的 MRI Z 坐标（体素坐标）
        
        实时计算，不依赖缓存的 dipole_vox_positions
        
        Args:
            dipole: Dipole 对象
            
        Returns:
            int: Z 坐标（体素索引），如果无法计算则返回 None
        """
        if dipole is None:
            return None
        
        # 优先使用缓存的位置
        if dipole.id in self.dipole_vox_positions:
            return int(self.dipole_vox_positions[dipole.id][2])
        
        # 实时计算
        if dipole.vertno is not None and self.vox_pts is not None:
            # 确定 src_idx
            src_idx = 0 if dipole.hemi == 'lh' else 1
            vertno = dipole.vertno
            
            # 计算偏移量
            offset = 0
            for i in range(src_idx):
                if i < len(self.src):
                    offset += len(self.src[i]['rr'])
            
            vox_idx = offset + vertno
            if vox_idx < len(self.vox_pts):
                return int(self.vox_pts[vox_idx][2])
        
        return None
    
    def init_ui(self):
        """初始化UI"""
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # 左侧面板 - MRI 切片图 + 所有偶极子
        left_panel = self._create_mri_panel()
        main_layout.addWidget(left_panel, 2)
        
        # 中间面板 - Patch 列表和创建/编辑
        middle_panel = self._create_patch_panel()
        main_layout.addWidget(middle_panel, 1)
        
        # 右侧面板 - Label 表格（两列：左脑、右脑）
        right_panel = self._create_label_panel()
        main_layout.addWidget(right_panel, 1)
    
    def _create_mri_panel(self):
        """创建 MRI 切片图面板"""
        from ..themes import get_color
        
        self.mri_panel = QFrame()
        self.mri_panel.setFrameShape(QFrame.Shape.StyledPanel)
        self.mri_panel.setStyleSheet(f"background-color: {get_color('bg_card')};")
        layout = QVBoxLayout(self.mri_panel)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 标题
        title = QLabel(tr('panel_source_space'))
        title.setObjectName("SubTitle")
        title.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # MRI 图形
        from ..themes import get_color
        bg_color = get_color('bg_card')
        text_color = get_color('text_main')
        
        self.fig = Figure(figsize=(8, 8), facecolor=bg_color)
        self.fig.subplots_adjust(left=0.02, right=0.98, top=0.95, bottom=0.15)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor(bg_color)
        
        self.canvas = FigureCanvas(self.fig)
        self.canvas.setStyleSheet(f"background-color: {bg_color};")
        layout.addWidget(self.canvas)
        
        # 滑块
        self.slider_ax = self.fig.add_axes([0.15, 0.02, 0.7, 0.03])
        self.slider_ax.set_facecolor(bg_color)  # 设置滑块轴背景色
        accent_color = get_color('accent')
        # 将hex颜色转换为matplotlib可识别的格式
        self.layer_slider = Slider(
            self.slider_ax, 
            'Z Layer', 
            0, 
            self.z_max, 
            valinit=self.current_z,
            valfmt='%d',
            color=accent_color,
            initcolor=get_color('red')
        )
        self.layer_slider.on_changed(self._on_slider_changed)
        self.slider_ax.tick_params(colors=text_color)
        # 设置滑块标签和数值文字颜色
        self.layer_slider.label.set_color(text_color)
        self.layer_slider.valtext.set_color(text_color)
        
        # 鼠标点击事件
        self.canvas.mpl_connect('button_press_event', self._on_mri_click)
        
        # 工具栏 - 只保留保存按钮
        class SaveOnlyToolbar(NavigationToolbar):
            toolitems = [t for t in NavigationToolbar.toolitems if t[0] == 'Save']
        
        toolbar = SaveOnlyToolbar(self.canvas, self)
        layout.addWidget(toolbar)
        
        # 初始化 MRI 显示
        self._update_mri_plot()
        
        return self.mri_panel
    
    def _create_patch_panel(self):
        """创建 Patch 列表面板"""
        panel = QFrame()
        panel.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 标题
        title = QLabel(tr('panel_patch_list'))
        title.setObjectName("SubTitle")
        title.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Patch 列表
        self.patch_list = QListWidget()
        self.patch_list.itemSelectionChanged.connect(self._on_patch_selected)
        layout.addWidget(self.patch_list)
        
        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(line)
        
        # 创建/编辑 Patch 区域
        self.edit_title = QLabel(tr('title_create_patch'))
        self.edit_title.setObjectName("SubTitle")
        layout.addWidget(self.edit_title)
        
        # 基本信息
        form_layout = QFormLayout()
        
        self.patch_name = QLineEdit()
        self.patch_name.setPlaceholderText(tr('placeholder_patch_name'))
        form_layout.addRow(tr('label_patch_name'), self.patch_name)
        
        self.selected_dipole_label = QLabel(tr('label_no_selection'))
        self.selected_dipole_label.setStyleSheet("color: gray;")
        form_layout.addRow(tr('label_center_dipole'), self.selected_dipole_label)
        
        # MRI Z轴坐标显示
        self.dipole_z_label = QLabel("MRI Z: --")
        self.dipole_z_label.setStyleSheet("color: gray; font-size: 11px;")
        form_layout.addRow("", self.dipole_z_label)
        
        self.radius_spin = QDoubleSpinBox()
        self.radius_spin.setRange(1, 100)  # 1mm 到 100mm
        self.radius_spin.setDecimals(1)
        self.radius_spin.setValue(5.0)  # 默认 5mm
        self.radius_spin.setSuffix(' mm')
        self.radius_spin.valueChanged.connect(self._update_nearby_dipoles)
        form_layout.addRow(tr('label_radius'), self.radius_spin)
        
        self.nearby_count_label = QLabel(tr('label_nearby_count', 0))
        form_layout.addRow(tr('label_affected_dipoles'), self.nearby_count_label)
        
        layout.addLayout(form_layout)
        
        # 波形设置
        waveform_group = self._create_waveform_group()
        layout.addWidget(waveform_group)
        
        layout.addStretch()
        
        # 按钮
        btn_layout = QHBoxLayout()
        
        self.save_btn = QPushButton(tr('btn_save_patch'))
        self.save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {get_color('accent')};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
                min-height: 36px;
            }}
            QPushButton:hover {{
                background-color: #45a049;
            }}
            QPushButton:disabled {{
                background-color: #757575;
                color: #bdbdbd;
            }}
        """)
        self.save_btn.setAutoDefault(False)  # 禁用回车键触发
        self.save_btn.clicked.connect(self._on_save_patch)
        btn_layout.addWidget(self.save_btn)
        
        self.delete_btn = QPushButton(tr('delete'))
        self.delete_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {get_color('error')};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
                min-height: 36px;
            }}
            QPushButton:hover {{
                background-color: #d32f2f;
            }}
            QPushButton:disabled {{
                background-color: #757575;
                color: #bdbdbd;
            }}
        """)
        self.delete_btn.setEnabled(False)
        self.delete_btn.clicked.connect(self._on_delete_patch)
        btn_layout.addWidget(self.delete_btn)
        
        layout.addLayout(btn_layout)
        
        return panel
    
    def _create_label_panel(self):
        """创建 Label 表格和源点列表面板"""
        panel = QFrame()
        panel.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 标题
        title = QLabel(tr('panel_anatomy_labels'))
        title.setObjectName("SubTitle")
        title.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Atlas 选择
        layout.addWidget(QLabel(tr('label_select_atlas')))
        self.atlas_combo = QComboBox()
        self.atlas_combo.addItem("Desikan-Killiany (aparc)", "aparc")
        self.atlas_combo.addItem("Destrieux (a2009s)", "a2009s")
        self.atlas_combo.currentIndexChanged.connect(self._populate_label_table)
        layout.addWidget(self.atlas_combo)
        
        # Label 表格（两列：左脑、右脑）
        self.label_table = QTableWidget()
        self.label_table.setColumnCount(2)
        self.label_table.setHorizontalHeaderLabels([tr('label_left'), tr('label_right')])
        self.label_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.label_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.label_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.label_table.itemSelectionChanged.connect(self._on_label_table_selected)
        
        # 设置表格样式
        self._update_label_table_style()
        
        layout.addWidget(self.label_table, 1)
        
        # 选中 Label 显示
        self.selected_label_display = QLabel(tr('label_selected_label') + " " + tr('label_none'))
        self.selected_label_display.setStyleSheet("color: #4CAF50; font-weight: bold;")
        layout.addWidget(self.selected_label_display)
        
        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("background-color: #555; margin: 10px 0;")
        layout.addWidget(line)
        
        # 选中 Label 的源点列表
        sources_title = QLabel(tr('label_dipoles_in_selected_label'))
        sources_title.setObjectName("SubTitle")
        sources_title.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
        layout.addWidget(sources_title)
        
        from ..themes import get_color
        bg_color = get_color('bg_card')
        text_color = get_color('text_main')
        border_color = get_color('border')
        accent_color = get_color('accent')
        
        self.label_dipole_list = QListWidget()
        self.label_dipole_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.label_dipole_list.setStyleSheet(f"""
            QListWidget {{
                outline: none;
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: 4px;
            }}
            QListWidget::item {{
                padding: 6px 10px;
                border-bottom: 1px solid {border_color};
                color: {text_color};
                font-size: 13px;
            }}
            QListWidget::item:selected {{
                background-color: {accent_color};
                color: {get_color('text_inverse')};
                border-radius: 4px;
                font-weight: bold;
            }}
            QListWidget::item:selected:!active {{
                background-color: {accent_color};
                color: {get_color('text_inverse')};
            }}
            QListWidget::item:hover:!selected {{
                background-color: {border_color}80;
            }}
        """)
        self.label_dipole_list.itemClicked.connect(self._on_label_dipole_selected)
        layout.addWidget(self.label_dipole_list, 2)
        
        self._populate_label_table()
        
        return panel
    
    def _create_waveform_group(self):
        """创建波形设置组（与 DipoleManager 一致）"""
        from PyQt6.QtWidgets import QTextEdit
        
        waveform_group = QGroupBox(tr('label_waveform_settings'))
        waveform_layout = QVBoxLayout(waveform_group)
        
        # 波形类型选择
        self.waveform_combo = QComboBox()
        self.waveform_combo.addItem('Sin', 'sin')
        self.waveform_combo.addItem('Cos', 'cos')
        self.waveform_combo.addItem('ERP', 'erp')
        self.waveform_combo.addItem('Gaussian', 'gaussian')
        self.waveform_combo.addItem('Gamma', 'gamma')
        self.waveform_combo.addItem('Oscillation', 'oscillation')
        self.waveform_combo.addItem('Custom', 'custom')
        self.waveform_combo.currentIndexChanged.connect(self._on_waveform_changed)
        waveform_layout.addWidget(self.waveform_combo)
        
        # 动态参数区域
        self.waveform_stack = QStackedWidget()
        
        # ========== Sin 参数 ==========
        sin_widget = QWidget()
        sin_layout = QFormLayout(sin_widget)
        
        self.sin_amplitude = QDoubleSpinBox()
        self.sin_amplitude.setRange(0, 10000)
        self.sin_amplitude.setDecimals(2)
        self.sin_amplitude.setSuffix(' nAm')
        self.sin_amplitude.setValue(10.0)
        sin_layout.addRow(tr('label_amplitude'), self.sin_amplitude)
        
        self.sin_frequency = QDoubleSpinBox()
        self.sin_frequency.setRange(0.1, 1000)
        self.sin_frequency.setDecimals(2)
        self.sin_frequency.setSuffix(' Hz')
        self.sin_frequency.setValue(10.0)
        sin_layout.addRow(tr('label_frequency'), self.sin_frequency)
        
        self.sin_phase = QDoubleSpinBox()
        self.sin_phase.setRange(0, 360)
        self.sin_phase.setDecimals(2)
        self.sin_phase.setSuffix('°')
        self.sin_phase.setValue(0)
        sin_layout.addRow(tr('label_phase'), self.sin_phase)
        
        self.sin_offset = QDoubleSpinBox()
        self.sin_offset.setRange(-1000, 1000)
        self.sin_offset.setDecimals(2)
        self.sin_offset.setValue(0)
        sin_layout.addRow(tr('label_offset'), self.sin_offset)
        
        self.sin_onset = QDoubleSpinBox()
        self.sin_onset.setRange(0, 100)
        self.sin_onset.setDecimals(3)
        self.sin_onset.setSuffix(' s')
        self.sin_onset.setValue(0)
        sin_layout.addRow(tr('label_onset'), self.sin_onset)
        
        self.sin_duration = QDoubleSpinBox()
        self.sin_duration.setRange(0, 100)
        self.sin_duration.setDecimals(3)
        self.sin_duration.setSuffix(' s')
        self.sin_duration.setValue(0)
        self.sin_duration.setSpecialValueText("∞")
        sin_layout.addRow(tr('label_duration'), self.sin_duration)
        
        self.waveform_stack.addWidget(sin_widget)
        
        # ========== Cos 参数 ==========
        cos_widget = QWidget()
        cos_layout = QFormLayout(cos_widget)
        
        self.cos_amplitude = QDoubleSpinBox()
        self.cos_amplitude.setRange(0, 10000)
        self.cos_amplitude.setDecimals(2)
        self.cos_amplitude.setSuffix(' nAm')
        self.cos_amplitude.setValue(10.0)
        cos_layout.addRow(tr('label_amplitude'), self.cos_amplitude)
        
        self.cos_frequency = QDoubleSpinBox()
        self.cos_frequency.setRange(0.1, 1000)
        self.cos_frequency.setDecimals(2)
        self.cos_frequency.setSuffix(' Hz')
        self.cos_frequency.setValue(10.0)
        cos_layout.addRow(tr('label_frequency'), self.cos_frequency)
        
        self.cos_phase = QDoubleSpinBox()
        self.cos_phase.setRange(0, 360)
        self.cos_phase.setDecimals(2)
        self.cos_phase.setSuffix('°')
        self.cos_phase.setValue(0)
        cos_layout.addRow(tr('label_phase'), self.cos_phase)
        
        self.cos_offset = QDoubleSpinBox()
        self.cos_offset.setRange(-1000, 1000)
        self.cos_offset.setDecimals(2)
        self.cos_offset.setValue(0)
        cos_layout.addRow(tr('label_offset'), self.cos_offset)
        
        self.cos_onset = QDoubleSpinBox()
        self.cos_onset.setRange(0, 100)
        self.cos_onset.setDecimals(3)
        self.cos_onset.setSuffix(' s')
        self.cos_onset.setValue(0)
        cos_layout.addRow(tr('label_onset'), self.cos_onset)
        
        self.cos_duration = QDoubleSpinBox()
        self.cos_duration.setRange(0, 100)
        self.cos_duration.setDecimals(3)
        self.cos_duration.setSuffix(' s')
        self.cos_duration.setValue(0)
        self.cos_duration.setSpecialValueText("∞")
        cos_layout.addRow(tr('label_duration'), self.cos_duration)
        
        self.waveform_stack.addWidget(cos_widget)
        
        # ========== ERP 参数 ==========
        erp_widget = QWidget()
        erp_layout = QFormLayout(erp_widget)
        
        self.erp_amplitude = QDoubleSpinBox()
        self.erp_amplitude.setRange(0, 10000)
        self.erp_amplitude.setDecimals(2)
        self.erp_amplitude.setSuffix(' nAm')
        self.erp_amplitude.setValue(10.0)
        erp_layout.addRow(tr('label_amplitude'), self.erp_amplitude)
        
        self.erp_frequency = QDoubleSpinBox()
        self.erp_frequency.setRange(0.1, 100)
        self.erp_frequency.setDecimals(2)
        self.erp_frequency.setSuffix(' Hz')
        self.erp_frequency.setValue(1.0)
        erp_layout.addRow(tr('label_frequency'), self.erp_frequency)
        
        self.erp_latency = QDoubleSpinBox()
        self.erp_latency.setRange(0, 10)
        self.erp_latency.setDecimals(3)
        self.erp_latency.setSuffix(' s')
        self.erp_latency.setValue(0.1)
        erp_layout.addRow(tr('label_latency'), self.erp_latency)
        
        self.erp_width = QDoubleSpinBox()
        self.erp_width.setRange(0.001, 1)
        self.erp_width.setDecimals(3)
        self.erp_width.setSuffix(' s')
        self.erp_width.setValue(0.05)
        erp_layout.addRow(tr('label_width'), self.erp_width)
        
        self.erp_polarity = QComboBox()
        self.erp_polarity.addItem(tr('label_positive'), 'positive')
        self.erp_polarity.addItem(tr('label_negative'), 'negative')
        erp_layout.addRow(tr('label_polarity'), self.erp_polarity)
        
        self.waveform_stack.addWidget(erp_widget)
        
        # ========== Gaussian 参数 ==========
        gaussian_widget = QWidget()
        gaussian_layout = QFormLayout(gaussian_widget)
        
        self.gaussian_amplitude = QDoubleSpinBox()
        self.gaussian_amplitude.setRange(0, 10000)
        self.gaussian_amplitude.setDecimals(2)
        self.gaussian_amplitude.setSuffix(' nAm')
        self.gaussian_amplitude.setValue(10.0)
        gaussian_layout.addRow(tr('label_amplitude'), self.gaussian_amplitude)
        
        self.gaussian_frequency = QDoubleSpinBox()
        self.gaussian_frequency.setRange(0.1, 1000)
        self.gaussian_frequency.setDecimals(2)
        self.gaussian_frequency.setSuffix(' Hz')
        self.gaussian_frequency.setValue(10.0)
        gaussian_layout.addRow(tr('label_frequency'), self.gaussian_frequency)
        
        self.gaussian_sigma = QDoubleSpinBox()
        self.gaussian_sigma.setRange(0.001, 1)
        self.gaussian_sigma.setDecimals(3)
        self.gaussian_sigma.setValue(0.1)
        gaussian_layout.addRow(tr('label_sigma'), self.gaussian_sigma)
        
        self.gaussian_center = QDoubleSpinBox()
        self.gaussian_center.setRange(0, 1)
        self.gaussian_center.setDecimals(3)
        self.gaussian_center.setValue(0.5)
        gaussian_layout.addRow(tr('label_center'), self.gaussian_center)
        
        self.waveform_stack.addWidget(gaussian_widget)
        
        # ========== Gamma 参数 ==========
        gamma_widget = QWidget()
        gamma_layout = QFormLayout(gamma_widget)
        
        self.gamma_amplitude = QDoubleSpinBox()
        self.gamma_amplitude.setRange(0, 10000)
        self.gamma_amplitude.setDecimals(2)
        self.gamma_amplitude.setSuffix(' nAm')
        self.gamma_amplitude.setValue(10.0)
        gamma_layout.addRow(tr('label_amplitude'), self.gamma_amplitude)
        
        self.gamma_frequency = QDoubleSpinBox()
        self.gamma_frequency.setRange(0.1, 1000)
        self.gamma_frequency.setDecimals(2)
        self.gamma_frequency.setSuffix(' Hz')
        self.gamma_frequency.setValue(10.0)
        gamma_layout.addRow(tr('label_frequency'), self.gamma_frequency)
        
        self.gamma_alpha = QDoubleSpinBox()
        self.gamma_alpha.setRange(0.1, 10)
        self.gamma_alpha.setDecimals(2)
        self.gamma_alpha.setValue(2.0)
        gamma_layout.addRow(tr('label_alpha'), self.gamma_alpha)
        
        self.gamma_beta = QDoubleSpinBox()
        self.gamma_beta.setRange(0.001, 1)
        self.gamma_beta.setDecimals(3)
        self.gamma_beta.setValue(0.1)
        gamma_layout.addRow(tr('label_beta'), self.gamma_beta)
        
        self.waveform_stack.addWidget(gamma_widget)
        
        # ========== Oscillation 参数 ==========
        oscillation_widget = QWidget()
        oscillation_layout = QFormLayout(oscillation_widget)
        
        self.oscillation_freq = QDoubleSpinBox()
        self.oscillation_freq.setRange(0.1, 1000)
        self.oscillation_freq.setDecimals(2)
        self.oscillation_freq.setSuffix(' Hz')
        self.oscillation_freq.setValue(10.0)
        oscillation_layout.addRow(tr('label_osc_freq'), self.oscillation_freq)
        
        self.oscillation_phase = QDoubleSpinBox()
        self.oscillation_phase.setRange(0, 360)
        self.oscillation_phase.setDecimals(2)
        self.oscillation_phase.setSuffix('°')
        self.oscillation_phase.setValue(0)
        oscillation_layout.addRow(tr('label_osc_phase'), self.oscillation_phase)
        
        self.oscillation_amp = QDoubleSpinBox()
        self.oscillation_amp.setRange(0, 10000)
        self.oscillation_amp.setDecimals(2)
        self.oscillation_amp.setValue(20.0)
        oscillation_layout.addRow(tr('label_osc_amp'), self.oscillation_amp)
        
        self.oscillation_center = QDoubleSpinBox()
        self.oscillation_center.setRange(0, 10)
        self.oscillation_center.setDecimals(3)
        self.oscillation_center.setSuffix(' s')
        self.oscillation_center.setValue(0.5)
        oscillation_layout.addRow(tr('label_osc_center'), self.oscillation_center)
        
        self.oscillation_width = QDoubleSpinBox()
        self.oscillation_width.setRange(0.001, 1)
        self.oscillation_width.setDecimals(3)
        self.oscillation_width.setSuffix(' s')
        self.oscillation_width.setValue(0.1)
        oscillation_layout.addRow(tr('label_osc_width'), self.oscillation_width)
        
        self.waveform_stack.addWidget(oscillation_widget)
        
        # ========== Custom 参数 ==========
        custom_widget = QWidget()
        custom_layout = QVBoxLayout(custom_widget)
        
        custom_amp_layout = QHBoxLayout()
        custom_amp_layout.addWidget(QLabel(tr('label_amplitude')))
        self.custom_amplitude = QDoubleSpinBox()
        self.custom_amplitude.setRange(0, 10000)
        self.custom_amplitude.setDecimals(2)
        self.custom_amplitude.setSuffix(' nAm')
        self.custom_amplitude.setValue(10.0)
        custom_amp_layout.addWidget(self.custom_amplitude)
        custom_layout.addLayout(custom_amp_layout)
        
        custom_freq_layout = QHBoxLayout()
        custom_freq_layout.addWidget(QLabel(tr('label_frequency')))
        self.custom_frequency = QDoubleSpinBox()
        self.custom_frequency.setRange(0.1, 1000)
        self.custom_frequency.setDecimals(2)
        self.custom_frequency.setSuffix(' Hz')
        self.custom_frequency.setValue(10.0)
        custom_freq_layout.addWidget(self.custom_frequency)
        custom_layout.addLayout(custom_freq_layout)
        
        custom_hint = QLabel(tr('hint_custom_waveform'))
        custom_hint.setStyleSheet("color: gray; font-size: 10px;")
        custom_hint.setWordWrap(True)
        custom_layout.addWidget(custom_hint)
        
        self.custom_data = QTextEdit()
        self.custom_data.setPlaceholderText(tr('placeholder_custom_data'))
        self.custom_data.setMaximumHeight(80)
        custom_layout.addWidget(self.custom_data)
        
        self.waveform_stack.addWidget(custom_widget)
        
        waveform_layout.addWidget(self.waveform_stack)
        
        # ========== MNE 幅度因子设置 ==========
        amp_scale_layout = QHBoxLayout()
        amp_scale_layout.addWidget(QLabel(tr('label_amplitude_scale')))
        self.amp_scale_spin = QDoubleSpinBox()
        self.amp_scale_spin.setRange(1e-12, 1e-6)
        self.amp_scale_spin.setDecimals(12)
        self.amp_scale_spin.setValue(1e-9)
        self.amp_scale_spin.setSingleStep(1e-10)
        self.amp_scale_spin.setToolTip(tr('tooltip_amplitude_scale'))
        amp_scale_layout.addWidget(self.amp_scale_spin)
        waveform_layout.addLayout(amp_scale_layout)
        
        # ========== 波形预览 ==========
        self._create_waveform_preview(waveform_layout)
        
        # 连接信号
        self._connect_waveform_signals()
        
        # 初始显示波形预览
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(100, self._update_waveform_preview)
        
        return waveform_group
    
    def _create_waveform_preview(self, parent_layout):
        """创建波形预览图表"""
        from ..themes import get_color
        
        # 创建波形预览容器（无框）
        preview_widget = QWidget()
        preview_layout = QVBoxLayout(preview_widget)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        
        # 使用主题颜色
        bg_color = get_color('bg_card')
        text_color = get_color('text_main')
        
        self.waveform_fig = Figure(figsize=(4, 2.2), facecolor=bg_color)
        # 调整图表边距，减少顶部和右侧留白
        self.waveform_fig.subplots_adjust(left=0.22, right=0.995, top=0.98, bottom=0.28)
        self.waveform_ax = self.waveform_fig.add_subplot(111)
        self.waveform_ax.set_facecolor(bg_color)
        self.waveform_ax.tick_params(colors=text_color, labelsize=8)
        self.waveform_ax.spines['bottom'].set_color(text_color)
        self.waveform_ax.spines['top'].set_color(text_color)
        self.waveform_ax.spines['left'].set_color(text_color)
        self.waveform_ax.spines['right'].set_color(text_color)
        
        self.waveform_canvas = FigureCanvas(self.waveform_fig)
        self.waveform_canvas.setStyleSheet(f"background-color: {bg_color};")
        self.waveform_canvas.setMinimumHeight(150)
        preview_layout.addWidget(self.waveform_canvas)
        
        parent_layout.addWidget(preview_widget)
    
    def _connect_waveform_signals(self):
        """连接波形参数变化信号到预览更新"""
        # Sin
        self.sin_amplitude.valueChanged.connect(self._update_waveform_preview)
        self.sin_frequency.valueChanged.connect(self._update_waveform_preview)
        self.sin_phase.valueChanged.connect(self._update_waveform_preview)
        self.sin_offset.valueChanged.connect(self._update_waveform_preview)
        self.sin_onset.valueChanged.connect(self._update_waveform_preview)
        self.sin_duration.valueChanged.connect(self._update_waveform_preview)
        # Cos
        self.cos_amplitude.valueChanged.connect(self._update_waveform_preview)
        self.cos_frequency.valueChanged.connect(self._update_waveform_preview)
        self.cos_phase.valueChanged.connect(self._update_waveform_preview)
        self.cos_offset.valueChanged.connect(self._update_waveform_preview)
        self.cos_onset.valueChanged.connect(self._update_waveform_preview)
        self.cos_duration.valueChanged.connect(self._update_waveform_preview)
        # ERP
        self.erp_amplitude.valueChanged.connect(self._update_waveform_preview)
        self.erp_frequency.valueChanged.connect(self._update_waveform_preview)
        self.erp_latency.valueChanged.connect(self._update_waveform_preview)
        self.erp_width.valueChanged.connect(self._update_waveform_preview)
        self.erp_polarity.currentIndexChanged.connect(self._update_waveform_preview)
        # Gaussian
        self.gaussian_amplitude.valueChanged.connect(self._update_waveform_preview)
        self.gaussian_frequency.valueChanged.connect(self._update_waveform_preview)
        self.gaussian_sigma.valueChanged.connect(self._update_waveform_preview)
        self.gaussian_center.valueChanged.connect(self._update_waveform_preview)
        # Gamma
        self.gamma_amplitude.valueChanged.connect(self._update_waveform_preview)
        self.gamma_frequency.valueChanged.connect(self._update_waveform_preview)
        self.gamma_alpha.valueChanged.connect(self._update_waveform_preview)
        self.gamma_beta.valueChanged.connect(self._update_waveform_preview)
        # Oscillation
        self.oscillation_freq.valueChanged.connect(self._update_waveform_preview)
        self.oscillation_phase.valueChanged.connect(self._update_waveform_preview)
        self.oscillation_amp.valueChanged.connect(self._update_waveform_preview)
        self.oscillation_center.valueChanged.connect(self._update_waveform_preview)
        self.oscillation_width.valueChanged.connect(self._update_waveform_preview)
        # Custom
        self.custom_amplitude.valueChanged.connect(self._update_waveform_preview)
        self.custom_frequency.valueChanged.connect(self._update_waveform_preview)
        self.custom_data.textChanged.connect(self._update_waveform_preview)
    
    def _update_waveform_preview(self):
        """更新波形预览"""
        try:
            import numpy as np
            
            waveform_type = self.waveform_combo.currentData()
            
            # 计算合适的显示时长
            if waveform_type in ['sin', 'cos']:
                freq = self.sin_frequency.value()
            elif waveform_type == 'erp':
                freq = self.erp_frequency.value()
            elif waveform_type == 'gaussian':
                freq = self.gaussian_frequency.value()
            elif waveform_type == 'gamma':
                freq = self.gamma_frequency.value()
            elif waveform_type == 'oscillation':
                freq = self.oscillation_freq.value()
            elif waveform_type == 'custom':
                freq = self.custom_frequency.value()
            else:
                freq = 10.0
            
            duration = max(1.0, 3.0 / freq) if freq > 0 else 1.0
            sfreq = getattr(self.parent_simulator, 'sampling_rate', 1000)
            t = np.linspace(0, duration, int(duration * sfreq))
            
            # 获取参数并生成信号
            if waveform_type == 'sin':
                params = {
                    'amplitude': self.sin_amplitude.value(),
                    'frequency': self.sin_frequency.value(),
                    'phase': self.sin_phase.value(),
                    'offset': self.sin_offset.value(),
                    'onset': self.sin_onset.value(),
                    'duration': self.sin_duration.value()
                }
                signal = self._generate_preview_signal(waveform_type, params, t)
            elif waveform_type == 'cos':
                params = {
                    'amplitude': self.cos_amplitude.value(),
                    'frequency': self.cos_frequency.value(),
                    'phase': self.cos_phase.value(),
                    'offset': self.cos_offset.value(),
                    'onset': self.cos_onset.value(),
                    'duration': self.cos_duration.value()
                }
                signal = self._generate_preview_signal(waveform_type, params, t)
            elif waveform_type == 'erp':
                params = {
                    'amplitude': self.erp_amplitude.value(),
                    'frequency': self.erp_frequency.value(),
                    'latency': self.erp_latency.value(),
                    'width': self.erp_width.value(),
                    'polarity': self.erp_polarity.currentData()
                }
                signal = self._generate_preview_signal(waveform_type, params, t)
            elif waveform_type == 'gaussian':
                params = {
                    'amplitude': self.gaussian_amplitude.value(),
                    'frequency': self.gaussian_frequency.value(),
                    'sigma': self.gaussian_sigma.value(),
                    'center': self.gaussian_center.value()
                }
                signal = self._generate_preview_signal(waveform_type, params, t)
            elif waveform_type == 'gamma':
                params = {
                    'amplitude': self.gamma_amplitude.value(),
                    'frequency': self.gamma_frequency.value(),
                    'alpha': self.gamma_alpha.value(),
                    'beta': self.gamma_beta.value()
                }
                signal = self._generate_preview_signal(waveform_type, params, t)
            elif waveform_type == 'oscillation':
                params = {
                    'freq': self.oscillation_freq.value(),
                    'phase': self.oscillation_phase.value(),
                    'amp': self.oscillation_amp.value(),
                    'center': self.oscillation_center.value(),
                    'width': self.oscillation_width.value()
                }
                signal = self._generate_preview_signal(waveform_type, params, t)
            elif waveform_type == 'custom':
                params = {
                    'amplitude': self.custom_amplitude.value(),
                    'frequency': self.custom_frequency.value(),
                    'data': self._get_custom_waveform_data().get('data', [])
                }
                signal = self._generate_preview_signal(waveform_type, params, t)
            else:
                signal = np.zeros_like(t)
            
            # 绘制
            from ..themes import get_color
            bg_color = get_color('bg_card')
            text_color = get_color('text_main')
            accent_color = get_color('accent')
            
            # 重新设置 Figure 和 Axes 的背景色（clear() 会清除这些设置）
            self.waveform_fig.set_facecolor(bg_color)
            self.waveform_ax.clear()
            self.waveform_ax.set_facecolor(bg_color)
            self.waveform_ax.plot(t, signal, color=accent_color, linewidth=1.5)
            # 显示坐标轴标签（使用英文避免字体问题）
            self.waveform_ax.set_xlabel('Time (s)', color=text_color, fontsize=8)
            self.waveform_ax.set_ylabel('Amplitude (nAm)', color=text_color, fontsize=8)
            self.waveform_ax.tick_params(colors=text_color, labelsize=8)
            self.waveform_ax.grid(True, alpha=0.3)
            
            # 设置Y轴范围，让波形紧贴边界（仅留2%边距）
            if len(signal) > 0:
                y_min, y_max = np.min(signal), np.max(signal)
                y_range = y_max - y_min
                if y_range < 1e-10:  # 如果信号几乎为常数
                    y_range = 2.0
                margin = y_range * 0.02  # 仅2%边距
                self.waveform_ax.set_ylim(y_min - margin, y_max + margin)
            
            self.waveform_canvas.draw()
        except Exception as e:
            logger.warning(f"Failed to update waveform preview: {e}")
    
    def _generate_preview_signal(self, waveform_type, params, t):
        """生成预览信号"""
        import numpy as np
        signal = np.zeros_like(t)
        
        if waveform_type == 'sin':
            amp = params.get('amplitude', 10.0)
            freq = params.get('frequency', 10.0)
            phase = params.get('phase', 0.0)
            offset = params.get('offset', 0.0)
            onset = params.get('onset', 0.0)
            duration = params.get('duration', 0.0)
            for i, ti in enumerate(t):
                if ti >= onset:
                    if duration <= 0 or ti <= onset + duration:
                        t_eff = ti - onset
                        signal[i] = amp * np.sin(2 * np.pi * freq * t_eff + np.radians(phase)) + offset
        elif waveform_type == 'cos':
            amp = params.get('amplitude', 10.0)
            freq = params.get('frequency', 10.0)
            phase = params.get('phase', 0.0)
            offset = params.get('offset', 0.0)
            onset = params.get('onset', 0.0)
            duration = params.get('duration', 0.0)
            for i, ti in enumerate(t):
                if ti >= onset:
                    if duration <= 0 or ti <= onset + duration:
                        t_eff = ti - onset
                        signal[i] = amp * np.cos(2 * np.pi * freq * t_eff + np.radians(phase)) + offset
        elif waveform_type == 'erp':
            amp = params.get('amplitude', 10.0)
            freq = params.get('frequency', 1.0)
            latency = params.get('latency', 0.1)
            width = params.get('width', 0.05)
            polarity = params.get('polarity', 'positive')
            polarity_factor = -1 if polarity == 'negative' else 1
            for i, ti in enumerate(t):
                envelope = np.exp(-((ti - latency) ** 2) / (2 * width ** 2))
                signal[i] = amp * polarity_factor * envelope * np.sin(2 * np.pi * freq * ti)
        elif waveform_type == 'gaussian':
            amp = params.get('amplitude', 10.0)
            freq = params.get('frequency', 10.0)
            sigma = params.get('sigma', 0.1)
            center = params.get('center', 0.5)
            for i, ti in enumerate(t):
                envelope = np.exp(-((ti - center) ** 2) / (2 * sigma ** 2))
                signal[i] = amp * envelope * np.sin(2 * np.pi * freq * ti)
        elif waveform_type == 'gamma':
            amp = params.get('amplitude', 10.0)
            freq = params.get('frequency', 10.0)
            alpha = params.get('alpha', 2.0)
            beta = params.get('beta', 0.1)
            for i, ti in enumerate(t):
                if ti > 0:
                    envelope = (ti ** alpha) * np.exp(-ti / beta)
                    signal[i] = amp * envelope * np.sin(2 * np.pi * freq * ti)
        elif waveform_type == 'custom':
            data = params.get('data', [])
            amp = params.get('amplitude', 10.0)
            if len(data) > 0:
                data_array = np.array(data)
                indices = np.linspace(0, len(data_array) - 1, len(t))
                signal = amp * np.interp(indices, np.arange(len(data_array)), data_array)
        elif waveform_type == 'oscillation':
            freq = params.get('freq', 10.0)
            phase = params.get('phase', 0.0)
            amp = params.get('amp', 20.0)
            center = params.get('center', 0.5)
            width = params.get('width', 0.1)
            for i, ti in enumerate(t):
                envelope = np.exp(-((ti - center) ** 2) / (2 * width ** 2))
                signal[i] = amp * envelope * np.sin(2 * np.pi * freq * ti + np.radians(phase))
        
        return signal
    
    def _get_custom_waveform_data(self):
        """获取自定义波形数据"""
        try:
            import numpy as np
            data_str = self.custom_data.toPlainText().strip()
            if data_str:
                data = eval(data_str)
                if isinstance(data, list):
                    return {'data': data}
                elif isinstance(data, np.ndarray):
                    return {'data': data.tolist()}
        except Exception as e:
            logger.warning(f"Invalid custom waveform data: {e}")
        return {}
    
    def _populate_label_table(self):
        """填充 Label 表格（两列：左脑、右脑）"""
        self.label_table.clearContents()
        
        # 从 source_page 获取最新的 label_source_map
        self.label_source_map = getattr(
            self.parent_simulator.source_page, 'label_source_map', {'lh': {}, 'rh': {}}
        )
        
        current_atlas = self.atlas_combo.currentData()
        
        # 收集左右半球的 labels
        lh_labels = []
        rh_labels = []
        
        for label_name in sorted(self.label_source_map.get('lh', {}).keys()):
            if current_atlas == 'a2009s':
                if label_name.lower().startswith('a2009s.'):
                    lh_labels.append(label_name[7:])  # 移除 a2009s. 前缀
            else:
                if not label_name.lower().startswith('a2009s.'):
                    lh_labels.append(label_name)
        
        for label_name in sorted(self.label_source_map.get('rh', {}).keys()):
            if current_atlas == 'a2009s':
                if label_name.lower().startswith('a2009s.'):
                    rh_labels.append(label_name[7:])
            else:
                if not label_name.lower().startswith('a2009s.'):
                    rh_labels.append(label_name)
        
        # 设置行数
        max_rows = max(len(lh_labels), len(rh_labels))
        self.label_table.setRowCount(max_rows)
        
        # 填充左列（左脑）
        for i, label in enumerate(lh_labels):
            item = QTableWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, {'name': label, 'hemi': 'lh', 'display': label})
            self.label_table.setItem(i, 0, item)
        
        # 填充右列（右脑）
        for i, label in enumerate(rh_labels):
            item = QTableWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, {'name': label, 'hemi': 'rh', 'display': label})
            self.label_table.setItem(i, 1, item)
    
    def _on_label_table_selected(self):
        """Label 表格选中改变"""
        selected_items = self.label_table.selectedItems()
        if not selected_items:
            return
        
        item = selected_items[0]
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return
        
        # 找到完整的 label_name
        hemi = data['hemi']
        display_name = data['display']
        
        # 根据 atlas 还原完整的 label_name
        current_atlas = self.atlas_combo.currentData()
        if current_atlas == 'a2009s':
            full_name = f"a2009s.{display_name}"
        else:
            full_name = display_name
        
        self.selected_label = {'name': full_name, 'hemi': hemi}
        self.selected_label_display.setText(f"{hemi}: {full_name}")
        
        # 刷新该 Label 下的偶极子列表
        self._refresh_label_dipole_list(hemi, full_name)
    
    def _refresh_label_dipole_list(self, hemi, label_name):
        """根据选中的 Label 刷新源点列表
        
        显示该 Label 下的所有源点（从源空间获取），无论是否已经创建为偶极子。
        
        Args:
            hemi: 半球 'lh' 或 'rh'
            label_name: Label 名称
        """
        self.label_dipole_list.clear()
        self._collect_dipole_positions()  # 重新收集位置
        
        # 获取该 Label 的所有源点
        sources = self.label_source_map.get(hemi, {}).get(label_name, [])
        
        # 获取已创建的偶极子映射 (vertno -> dipole)
        # 从所有 Patch 中收集
        vertno_to_dipole = {}
        in_patch_dipoles = set()  # 存储已在 Patch 中的 dipole_id
        for patch in self.parent_simulator.patches.values():
            for dipole in patch.dipoles:
                if dipole.hemi == hemi and dipole.vertno is not None:
                    vertno_to_dipole[dipole.vertno] = dipole
                    in_patch_dipoles.add(dipole.id)
        
        # 加上临时存储的偶极子
        for dipole in self._temp_dipoles.values():
            if dipole.hemi == hemi and dipole.vertno is not None:
                vertno_to_dipole[dipole.vertno] = dipole
        
        # 显示该 Label 下的所有源点
        for source_info in sources:
            vertno = source_info['vertno']
            
            # 检查是否已创建为偶极子
            if vertno in vertno_to_dipole:
                dipole = vertno_to_dipole[vertno]
                
                # 已创建为偶极子的源点 - 只显示顶点号
                item_text = f"V{vertno}"
                
                list_item = QListWidgetItem(item_text)
                list_item.setData(Qt.ItemDataRole.UserRole, {'type': 'dipole', 'id': dipole.id, 'vertno': vertno})
                
                # 如果已经在 Patch 中，标记为灰色
                if dipole.id in in_patch_dipoles:
                    list_item.setToolTip(tr('tooltip_already_in_patch'))
                else:
                    list_item.setToolTip(tr('tooltip_click_to_select'))
            else:
                # 尚未创建为偶极子的源点
                item_text = f"V{vertno}"
                list_item = QListWidgetItem(item_text)
                list_item.setData(Qt.ItemDataRole.UserRole, {'type': 'vertex', 'vertno': vertno, 'index': source_info['index'], 'hemi': hemi})
                list_item.setToolTip(tr('tooltip_click_to_create'))
            
            self.label_dipole_list.addItem(list_item)
        
        logger.info(f"Label {label_name} ({hemi}): {len(sources)} sources, {len(vertno_to_dipole)} already dipoles")
    
    def _on_label_dipole_selected(self, item):
        """从 Label 源点列表中选择中心点
        
        如果该源点已创建为偶极子，直接选中；
        如果未创建，先创建为偶极子，然后选中。
        """
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return
        
        if data['type'] == 'dipole':
            # 已存在的偶极子，直接选中
            self._select_dipole(data['id'])
        elif data['type'] == 'vertex':
            # 未创建的源点，先创建为偶极子
            vertno = data['vertno']
            hemi = data['hemi']
            index = data['index']
            
            # 从源空间获取位置和方向
            src_idx = 0 if hemi == 'lh' else 1
            if self.src and src_idx < len(self.src):
                src = self.src[src_idx]
                position = src['rr'][vertno].tolist()
                orientation = src['nn'][vertno].tolist() if 'nn' in src else [0, 0, 1]
                
                # 创建偶极子（不放入任何 Patch，临时存储）
                dipole = self.parent_simulator.create_dipole(
                    position=position,
                    orientation=orientation,
                    hemi=hemi,
                    vertno=vertno,
                    src_idx=src_idx
                )
                
                # 添加到临时存储
                self._temp_dipoles[dipole.id] = dipole
                
                # 重新收集位置信息
                self._collect_dipole_positions()
                
                # 刷新列表（更新显示状态）
                self._refresh_label_dipole_list(hemi, self.selected_label['name'])
                
                # 选中新创建的偶极子
                self._select_dipole(dipole.id)
                
                logger.info(f"Created dipole {dipole.id} from vertex {vertno} ({hemi})")
    
    def _select_dipole(self, dipole_id):
        """选中偶极子"""
        # 从临时存储或所有 Patch 中查找偶极子
        dipole = self._temp_dipoles.get(dipole_id)
        if not dipole:
            # 遍历所有 Patch 查找
            for patch in self.parent_simulator.patches.values():
                dipole = patch.get_dipole_by_id(dipole_id)
                if dipole:
                    break
        
        if not dipole:
            return
        
        self.selected_dipole_id = dipole_id
        
        # 清除 current_patch_id，确保选择新源点时进入创建模式而非更新模式
        if self.current_patch_id:
            self.current_patch_id = None
            self.edit_title.setText(tr('title_create_patch'))
            self.delete_btn.setEnabled(False)
            # 清除 Patch 列表的选择状态
            self.patch_list.clearSelection()
        # 使用原始标识（hemi-vertno）代替内部 dipole_id
        display_name = f"{dipole.hemi}-v{dipole.vertno}" if dipole.vertno is not None else dipole_id
        self.selected_dipole_label.setText(
            f"{display_name} ({dipole.position[0]:.3f}, {dipole.position[1]:.3f}, {dipole.position[2]:.3f})"
        )
        self.selected_dipole_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
        
        # 更新MRI Z轴坐标显示
        if dipole_id in self.dipole_vox_positions:
            z_vox = int(self.dipole_vox_positions[dipole_id][2])
            self.dipole_z_label.setText(f"MRI Z: {z_vox}")
            self.dipole_z_label.setStyleSheet("color: #4CAF50; font-size: 11px;")
        else:
            self.dipole_z_label.setText("MRI Z: --")
            self.dipole_z_label.setStyleSheet("color: gray; font-size: 11px;")
        
        # 同步更新列表选中状态
        self._sync_list_selection(dipole_id)
        
        # 自动填充默认 Patch 名称
        self._auto_fill_patch_name(dipole)
        
        # 更新受影响的偶极子数量
        self._update_nearby_dipoles()
    
    def _sync_list_selection(self, dipole_id):
        """同步列表的选中状态
        确保只有当前偶极子对应的列表项被选中
        """
        # 先清除所有选中
        self.label_dipole_list.clearSelection()
        
        for i in range(self.label_dipole_list.count()):
            item = self.label_dipole_list.item(i)
            data = item.data(Qt.ItemDataRole.UserRole)
            if not data:
                continue
            
            # 匹配 dipole 类型
            if data.get('type') == 'dipole' and data.get('id') == dipole_id:
                self.label_dipole_list.setCurrentItem(item)
                return
            # 匹配 vertex 类型（通过 vertno 匹配）
            if data.get('type') == 'vertex':
                # 检查该 vertex 是否对应选中的偶极子
                dipole = self._temp_dipoles.get(dipole_id)
                if dipole and dipole.vertno == data.get('vertno'):
                    self.label_dipole_list.setCurrentItem(item)
                    return
        
        # 如果有该偶极子的体素位置，跳转到对应层
        if dipole_id in self.dipole_vox_positions:
            vox_pos = self.dipole_vox_positions[dipole_id]
            self.current_z = int(vox_pos[2])
            self.layer_slider.set_val(self.current_z)
            self._update_mri_plot()
        
        # 更新附近偶极子数量
        self._update_nearby_dipoles()
    
    def _auto_fill_patch_name(self, dipole):
        """根据选中的偶极子自动填充默认 Patch 名称
        
        格式：{hemi}-{label_name}-{vertno}
        """
        if not hasattr(self, 'selected_label') or not self.selected_label:
            return
        
        # 只有当输入框为空时才填充
        if self.patch_name.text().strip():
            return
        
        label_name = self.selected_label['name']
        hemi = self.selected_label['hemi']
        vertno = dipole.vertno if dipole.vertno is not None else 0
        
        default_name = f"{hemi}-{label_name}-{vertno}"
        self.patch_name.setText(default_name)
    
    def _on_slider_changed(self, value):
        """MRI 滑块值改变"""
        self.current_z = int(value)
        self._update_mri_plot()
    
    def _update_mri_plot(self):
        """更新 MRI 切片图"""
        from ..themes import get_color
        bg_color = get_color('bg_card')
        text_color = get_color('text_main')
        
        # 重新设置 Figure 和 Axes 的背景色（clear() 会清除这些设置）
        self.fig.set_facecolor(bg_color)
        self.ax.clear()
        self.ax.set_facecolor(bg_color)
        # 滑块轴背景色也需要更新
        if hasattr(self, 'slider_ax'):
            self.slider_ax.set_facecolor(bg_color)
        
        if self.t1_data is None:
            self.canvas.draw()
            return
        
        z = self.current_z
        slice_data = np.rot90(self.t1_data[:, :, z])
        
        # 根据背景色亮度调整MRI显示：深色背景使用反转灰度
        bg_card_color = get_color('bg_card')
        is_dark = bg_card_color in ['#18181b', '#0a0a0a', '#27272a'] or bg_card_color < '#808080'
        if is_dark:
            slice_data_display = 150 - slice_data  # 反转数据，保持与原始相同的 vmax=150 范围
        else:
            slice_data_display = slice_data
        self.ax.imshow(slice_data_display, cmap='gray', vmin=0, vmax=150, aspect='equal')
        self.ax.set_title(f'Z = {z} | Click dipole to select', color=text_color, fontsize=11)
        
        img_height, img_width = slice_data.shape
        self.ax.set_xlim(0, slice_data.shape[1])
        self.ax.set_ylim(0, slice_data.shape[0])
        self.ax.axis('off')
        
        # 添加方向指示
        self.ax.text(img_width/2, 20, 'A (Face)', color='yellow', fontsize=12, 
                    ha='center', va='top', fontweight='bold',
                    bbox=dict(boxstyle='round,pad=0.3', facecolor=bg_color, alpha=0.7))
        self.ax.text(img_width/2, img_height-20, 'P (Back)', color='yellow', fontsize=12,
                    ha='center', va='bottom', fontweight='bold',
                    bbox=dict(boxstyle='round,pad=0.3', facecolor=bg_color, alpha=0.7))
        self.ax.text(20, img_height/2, 'R', color='cyan', fontsize=14,
                    ha='left', va='center', fontweight='bold',
                    bbox=dict(boxstyle='round,pad=0.3', facecolor=bg_color, alpha=0.7))
        self.ax.text(img_width-20, img_height/2, 'L', color='cyan', fontsize=14,
                    ha='right', va='center', fontweight='bold',
                    bbox=dict(boxstyle='round,pad=0.3', facecolor=bg_color, alpha=0.7))
        
        # 绘制所有偶极子
        self._draw_dipoles_on_mri()
        
        self.canvas.draw()
    
    def _draw_dipoles_on_mri(self):
        """在 MRI 上绘制源点和偶极子
        
        显示策略：
        - 其他偶极子用灰色小点显示（低透明度）
        - 当前 Label 下未创建为偶极子的用橙色显示
        - 已在 Patch 中的用蓝色显示
        - 选中的用黄色星形
        - 半径内的用青色显示
        """
        if self.t1_data is None:
            return
        
        z = self.current_z
        z_tolerance = 5
        
        # 收集所有偶极子（从 Patch 和临时存储）
        all_dipoles = {}
        in_patch_dipole_ids = set()
        for patch in self.parent_simulator.patches.values():
            for dipole in patch.dipoles:
                all_dipoles[dipole.id] = dipole
                in_patch_dipole_ids.add(dipole.id)
        all_dipoles.update(self._temp_dipoles)
        
        # 计算半径内的偶极子（如果有选中偶极子和半径设置）
        radius = self.radius_spin.value() / 1000.0 if hasattr(self, 'radius_spin') else 0.0  # mm to m
        in_radius_dipole_ids = set()
        in_radius_vertnos = set()
        center_dipole = None
        if self.selected_dipole_id and radius > 0:
            center_dipole = all_dipoles.get(self.selected_dipole_id)
            if center_dipole:
                # 在源空间中查找半径内的所有顶点
                nearby_vertices = self.parent_simulator.find_dipoles_in_radius(
                    center_position=center_dipole.position.tolist(),
                    radius=radius,
                    src=self.src,
                    hemi=center_dipole.hemi
                )
                # 收集这些顶点的 vertno
                in_radius_vertnos = {v['vertno'] for v in nearby_vertices}
                # 找到对应的偶极子
                for dipole in all_dipoles.values():
                    if dipole.vertno in in_radius_vertnos:
                        in_radius_dipole_ids.add(dipole.id)
        
        # 获取当前 Label 的顶点和偶极子映射
        label_vertnos = set()
        label_vertnos_created = set()  # 已创建为偶极子的 vertno 集合
        label_dipoles_map = {}  # vertno -> dipole
        if hasattr(self, 'selected_label') and self.selected_label:
            sources = self.label_source_map.get(
                self.selected_label['hemi'], {}
            ).get(self.selected_label['name'], [])
            label_vertnos = {s['vertno'] for s in sources}
            
            # 找出哪些顶点已经创建为偶极子
            for dipole in all_dipoles.values():
                if dipole.hemi == self.selected_label['hemi'] and dipole.vertno in label_vertnos:
                    label_vertnos_created.add(dipole.vertno)
                    label_dipoles_map[dipole.vertno] = dipole
        
        # 收集不同状态的点
        other_dipoles = []  # 其他偶极子（淡色）
        label_not_created = []  # 当前 Label 下未创建的源点（橙色）
        selected_point = None
        patch_dipoles = []  # 其他 Patch 中的偶极子（蓝色）
        radius_dipoles = []  # 半径内的偶极子（青色）
        
        # 1. 绘制已创建的偶极子
        for dipole_id, vox_pos in self.dipole_vox_positions.items():
            if abs(vox_pos[2] - z) > z_tolerance:
                continue
            
            dipole = all_dipoles.get(dipole_id)
            if not dipole:
                continue
            
            display_x = vox_pos[0]
            display_y = self.t1_data.shape[1] - vox_pos[1]
            
            # 检查是否在当前 Label 中
            in_current_label = dipole.vertno in label_vertnos
            # 检查是否在当前选中的 Patch 中
            in_selected_patch = dipole.id in in_patch_dipole_ids
            
            if dipole_id == self.selected_dipole_id:
                selected_point = (display_x, display_y, 'dipole')
            elif dipole_id in in_radius_dipole_ids:
                # 半径内的偶极子（青色，高优先级）
                radius_dipoles.append((display_x, display_y))
            elif in_selected_patch:
                patch_dipoles.append((display_x, display_y))
            # 注意：已移除 temp_dipoles 和 label_created 的统计
        
        # 2. 绘制半径内未创建为偶极子的源点（青色）
        # 注意：这里处理所有在半径内但未创建的顶点
        if self.selected_dipole_id and radius > 0 and self.src and center_dipole:
            src_idx = 0 if center_dipole.hemi == 'lh' else 1
            if src_idx < len(self.src):
                src = self.src[src_idx]
                for vertno in in_radius_vertnos:
                    # 如果这个顶点已经有对应的偶极子，则已经在 radius_dipoles 中绘制过了
                    if vertno in label_vertnos_created or any(d.vertno == vertno for d in all_dipoles.values()):
                        continue
                    # 计算体素坐标
                    offset = sum(len(self.src[i]['rr']) for i in range(src_idx))
                    vox_idx = offset + vertno
                    
                    if self.vox_pts is not None and vox_idx < len(self.vox_pts):
                        vox_pos = self.vox_pts[vox_idx]
                        if abs(vox_pos[2] - z) <= z_tolerance:
                            display_x = vox_pos[0]
                            display_y = self.t1_data.shape[1] - vox_pos[1]
                            radius_dipoles.append((display_x, display_y))
        
        # 3. 绘制当前 Label 下未创建的源点（不在半径内的）
        if hasattr(self, 'selected_label') and self.selected_label and self.src:
            src_idx = 0 if self.selected_label['hemi'] == 'lh' else 1
            if src_idx < len(self.src):
                src = self.src[src_idx]
                for vertno in (label_vertnos - label_vertnos_created):
                    # 如果已经在半径内，则跳过（已经在上面处理了）
                    if self.selected_dipole_id and vertno in in_radius_vertnos:
                        continue
                    # 计算体素坐标
                    offset = sum(len(self.src[i]['rr']) for i in range(src_idx))
                    vox_idx = offset + vertno
                    
                    if self.vox_pts is not None and vox_idx < len(self.vox_pts):
                        vox_pos = self.vox_pts[vox_idx]
                        if abs(vox_pos[2] - z) <= z_tolerance:
                            display_x = vox_pos[0]
                            display_y = self.t1_data.shape[1] - vox_pos[1]
                            label_not_created.append((display_x, display_y, vertno))
        
        # 绘制其他偶极子（灰色，低透明度）
        # if other_dipoles:
        #     xs, ys = zip(*other_dipoles)
        #     self.ax.scatter(xs, ys, c='gray', s=15, alpha=0.2, 
        #                   zorder=2, marker='o')
        
        # 绘制当前 Label 下未创建的源点（橙色，空心）
        if label_not_created:
            xs, ys, _ = zip(*label_not_created)
            self.ax.scatter(xs, ys, c='none', s=50, alpha=0.8,
                          edgecolors='orange', linewidths=2,
                          zorder=4, marker='o')
        
        # 绘制当前 Label 下已在 Patch 中的偶极子（绿色）- 已禁用
        # if label_created:
        #     xs, ys = zip(*label_created)
        #     self.ax.scatter(xs, ys, c='lime', s=60, alpha=0.9, 
        #                   edgecolors='white', linewidths=1.5,
        #                   zorder=5, marker='o')
        
        # 绘制临时偶极子（紫色）- 点击过但未保存到 Patch - 已禁用
        # if temp_dipoles:
        #     xs, ys = zip(*temp_dipoles)
        #     self.ax.scatter(xs, ys, c='magenta', s=50, alpha=0.8,
        #                   edgecolors='white', linewidths=1.5,
        #                   zorder=4, marker='o')
        
        # 绘制半径内的偶极子（青色）- 在 Label 颜色之后绘制，优先级更高
        if radius_dipoles:
            xs, ys = zip(*radius_dipoles)
            self.ax.scatter(xs, ys, c='cyan', s=55, alpha=0.85,
                          edgecolors='white', linewidths=1.5,
                          zorder=6, marker='o')
        
        # 绘制已在 Patch 中的偶极子（蓝色）
        if patch_dipoles:
            xs, ys = zip(*patch_dipoles)
            self.ax.scatter(xs, ys, c='blue', s=40, alpha=0.6, 
                          edgecolors='white', linewidths=0.5, 
                          zorder=3, marker='o')
        
        # 绘制选中的点（黄色星形）
        if selected_point:
            self.ax.scatter([selected_point[0]], [selected_point[1]], 
                          c='yellow', s=300, marker='*', 
                          edgecolors='red', linewidths=2, zorder=10)
        
        # 添加图例说明
        from matplotlib.lines import Line2D
        from ..themes import get_color
        bg_color = get_color('bg_card')
        text_color = get_color('text_main')
        
        legend_elements = [
            Line2D([0], [0], marker='*', color=text_color, markerfacecolor='yellow', 
                   markeredgecolor='red', markersize=15, label='Selected'),
            Line2D([0], [0], marker='o', color=text_color, markerfacecolor='cyan', 
                   markersize=8, label='In Radius'),
            Line2D([0], [0], marker='o', color=text_color, markerfacecolor='blue', 
                   markersize=6, label='In Other Patch'),
            # Line2D([0], [0], marker='o', color='w', markerfacecolor='lime', 
            #        markersize=6, label='In This Patch'),
            # Line2D([0], [0], marker='o', color='w', markerfacecolor='magenta', 
            #        markersize=6, label='Selected (unsaved)'),
            Line2D([0], [0], marker='o', color=text_color, markerfacecolor='none',
                   markeredgecolor='orange', markersize=6, label='Current Label'),
        ]
        self.ax.legend(handles=legend_elements, loc='upper left', 
                      fontsize=8, facecolor=bg_color, edgecolor=get_color('border'),
                      labelcolor=text_color, framealpha=0.7)
    
    def _on_mri_click(self, event):
        """处理 MRI 上的鼠标点击"""
        if event.inaxes != self.ax:
            return
        
        x, y = event.xdata, event.ydata
        if x is None or y is None:
            return
        
        # 获取当前 Label 的信息
        label_vertnos = set()
        label_vertnos_created = {}  # vertno -> dipole
        if hasattr(self, 'selected_label') and self.selected_label:
            sources = self.label_source_map.get(
                self.selected_label['hemi'], {}
            ).get(self.selected_label['name'], [])
            label_vertnos = {s['vertno'] for s in sources}
            
            # 收集所有偶极子（从 Patch 和临时存储）
            all_dipoles = {}
            for patch in self.parent_simulator.patches.values():
                for dipole in patch.dipoles:
                    all_dipoles[dipole.id] = dipole
            all_dipoles.update(self._temp_dipoles)
            
            # 找出哪些顶点已经创建为偶极子
            for dipole in all_dipoles.values():
                if dipole.hemi == self.selected_label['hemi'] and dipole.vertno in label_vertnos:
                    label_vertnos_created[dipole.vertno] = dipole
        
        z_tolerance = 5
        
        # 在当前 Label 下的源点（包括已创建和未创建的）中查找
        min_dist = float('inf')
        closest_type = None  # 'dipole' 或 'vertex'
        closest_id = None
        closest_vertno = None
        
        # 1. 检查已创建的偶极子
        for dipole_id, vox_pos in self.dipole_vox_positions.items():
            if abs(vox_pos[2] - self.current_z) > z_tolerance:
                continue
            
            dipole = all_dipoles.get(dipole_id)
            if not dipole or dipole.vertno not in label_vertnos:
                continue
            
            vx = vox_pos[0]
            vy = self.t1_data.shape[1] - vox_pos[1]
            dist = ((vx - x)**2 + (vy - y)**2)**0.5
            
            if dist < min_dist:
                min_dist = dist
                closest_type = 'dipole'
                closest_id = dipole_id
                closest_vertno = dipole.vertno
        
        # 2. 检查未创建的源点
        if self.src and hasattr(self, 'selected_label') and self.selected_label:
            src_idx = 0 if self.selected_label['hemi'] == 'lh' else 1
            if src_idx < len(self.src):
                for vertno in label_vertnos - set(label_vertnos_created.keys()):
                    offset = sum(len(self.src[i]['rr']) for i in range(src_idx))
                    vox_idx = offset + vertno
                    
                    if self.vox_pts is not None and vox_idx < len(self.vox_pts):
                        vox_pos = self.vox_pts[vox_idx]
                        if abs(vox_pos[2] - self.current_z) <= z_tolerance:
                            vx = vox_pos[0]
                            vy = self.t1_data.shape[1] - vox_pos[1]
                            dist = ((vx - x)**2 + (vy - y)**2)**0.5
                            
                            if dist < min_dist:
                                min_dist = dist
                                closest_type = 'vertex'
                                closest_vertno = vertno
        
        # 距离阈值
        if min_dist > 20:
            return
        
        # 处理选择
        if closest_type == 'dipole':
            # 选中已存在的偶极子
            self._select_dipole(closest_id)
        elif closest_type == 'vertex':
            # 创建偶极子并选中（_create_dipole_from_vertex 会调用 _select_dipole）
            self._create_dipole_from_vertex(closest_vertno, self.selected_label['hemi'])
    
    def _create_dipole_from_vertex(self, vertno, hemi):
        """从顶点创建偶极子"""
        src_idx = 0 if hemi == 'lh' else 1
        if not self.src or src_idx >= len(self.src):
            return
        
        src = self.src[src_idx]
        position = src['rr'][vertno].tolist()
        orientation = src['nn'][vertno].tolist() if 'nn' in src else [0, 0, 1]
        
        # 创建偶极子
        dipole_id = self.parent_simulator.add_dipole(
            position=position,
            orientation=orientation,
            hemi=hemi,
            vertno=vertno,
            src_idx=src_idx
        )
        
        # 重新收集位置信息
        self._collect_dipole_positions()
        
        # 刷新列表
        if hasattr(self, 'selected_label') and self.selected_label:
            self._refresh_label_dipole_list(hemi, self.selected_label['name'])
        
        # 选中新创建的偶极子
        self._select_dipole(dipole_id)
        
        logger.info(f"Created dipole {dipole_id} from vertex {vertno} ({hemi})")
    
    def _update_nearby_dipoles(self):
        """更新附近偶极子数量（半径内的所有顶点数量）"""
        if not self.selected_dipole_id:
            return
        
        # 获取选中的偶极子位置
        dipole = self._temp_dipoles.get(self.selected_dipole_id)
        if not dipole:
            # 从现有 Patch 中查找
            for patch in self.parent_simulator.patches.values():
                dipole = patch.get_dipole_by_id(self.selected_dipole_id)
                if dipole:
                    break
        
        if not dipole:
            return
        
        radius = self.radius_spin.value() / 1000.0  # mm to m
        
        # 在源空间中查找半径内的所有顶点
        nearby_vertices = self.parent_simulator.find_dipoles_in_radius(
            center_position=dipole.position.tolist(),
            radius=radius,
            src=self.src,
            hemi=dipole.hemi
        )
        
        # 半径内的顶点数量（不包括中心偶极子本身）
        # find_dipoles_in_radius 返回的列表包含中心偶极子，需要减去1
        vertices_count = len(nearby_vertices) - 1 if nearby_vertices and len(nearby_vertices) > 0 else 0
        
        # 受影响的偶极子 = 半径内的其他顶点数（不包括中心偶极子）
        self.nearby_count_label.setText(tr('label_nearby_count', vertices_count))
    
    def _on_waveform_changed(self, index):
        """波形类型改变"""
        self.waveform_stack.setCurrentIndex(index)
        self._update_waveform_preview()
    
    def _get_waveform_params(self):
        """获取当前波形参数（完整版，与 DipoleManager 一致）"""
        waveform_type = self.waveform_combo.currentData()
        
        if waveform_type == 'sin':
            return {
                'amplitude': self.sin_amplitude.value(),
                'frequency': self.sin_frequency.value(),
                'phase': self.sin_phase.value(),
                'offset': self.sin_offset.value(),
                'onset': self.sin_onset.value(),
                'duration': self.sin_duration.value()
            }
        elif waveform_type == 'cos':
            return {
                'amplitude': self.cos_amplitude.value(),
                'frequency': self.cos_frequency.value(),
                'phase': self.cos_phase.value(),
                'offset': self.cos_offset.value(),
                'onset': self.cos_onset.value(),
                'duration': self.cos_duration.value()
            }
        elif waveform_type == 'erp':
            return {
                'amplitude': self.erp_amplitude.value(),
                'frequency': self.erp_frequency.value(),
                'latency': self.erp_latency.value(),
                'width': self.erp_width.value(),
                'polarity': self.erp_polarity.currentData()
            }
        elif waveform_type == 'oscillation':
            return {
                'freq': self.oscillation_freq.value(),
                'phase': self.oscillation_phase.value(),
                'amp': self.oscillation_amp.value(),
                'center': self.oscillation_center.value(),
                'width': self.oscillation_width.value()
            }
        elif waveform_type == 'gaussian':
            return {
                'amplitude': self.gaussian_amplitude.value(),
                'frequency': self.gaussian_frequency.value(),
                'sigma': self.gaussian_sigma.value(),
                'center': self.gaussian_center.value()
            }
        elif waveform_type == 'gamma':
            return {
                'amplitude': self.gamma_amplitude.value(),
                'frequency': self.gamma_frequency.value(),
                'alpha': self.gamma_alpha.value(),
                'beta': self.gamma_beta.value()
            }
        elif waveform_type == 'custom':
            params = {'data': []}
            try:
                data_str = self.custom_data.toPlainText().strip()
                if data_str:
                    data = eval(data_str)
                    if isinstance(data, list):
                        params['data'] = data
                    elif isinstance(data, np.ndarray):
                        params['data'] = data.tolist()
            except Exception:
                pass
            params['amplitude'] = self.custom_amplitude.value()
            params['frequency'] = self.custom_frequency.value()
            return params
        else:
            return {
                'frequency': self.sin_frequency.value(),
                'phase': self.sin_phase.value()
            }
    
    def _on_save_patch(self):
        """保存 Patch - 根据 current_patch_id 判断是创建还是更新"""
        if self.current_patch_id:
            # 更新已有 Patch
            self._do_update_patch()
        else:
            # 创建新 Patch
            self._do_create_patch()
    
    def _do_update_patch(self):
        """更新已有 Patch 参数"""
        waveform_type = self.waveform_combo.currentData()
        waveform_params = self._get_waveform_params()
        
        # 如果用户输入了名称则更新，否则保持原名称
        user_name = self.patch_name.text().strip()
        name = user_name if user_name else None
        
        self.parent_simulator.modify_patch(
            self.current_patch_id,
            name=name,
            waveform_type=waveform_type,
            waveform_params=waveform_params
        )
        
        # 更新幅度因子
        patch = self.parent_simulator.patches.get(self.current_patch_id)
        if patch:
            patch.amplitude_scale = self.amp_scale_spin.value()
        
        self.patch_modified.emit(self.current_patch_id, {
            'waveform_type': waveform_type,
            'waveform_params': waveform_params
        })
        
        self.refresh_patch_list()
        QMessageBox.information(self, tr('success'), tr('msg_patch_updated'))
    
    def _do_create_patch(self):
        """创建新 Patch"""
        if not self.selected_dipole_id:
            QMessageBox.warning(self, tr('warning'), tr('msg_select_center_dipole'))
            return
        
        if not hasattr(self, 'selected_label') or not self.selected_label:
            QMessageBox.warning(self, tr('warning'), tr('msg_select_label'))
            return
        
        # 获取中心偶极子（从临时存储或现有 Patch）
        center_dipole = self._temp_dipoles.get(self.selected_dipole_id)
        if not center_dipole:
            # 从现有 Patch 中查找
            for patch in self.parent_simulator.patches.values():
                center_dipole = patch.get_dipole_by_id(self.selected_dipole_id)
                if center_dipole:
                    break
        
        if not center_dipole:
            QMessageBox.warning(self, tr('warning'), tr('msg_select_center_dipole'))
            return
        
        # 检查该偶极子是否已在 Patch 中
        for patch in self.parent_simulator.patches.values():
            if patch.get_dipole_by_id(self.selected_dipole_id):
                QMessageBox.warning(self, tr('warning'), 
                    tr('msg_dipole_already_in_patch', self.selected_dipole_id))
                return
        
        # 创建 Patch
        radius = self.radius_spin.value() / 1000.0  # mm to m
        
        # 生成默认名称：脑区-label-源点
        user_name = self.patch_name.text().strip()
        if user_name:
            name = user_name
        else:
            # 默认格式：{hemi}-{label_name}-{vertno}
            label_name = self.selected_label['name']
            hemi = self.selected_label['hemi']
            vertno = center_dipole.vertno if center_dipole.vertno is not None else 0
            name = f"{hemi}-{label_name}-{vertno}"
        
        waveform_type = self.waveform_combo.currentData()
        waveform_params = self._get_waveform_params()
        
        # 计算 src_idx
        src_idx = 0 if center_dipole.hemi == 'lh' else 1
        
        patch_id = self.parent_simulator.create_patch(
            position=center_dipole.position.tolist(),
            orientation=center_dipole.orientation.tolist(),
            radius=radius,
            label_name=self.selected_label['name'],
            hemi=self.selected_label['hemi'],
            name=name,
            waveform_type=waveform_type,
            waveform_params=waveform_params,
            vertno=center_dipole.vertno,
            src_idx=src_idx,
            anchor_dipole=center_dipole  # 传入已有的中心偶极子
        )
        
        # 在源空间中查找半径内的所有顶点
        nearby_vertices = self.parent_simulator.find_dipoles_in_radius(
            center_position=center_dipole.position.tolist(),
            radius=radius,
            src=self.src,
            hemi=center_dipole.hemi
        )
        
        # 获取新创建的 Patch
        patch = self.parent_simulator.patches.get(patch_id)
        actual_dipole_count = 1  # 中心偶极子
        if patch:
            # 设置幅度因子
            patch.amplitude_scale = self.amp_scale_spin.value()
            
            if nearby_vertices:
                # 为中心偶极子周围的顶点创建偶极子并添加到 Patch
                for vertex_info in nearby_vertices:
                    # 跳过中心偶极子本身
                    if vertex_info['vertno'] == center_dipole.vertno:
                        continue
                    
                    # 创建偶极子
                    dipole = self.parent_simulator.create_dipole(
                        position=vertex_info['position'],
                        orientation=vertex_info['orientation'],
                        hemi=vertex_info['hemi'],
                        vertno=vertex_info['vertno'],
                        src_idx=vertex_info['src_idx']
                    )
                    
                    # 添加到 Patch
                    patch.add_dipole(dipole)
                    actual_dipole_count += 1
        
        # 从临时存储中移除已使用的偶极子
        if self.selected_dipole_id in self._temp_dipoles:
            del self._temp_dipoles[self.selected_dipole_id]
        
        # 使用实际创建的偶极子数
        dipole_count = actual_dipole_count
        
        self.patch_created.emit(patch_id, {
            'anchor': self.selected_dipole_id,
            'radius': radius,
            'dipole_count': dipole_count
        })
        
        self.refresh_patch_list()
        # 刷新当前 Label 的源点列表
        if hasattr(self, 'selected_label') and self.selected_label:
            self._refresh_label_dipole_list(self.selected_label['hemi'], self.selected_label['name'])
        self._update_mri_plot()
        self._clear_form()
        
        QMessageBox.information(self, tr('success'), 
            tr('msg_patch_created', patch_id, dipole_count))
    
    def _on_delete_patch(self):
        """删除 Patch"""
        if not self.current_patch_id:
            return
        
        reply = QMessageBox.question(
            self, tr('confirm'),
            tr('msg_confirm_delete_patch', self.current_patch_id),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.parent_simulator.delete_patch(self.current_patch_id)
            self.patch_deleted.emit(self.current_patch_id)
            self.refresh_patch_list()
            # 刷新当前 Label 的偶极子列表（因为有些可能被释放）
            if hasattr(self, 'selected_label') and self.selected_label:
                self._refresh_label_dipole_list(self.selected_label['hemi'], self.selected_label['name'])
            self._update_mri_plot()
            self._clear_form()
    
    def _on_patch_selected(self):
        """Patch 列表选中改变"""
        items = self.patch_list.selectedItems()
        if not items:
            # 取消选择，进入新建模式
            self.delete_btn.setEnabled(False)
            self.save_btn.setEnabled(True)  # 允许创建新 Patch
            self._clear_form()
            return
        
        item = items[0]
        patch_id = item.data(Qt.ItemDataRole.UserRole)
        patch = self.patches.get(patch_id)
        
        if patch:
            self.current_patch_id = patch_id
            self.delete_btn.setEnabled(True)
            self.save_btn.setEnabled(True)
            self._load_patch_to_form(patch)
    
    def _load_patch_to_form(self, patch):
        """加载 Patch 到表单"""
        self.edit_title.setText(tr('title_edit_patch', patch.id))
        self.save_btn.setEnabled(True)
        
        self.patch_name.setText(patch.name or '')
        anchor_id = patch.anchor_dipole.id if patch.anchor_dipole else None
        self.selected_dipole_id = anchor_id
        
        # 使用原始标识（hemi-vertno）代替内部 dipole_id
        if patch.anchor_dipole:
            display_name = f"{patch.anchor_dipole.hemi}-v{patch.anchor_dipole.vertno}" if patch.anchor_dipole.vertno is not None else anchor_id
            self.selected_dipole_label.setText(display_name)
        else:
            self.selected_dipole_label.setText(tr('label_none'))
        self.radius_spin.setValue(patch.radius * 1000)  # m to mm
        
        # 更新MRI Z轴坐标显示
        z_vox = self._get_dipole_z_vox(patch.anchor_dipole)
        if z_vox is not None:
            self.dipole_z_label.setText(f"MRI Z: {z_vox}")
            self.dipole_z_label.setStyleSheet("color: #4CAF50; font-size: 11px;")
        else:
            self.dipole_z_label.setText("MRI Z: --")
            self.dipole_z_label.setStyleSheet("color: gray; font-size: 11px;")
        
        # 设置 Label 显示
        self.selected_label = {'name': patch.label_name, 'hemi': patch.hemi}
        self.selected_label_display.setText(f"{patch.hemi}: {patch.label_name}")
        
        # 设置波形
        index = self.waveform_combo.findData(patch.waveform_type)
        if index >= 0:
            self.waveform_combo.setCurrentIndex(index)
        
        # 加载波形参数（完整版）
        params = patch.waveform_params
        if patch.waveform_type == 'sin':
            self.sin_amplitude.setValue(params.get('amplitude', 10.0))
            self.sin_frequency.setValue(params.get('frequency', 10.0))
            self.sin_phase.setValue(params.get('phase', 0.0))
            self.sin_offset.setValue(params.get('offset', 0.0))
            self.sin_onset.setValue(params.get('onset', 0.0))
            self.sin_duration.setValue(params.get('duration', 0.0))
        elif patch.waveform_type == 'cos':
            self.cos_amplitude.setValue(params.get('amplitude', 10.0))
            self.cos_frequency.setValue(params.get('frequency', 10.0))
            self.cos_phase.setValue(params.get('phase', 0.0))
            self.cos_offset.setValue(params.get('offset', 0.0))
            self.cos_onset.setValue(params.get('onset', 0.0))
            self.cos_duration.setValue(params.get('duration', 0.0))
        elif patch.waveform_type == 'erp':
            self.erp_amplitude.setValue(params.get('amplitude', 10.0))
            self.erp_frequency.setValue(params.get('frequency', 1.0))
            self.erp_latency.setValue(params.get('latency', 0.1))
            self.erp_width.setValue(params.get('width', 0.05))
            polarity_index = self.erp_polarity.findData(params.get('polarity', 'positive'))
            if polarity_index >= 0:
                self.erp_polarity.setCurrentIndex(polarity_index)
        elif patch.waveform_type == 'oscillation':
            self.oscillation_freq.setValue(params.get('freq', 10.0))
            self.oscillation_phase.setValue(params.get('phase', 0.0))
            self.oscillation_amp.setValue(params.get('amp', 20.0))
            self.oscillation_center.setValue(params.get('center', 0.5))
            self.oscillation_width.setValue(params.get('width', 0.1))
        elif patch.waveform_type == 'gaussian':
            self.gaussian_amplitude.setValue(params.get('amplitude', 10.0))
            self.gaussian_frequency.setValue(params.get('frequency', 10.0))
            self.gaussian_sigma.setValue(params.get('sigma', 0.1))
            self.gaussian_center.setValue(params.get('center', 0.5))
        elif patch.waveform_type == 'gamma':
            self.gamma_amplitude.setValue(params.get('amplitude', 10.0))
            self.gamma_frequency.setValue(params.get('frequency', 10.0))
            self.gamma_alpha.setValue(params.get('alpha', 2.0))
            self.gamma_beta.setValue(params.get('beta', 0.1))
        elif patch.waveform_type == 'custom':
            self.custom_amplitude.setValue(params.get('amplitude', 10.0))
            self.custom_frequency.setValue(params.get('frequency', 10.0))
            data = params.get('data', [])
            if isinstance(data, np.ndarray):
                data = data.tolist()
            self.custom_data.setPlainText(str(data))
        
        # 加载幅度因子
        self.amp_scale_spin.setValue(getattr(patch, 'amplitude_scale', 1e-9))
        
        # 更新显示
        self._update_nearby_dipoles()
        self._update_mri_plot()
    
    def _clear_form(self):
        """清空表单"""
        self.edit_title.setText(tr('title_create_patch'))
        self.current_patch_id = None
        self.selected_dipole_id = None
        self.selected_label = None
        
        self.patch_name.clear()
        self.selected_dipole_label.setText(tr('label_no_selection'))
        self.selected_dipole_label.setStyleSheet("color: gray;")
        self.dipole_z_label.setText("MRI Z: --")
        self.dipole_z_label.setStyleSheet("color: gray; font-size: 11px;")
        self.selected_label_display.setText(tr('label_selected_label') + " " + tr('label_none'))
        self.radius_spin.setValue(5.0)  # 5mm
        self.nearby_count_label.setText(tr('label_nearby_count', 0))
        
        self.save_btn.setEnabled(True)
        self.delete_btn.setEnabled(False)
        
        # 重置波形参数
        self._reset_waveform_params()
        
        # 清除临时存储的偶极子
        self._temp_dipoles.clear()
        
        # 清除选择
        self.patch_list.clearSelection()
        self.label_dipole_list.clear()
        self.label_table.clearSelection()
    
    def _reset_waveform_params(self):
        """重置所有波形参数到默认值"""
        # Sin
        self.sin_amplitude.setValue(10.0)
        self.sin_frequency.setValue(10.0)
        self.sin_phase.setValue(0.0)
        self.sin_offset.setValue(0.0)
        self.sin_onset.setValue(0.0)
        self.sin_duration.setValue(0.0)
        # Cos
        self.cos_amplitude.setValue(10.0)
        self.cos_frequency.setValue(10.0)
        self.cos_phase.setValue(0.0)
        self.cos_offset.setValue(0.0)
        self.cos_onset.setValue(0.0)
        self.cos_duration.setValue(0.0)
        # ERP
        self.erp_amplitude.setValue(10.0)
        self.erp_frequency.setValue(1.0)
        self.erp_latency.setValue(0.1)
        self.erp_width.setValue(0.05)
        self.erp_polarity.setCurrentIndex(0)
        # Gaussian
        self.gaussian_amplitude.setValue(10.0)
        self.gaussian_frequency.setValue(10.0)
        self.gaussian_sigma.setValue(0.1)
        self.gaussian_center.setValue(0.5)
        # Gamma
        self.gamma_amplitude.setValue(10.0)
        self.gamma_frequency.setValue(10.0)
        self.gamma_alpha.setValue(2.0)
        self.gamma_beta.setValue(0.1)
        # Oscillation
        self.oscillation_freq.setValue(10.0)
        self.oscillation_phase.setValue(0.0)
        self.oscillation_amp.setValue(20.0)
        self.oscillation_center.setValue(0.5)
        self.oscillation_width.setValue(0.1)
        # Custom
        self.custom_amplitude.setValue(10.0)
        self.custom_frequency.setValue(10.0)
        self.custom_data.clear()
    
    def refresh_patch_list(self):
        """刷新 Patch 列表"""
        self.patch_list.clear()
        
        # 从 parent_simulator 获取最新的 patches 引用
        patches = self.parent_simulator.patches
        logger.debug(f"刷新 Patch 列表，当前有 {len(patches)} 个 patches")
        
        for patch_id, patch in list(patches.items()):
            try:
                item = QListWidgetItem(
                    f"{patch.name} ({patch.get_dipole_count()} dipoles)"
                )
                item.setData(Qt.ItemDataRole.UserRole, patch_id)
                item.setToolTip(
                    f"ID: {patch_id}\n"
                    f"Label: {patch.label_name}\n"
                    f"Hemi: {patch.hemi}\n"
                    f"Anchor: {patch.anchor_dipole.id if patch.anchor_dipole else 'None'}\n"
                    f"Radius: {patch.radius*1000:.1f}mm\n"
                    f"Waveform: {patch.waveform_type}"
                )
                self.patch_list.addItem(item)
                logger.debug(f"  添加 Patch 到列表: {patch_id} - {patch.name}")
            except Exception as e:
                logger.error(f"添加 Patch {patch_id} 到列表时出错: {e}")
        
        logger.debug(f"Patch 列表刷新完成，共 {self.patch_list.count()} 项")
    
    def _update_label_table_style(self):
        """更新 Label 表格样式，适配当前主题"""
        self.label_table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {get_color('bg_card')};
                border: 1px solid {get_color('border')};
                border-radius: 4px;
                gridline-color: {get_color('border')};
            }}
            QTableWidget::item {{
                padding: 6px 10px;
                color: {get_color('text_main')};
                border-bottom: 1px solid {get_color('border')};
            }}
            QTableWidget::item:selected {{
                background-color: {get_color('accent')};
                color: {get_color('text_inverse')};
            }}
            QTableWidget::item:hover {{
                background-color: {get_color('border')}80;
            }}
            QHeaderView::section {{
                background-color: {get_color('bg_input')};
                color: {get_color('text_main')};
                padding: 8px 12px;
                border: 1px solid {get_color('border')};
                font-weight: bold;
            }}
            QHeaderView::section:first {{
                border-top-left-radius: 4px;
            }}
            QHeaderView::section:last {{
                border-top-right-radius: 4px;
            }}
            QTableCornerButton::section {{
                background-color: {get_color('bg_input')};
                border: 1px solid {get_color('border')};
            }}
        """)
    
    def update_theme(self):
        """更新主题颜色"""
        from ..themes import get_color
        bg_color = get_color('bg_card')
        text_color = get_color('text_main')
        border_color = get_color('border')
        accent_color = get_color('accent')
        
        # 更新 MRI 面板背景
        if hasattr(self, 'mri_panel'):
            self.mri_panel.setStyleSheet(f"background-color: {bg_color};")
        
        # 更新 MRI 图表背景
        if hasattr(self, 'fig') and hasattr(self, 'ax'):
            self.fig.set_facecolor(bg_color)
            self.ax.set_facecolor(bg_color)
            # 更新画布样式表
            if hasattr(self, 'canvas'):
                self.canvas.setStyleSheet(f"background-color: {bg_color};")
            # 更新滑块颜色
            if hasattr(self, 'slider_ax'):
                self.slider_ax.set_facecolor(bg_color)
                self.slider_ax.tick_params(colors=text_color)
            if hasattr(self, 'layer_slider'):
                self.layer_slider.label.set_color(text_color)
                self.layer_slider.valtext.set_color(text_color)
            # 重绘MRI
            self._update_mri_plot()
        
        # 更新波形预览
        if hasattr(self, 'waveform_fig') and hasattr(self, 'waveform_ax'):
            self.waveform_fig.set_facecolor(bg_color)
            self.waveform_ax.set_facecolor(bg_color)
            self.waveform_canvas.setStyleSheet(f"background-color: {bg_color};")
            self._update_waveform_preview()
        
        # 更新偶极子列表样式
        if hasattr(self, 'label_dipole_list'):
            self.label_dipole_list.setStyleSheet(f"""
                QListWidget {{
                    outline: none;
                    background-color: {bg_color};
                    border: 1px solid {border_color};
                    border-radius: 4px;
                }}
                QListWidget::item {{
                    padding: 6px 10px;
                    border-bottom: 1px solid {border_color};
                    color: {text_color};
                    font-size: 13px;
                }}
                QListWidget::item:selected {{
                    background-color: {accent_color};
                    color: {get_color('text_inverse')};
                    border-radius: 4px;
                    font-weight: bold;
                }}
                QListWidget::item:selected:!active {{
                    background-color: {accent_color};
                    color: {get_color('text_inverse')};
                }}
                QListWidget::item:hover:!selected {{
                    background-color: {border_color}80;
                }}
            """)
        
        # 更新 Label 表格样式
        if hasattr(self, 'label_table'):
            self._update_label_table_style()
        
        # 更新 Patch 列表样式
        if hasattr(self, 'patch_list'):
            self.patch_list.setStyleSheet(f"""
                QListWidget {{
                    outline: none;
                    background-color: {bg_color};
                    border: 1px solid {border_color};
                    border-radius: 4px;
                }}
                QListWidget::item {{
                    padding: 8px 12px;
                    border-bottom: 1px solid {border_color};
                    color: {text_color};
                }}
                QListWidget::item:selected {{
                    background-color: {accent_color};
                    color: {get_color('text_inverse')};
                    border-radius: 4px;
                }}
                QListWidget::item:hover:!selected {{
                    background-color: {border_color}80;
                }}
            """)
