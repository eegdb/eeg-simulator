"""可折叠面板组件"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QFrame, QSizePolicy)
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QSize

from ..styles import COLORS
from ...utils import tr


class CollapsibleBox(QWidget):
    """可折叠面板 - 点击标题栏展开/折叠内容"""
    
    def __init__(self, title, parent=None, expanded=True):
        super().__init__(parent)
        
        self._title = title
        self._expanded = expanded
        
        # 主布局
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        # 标题栏
        self.header = QFrame()
        self.header.setObjectName("CollapsibleHeader")
        self.header.setStyleSheet(f"""
            #CollapsibleHeader {{
                background-color: {COLORS['bg_card']};
                border: 1px solid {COLORS['border']};
                border-radius: 4px;
            }}
            #CollapsibleHeader:hover {{
                background-color: {COLORS['bg_hover']};
            }}
        """)
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(10, 8, 10, 8)
        
        # 展开/折叠图标
        self.toggle_btn = QLabel("▼" if expanded else "▶")
        self.toggle_btn.setStyleSheet(f"color: {COLORS['text_muted']};")
        header_layout.addWidget(self.toggle_btn)
        
        # 标题
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet(f"color: {COLORS['text_main']}; font-weight: bold;")
        header_layout.addWidget(self.title_label, 1)
        
        # 点击标题栏切换展开状态
        self.header.mousePressEvent = self._toggle_expand
        self.toggle_btn.mousePressEvent = self._toggle_expand
        self.title_label.mousePressEvent = self._toggle_expand
        
        self.main_layout.addWidget(self.header)
        
        # 内容区域
        self.content_frame = QFrame()
        self.content_frame.setObjectName("CollapsibleContent")
        self.content_frame.setStyleSheet(f"""
            #CollapsibleContent {{
                background-color: {COLORS['bg_dark']};
                border: 1px solid {COLORS['border']};
                border-top: none;
                border-radius: 0 0 4px 4px;
            }}
        """)
        self.content_layout = QVBoxLayout(self.content_frame)
        self.content_layout.setContentsMargins(10, 10, 10, 10)
        self.content_layout.setSpacing(8)
        
        self.main_layout.addWidget(self.content_frame)
        
        # 动画
        self.animation = QPropertyAnimation(self.content_frame, b"maximumHeight")
        self.animation.setDuration(200)
        self.animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        
        # 初始状态
        if not expanded:
            self.content_frame.setMaximumHeight(0)
            self.content_frame.hide()
    
    def _toggle_expand(self, event=None):
        """切换展开/折叠状态"""
        self._expanded = not self._expanded
        
        if self._expanded:
            self.toggle_btn.setText("▼")
            self.content_frame.show()
            # 计算内容高度
            content_height = self.content_layout.sizeHint().height() + 20
            self.animation.setStartValue(0)
            self.animation.setEndValue(content_height)
        else:
            self.toggle_btn.setText("▶")
            self.animation.setStartValue(self.content_frame.height())
            self.animation.setEndValue(0)
            self.animation.finished.connect(lambda: self.content_frame.hide())
        
        self.animation.start()
    
    def set_expanded(self, expanded):
        """设置展开状态"""
        if expanded != self._expanded:
            self._toggle_expand()
    
    def is_expanded(self):
        """获取当前展开状态"""
        return self._expanded
    
    def add_widget(self, widget):
        """添加控件到内容区域"""
        self.content_layout.addWidget(widget)
    
    def add_layout(self, layout):
        """添加布局到内容区域"""
        self.content_layout.addLayout(layout)
    
    def content_widget(self):
        """获取内容区域，用于设置布局"""
        return self.content_frame
    
    def update_theme(self):
        """更新主题颜色"""
        # 更新标题栏
        self.header.setStyleSheet(f"""
            #CollapsibleHeader {{
                background-color: {COLORS['bg_card']};
                border: 1px solid {COLORS['border']};
                border-radius: 4px;
            }}
            #CollapsibleHeader:hover {{
                background-color: {COLORS['bg_hover']};
            }}
        """)
        
        # 更新内容区域
        self.content_frame.setStyleSheet(f"""
            #CollapsibleContent {{
                background-color: {COLORS['bg_dark']};
                border: 1px solid {COLORS['border']};
                border-top: none;
                border-radius: 0 0 4px 4px;
            }}
        """)
        
        # 更新图标和标题颜色
        self.toggle_btn.setStyleSheet(f"color: {COLORS['text_muted']};")
        self.title_label.setStyleSheet(f"color: {COLORS['text_main']}; font-weight: bold;")
