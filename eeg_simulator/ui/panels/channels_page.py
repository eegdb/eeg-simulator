"""通道选择页面 - NavigationView 布局"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
                             QListWidget, QListWidgetItem, QPushButton,
                             QLabel, QFrame)
from PyQt6.QtCore import Qt

from ..themes import get_color


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
from ..widgets.navigation_view import NavigationPage
from ...utils import tr


class ChannelsPage(NavigationPage):
    """通道选择页面"""
    
    def __init__(self, parent_simulator, parent=None):
        self.parent_simulator = parent_simulator
        super().__init__(
            title=tr('nav_channels'),
            subtitle=tr('nav_channels_subtitle'),
            parent=parent
        )
        
        self._setup_content()
    
    def _setup_content(self):
        """设置页面内容"""
        layout = self.get_content_layout()
        
        # 说明文字
        self.info_frame = QFrame()
        self.info_frame.setStyleSheet(f"""
            background-color: rgba(59, 130, 246, 0.1);
            border-radius: 8px;
            border: 1px solid rgba(59, 130, 246, 0.3);
        """)
        info_layout = QVBoxLayout(self.info_frame)
        info_layout.setContentsMargins(16, 12, 16, 12)
        
        self.info_label = QLabel(tr('channels_info'))
        self.info_label.setStyleSheet(f"color: {get_color('blue')}; font-size: 12px;")
        self.info_label.setWordWrap(True)
        info_layout.addWidget(self.info_label)
        
        layout.addWidget(self.info_frame)
        
        # 通道列表组
        channels_group = QGroupBox(tr('label_channels'))
        channels_layout = QVBoxLayout(channels_group)
        
        # 按钮区域
        btn_layout = QHBoxLayout()
        
        self.select_all_btn = QPushButton(tr('btn_select_all'))
        self.select_all_btn.clicked.connect(self._select_all_channels)
        btn_layout.addWidget(self.select_all_btn)
        
        self.clear_btn = QPushButton(tr('btn_clear'))
        self.clear_btn.clicked.connect(self._clear_channels)
        btn_layout.addWidget(self.clear_btn)
        
        self.invert_btn = QPushButton(tr('btn_invert_selection'))
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
                background-color: {get_color('border')}80;
            }}
            QListWidget::item:selected:hover {{
                background-color: {get_color('accent')};
            }}
        """)
        self.channel_list.itemSelectionChanged.connect(self._on_selection_changed)
        channels_layout.addWidget(self.channel_list)
        
        layout.addWidget(channels_group)
        
        # 已选通道预览
        selected_group = QGroupBox(tr('selected_channels'))
        selected_layout = QVBoxLayout(selected_group)
        
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
        
        layout.addWidget(selected_group)
        
        layout.addStretch()
    
    def update_channel_list(self, channel_names):
        """更新通道列表"""
        self.channel_list.clear()
        
        for ch_name in channel_names:
            item = QListWidgetItem(ch_name)
            self.channel_list.addItem(item)
        
        self._update_stats()
    
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
                background-color: rgba(16, 185, 129, 0.1);
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
        
        # 更新信息框架和标签
        if hasattr(self, 'info_frame'):
            self.info_frame.setStyleSheet(f"""
                background-color: rgba(59, 130, 246, 0.1);
                border-radius: 8px;
                border: 1px solid rgba(59, 130, 246, 0.3);
            """)
        if hasattr(self, 'info_label'):
            self.info_label.setStyleSheet(f"color: {get_color('blue')}; font-size: 12px;")
        
        # 更新统计标签
        self.stats_label.setStyleSheet(f"color: {get_color('text_muted')}; font-size: 12px;")
        
        # 更新通道列表样式
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
                background-color: {get_color('border')}80;
            }}
            QListWidget::item:selected:hover {{
                background-color: {get_color('accent')};
            }}
        """)
        
        # 更新预览标签（根据当前状态）
        selected = self.get_selected_channels()
        if selected:
            self.selected_preview.setStyleSheet(f"""
                color: {get_color('text_main')};
                font-size: 12px;
                padding: 12px;
                background-color: rgba(16, 185, 129, 0.1);
                border-radius: 8px;
                border: 1px solid {get_color('border')};
            """)
        else:
            self.selected_preview.setStyleSheet(f"""
                color: {get_color('text_muted')};
                font-size: 12px;
                padding: 12px;
                background-color: {get_color('bg_card')};
                border-radius: 8px;
            """)
