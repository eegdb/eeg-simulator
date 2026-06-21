"""NavigationView - 现代导航视图布局

模仿 Win11/Fluent Design 的导航视图，提供：
- 左侧导航栏（可折叠）
- 图标 + 文字的导航项
- 点击切换不同页面
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                             QLabel, QFrame, QStackedWidget, QScrollArea,
                             QSizePolicy, QGraphicsOpacityEffect, QApplication)
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QSize, pyqtSignal

from ..themes import get_color
from ...utils import tr

# 侧边栏宽度（修改此值调整导航栏宽度）
SIDEBAR_WIDTH = 200


class NavigationItem(QPushButton):
    """导航项 - 带图标和文字的按钮"""
    
    clicked_item = pyqtSignal(str)  # 发送 item_id
    
    def __init__(self, item_id: str, icon_text: str, text: str, parent=None):
        super().__init__(parent)
        self.item_id = item_id
        self._icon_text = icon_text
        self._text = text
        self._expanded = True
        self._is_selected = False
        
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(44)
        
        # 设置样式
        self._update_style()
        
        # 设置初始文字
        self.set_expanded(True)
        
        # 连接点击信号
        self.clicked.connect(lambda: self.clicked_item.emit(self.item_id))
    
    def _update_style(self, center=False):
        """更新样式 - 使用当前主题颜色"""
        text_main = get_color('text_main')
        accent = get_color('accent')
        bg_card = get_color('bg_card')
        bg_input = get_color('bg_input')
        # 将accent颜色转换为带透明度的rgba
        accent_r = int(accent[1:3], 16)
        accent_g = int(accent[3:5], 16)
        accent_b = int(accent[5:7], 16)
        accent_rgba = f"rgba({accent_r}, {accent_g}, {accent_b}, 0.15)"
        accent_hover_rgba = f"rgba({accent_r}, {accent_g}, {accent_b}, 0.25)"
        
        align = "center" if center else "left"
        # padding: 上 右 下 左，左边距减少让内容往左移
        padding = "0px" if center else "10px 16px 10px 4px"
        
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg_card};
                color: {text_main};
                border: none;
                border-radius: 8px;
                padding: {padding};
                text-align: {align};
                font-size: 14px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {bg_input};
                color: {text_main};
            }}
            QPushButton:checked {{
                background-color: {accent_rgba};
                color: {accent};
                font-weight: 600;
            }}
            QPushButton:checked:hover {{
                background-color: {accent_hover_rgba};
            }}
        """)
    
    def set_expanded(self, expanded: bool):
        """设置展开/折叠状态"""
        self._expanded = expanded
        if expanded:
            self._update_style(center=False)
            self.setText(f"{self._icon_text}  {self._text}")
            self.setMinimumWidth(SIDEBAR_WIDTH - 25)
            self.setFixedHeight(44)
        else:
            self._update_style(center=True)
            self.setText(self._icon_text)
            self.setFixedSize(48, 48)
    
    def set_selected(self, selected: bool):
        """设置选中状态"""
        self._is_selected = selected
        self.setChecked(selected)


