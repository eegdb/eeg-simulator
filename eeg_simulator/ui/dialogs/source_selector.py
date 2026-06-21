"""源空间选择器对话框 - 使用MRI切片可视化"""

import os
import numpy as np
import nibabel as nib
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

from PyQt6.QtWidgets import (QDialog, QWidget, QVBoxLayout, QHBoxLayout,
                             QGroupBox, QPushButton, QLabel, QListWidget,
                             QListWidgetItem, QTreeWidget, QTreeWidgetItem,
                             QSplitter, QComboBox, QCheckBox, QMessageBox,
                             QFrame)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

import mne

from ..styles import COLORS
from ...utils import tr
from ...utils.mri_display import prepare_axial_slice, vox_to_display_xy


class SourceSpaceSelectorDialog(QDialog):
    """源空间选择器 - MRI切片视图"""

    def __init__(self, src, labels=None, label_source_map=None, subject=None, subjects_dir=None, parent=None):
        super().__init__(parent)
        self.src = src
        self.labels = labels or {'lh': {}, 'rh': {}}
        # 预计算的label-source映射
        self.label_source_map = label_source_map or {'lh': {}, 'rh': {}}
        self.subject = subject
        self.subjects_dir = subjects_dir
        
        # 尝试获取 subjects_dir
        if self.subjects_dir is None and self.subject:
            try:
                data_path = mne.datasets.sample.data_path()
                self.subjects_dir = os.path.join(data_path, 'subjects')
            except:
                pass
        
        self.setWindowTitle(f"{tr('panel_source_space')} - {subject or 'Unknown'}")
        self.setMinimumSize(1400, 900)

        # 数据存储
        self.all_vertices = []      # 所有顶点信息列表，每个元素是字典，包含 pos(物理坐标)、vox_pos(体素坐标)、vertno(顶点编号) 等
        self.selected_indices = set()  # 当前选中的顶点索引集合（对应 all_vertices 中的索引）
        self.label_colors = {}      # 解剖标签颜色映射
        self.t1_data = None         # MRI T1 加权图像数据 (3D numpy数组)
        self.vox_pts = None         # 所有源点转换后的体素坐标 (N x 3 数组，单位：体素)
        self.current_z = 128        # 当前显示的MRI切片Z层索引
        self.z_max = 255            # MRI数据最大Z层数
        
        # 加载MRI和源点
        self.load_mri_data()
        self.collect_vertices()
        
        self.init_ui()
        self.setup_label_tree()
        self.update_plot()

    def load_mri_data(self):
        # 目标：把大脑表面的源点画在MRI切片图像上
        """加载MRI T1数据和源点坐标
        
        坐标系说明：
        - RAS坐标系：神经影像学标准坐标系
          * R (X+): 向右
          * A (Y+): 向前 (朝向面部)
          * S (Z+): 向上 (朝向头顶)
          * 原点(0,0,0)：大致位于前连合(AC)附近，即大脑解剖学中心
        - 单位：米(m)
        
        体素坐标系：
        - MRI图像的体素索引坐标 (i, j, k)
        - 单位：体素(voxel)
        - 通过 vox2ras 变换矩阵与RAS坐标相互转换
        """
        try:
            if self.subjects_dir and self.subject:
                t1_path = os.path.join(self.subjects_dir, self.subject, 'mri', 'T1.mgz')
                
                if os.path.exists(t1_path):
                    print(f"Loading MRI: {t1_path}")
                    img = nib.load(t1_path)
                    self.t1_data = img.get_fdata()
                    
                    # 获取变换矩阵：vox2ras_tkr 是FreeSurfer的TKregister格式
                    # 它将MRI体素坐标(voxel)转换为RAS物理坐标(mm)
                    vox2ras = img.header.get_vox2ras_tkr()
                    ras2vox = np.linalg.inv(vox2ras)  # 逆变换：RAS -> 体素
                    
                    # 提取所有源点坐标
                    # s['rr'] 是MNE源空间中的顶点坐标，单位：米(m)，坐标系：RAS
                    # 需要乘以1000转换为毫米(mm)，因为vox2ras矩阵期望的是mm单位
                    src_pts = np.vstack([s['rr'] for s in self.src]) * 1000
                    
                    # 转换为齐次坐标 (添加第4维为1，用于矩阵变换)
                    src_pts_homo = np.hstack([src_pts, np.ones((len(src_pts), 1))])
                    
                    # 应用逆变换，将RAS物理坐标(mm)转换为MRI体素坐标
                    # 结果vox_pts[i] = [x_vox, y_vox, z_vox]，表示第i个源点在MRI中的体素位置
                    self.vox_pts = (src_pts_homo @ ras2vox.T)[:, :3]
                    
                    self.z_max = self.t1_data.shape[2] - 1
                    self.current_z = self.z_max // 2
                    
                    print(f"MRI loaded: shape={self.t1_data.shape}, {len(self.vox_pts)} source points")
                else:
                    print(f"MRI file not found: {t1_path}")
                    self.init_fallback_data()
            else:
                print(f"No subjects_dir or subject provided")
                self.init_fallback_data()
        except Exception as e:
            print(f"Error loading MRI: {e}")
            import traceback
            traceback.print_exc()
            self.init_fallback_data()
    
    def init_fallback_data(self):
        """初始化备选数据（当MRI不可用时）
        
        当无法加载MRI T1图像时，使用简化的坐标系统：
        - 直接使用源空间的rr坐标(米) * 1000 作为伪体素坐标
        - 此时体素坐标与物理坐标只是单位不同(1000倍关系)
        """
        self.t1_data = np.zeros((256, 256, 256), dtype=np.uint8)
        # 创建一个简单的渐变作为背景
        for i in range(256):
            self.t1_data[:, :, i] = i
        
        # 使用源空间的坐标（假设已在体素空间）
        all_pts = []
        for s in self.src:
            pts = s['rr'].copy() * 1000  # 转换为毫米
            all_pts.extend(pts)
        
        if all_pts:
            self.vox_pts = np.array(all_pts)
        else:
            self.vox_pts = np.zeros((0, 3))
        
        self.z_max = 255
        self.current_z = 128
        print(f"Using fallback data: {len(self.vox_pts)} points")

    def collect_vertices(self):
        """收集所有顶点信息
        
        构建 all_vertices 列表，每个顶点包含以下信息：
        - pos: [x, y, z] 物理坐标，单位：米(m)，RAS坐标系
                 RAS坐标系定义：X+右，Y+前，Z+上，原点在大脑中心
        - vox_pos: [x, y, z] 体素坐标，单位：体素(voxel)
                   对应MRI切片的实际像素索引，范围约 0~255
        - ori: [nx, ny, nz] 表面法向量（顶点朝外的方向）
        - hemi: 'lh'(左半球) 或 'rh'(右半球)
        - vertno: 顶点编号，在原始表面网格中的索引号
                  注意：vertno只是编号，与坐标值无关！
        - src_idx: 源空间索引(0=左半球, 1=右半球)
        - index: 在all_vertices中的顺序索引
        
        注意区分：
        - vertno: 顶点的ID编号（如1234）
        - pos[2]: 物理Z坐标（如0.085米 = 头顶附近）
        - vox_pos[2]: MRI切片层号（如180 = 第180层）
        """
        self.all_vertices = []
        idx = 0
        vox_idx_offset = 0
        
        for src_idx, s in enumerate(self.src):
            if s['type'] == 'surf':
                hemi = 'lh' if src_idx == 0 else 'rh'
                
                # 计算该半球在vox_pts中的起始索引
                # vox_pts是按src顺序堆叠的：先左半球所有顶点，后右半球所有顶点
                # 每个s['rr']包含该半球表面网格的所有顶点坐标
                n_rr = len(s['rr'])  # 该半球表面网格的顶点总数
                
                # s['vertno'] 是当前源空间实际使用的顶点索引列表
                # 例如oct-6采样可能只使用几千个顶点，而原始网格可能有十几万个
                for i, vert_idx in enumerate(s['vertno']):
                    # vert_idx: 顶点在原始表面网格(s['rr'])中的索引
                    # 使用vox_idx_offset + vert_idx 索引 vox_pts，因为vox_pts包含所有顶点
                    if self.vox_pts is not None and (vox_idx_offset + vert_idx) < len(self.vox_pts):
                        vox_pos = self.vox_pts[vox_idx_offset + vert_idx]
                    else:
                        # 备选方案：将物理坐标(m)简单转换为伪体素坐标(mm)
                        pos = s['rr'][vert_idx]
                        vox_pos = pos * 1000
                    
                    # s['rr'][vert_idx]: 获取该顶点的RAS物理坐标，单位：米
                    # 典型值范围：X约±0.07m，Y约±0.10m，Z约-0.06~+0.09m
                    pos = s['rr'][vert_idx]
                    
                    # s['nn'][vert_idx]: 该顶点的表面法向量（方向朝外）
                    ori = s['nn'][vert_idx] if 'nn' in s else [0, 0, 1]
                    
                    self.all_vertices.append({
                        'pos': pos,           # 物理坐标 [x, y, z] 单位：米
                        'vox_pos': vox_pos,   # 体素坐标 [x, y, z] 单位：体素索引
                        'ori': ori,           # 法向量 [nx, ny, nz]
                        'hemi': hemi,         # 半球 'lh' 或 'rh'
                        'vertno': vert_idx,   # 顶点编号（原始网格中的索引）
                        'src_idx': src_idx,   # 源空间索引 0或1
                        'index': idx          # 在all_vertices中的序号
                    })
                    idx += 1
                
                # 更新偏移量，为下一个半球做准备
                vox_idx_offset += n_rr
        
        print(f"Collected {len(self.all_vertices)} vertices: LH={sum(1 for v in self.all_vertices if v['hemi']=='lh')}, RH={sum(1 for v in self.all_vertices if v['hemi']=='rh')}")

    def init_ui(self):
        """初始化UI"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # 左侧：MRI切片可视化
        left_frame = QFrame()
        left_frame.setFrameShape(QFrame.Shape.StyledPanel)
        left_layout = QVBoxLayout(left_frame)
        left_layout.setContentsMargins(5, 5, 5, 5)

        # 标题
        title = QLabel(tr('panel_source_space'))
        title.setObjectName("SubTitle")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_layout.addWidget(title)

        # Matplotlib图形
        self.fig = Figure(figsize=(8, 8), facecolor='black')
        # 减少边距，使图像填满画布
        self.fig.subplots_adjust(left=0.02, right=0.98, top=0.95, bottom=0.02)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor('black')
        
        self.canvas = FigureCanvas(self.fig)
        self.canvas.setStyleSheet("background-color: black;")
        left_layout.addWidget(self.canvas)

        # 在Matplotlib figure中添加滑块
        # 调整子图位置，为滑块留出空间
        self.fig.subplots_adjust(bottom=0.15)
        
        # 创建滑块轴
        self.slider_ax = self.fig.add_axes([0.15, 0.02, 0.7, 0.03])
        self.layer_slider = Slider(
            self.slider_ax, 
            'Z Layer', 
            0, 
            self.z_max, 
            valinit=self.current_z,
            valfmt='%d',
            color='#10b981',      # 已滑动区域的颜色（主题绿色）
            initcolor='#ef4444'   # 中值标记红线
        )
        self.layer_slider.on_changed(self.on_slider_changed)
        
        # 滑块标签样式
        self.slider_ax.tick_params(colors='white')
        self.slider_ax.xaxis.label.set_color('white')
        
        # 添加当前值显示文本
        self.value_text = self.fig.text(0.88, 0.03, f'{self.current_z}', 
                                        color='white', fontsize=11, fontweight='bold')

        # 工具栏
        toolbar = NavigationToolbar(self.canvas, self)
        left_layout.addWidget(toolbar)

        # 鼠标点击事件
        self.canvas.mpl_connect('button_press_event', self.on_click)

        # 右侧：控制面板
        right_widget = QWidget()
        right_widget.setFixedWidth(340)
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(10, 10, 10, 10)

        # 选择模式
        mode_group = QGroupBox(tr('label_selection_mode'))
        mode_layout = QHBoxLayout(mode_group)

        self.mode_single = QPushButton(tr('label_single_select'))
        self.mode_single.setCheckable(True)
        self.mode_single.setChecked(True)
        self.mode_single.setObjectName("PrimaryBtn")
        self.mode_single.clicked.connect(lambda: self.set_selection_mode('single'))
        mode_layout.addWidget(self.mode_single)

        self.mode_multi = QPushButton(tr('label_multi_select'))
        self.mode_multi.setCheckable(True)
        self.mode_multi.setObjectName("PrimaryBtn")
        self.mode_multi.clicked.connect(lambda: self.set_selection_mode('multi'))
        mode_layout.addWidget(self.mode_multi)

        right_layout.addWidget(mode_group)

        # 半球筛选
        hemi_group = QGroupBox(tr('label_display_hemisphere'))
        hemi_layout = QHBoxLayout(hemi_group)

        self.show_lh = QCheckBox(tr('label_left'))
        self.show_lh.setChecked(True)
        self.show_lh.stateChanged.connect(self.update_plot)
        hemi_layout.addWidget(self.show_lh)

        self.show_rh = QCheckBox(tr('label_right'))
        self.show_rh.setChecked(True)
        self.show_rh.stateChanged.connect(self.update_plot)
        hemi_layout.addWidget(self.show_rh)

        right_layout.addWidget(hemi_group)

        # 标签分组面板 (Anatomy Labels 在 Selected Points 上面)
        self.setup_label_group_panel(right_layout)

        # 选中列表
        list_group = QGroupBox(tr('panel_selected_points'))
        list_layout = QVBoxLayout(list_group)

        self.selected_list = QListWidget()
        list_layout.addWidget(self.selected_list)

        btn_layout = QHBoxLayout()

        select_all_btn = QPushButton(tr('btn_select_all'))
        select_all_btn.setObjectName("PrimaryBtn")
        select_all_btn.clicked.connect(self.select_all_vertices)
        btn_layout.addWidget(select_all_btn)

        clear_btn = QPushButton(tr('btn_clear'))
        clear_btn.setObjectName("StopBtn")
        clear_btn.clicked.connect(self.clear_selection)
        btn_layout.addWidget(clear_btn)

        remove_btn = QPushButton(tr('btn_remove'))
        remove_btn.setObjectName("StopBtn")
        remove_btn.clicked.connect(self.remove_selected_from_list)
        btn_layout.addWidget(remove_btn)

        list_layout.addLayout(btn_layout)
        right_layout.addWidget(list_group)

        # 统计
        self.info_label = QLabel(tr('label_points_selected', 0))
        self.info_label.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 12px;")
        right_layout.addWidget(self.info_label)

        right_layout.addStretch()

        # 确定/取消
        btn_layout = QHBoxLayout()

        cancel_btn = QPushButton(tr('btn_cancel'))
        cancel_btn.setObjectName("StopBtn")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        ok_btn = QPushButton(tr('btn_save'))
        ok_btn.setObjectName("PrimaryBtn")
        ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(ok_btn)

        right_layout.addLayout(btn_layout)

        # 分割器
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_frame)
        splitter.addWidget(right_widget)
        splitter.setSizes([800, 340])
        layout.addWidget(splitter)

        self.selection_mode = 'single'

    def on_slider_changed(self, value):
        """滑块值改变"""
        self.current_z = int(value)
        # 更新数值显示
        if hasattr(self, 'value_text'):
            self.value_text.set_text(f'{self.current_z}')
        self.update_plot()

    def set_selection_mode(self, mode):
        """设置选择模式"""
        self.selection_mode = mode
        if mode == 'single':
            self.mode_single.setChecked(True)
            self.mode_multi.setChecked(False)
        else:
            self.mode_single.setChecked(False)
            self.mode_multi.setChecked(True)

    def setup_label_group_panel(self, parent_layout):
        """设置标签分组面板"""
        label_group = QGroupBox(tr('panel_anatomy_labels'))
        label_layout = QVBoxLayout(label_group)

        self.atlas_combo = QComboBox()
        self.atlas_combo.addItem("Desikan-Killiany (aparc)", "aparc")
        self.atlas_combo.addItem("Destrieux (a2009s)", "a2009s")
        self.atlas_combo.currentIndexChanged.connect(self.on_atlas_changed)
        label_layout.addWidget(QLabel(tr('label_select_atlas')))
        label_layout.addWidget(self.atlas_combo)

        # 使用左右分栏显示两个树形控件
        tree_container = QWidget()
        tree_layout = QHBoxLayout(tree_container)
        tree_layout.setContentsMargins(0, 0, 0, 0)
        tree_layout.setSpacing(5)

        # 左半球树
        lh_group = QGroupBox(tr('label_left'))
        lh_layout = QVBoxLayout(lh_group)
        lh_layout.setContentsMargins(5, 5, 5, 5)
        
        self.lh_tree = QTreeWidget()
        self.lh_tree.setHeaderHidden(True)
        self.lh_tree.setIndentation(0)  # 去除左侧缩进空白
        self.lh_tree.setRootIsDecorated(False)  # 隐藏根节点装饰
        self.lh_tree.itemChanged.connect(self.on_label_item_changed)
        lh_layout.addWidget(self.lh_tree)
        tree_layout.addWidget(lh_group)

        # 右半球树
        rh_group = QGroupBox(tr('label_right'))
        rh_layout = QVBoxLayout(rh_group)
        rh_layout.setContentsMargins(5, 5, 5, 5)
        
        self.rh_tree = QTreeWidget()
        self.rh_tree.setHeaderHidden(True)
        self.rh_tree.setIndentation(0)  # 去除左侧缩进空白
        self.rh_tree.setRootIsDecorated(False)  # 隐藏根节点装饰
        self.rh_tree.itemChanged.connect(self.on_label_item_changed)
        rh_layout.addWidget(self.rh_tree)
        tree_layout.addWidget(rh_group)

        label_layout.addWidget(tree_container)

        btn_layout = QHBoxLayout()

        highlight_btn = QPushButton(tr('btn_highlight'))
        highlight_btn.setObjectName("PrimaryBtn")
        highlight_btn.clicked.connect(self.highlight_selected_labels)
        btn_layout.addWidget(highlight_btn)

        select_btn = QPushButton(tr('btn_select'))
        select_btn.setObjectName("PrimaryBtn")
        select_btn.clicked.connect(self.select_all_in_label)
        btn_layout.addWidget(select_btn)

        label_layout.addLayout(btn_layout)
        parent_layout.addWidget(label_group)

    def on_label_item_changed(self, item, column):
        """标签项状态改变 - 只处理label层级的勾选"""
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return

        item_type = data.get('type')
        check_state = item.checkState(0)

        if item_type == 'label':
            # Label被勾选/取消，直接选中/取消该label下的所有source
            sources = data.get('sources', [])
            if check_state == Qt.CheckState.Checked:
                for source_info in sources:
                    self.selected_indices.add(source_info['index'])
            else:
                for source_info in sources:
                    self.selected_indices.discard(source_info['index'])
        
        self.update_plot()

    def highlight_selected_labels(self):
        """高亮显示选中的标签"""
        selected_labels = []
        
        # 遍历左右两棵树
        for tree in [self.lh_tree, self.rh_tree]:
            root = tree.invisibleRootItem()
            for i in range(root.childCount()):
                label_item = root.child(i)
                if label_item.checkState(0) in (Qt.CheckState.Checked, Qt.CheckState.PartiallyChecked):
                    data = label_item.data(0, Qt.ItemDataRole.UserRole)
                    if data and data.get('type') == 'label':
                        selected_labels.append(data)

        if not selected_labels:
            QMessageBox.information(self, tr('warning'), tr('msg_select_region_first'))
            return

        self.update_plot(highlight_labels=selected_labels)

    def select_all_in_label(self):
        """选择选中标签内的所有源点"""
        count = 0
        
        # 遍历左右两棵树
        for tree in [self.lh_tree, self.rh_tree]:
            root = tree.invisibleRootItem()
            for i in range(root.childCount()):
                label_item = root.child(i)
                
                if label_item.checkState(0) == Qt.CheckState.Checked:
                    label_data = label_item.data(0, Qt.ItemDataRole.UserRole)
                    if label_data and label_data.get('type') == 'label':
                        sources = label_data.get('sources', [])
                        for source_info in sources:
                            self.selected_indices.add(source_info['index'])
                            count += 1

        if count == 0:
            QMessageBox.information(self, tr('warning'), tr('msg_select_region_for_points'))
            return

        self.update_plot()
        QMessageBox.information(self, tr('success'), tr('msg_selection_complete', count))

    def on_atlas_changed(self, index):
        """Atlas选择改变时重新加载标签树"""
        self.setup_label_tree()
    
    def _get_current_atlas(self):
        """获取当前选择的atlas名称"""
        return self.atlas_combo.currentData()
    
    def _filter_labels_by_atlas(self, label_name, atlas):
        """根据atlas过滤label名称
        
        Label名称格式（从.annot文件加载后）：
        - Desikan-Killiany (aparc): {label_name}-{hemi} (如: superiortemporal-lh)
        - Destrieux (a2009s): a2009s.{label_name}-{hemi} (如: a2009s.G_and_S_frontomargin-lh)
        """
        # 统一使用小写进行匹配
        label_lower = label_name.lower()
        
        if atlas == 'a2009s':
            # Destrieux atlas: 以 'a2009s.' 开头的label名称
            return label_lower.startswith('a2009s.')
        else:
            # Desikan-Killiany atlas: 不以 'a2009s.' 开头的label名称
            return not label_lower.startswith('a2009s.')

    def setup_label_tree(self):
        """初始化标签树 - 只显示label层级"""
        self.lh_tree.clear()
        self.rh_tree.clear()

        # 临时断开信号连接，避免批量创建时频繁触发update_plot
        self.lh_tree.itemChanged.disconnect(self.on_label_item_changed)
        self.rh_tree.itemChanged.disconnect(self.on_label_item_changed)

        try:
            colors = plt.cm.Set3(np.linspace(0, 1, 50))
            color_idx = 0
            
            # 获取当前选择的atlas
            current_atlas = self._get_current_atlas()
            
            # 调试：打印所有可用的label
            all_labels = []
            for hemi in ['lh', 'rh']:
                source_map = self.label_source_map.get(hemi, {})
                all_labels.extend(list(source_map.keys()))
            print(f"[SourceSelector] Available labels ({len(all_labels)} total): {all_labels[:5]}...")
            print(f"[SourceSelector] Current atlas: {current_atlas}")

            # 使用预计算的label_source_map构建树，只创建label项
            matched_count = 0
            for hemi, tree_widget in [('lh', self.lh_tree), ('rh', self.rh_tree)]:
                source_map = self.label_source_map.get(hemi, {})
                
                for label_name in sorted(source_map.keys()):
                    # 根据当前atlas过滤
                    if not self._filter_labels_by_atlas(label_name, current_atlas):
                        continue
                    
                    sources = source_map[label_name]
                    
                    if not sources:
                        continue
                    
                    matched_count += 1
                    
                    # 清理显示名称（去掉atlas前缀和hemi后缀）
                    display_name = label_name
                    if label_name.lower().startswith('a2009s.'):
                        # 移除 a2009s. 前缀，如: a2009s.G_and_S_frontomargin-lh -> G_and_S_frontomargin-lh
                        display_name = label_name[7:]  # len('a2009s.') == 7

                    # 创建label项（不再创建source子项）
                    label_item = QTreeWidgetItem(tree_widget)
                    label_item.setText(0, f"{display_name} ({len(sources)})")
                    label_item.setFlags(label_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                    label_item.setCheckState(0, Qt.CheckState.Unchecked)
                    label_item.setData(0, Qt.ItemDataRole.UserRole, {
                        'type': 'label',
                        'hemi': hemi,
                        'name': label_name,  # 保留原始名称用于查找
                        'sources': sources
                    })

                    # 颜色
                    if label_name not in self.label_colors:
                        self.label_colors[label_name] = colors[color_idx % len(colors)][:3]
                        color_idx += 1
            
            print(f"[SourceSelector] Matched {matched_count} labels for atlas '{current_atlas}'")
        finally:
            # 恢复信号连接
            self.lh_tree.itemChanged.connect(self.on_label_item_changed)
            self.rh_tree.itemChanged.connect(self.on_label_item_changed)

    def update_plot(self, highlight_labels=None):
        """更新MRI切片图
        
        绘制当前Z层的MRI切片，并在其上叠加显示源空间顶点。
        
        坐标转换说明：
        - vox_pos 是体素坐标 [x, y, z]，其中 z 对应MRI切片层号
        - 切片经 rot90 + flipud 校正为放射学方向（A 在上、P 在下）
        - 散点坐标与体素 x/y 一一对应：display = (vox_x, vox_y)
        - 只显示当前Z层附近 (current_z ± z_tolerance) 的顶点
        """
        self.ax.clear()
        self.ax.set_facecolor('black')

        if self.t1_data is None:
            return

        # 显示MRI切片 (rot90 + flipud 使前后方向与放射学惯例一致)
        z = self.current_z
        slice_data = prepare_axial_slice(self.t1_data, z)
        
        self.ax.imshow(slice_data, cmap='gray', vmin=0, vmax=150, aspect='equal')
        self.ax.set_title(f'Z = {z} | Face↑ | Click points to select', color='white', fontsize=11)
        
        # 紧凑显示，减少边距
        self.ax.set_xlim(0, slice_data.shape[1])
        self.ax.set_ylim(0, slice_data.shape[0])
        self.ax.axis('off')  # 隐藏坐标轴，最大化显示区域
        
        # 添加方向指示
        # 在图像边缘添加方向文字（使用放射学惯例：左=R，右=L）
        img_height, img_width = slice_data.shape
        
        # 上方 - 前/脸的方向
        self.ax.text(img_width/2, 20, 'A (Face)', color='yellow', fontsize=12, 
                    ha='center', va='top', fontweight='bold',
                    bbox=dict(boxstyle='round,pad=0.3', facecolor='black', alpha=0.7))
        
        # 下方 - 后
        self.ax.text(img_width/2, img_height-20, 'P (Back)', color='yellow', fontsize=12,
                    ha='center', va='bottom', fontweight='bold',
                    bbox=dict(boxstyle='round,pad=0.3', facecolor='black', alpha=0.7))
        
        # 左侧 - 患者的右
        self.ax.text(20, img_height/2, 'R', color='cyan', fontsize=14,
                    ha='left', va='center', fontweight='bold',
                    bbox=dict(boxstyle='round,pad=0.3', facecolor='black', alpha=0.7))
        
        # 右侧 - 患者的左
        self.ax.text(img_width-20, img_height/2, 'L', color='cyan', fontsize=14,
                    ha='right', va='center', fontweight='bold',
                    bbox=dict(boxstyle='round,pad=0.3', facecolor='black', alpha=0.7))
        
        # 添加中心十字线帮助定位
        self.ax.axhline(y=img_height/2, color='gray', linestyle='--', alpha=0.3, linewidth=0.5)
        self.ax.axvline(x=img_width/2, color='gray', linestyle='--', alpha=0.3, linewidth=0.5)

        # 准备散点数据
        show_lh = self.show_lh.isChecked()
        show_rh = self.show_rh.isChecked()
        z_tolerance = 5  # 层数容差

        # 构建标签颜色查找表
        vert_label_color = {}
        if highlight_labels and isinstance(highlight_labels, list):
            for label_data in highlight_labels:
                hemi = label_data['hemi']
                color = self.label_colors.get(label_data['name'], [1, 0, 0])
                for vertno in label_data['vertices']:
                    vert_label_color[(hemi, vertno)] = color

        # 收集要显示的点
        lh_pts = []
        rh_pts = []
        highlighted_pts = []
        selected_lh = []
        selected_rh = []

        for v in self.all_vertices:
            hemi = v['hemi']
            
            # 检查半球显示
            if (hemi == 'lh' and not show_lh) or (hemi == 'rh' and not show_rh):
                continue

            # 检查Z层
            vox_z = v['vox_pos'][2]
            if abs(vox_z - z) > z_tolerance:
                continue

            # 转换坐标 (vox_x, vox_y) 与 prepare_axial_slice 输出对齐
            display_x, display_y = vox_to_display_xy(v['vox_pos'])

            pt = (display_x, display_y, v['index'])

            # 分类
            is_selected = v['index'] in self.selected_indices
            
            if is_selected:
                if hemi == 'lh':
                    selected_lh.append(pt)
                else:
                    selected_rh.append(pt)
            else:
                key = (hemi, v['vertno'])
                if key in vert_label_color:
                    highlighted_pts.append((display_x, display_y, vert_label_color[key]))
                elif hemi == 'lh':
                    lh_pts.append(pt)
                else:
                    rh_pts.append(pt)
        
        # 调试输出
        print(f"Z={z}: LH={len(lh_pts)} (selected={len(selected_lh)}), RH={len(rh_pts)} (selected={len(selected_rh)}), Highlight={len(highlighted_pts)}")

        # 绘制点 (注意绘制顺序：底层先画)
        
        # 1. 普通未选中的点 - 使用更明显的发光颜色
        if lh_pts:
            xs, ys, _ = zip(*lh_pts)
            self.ax.scatter(xs, ys, c='lime', s=30, alpha=0.8, edgecolors='white', linewidths=0.5, zorder=5)
        
        if rh_pts:
            xs, ys, _ = zip(*rh_pts)
            self.ax.scatter(xs, ys, c='red', s=30, alpha=0.8, edgecolors='white', linewidths=0.5, zorder=5)

        # 2. 高亮的点
        if highlighted_pts:
            xs, ys, colors = zip(*highlighted_pts)
            self.ax.scatter(xs, ys, c=colors, s=60, alpha=0.9, edgecolors='white', linewidths=1, zorder=7)

        # 3. 选中的点 (最上层，黄色星形)
        all_selected = selected_lh + selected_rh
        if all_selected:
            xs, ys, _ = zip(*all_selected)
            self.ax.scatter(xs, ys, c='yellow', s=200, marker='*', 
                          edgecolors='red', linewidths=2, zorder=10)

        self.canvas.draw()
        self.update_selected_list()

    def on_click(self, event):
        """处理鼠标点击"""
        if event.inaxes != self.ax:
            return

        x, y = event.xdata, event.ydata
        if x is None or y is None:
            return

        # 找到最近的源点
        min_dist = float('inf')
        closest_idx = None
        z_tolerance = 5

        for v in self.all_vertices:
            # 检查Z层
            if abs(v['vox_pos'][2] - self.current_z) > z_tolerance:
                continue

            # 计算2D距离
            vx, vy = vox_to_display_xy(v['vox_pos'])
            dist = ((vx - x)**2 + (vy - y)**2)**0.5

            if dist < min_dist:
                min_dist = dist
                closest_idx = v['index']

        # 距离阈值 (像素)
        if min_dist > 10:
            return

        # 更新选择
        if self.selection_mode == 'single':
            self.selected_indices.clear()
            self.selected_indices.add(closest_idx)
        else:
            if closest_idx in self.selected_indices:
                self.selected_indices.remove(closest_idx)
            else:
                self.selected_indices.add(closest_idx)

        self.update_plot()

    def update_selected_list(self):
        """更新选中列表显示
        
        显示格式："左半球 | V顶点号 | Z体素层 | (X, Y, Z)"
        
        各字段含义：
        - 左半球/右半球：解剖学半球位置
        - V顶点号：vertno，顶点在原始表面网格中的编号（纯ID，与位置无关）
        - Z体素层：vox_pos[2]，该顶点在MRI第几层切片上（0~255）
        - (X, Y, Z)：pos，物理坐标，单位米，RAS坐标系
          * X：左右，正值向右（如+0.052 = 右方5.2cm）
          * Y：前后，正值向前（如-0.018 = 后方1.8cm）
          * Z：上下，正值向上（如+0.095 = 头顶方向9.5cm）
        
        注意：顶点号(V)和Z层号是两个完全不同的概念！
        """
        self.selected_list.clear()
        for idx in sorted(self.selected_indices):
            v = self.all_vertices[idx]
            hemi_text = tr('label_left') if v['hemi'] == 'lh' else tr('label_right')
            item = QListWidgetItem(
                f"{hemi_text} | V{v['vertno']} | Z{v['vox_pos'][2]:.0f} | "
                f"({v['pos'][0]:.3f}, {v['pos'][1]:.3f}, {v['pos'][2]:.3f})"
            )
            item.setData(Qt.ItemDataRole.UserRole, idx)
            self.selected_list.addItem(item)

        self.info_label.setText(tr('label_points_selected', len(self.selected_indices)))

    def select_all_vertices(self):
        """选择当前层可见的所有顶点"""
        z = self.current_z
        z_tolerance = 5
        
        for v in self.all_vertices:
            if abs(v['vox_pos'][2] - z) <= z_tolerance:
                self.selected_indices.add(v['index'])
        
        self.update_plot()

    def clear_selection(self):
        """清空选择"""
        self.selected_indices.clear()
        self.update_plot()

    def remove_selected_from_list(self):
        """从列表移除选中项"""
        for item in self.selected_list.selectedItems():
            idx = item.data(Qt.ItemDataRole.UserRole)
            if idx in self.selected_indices:
                self.selected_indices.remove(idx)
        self.update_plot()

    def get_selected_vertices(self):
        """获取选中的顶点"""
        return [self.all_vertices[idx] for idx in self.selected_indices]
