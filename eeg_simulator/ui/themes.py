"""主题样式定义 - 支持深色和浅色模式"""

# 深色主题
DARK_THEME = {
    "name": "dark",
    "bg_dark": "#0a0a0a",
    "bg_card": "#18181b",
    "bg_input": "#27272a",
    "accent": "#10b981",  # Emerald 500
    "accent_hover": "#34d399",
    "text_main": "#f4f4f5",
    "text_muted": "#71717a",
    "text_inverse": "#000000",
    "border": "#27272a",
    "border_focus": "#10b981",
    "red": "#ef4444",
    "blue": "#3b82f6",
    "green": "#10b981",
    "yellow": "#f59e0b",
    "purple": "#8b5cf6",
    "pink": "#ec4899",
}

# 浅色主题
LIGHT_THEME = {
    "name": "light",
    "bg_dark": "#f8fafc",  # Slate 50
    "bg_card": "#ffffff",
    "bg_input": "#f1f5f9",
    "accent": "#059669",  # Emerald 600
    "accent_hover": "#047857",
    "text_main": "#1e293b",  # Slate 800
    "text_muted": "#64748b",  # Slate 500
    "text_inverse": "#ffffff",
    "border": "#e2e8f0",  # Slate 200
    "border_focus": "#059669",
    "red": "#dc2626",
    "blue": "#2563eb",
    "green": "#059669",
    "yellow": "#d97706",
    "purple": "#7c3aed",
    "pink": "#db2777",
}

# 当前主题
_current_theme = DARK_THEME


def set_theme(theme_name):
    """设置主题
    
    Args:
        theme_name: 'dark' 或 'light'
    """
    global _current_theme
    if theme_name == 'light':
        _current_theme = LIGHT_THEME
    else:
        _current_theme = DARK_THEME
    return _current_theme


def get_theme():
    """获取当前主题"""
    return _current_theme


def get_color(key, default="#000000"):
    """获取颜色值"""
    return _current_theme.get(key, default)


