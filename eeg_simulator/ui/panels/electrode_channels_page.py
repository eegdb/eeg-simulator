"""电极布局与通道选择页面 - NavigationView 布局

合并原 ElectrodePage 和 ChannelsPage 的功能
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
                             QLabel, QComboBox, QPushButton, QFrame, QListWidget,
                             QListWidgetItem, QSplitter, QSizePolicy)
from PyQt6.QtCore import Qt

from ..themes import get_color
from ..widgets.navigation_view import NavigationPage
from ..widgets.head_layout import HeadLayoutSelector
from ...utils import tr, get_logger

logger = get_logger(__name__)


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


class ElectrodeChannelsPage(NavigationPage):
    """电极布局与通道选择页面"""
    
    def __init__(self, parent_simulator, parent=None):
        self.parent_simulator = parent_simulator
        super().__init__(
            title=tr('nav_electrode_channels'),
            subtitle=tr('nav_electrode_channels_subtitle'),
            parent=parent
        )
        
        self._setup_content()
    
    def _setup_content(self):
        """设置页面内容"""
        layout = self.get_content_layout()
        
        # 使用分割器：左侧电极布局，右侧通道列表
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # ========== 左侧：电极布局 ==========
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(16)
        
        # 头部布局可视化（包含布局选择下拉框）
        self.viz_group = QGroupBox(tr('panel_head_layout'))
        viz_layout = QVBoxLayout(self.viz_group)
        
        self.head_selector = HeadLayoutSelector(on_layout_changed=self._on_head_layout_changed)
        self.head_selector.setMinimumHeight(350)
        viz_layout.addWidget(self.head_selector)
        
        left_layout.addWidget(self.viz_group)
        
        left_layout.addStretch()
        splitter.addWidget(left_widget)
        
        # ========== 右侧：通道选择 ==========
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(16)
        
        # 说明文字
        self.info_frame = QFrame()
        self.info_frame.setStyleSheet(f"""
            background-color: {get_color('bg_input')};
            border-radius: 8px;
            border: 1px solid {get_color('border')};
        """)
        info_layout = QVBoxLayout(self.info_frame)
        info_layout.setContentsMargins(16, 12, 16, 12)
        
        self.info_label = QLabel(tr('channels_info'))
        self.info_label.setStyleSheet(f"color: {get_color('blue')}; font-size: 12px;")
        self.info_label.setWordWrap(True)
        info_layout.addWidget(self.info_label)
        
        right_layout.addWidget(self.info_frame)
        
        # 通道列表组
        self.channels_group = QGroupBox(tr('label_channels'))
        channels_layout = QVBoxLayout(self.channels_group)
        
        # 按钮区域
        btn_layout = QHBoxLayout()
        
        self.select_all_btn = QPushButton(tr('btn_select_all'))
        self.select_all_btn.setStyleSheet(get_primary_btn_style())
        self.select_all_btn.clicked.connect(self._select_all_channels)
        btn_layout.addWidget(self.select_all_btn)
        
        self.clear_btn = QPushButton(tr('btn_clear'))
        self.clear_btn.setStyleSheet(get_primary_btn_style())
        self.clear_btn.clicked.connect(self._clear_channels)
        btn_layout.addWidget(self.clear_btn)
        
        self.invert_btn = QPushButton(tr('btn_invert_selection'))
        self.invert_btn.setStyleSheet(get_primary_btn_style())
        self.invert_btn.clicked.connect(self._invert_selection)
        btn_layout.addWidget(self.invert_btn)
        
        btn_layout.addStretch()
        channels_layout.addLayout(btn_layout)
        
        # 统计信息
        self.stats_label = QLabel(tr('channels_selected', 0, 0))
        self.stats_label.setStyleSheet(f"color: {get_color('text_muted')}; font-size: 12px;")
        channels_layout.addWidget(self.stats_label)
        
        # 通道列表
        self.channel_list = QListWidget()
        self.channel_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self.channel_list.setStyleSheet(f"""
            QListWidget {{
                background-color: {get_color('bg_card')};
                border: 1px solid {get_color('border')};
                border-radius: 8px;
                outline: none;
                padding: 8px;
            }}
            QListWidget::item {{
                background-color: transparent;
                color: {get_color('text_main')};
                padding: 8px 12px;
                border-radius: 6px;
                margin: 2px 0px;
            }}
            QListWidget::item:selected {{
                background-color: {get_color('accent')};
                color: {get_color('text_inverse')};
            }}
            QListWidget::item:hover {{
                background-color: {get_color('bg_input')};
            }}
        """)
        self.channel_list.itemSelectionChanged.connect(self._on_selection_changed)
        channels_layout.addWidget(self.channel_list)
        
        right_layout.addWidget(self.channels_group)
        
        # 已选通道预览
        self.selected_group = QGroupBox(tr('selected_channels'))
        selected_layout = QVBoxLayout(self.selected_group)
        
        self.selected_preview = QLabel(tr('no_channels_selected'))
        self.selected_preview.setStyleSheet(f"""
            color: {get_color('text_muted')};
            font-size: 12px;
            padding: 12px;
            background-color: {get_color('bg_card')};
            border-radius: 8px;
        """)
        self.selected_preview.setWordWrap(True)
        selected_layout.addWidget(self.selected_preview)
        
        right_layout.addWidget(self.selected_group)
        
        right_layout.addStretch()
        splitter.addWidget(right_widget)
        
        # 设置分割器比例
        splitter.setSizes([500, 500])
        layout.addWidget(splitter)
        
        # 初始化通道列表
        self._update_channel_list()
    
    def _on_head_layout_changed(self, layout_key):
        """头部布局改变回调"""
        # 更新通道列表
        self._update_channel_list()
    
    def get_head_widget(self):
        """获取头部布局部件"""
        return self.head_selector.get_head_widget()
    
    def _update_channel_list(self):
        """更新通道列表"""
        head_widget = self.get_head_widget()
        montage = head_widget._montage if hasattr(head_widget, '_montage') else None
        
        channel_names = []
        if montage is not None:
            channel_names = montage.ch_names
        
        self.channel_list.clear()
        for ch_name in channel_names:
            item = QListWidgetItem(ch_name)
            self.channel_list.addItem(item)
        
        self._update_stats()
        
        # 更新父级的通道列表
        if hasattr(self.parent_simulator, 'selected_channels'):
            self.parent_simulator.selected_channels = []
    
    def get_selected_channels(self):
        """获取选中的通道"""
        selected_items = self.channel_list.selectedItems()
        return [item.text() for item in selected_items]
    
    def set_selected_channels(self, channel_names):
        """设置选中的通道"""
        self.channel_list.clearSelection()
        
        for i in range(self.channel_list.count()):
            item = self.channel_list.item(i)
            if item.text() in channel_names:
                item.setSelected(True)
        
        self._update_stats()
    
    def _select_all_channels(self):
        """全选通道"""
        self.channel_list.selectAll()
    
    def _clear_channels(self):
        """清空选择"""
        self.channel_list.clearSelection()
    
    def _invert_selection(self):
        """反选通道"""
        for i in range(self.channel_list.count()):
            item = self.channel_list.item(i)
            item.setSelected(not item.isSelected())
    
    def _on_selection_changed(self):
        """选择改变时"""
        selected = self.get_selected_channels()
        
        # 更新父级
        if hasattr(self.parent_simulator, 'selected_channels'):
            self.parent_simulator.selected_channels = selected
        
        self._update_stats()
        
        # 通知父级更新图表
        if hasattr(self.parent_simulator, '_update_plot_curves'):
            self.parent_simulator._update_plot_curves()
        
        # 更新状态栏
        if hasattr(self.parent_simulator, '_update_status_bar'):
            self.parent_simulator._update_status_bar()
    
    def get_current_montage(self):
        """获取当前选中的电极布局"""
        head_widget = self.get_head_widget()
        if hasattr(head_widget, '_montage'):
            return head_widget._montage
        return None
    
    def _update_stats(self):
        """更新统计信息"""
        selected_count = len(self.channel_list.selectedItems())
        total_count = self.channel_list.count()
        
        self.stats_label.setText(tr('channels_selected', selected_count, total_count))
        
        # 更新预览
        selected = self.get_selected_channels()
        if selected:
            preview_text = ", ".join(selected[:10])
            if len(selected) > 10:
                preview_text += f" ... (+{len(selected) - 10})"
            self.selected_preview.setText(preview_text)
            self.selected_preview.setStyleSheet(f"""
                color: {get_color('text_main')};
                font-size: 12px;
                padding: 12px;
                background-color: {get_color('bg_input')};
                border-radius: 8px;
                border: 1px solid {get_color('border')};
            """)
        else:
            self.selected_preview.setText(tr('no_channels_selected'))
            self.selected_preview.setStyleSheet(f"""
                color: {get_color('text_muted')};
                font-size: 12px;
                padding: 12px;
                background-color: {get_color('bg_card')};
                border-radius: 8px;
            """)


    def update_theme(self):
        """更新主题颜色"""
        # 调用父类方法更新基础样式（标题、背景等）
        super().update_theme()
        
        from ..themes import get_color
        
        # 更新信息框架
        if hasattr(self, 'info_frame'):
            self.info_frame.setStyleSheet(f"""
                background-color: {get_color('bg_input')};
                border-radius: 8px;
                border: 1px solid {get_color('border')};
            """)
        if hasattr(self, 'info_label'):
            self.info_label.setStyleSheet(f"color: {get_color('blue')}; font-size: 12px;")
        
        # 更新统计标签
        if hasattr(self, 'stats_label'):
            self.stats_label.setStyleSheet(f"color: {get_color('text_muted')}; font-size: 12px;")
        
        # 更新列表样式
        self.channel_list.setStyleSheet(f"""
            QListWidget {{
                background-color: {get_color('bg_card')};
                border: 1px solid {get_color('border')};
                border-radius: 8px;
                outline: none;
                padding: 8px;
            }}
            QListWidget::item {{
                background-color: transparent;
                color: {get_color('text_main')};
                padding: 8px 12px;
                border-radius: 6px;
                margin: 2px 0px;
            }}
            QListWidget::item:selected {{
                background-color: {get_color('accent')};
                color: {get_color('text_inverse')};
            }}
            QListWidget::item:hover {{
                background-color: {get_color('bg_input')};
            }}
        """)
        
        # 更新按钮样式
        for btn in [self.select_all_btn, self.clear_btn, self.invert_btn]:
            if btn:
                btn.setStyleSheet(get_primary_btn_style())
        
        # 更新预览标签
        self._update_stats()
    
    def update_texts(self):
        """更新界面文本"""
        # 更新标题
        self.set_title(tr('nav_electrode_channels'))
        self.set_subtitle(tr('nav_electrode_channels_subtitle'))
        
        # 更新组标题
        self.viz_group.setTitle(tr('panel_head_layout'))
        self.channels_group.setTitle(tr('label_channels'))
        self.selected_group.setTitle(tr('selected_channels'))
        
        # 更新按钮文本
        self.select_all_btn.setText(tr('btn_select_all'))
        self.clear_btn.setText(tr('btn_clear'))
        self.invert_btn.setText(tr('btn_invert_selection'))
        
        # 更新统计
        self._update_stats()
