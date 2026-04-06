"""电极布局页面 - NavigationView 布局"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
                             QLabel, QComboBox, QPushButton, QFrame)
from PyQt6.QtCore import Qt

from ..themes import get_color
from ..widgets.navigation_view import NavigationPage
from ..widgets.head_layout import HeadLayoutSelector
from ...utils import tr


class ElectrodePage(NavigationPage):
    """电极布局页面"""
    
    def __init__(self, parent_simulator, parent=None):
        self.parent_simulator = parent_simulator
        super().__init__(
            title=tr('nav_electrode'),
            subtitle=tr('nav_electrode_subtitle'),
            parent=parent
        )
        
        self._setup_content()
    
    def _setup_content(self):
        """设置页面内容"""
        layout = self.get_content_layout()
        
        # 布局选择
        layout_group = QGroupBox(tr('label_layout'))
        layout_select_layout = QVBoxLayout(layout_group)
        
        self.layout_combo = QComboBox()
        self.layout_combo.addItem('Standard 10-20', 'standard_1020')
        self.layout_combo.addItem('Standard 10-10', 'standard_1010')
        self.layout_combo.addItem('Standard 1005', 'standard_1005')
        self.layout_combo.addItem('Easycap M1', 'easycap-M1')
        self.layout_combo.addItem('Easycap M10', 'easycap-M10')
        self.layout_combo.addItem('Biosemi 16', 'biosemi16')
        self.layout_combo.addItem('Biosemi 32', 'biosemi32')
        self.layout_combo.addItem('Biosemi 64', 'biosemi64')
        self.layout_combo.currentIndexChanged.connect(self._on_layout_changed)
        layout_select_layout.addWidget(self.layout_combo)
        
        layout.addWidget(layout_group)
        
        # 头部布局可视化
        viz_group = QGroupBox(tr('panel_head_layout'))
        viz_layout = QVBoxLayout(viz_group)
        viz_layout.setContentsMargins(4, 4, 4, 4)  # 减小边距以节省空间
        viz_layout.setSpacing(4)
        
        self.head_selector = HeadLayoutSelector(on_layout_changed=self._on_head_layout_changed)
        self.head_selector.setMinimumHeight(300)  # 降低最小高度要求
        viz_layout.addWidget(self.head_selector, 1)  # 添加拉伸因子以填充空间
        
        # 热力图控制
        self.heatmap_frame = QFrame()
        self.heatmap_frame.setStyleSheet(f"""
            background-color: {get_color('bg_input')};
            border-radius: 8px;
            border: 1px solid {get_color('border')};
        """)
        heatmap_layout = QHBoxLayout(self.heatmap_frame)
        heatmap_layout.setContentsMargins(16, 12, 16, 12)
        
        self.clear_heatmap_btn = QPushButton(tr('btn_clear_heatmap'))
        self.clear_heatmap_btn.clicked.connect(self._on_clear_heatmap)
        heatmap_layout.addWidget(self.clear_heatmap_btn)
        
        heatmap_layout.addStretch()
        
        self.heatmap_info_label = QLabel(tr('heatmap_info'))
        self.heatmap_info_label.setStyleSheet(f"color: {get_color('text_muted')}; font-size: 12px;")
        heatmap_layout.addWidget(self.heatmap_info_label)
        
        viz_layout.addWidget(self.heatmap_frame)
        layout.addWidget(viz_group)
        
        layout.addStretch()
    
    def _on_layout_changed(self, index):
        """布局选择改变"""
        layout_key = self.layout_combo.currentData()
        self.head_selector.set_layout(layout_key)
        # 通知父级更新通道列表
        if hasattr(self.parent_simulator, '_on_layout_changed'):
            self.parent_simulator._on_layout_changed(layout_key)
    
    def _on_head_layout_changed(self, layout_key):
        """头部布局改变回调"""
        pass
    
    def _on_clear_heatmap(self):
        """清除热力图"""
        self.head_selector.clear_heatmap()
    
    def get_head_widget(self):
        """获取头部布局部件"""
        return self.head_selector.get_head_widget()
    
    def update_heatmap(self, channel_activities):
        """更新热力图"""
        self.head_selector.update_heatmap(channel_activities)
    
    def get_current_montage(self):
        """获取当前选中的电极布局"""
        if hasattr(self.head_selector, 'head_widget') and hasattr(self.head_selector.head_widget, '_montage'):
            return self.head_selector.head_widget._montage
        return None
    
    def get_current_layout_key(self):
        """获取当前布局的 key"""
        return self.layout_combo.currentData()
    
    def update_theme(self):
        """更新主题颜色"""
        # 调用父类方法更新基础样式（标题、背景等）
        super().update_theme()
        
        # 更新热力图控制框架
        if hasattr(self, 'heatmap_frame'):
            self.heatmap_frame.setStyleSheet(f"""
                background-color: {get_color('bg_input')};
                border-radius: 8px;
                border: 1px solid {get_color('border')};
            """)
        
        # 更新热力图信息标签
        if hasattr(self, 'heatmap_info_label'):
            self.heatmap_info_label.setStyleSheet(f"color: {get_color('text_muted')}; font-size: 12px;")
