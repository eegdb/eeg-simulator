"""样式定义 - 颜色主题和QSS样式表

注意：新代码应使用 themes.py 中的 get_color() 函数获取动态主题颜色
"""

from .themes import CHECKMARK_ICON, get_color, get_theme

# 为了向后兼容，提供一个类似字典的类来动态获取颜色
class _DynamicColors:
    """动态颜色类 - 每次访问时都从当前主题获取最新颜色"""
    
    def __getitem__(self, key):
        return get_color(key)
    
    def __contains__(self, key):
        return True  # 允许任何键，get_color会处理默认值
    
    def get(self, key, default=None):
        return get_color(key) or default

# 向后兼容：COLORS现在是一个动态获取颜色的对象
COLORS = _DynamicColors()

# QSS样式表 - 使用动态颜色
def get_qss():
    """获取当前主题的QSS样式表"""
    c = get_theme()
    checkmark = CHECKMARK_ICON
    
    return f"""
QMainWindow, QWidget {{
    background-color: {c['bg_dark']};
    color: {c['text_main']};
    font-family: 'Inter', 'Segoe UI', sans-serif;
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

QPushButton#StopBtn {{
    background-color: {c['red']}20;
    color: {c['red']};
    border: 1px solid {c['red']}40;
    border-radius: 18px;
    padding: 8px 20px;
    font-weight: bold;
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
    border-radius: 8px;
    padding-top: 10px;
    font-weight: bold;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 3px 0 3px;
}}

QComboBox {{
    background-color: {c['bg_input']};
    color: {c['text_main']};
    border: 1px solid {c['border']};
    padding: 5px 28px 5px 10px;
    border-radius: 5px;
    min-width: 100px;
    selection-background-color: {c['accent']};
    selection-color: {c['text_inverse']};
}}

QComboBox:hover {{
    border-color: {c['border_focus']};
}}

QComboBox:focus {{
    border-color: {c['border_focus']};
}}

QComboBox:disabled {{
    background-color: {c['bg_card']};
    color: {c['text_muted']};
    border-color: {c['border']};
}}

QComboBox::drop-down {{
    border: none;
    width: 24px;
}}

QComboBox QAbstractItemView {{
    background-color: {c['bg_card']};
    color: {c['text_main']};
    selection-background-color: {c['accent']};
    selection-color: {c['text_inverse']};
    border: 1px solid {c['border']};
    outline: none;
}}

QComboBox QAbstractItemView::item {{
    padding: 6px 10px;
    padding-left: 24px;
    min-height: 22px;
    background-color: {c['bg_card']};
    color: {c['text_main']};
}}

QComboBox QAbstractItemView::item:hover {{
    background-color: {c['bg_input']};
    color: {c['text_main']};
}}

QComboBox QAbstractItemView::item:selected {{
    background-color: {c['accent']};
    color: {c['text_inverse']};
}}

QComboBox QAbstractItemView::item:checked {{
    background-image: url(data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%2310b981' stroke-width='2'><polyline points='20 6 9 17 4 12'></polyline></svg>);
    background-repeat: no-repeat;
    background-position: left center;
    background-position-x: 6px;
}}

QComboBox QAbstractItemView::item:checked:selected {{
    background-image: url(data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%23000000' stroke-width='2'><polyline points='20 6 9 17 4 12'></polyline></svg>);
    background-repeat: no-repeat;
    background-position: left center;
}}

QSpinBox, QDoubleSpinBox {{
    background-color: {c['bg_input']};
    color: {c['text_main']};
    border: 1px solid {c['border']};
    padding: 5px;
    border-radius: 5px;
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
}}

QListWidget::item:selected, QTreeWidget::item:selected {{
    background-color: {c['accent']};
    color: {c['text_inverse']};
}}

QListWidget::item:selected:active, QTreeWidget::item:selected:active {{
    background-color: {c['accent']};
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
    padding: 5px;
    border-radius: 5px;
}}

QCheckBox {{
    color: {c['text_main']};
    spacing: 8px;
}}

QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    min-width: 16px;
    min-height: 16px;
    max-width: 16px;
    max-height: 16px;
    border-radius: 3px;
    border: 2px solid {c['checkbox_border']};
    background-color: {c['checkbox_bg']};
    image: none;
}}

QCheckBox::indicator:unchecked {{
    border: 2px solid {c['checkbox_border']};
    background-color: {c['checkbox_bg']};
    image: none;
}}

QCheckBox::indicator:hover {{
    border-color: {c['border_focus']};
    background-color: {c['checkbox_bg']};
}}

QCheckBox::indicator:checked {{
    background-color: {c['accent']};
    border-color: {c['accent']};
    image: url({checkmark});
}}

QCheckBox::indicator:checked:hover {{
    background-color: {c['accent_hover']};
    border-color: {c['accent_hover']};
    image: url({checkmark});
}}

QCheckBox::indicator:disabled {{
    border-color: {c['border']};
    background-color: {c['bg_input']};
}}

QCheckBox:disabled {{
    color: {c['text_muted']};
}}

QScrollArea {{
    border: none;
    background: transparent;
}}

QScrollBar:vertical {{
    background: {c['bg_card']};
    width: 12px;
    margin: 0px;
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
"""

# 为了向后兼容，保留QSS变量（但它是静态的，建议使用get_qss()函数）
QSS = get_qss()