class NavigationView(QFrame):
    """导航视图 - 现代侧边导航布局
    
    类似于 Win11 Settings / Fluent UI 的 NavigationView
    """
    
    page_changed = pyqtSignal(str, int)  # (page_id, page_index)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self._expanded = True
        self._items = []  # [(item_id, item_widget), ...]
        self._current_index = 0
        
        # 导航栏宽度（从 sidebar.py 导入，修改 sidebar.py 中的 SIDEBAR_WIDTH 调整宽度）
        self._expanded_width = SIDEBAR_WIDTH
        self._collapsed_width = 64
        
        self._init_ui()
    
    def _init_ui(self):
        """初始化UI - 使用当前主题颜色"""
        bg_card = get_color('bg_card')
        border = get_color('border')
        
        self.setObjectName("NavigationView")
        self.setStyleSheet(f"""
            #NavigationView {{
                background-color: {bg_card};
                border-right: 1px solid {border};
            }}
        """)
        
        # 主布局
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        # ========== 左侧导航栏 ==========
        self.nav_frame = QFrame()
        self.nav_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_card};
                border-right: 2px solid {border};
            }}
        """)
        self.nav_frame.setFixedWidth(self._expanded_width)
        self.nav_layout = QVBoxLayout(self.nav_frame)
        self.nav_layout.setContentsMargins(12, 16, 12, 16)
        self.nav_layout.setSpacing(4)
        
        # 标题区域（包含折叠按钮）
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)
        
        text_main = get_color('text_main')
        self.title_label = QLabel(tr('nav_sidebar_title'))
        self.title_label.setStyleSheet(f"""
            color: {text_main};
            font-size: 18px;
            font-weight: bold;
            padding: 8px 0px 8px 8px;
        """)
        header_layout.addWidget(self.title_label, 1)
        
        # 折叠/展开按钮（放在标题右侧）
        accent = get_color('accent')
        bg_input = get_color('bg_input')
        border = get_color('border')
        self.toggle_btn = QPushButton("◀")
        self.toggle_btn.setFixedSize(32, 32)
        self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg_input};
                color: {text_main};
                border: 1px solid {border};
                border-radius: 6px;
                font-size: 10px;
                font-weight: bold;
                padding: 0px;
            }}
            QPushButton:hover {{
                background-color: {accent};
                color: {get_color('text_inverse')};
                border-color: {accent};
            }}
        """)
        self.toggle_btn.clicked.connect(self._toggle_navigation)
        header_layout.addWidget(self.toggle_btn)
        
        self.nav_layout.addWidget(header_widget)
        
        # 分隔线
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet(f"background-color: {border}; max-height: 1px;")
        self.nav_layout.addWidget(separator)
        
        self.nav_layout.addSpacing(8)
        
        # 导航项容器
        self.nav_items_widget = QWidget()
        self.nav_items_widget.setStyleSheet(f"""
            QWidget {{
                background-color: {bg_card};
            }}
        """)
        self.nav_items_layout = QVBoxLayout(self.nav_items_widget)
        self.nav_items_layout.setContentsMargins(0, 0, 0, 0)
        self.nav_items_layout.setSpacing(4)
        self.nav_layout.addWidget(self.nav_items_widget)
        
        self.nav_layout.addStretch()
        
        self.main_layout.addWidget(self.nav_frame)
        
        # ========== 右侧内容区域 ==========
        bg_dark = get_color('bg_dark')
        self.content_frame = QFrame()
        self.content_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_dark};
            }}
        """)
        self.content_layout = QVBoxLayout(self.content_frame)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(0)
        
        # 使用堆叠部件管理页面
        self.stack_widget = QStackedWidget()
        self.content_layout.addWidget(self.stack_widget)
        
        self.main_layout.addWidget(self.content_frame, 1)
        
        # 动画
        self._animation = QPropertyAnimation(self.nav_frame, b"minimumWidth")
        self._animation.setDuration(250)
        self._animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
    
    def add_page(self, page_id: str, icon_text: str, title: str, widget: QWidget) -> int:
        """添加页面
        
        Args:
            page_id: 页面唯一标识
            icon_text: 图标（emoji或字符）
            title: 页面标题
            widget: 页面内容部件
        
        Returns:
            页面索引
        """
        # 创建导航项
        nav_item = NavigationItem(page_id, icon_text, title)
        nav_item.clicked_item.connect(self._on_item_clicked)
        self.nav_items_layout.addWidget(nav_item)
        self._items.append((page_id, nav_item))
        
        # 将页面添加到堆叠部件
        # 包装在滚动区域中
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        bg_dark = get_color('bg_dark')
        border = get_color('border')
        accent = get_color('accent')
        scroll.setStyleSheet(f"""
            QScrollArea {{
                border: none;
                background-color: {bg_dark};
            }}
            QScrollBar:vertical {{
                background: {bg_dark};
                width: 8px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background: {border};
                min-height: 30px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {accent};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)
        
        # 设置滚动区域内容
        widget.setParent(None)
        scroll.setWidget(widget)
        
        index = self.stack_widget.addWidget(scroll)
        
        # 默认选中第一个
        if len(self._items) == 1:
            nav_item.set_selected(True)
        
        return index
    
    def _on_item_clicked(self, page_id: str):
        """导航项点击处理"""
        for index, (pid, item) in enumerate(self._items):
            if pid == page_id:
                self._current_index = index
                self.stack_widget.setCurrentIndex(index)
                item.set_selected(True)
                self.page_changed.emit(page_id, index)
            else:
                item.set_selected(False)
    
    def set_current_page(self, page_id: str):
        """设置当前页面"""
        self._on_item_clicked(page_id)
    
    def get_current_page_id(self) -> str:
        """获取当前页面ID"""
        if 0 <= self._current_index < len(self._items):
            return self._items[self._current_index][0]
        return ""
    
    def update_theme(self):
        """更新主题颜色"""
        # 更新导航栏样式
        bg_card = get_color('bg_card')
        border = get_color('border')
        bg_dark = get_color('bg_dark')
        accent = get_color('accent')
        text_main = get_color('text_main')
        bg_input = get_color('bg_input')
        
        self.nav_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_card};
                border-right: 2px solid {border};
            }}
        """)
        
        self.nav_items_widget.setStyleSheet(f"""
            QWidget {{
                background-color: {bg_card};
            }}
        """)
        
        self.title_label.setStyleSheet(f"""
            color: {text_main};
            font-size: 18px;
            font-weight: bold;
            padding: 8px 0px 8px 8px;
        """)
        
        self.toggle_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg_input};
                color: {text_main};
                border: 1px solid {border};
                border-radius: 6px;
                font-size: 10px;
                font-weight: bold;
                padding: 0px;
            }}
            QPushButton:hover {{
                background-color: {accent};
                color: {get_color('text_inverse')};
                border-color: {accent};
            }}
        """)
        
        # 更新内容区域背景
        self.content_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_dark};
            }}
        """)
        
        # 更新所有导航项样式
        for _, item in self._items:
            item._update_style(center=not self._expanded)
        
        # 更新滚动区域样式
        for i in range(self.stack_widget.count()):
            scroll = self.stack_widget.widget(i)
            if isinstance(scroll, QScrollArea):
                scroll.setStyleSheet(f"""
                    QScrollArea {{
                        border: none;
                        background-color: {bg_dark};
                    }}
                    QScrollBar:vertical {{
                        background: {bg_dark};
                        width: 8px;
                        margin: 0px;
                    }}
                    QScrollBar::handle:vertical {{
                        background: {border};
                        min-height: 30px;
                        border-radius: 4px;
                    }}
                    QScrollBar::handle:vertical:hover {{
                        background: {accent};
                    }}
                    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                        height: 0px;
                    }}
                """)
    
    def update_texts(self, titles: dict):
        """更新导航项文字
        
        Args:
            titles: {page_id: new_title} 映射
        """
        if hasattr(self, 'title_label'):
            self.title_label.setText(tr('nav_sidebar_title'))
        for page_id, item in self._items:
            if page_id in titles:
                item._text = titles[page_id]
                item.set_expanded(self._expanded)
    
    def _toggle_navigation(self):
        """切换导航栏展开/折叠"""
        self._expanded = not self._expanded
        
        if self._expanded:
            # 展开
            self.title_label.show()
            self._animate_width(self._collapsed_width, self._expanded_width)
            self.toggle_btn.setText("◀")
            for _, item in self._items:
                item.set_expanded(True)
        else:
            # 折叠
            self.title_label.hide()
            self._animate_width(self._expanded_width, self._collapsed_width)
            self.toggle_btn.setText("▶")
            for _, item in self._items:
                item.set_expanded(False)
    
    def _animate_width(self, start_width: int, end_width: int):
        """执行宽度动画"""
        self._animation.setStartValue(start_width)
        self._animation.setEndValue(end_width)
        self._animation.start()
    
    def is_expanded(self) -> bool:
        """获取展开状态"""
        return self._expanded
    
    def set_expanded(self, expanded: bool):
        """设置展开状态"""
        if expanded != self._expanded:
            self._toggle_navigation()


class NavigationPage(QWidget):
    """导航页面基类
    
    所有导航页面的基类，提供统一的页面结构和样式
    """
    
    def __init__(self, title: str, subtitle: str = "", parent=None):
        super().__init__(parent)
        
        self._title = title
        self._subtitle = subtitle
        
        self._init_ui()
    
    def _init_ui(self):
        """初始化页面UI - 使用当前主题颜色"""
        bg_dark = get_color('bg_dark')
        text_main = get_color('text_main')
        text_muted = get_color('text_muted')
        border = get_color('border')
        
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {bg_dark};
            }}
        """)
        
        # 主布局
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(24, 24, 24, 24)
        self.main_layout.setSpacing(16)
        
        # 页面标题区域
        self.header_widget = QWidget()
        self.header_layout = QVBoxLayout(self.header_widget)
        self.header_layout.setContentsMargins(0, 0, 0, 0)
        self.header_layout.setSpacing(4)
        
        self.title_label = QLabel(self._title)
        self.title_label.setStyleSheet(f"""
            color: {get_color('text_main')};
            font-size: 28px;
            font-weight: bold;
        """)
        self.header_layout.addWidget(self.title_label)
        
        if self._subtitle:
            self.subtitle_label = QLabel(self._subtitle)
            self.subtitle_label.setStyleSheet(f"""
                color: {get_color('text_muted')};
                font-size: 14px;
            """)
            self.header_layout.addWidget(self.subtitle_label)
        
        self.main_layout.addWidget(self.header_widget)
        
        # 分隔线
        header_separator = QFrame()
        header_separator.setFrameShape(QFrame.Shape.HLine)
        header_separator.setStyleSheet(f"background-color: {get_color('border')}; max-height: 1px;")
        self.main_layout.addWidget(header_separator)
        
        # 内容区域（子类添加内容到此）
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 8, 0, 0)
        self.content_layout.setSpacing(16)
        
        self.main_layout.addWidget(self.content_widget, 1)
    
    def get_content_layout(self) -> QVBoxLayout:
        """获取内容布局，子类在此添加内容"""
        return self.content_layout
    
    def set_title(self, title: str):
        """设置页面标题"""
        self._title = title
        self.title_label.setText(title)
    
    def set_subtitle(self, subtitle: str):
        """设置页面副标题"""
        self._subtitle = subtitle
        if hasattr(self, 'subtitle_label'):
            self.subtitle_label.setText(subtitle)
    
    def update_theme(self):
        """更新主题颜色 - 子类可重写此方法"""
        bg_dark = get_color('bg_dark')
        text_main = get_color('text_main')
        text_muted = get_color('text_muted')
        border = get_color('border')
        
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {bg_dark};
            }}
        """)
        
        self.title_label.setStyleSheet(f"""
            color: {text_main};
            font-size: 28px;
            font-weight: bold;
        """)
        
        if hasattr(self, 'subtitle_label'):
            self.subtitle_label.setStyleSheet(f"""
                color: {text_muted};
                font-size: 14px;
            """)