def generate_stylesheet(theme=None):
    """生成 QSS 样式表"""
    if theme is None:
        theme = _current_theme
    
    c = theme  # 简写
    
    return f"""
QMainWindow, QWidget {{
    background-color: {c['bg_dark']};
    color: {c['text_main']};
    font-family: 'Inter', 'Segoe UI', 'Microsoft YaHei', sans-serif;
}}

QFrame#Sidebar {{
    background-color: {c['bg_card']};
    border-right: 1px solid {c['border']};
}}

QFrame#Card {{
    background-color: {c['bg_card']};
    border: 1px solid {c['border']};
    border-radius: 12px;
}}

QLabel#HeaderTitle {{
    font-size: 18px;
    font-weight: bold;
    color: {c['text_main']};
}}

QLabel#SubTitle {{
    color: {c['text_muted']};
    font-size: 10px;
    font-weight: bold;
    text-transform: uppercase;
}}

QPushButton#PrimaryBtn {{
    background-color: {c['accent']};
    color: {c['text_inverse']};
    border-radius: 18px;
    padding: 8px 20px;
    font-weight: bold;
    border: none;
}}

QPushButton#PrimaryBtn:hover {{
    background-color: {c['accent_hover']};
}}

QPushButton#PrimaryBtn:pressed {{
    background-color: {c['accent']};
}}

QPushButton#StopBtn {{
    background-color: {c['red']}20;
    color: {c['red']};
    border: 1px solid {c['red']}40;
    border-radius: 18px;
    padding: 8px 20px;
    font-weight: bold;
}}

QPushButton#StopBtn:hover {{
    background-color: {c['red']}30;
}}

QPushButton {{
    background-color: {c['bg_input']};
    color: {c['text_main']};
    border: 1px solid {c['border']};
    border-radius: 6px;
    padding: 6px 16px;
}}

QPushButton:hover {{
    background-color: {c['border']};
    border-color: {c['border_focus']};
}}

QSlider::groove:horizontal {{
    border: 1px solid {c['border']};
    height: 4px;
    background: {c['border']};
    margin: 2px 0;
    border-radius: 2px;
}}

QSlider::handle:horizontal {{
    background: {c['accent']};
    border: 1px solid {c['accent']};
    width: 12px;
    height: 12px;
    margin: -5px 0;
    border-radius: 6px;
}}

QGroupBox {{
    background-color: {c['bg_card']};
    color: {c['text_main']};
    border: 1px solid {c['border']};
    margin-top: 10px;
    border-radius: 5px;
    padding-top: 10px;
    font-weight: bold;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
    color: {c['text_muted']};
}}

QComboBox {{
    background-color: {c['bg_input']};
    color: {c['text_main']};
    border: 1px solid {c['border']};
    padding: 5px 10px;
    border-radius: 5px;
    min-width: 100px;
}}

QComboBox:hover {{
    border-color: {c['border_focus']};
}}

QComboBox::drop-down {{
    border: none;
    width: 20px;
}}

QComboBox QAbstractItemView {{
    background-color: {c['bg_card']};
    color: {c['text_main']};
    selection-background-color: {c['accent']};
    border: 1px solid {c['border']};
    outline: none;
}}

QComboBox QAbstractItemView::item {{
    padding: 6px 10px;
    padding-left: 24px;
}}

QComboBox QAbstractItemView::item:selected {{
    background-color: {c['accent']};
    color: {c['text_inverse']};
}}

QComboBox QAbstractItemView::item:checked {{
    background-image: url(data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='{c["accent"].replace("#", "%23")}' stroke-width='2'><polyline points='20 6 9 17 4 12'></polyline></svg>);
    background-repeat: no-repeat;
    background-position: left center;
    background-position-x: 6px;
    padding-left: 26px;
}}

QComboBox QAbstractItemView::item:checked:selected {{
    background-image: url(data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='{c["text_inverse"].replace("#", "%23")}' stroke-width='2'><polyline points='20 6 9 17 4 12'></polyline></svg>);
    background-repeat: no-repeat;
    background-position: left center;
    background-position-x: 6px;
}}

QSpinBox, QDoubleSpinBox {{
    background-color: {c['bg_input']};
    color: {c['text_main']};
    border: 1px solid {c['border']};
    padding: 5px;
    border-radius: 5px;
}}

QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {c['border_focus']};
}}

QListWidget, QTreeWidget {{
    background-color: {c['bg_card']};
    color: {c['text_main']};
    border: 1px solid {c['border']};
    border-radius: 5px;
    outline: none;
}}

QListWidget::item, QTreeWidget::item {{
    background-color: transparent;
    color: {c['text_main']};
    padding: 4px 8px;
    min-height: 20px;
}}

QListWidget::item:selected, QTreeWidget::item:selected {{
    background-color: {c['accent']};
    color: {c['text_inverse']};
}}

QListWidget::item:selected:active, QTreeWidget::item:selected:active {{
    background-color: {c['accent']};
    color: {c['text_inverse']};
}}

QListWidget::item:selected:!active, QTreeWidget::item:selected:!active {{
    background-color: {c['accent']}80;
    color: {c['text_inverse']};
}}

QListWidget::item:hover, QTreeWidget::item:hover {{
    background-color: {c['bg_input']};
}}

QListWidget::item:alternate, QTreeWidget::item:alternate {{
    background-color: transparent;
    color: {c['text_main']};
}}

QListWidget::item:alternate:selected, QTreeWidget::item:alternate:selected {{
    background-color: {c['accent']};
    color: {c['text_inverse']};
}}

QLineEdit {{
    background-color: {c['bg_input']};
    border: 1px solid {c['border']};
    color: {c['text_main']};
    padding: 5px 10px;
    border-radius: 5px;
}}

QLineEdit:focus {{
    border-color: {c['border_focus']};
}}

QTextEdit, QPlainTextEdit {{
    background-color: {c['bg_input']};
    border: 1px solid {c['border']};
    color: {c['text_main']};
    padding: 5px 10px;
    border-radius: 5px;
}}

QTextEdit:focus, QPlainTextEdit:focus {{
    border-color: {c['border_focus']};
}}

QCheckBox {{
    color: {c['text_main']};
    spacing: 8px;
}}

QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border-radius: 3px;
    border: 1px solid {c['border']};
    background-color: {c['bg_input']};
}}

QCheckBox::indicator:checked {{
    background-color: {c['accent']};
    border-color: {c['accent']};
}}

QScrollArea {{
    border: none;
    background: transparent;
}}

QScrollBar:vertical {{
    background: {c['bg_card']};
    width: 12px;
    margin: 0px;
    border-radius: 6px;
}}

QScrollBar::handle:vertical {{
    background: {c['border']};
    min-height: 20px;
    border-radius: 6px;
}}

QScrollBar::handle:vertical:hover {{
    background: {c['accent']};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QMenuBar {{
    background-color: {c['bg_card']};
    color: {c['text_main']};
    border-bottom: 1px solid {c['border']};
}}

QMenuBar::item {{
    background-color: transparent;
    padding: 6px 12px;
}}

QMenuBar::item:selected {{
    background-color: {c['accent']};
    color: {c['text_inverse']};
    border-radius: 4px;
}}

QMenu {{
    background-color: {c['bg_card']};
    color: {c['text_main']};
    border: 1px solid {c['border']};
    padding: 5px;
}}

QMenu::item {{
    padding: 6px 20px;
    border-radius: 3px;
}}

QMenu::item:selected {{
    background-color: {c['accent']};
    color: {c['text_inverse']};
}}

QMenu::separator {{
    height: 1px;
    background-color: {c['border']};
    margin: 5px 10px;
}}

QDialog {{
    background-color: {c['bg_dark']};
}}

QToolTip {{
    background-color: {c['bg_card']};
    color: {c['text_main']};
    border: 1px solid {c['border']};
    padding: 5px;
    border-radius: 3px;
}}
"""
