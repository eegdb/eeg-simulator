"""新建项目对话框"""

import re
import platform

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTextEdit, QPushButton, QMessageBox, QWidget
)
from PyQt6.QtGui import QShowEvent

from ...utils import tr


class NewProjectDialog(QDialog):
    """新建项目对话框"""
    
    # Windows 系统保留名称（不能用作文件夹名）
    WINDOWS_RESERVED_NAMES = {
        'CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4', 'COM5',
        'COM6', 'COM7', 'COM8', 'COM9', 'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5',
        'LPT6', 'LPT7', 'LPT8', 'LPT9'
    }
    
    # 非法字符（Windows/macOS/Linux）
    INVALID_CHARS_PATTERN = r'[<>:"/\\|?*\x00-\x1f]'
    
    def __init__(self, default_name="", parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr('dlg_new_project_title'))
        self.setMinimumSize(450, 320)
        self.setModal(True)
        
        self.project_name = ""
        self.project_description = ""
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 项目名称输入
        name_group = QWidget()
        name_layout = QVBoxLayout(name_group)
        name_layout.setContentsMargins(0, 0, 0, 0)
        name_layout.setSpacing(5)
        
        name_label_layout = QHBoxLayout()
        name_label_layout.addWidget(QLabel(tr('label_project_name')))
        name_required = QLabel("*")
        name_required.setStyleSheet("color: #ef4444;")
        name_label_layout.addWidget(name_required)
        name_label_layout.addStretch()
        name_layout.addLayout(name_label_layout)
        
        self.name_input = QLineEdit()
        self.name_input.setText(default_name)
        self.name_input.setPlaceholderText(tr('hint_project_name'))
        self.name_input.textChanged.connect(self._on_name_changed)
        name_layout.addWidget(self.name_input)
        
        # 错误提示标签
        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #ef4444; font-size: 11px;")
        self.error_label.setVisible(False)
        name_layout.addWidget(self.error_label)
        
        layout.addWidget(name_group)
        
        # 项目备注输入
        desc_group = QWidget()
        desc_layout = QVBoxLayout(desc_group)
        desc_layout.setContentsMargins(0, 0, 0, 0)
        desc_layout.setSpacing(5)
        
        desc_layout.addWidget(QLabel(tr('label_project_desc')))
        
        self.desc_input = QTextEdit()
        self.desc_input.setPlaceholderText(tr('hint_project_desc'))
        self.desc_input.setMaximumHeight(80)
        desc_layout.addWidget(self.desc_input)
        
        layout.addWidget(desc_group)
        
        # 提示信息
        hint_label = QLabel(tr('hint_project_folder_format'))
        hint_label.setStyleSheet("color: #6b7280; font-size: 11px;")
        layout.addWidget(hint_label)
        
        # 命名规则提示
        rules_label = QLabel(tr('hint_project_name_rules'))
        rules_label.setStyleSheet("color: #6b7280; font-size: 11px;")
        rules_label.setWordWrap(True)
        layout.addWidget(rules_label)
        
        layout.addStretch()
        
        # 按钮区域
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton(tr('cancel'))
        cancel_btn.setObjectName("StopBtn")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        self.create_btn = QPushButton(tr('btn_create_project'))
        self.create_btn.setObjectName("PrimaryBtn")
        self.create_btn.clicked.connect(self._on_create)
        self.create_btn.setEnabled(False)
        btn_layout.addWidget(self.create_btn)
        
        layout.addLayout(btn_layout)
        
        # 如果有默认值，检查是否可以启用创建按钮
        if default_name:
            self._on_name_changed(default_name)

    def showEvent(self, event: QShowEvent):
        super().showEvent(event)
        self.name_input.setFocus()

    def _on_name_changed(self, text):
        """项目名称改变时更新创建按钮状态和错误提示"""
        name = text.strip()
        
        if not name:
            self.error_label.setVisible(False)
            self.create_btn.setEnabled(False)
            return
        
        # 验证名称
        is_valid, error_msg = self._validate_project_name(name)
        
        if is_valid:
            self.error_label.setVisible(False)
            self.create_btn.setEnabled(True)
        else:
            self.error_label.setText(error_msg)
            self.error_label.setVisible(True)
            self.create_btn.setEnabled(False)
    
    def _validate_project_name(self, name):
        """验证项目名称是否合法
        
        Returns:
            (is_valid, error_message)
        """
        # 检查长度
        if len(name) > 100:
            return False, tr('msg_project_name_too_long')
        
        # 检查是否以点或空格开头/结尾（可能导致问题）
        if name.startswith('.') or name.startswith(' '):
            return False, tr('msg_project_name_start_invalid')
        if name.endswith(' ') or name.endswith('.'):
            return False, tr('msg_project_name_end_invalid')
        
        # 检查是否只包含空格
        if not name.replace(' ', ''):
            return False, tr('msg_project_name_empty')
        
        # 检查非法字符
        if re.search(self.INVALID_CHARS_PATTERN, name):
            return False, tr('msg_project_name_invalid')
        
        # 检查 Windows 保留名称（所有平台都检查以确保跨平台兼容）
        name_upper = name.upper()
        if name_upper in self.WINDOWS_RESERVED_NAMES:
            return False, tr('msg_project_name_reserved', name)
        
        # 检查 Windows 保留名称带点（如 CON.txt 也是非法的）
        base_name = name_upper.split('.')[0]
        if base_name in self.WINDOWS_RESERVED_NAMES:
            return False, tr('msg_project_name_reserved', base_name)
        
        return True, ""
    
    def _on_create(self):
        """创建项目"""
        name = self.name_input.text().strip()
        
        is_valid, error_msg = self._validate_project_name(name)
        if not is_valid:
            QMessageBox.warning(self, tr('warning'), error_msg)
            return
        
        self.project_name = name
        self.project_description = self.desc_input.toPlainText().strip()
        self.accept()
    
    def get_project_info(self):
        """获取项目信息"""
        return {
            'name': self.project_name,
            'description': self.project_description
        }
