"""可折叠侧边栏 - Win11 风格"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QLabel, QFrame, QSizePolicy, QScrollArea, QStackedWidget)
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QSize
from PyQt6.QtGui import QIcon, QFont

from ..styles import COLORS
from ...utils import tr


class SidebarButton(QPushButton):
    """侧边栏按钮 - 可显示图标和文字"""
    
    def __init__(self, icon_text, text, parent=None):
        super().__init__(parent)
        self._icon_text = icon_text
        self._text = text
        self._expanded = True
        
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {COLORS['text_muted']};
                border: none;
                border-radius: 8px;
                padding: 12px;
                text-align: left;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['bg_hover']};
            }}
            QPushButton:checked {{
                background-color: {COLORS['accent']};
                color: {COLORS['text_inverse']};
            }}
        """)
        
    def set_expanded(self, expanded):
        """设置展开/折叠状态"""
        self._expanded = expanded
        if expanded:
            self.setText(f"{self._icon_text}  {self._text}")
            self.setMinimumWidth(0)
        else:
            self.setText(self._icon_text)
            self.setFixedWidth(50)


class CollapsibleSidebar(QWidget):
    """可折叠侧边栏 - Win11 风格"""
    
    def __init__(self, parent=None, expanded=True):
        super().__init__(parent)
        
        self._expanded = expanded
        self._current_index = 0
        self._buttons = []
        
        # 侧边栏宽度（直接修改此值调整宽度）
        self._sidebar_width = 500
        
        # 主布局
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        # 侧边栏容器
        self.sidebar_frame = QFrame()
        self.sidebar_frame.setObjectName("SidebarFrame")
        self.sidebar_frame.setStyleSheet(f"""
            #SidebarFrame {{
                background-color: {COLORS['bg_card']};
                border-right: 1px solid {COLORS['border']};
            }}
        """)
        
        self.sidebar_layout = QVBoxLayout(self.sidebar_frame)
        self.sidebar_layout.setContentsMargins(8, 12, 8, 12)
        self.sidebar_layout.setSpacing(4)
        
        # 切换按钮
        self.toggle_btn = QPushButton("☰")
        self.toggle_btn.setFixedSize(40, 40)
        self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {COLORS['text_muted']};
                border: none;
                border-radius: 8px;
                font-size: 18px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['bg_hover']};
            }}
        """)
        self.toggle_btn.clicked.connect(self._toggle_sidebar)
        self.sidebar_layout.addWidget(self.toggle_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        
        self.sidebar_layout.addSpacing(10)
        
        # 按钮区域
        self.buttons_widget = QWidget()
        self.buttons_layout = QVBoxLayout(self.buttons_widget)
        self.buttons_layout.setContentsMargins(0, 0, 0, 0)
        self.buttons_layout.setSpacing(4)
        self.sidebar_layout.addWidget(self.buttons_widget)
        
        self.sidebar_layout.addStretch()
        
        self.main_layout.addWidget(self.sidebar_frame)
        
        # 内容区域 - 使用堆叠部件
        self.content_stack = QStackedWidget()
        self.content_stack.setStyleSheet(f"background-color: {COLORS['bg_dark']};")
        self.main_layout.addWidget(self.content_stack, 1)
        
        # 动画
        self.animation = QPropertyAnimation(self.sidebar_frame, b"minimumWidth")
        self.animation.setDuration(200)
        self.animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        
        # 初始宽度
        if expanded:
            self.sidebar_frame.setFixedWidth(self._sidebar_width)
        else:
            self.sidebar_frame.setFixedWidth(66)
    
    def add_section(self, icon_text, title, widget):
        """添加一个侧边栏部分"""
        button = SidebarButton(icon_text, title)
        button.clicked.connect(lambda: self._on_button_clicked(len(self._buttons)))
        self.buttons_layout.addWidget(button)
        self._buttons.append(button)
        
        # 将内容部件添加到堆叠部件
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        scroll.setWidget(widget)
        
        self.content_stack.addWidget(scroll)
        
        # 设置初始状态
        button.set_expanded(self._expanded)
        
        # 默认选中第一个
        if len(self._buttons) == 1:
            button.setChecked(True)
    
    def _on_button_clicked(self, index):
        """按钮点击时切换内容"""
        self._current_index = index
        self.content_stack.setCurrentIndex(index)
        
        # 更新按钮选中状态
        for i, btn in enumerate(self._buttons):
            btn.setChecked(i == index)
    
    def _toggle_sidebar(self):
        """切换侧边栏展开/折叠"""
        self._expanded = not self._expanded
        
        if self._expanded:
            # 展开
            self.animation.setStartValue(self.sidebar_frame.width())
            self.animation.setEndValue(self._sidebar_width)
            for btn in self._buttons:
                btn.set_expanded(True)
        else:
            # 折叠
            self.animation.setStartValue(self.sidebar_frame.width())
            self.animation.setEndValue(66)
            for btn in self._buttons:
                btn.set_expanded(False)
        
        self.animation.start()
    
    def set_expanded(self, expanded):
        """设置展开状态"""
        if expanded != self._expanded:
            self._toggle_sidebar()
    
    def is_expanded(self):
        """获取当前展开状态"""
        return self._expanded
    
    def update_theme(self):
        """更新主题颜色"""
        # 更新侧边栏框架
        self.sidebar_frame.setStyleSheet(f"""
            #SidebarFrame {{
                background-color: {COLORS['bg_card']};
                border-right: 1px solid {COLORS['border']};
            }}
        """)
        
        # 更新内容区域
        self.content_stack.setStyleSheet(f"background-color: {COLORS['bg_dark']};")
        
        # 更新切换按钮
        self.toggle_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {COLORS['text_muted']};
                border: none;
                border-radius: 8px;
                font-size: 18px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['bg_hover']};
            }}
        """)
        
        # 更新所有侧边栏按钮
        for btn in self._buttons:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    color: {COLORS['text_muted']};
                    border: none;
                    border-radius: 8px;
                    padding: 12px;
                    text-align: left;
                    font-size: 14px;
                }}
                QPushButton:hover {{
                    background-color: {COLORS['bg_hover']};
                }}
                QPushButton:checked {{
                    background-color: {COLORS['accent']};
                    color: {COLORS['text_inverse']};
                }}
            """)
