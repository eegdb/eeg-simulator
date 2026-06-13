"""源空间配置页面 - NavigationView 布局"""

import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
                             QPushButton, QLabel, QComboBox, QDoubleSpinBox,
                             QFrame, QCheckBox, QSpinBox)
from PyQt6.QtCore import Qt

from ..themes import get_color
from ..widgets.navigation_view import NavigationPage
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


class SourceSpacePage(NavigationPage):
    """源空间配置页面"""
    
    def __init__(self, parent_simulator, parent=None):
        self.parent_simulator = parent_simulator
        super().__init__(
            title=tr('nav_source_space'),
            subtitle=tr('nav_source_space_subtitle'),
            parent=parent
        )
        
        self.loaded_src = None
        self.src_labels = {'lh': {}, 'rh': {}}
        self.label_source_map = {'lh': {}, 'rh': {}}
        self.subject = None
        self.active_noise_configs = []
        
        self._setup_content()
    
    def _setup_content(self):
        """设置页面内容"""
        layout = self.get_content_layout()
        
        # ========== 源空间加载 ==========
        src_group = QGroupBox(tr('panel_source_space'))
        src_layout = QVBoxLayout(src_group)
        
        # Src文件选择
        src_select_layout = QHBoxLayout()
        src_select_layout.addWidget(QLabel(tr('label_select_src')))
        
        self.src_combo = QComboBox()
        self.src_combo.setToolTip(tr('tooltip_select_src'))
        self._populate_src_combo()
        src_select_layout.addWidget(self.src_combo, 1)
        src_layout.addLayout(src_select_layout)
        
        # 加载按钮
        self.sample_btn = QPushButton(tr('btn_load_sample'))
        self.sample_btn.setStyleSheet(f"""
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
        """)
        self.sample_btn.setToolTip(tr('tooltip_load_sample'))
        self.sample_btn.clicked.connect(self._on_load_sample_src)
        src_layout.addWidget(self.sample_btn)
        
        # 源空间信息
        self.src_info_label = QLabel(tr('not_loaded'))
        self.src_info_label.setStyleSheet(f"color: {get_color('text_muted')}; font-size: 12px;")
        self.src_info_label.setWordWrap(True)
        src_layout.addWidget(self.src_info_label)
        
        layout.addWidget(src_group)
        
        # ========== Patch 管理 ==========
        patch_group = QGroupBox(tr('panel_patch'))
        patch_layout = QVBoxLayout(patch_group)
        
        self.patch_btn = QPushButton(tr('btn_manage_patches'))
        self.patch_btn.setStyleSheet(get_primary_btn_style())
        self.patch_btn.clicked.connect(self._on_manage_patches)
        patch_layout.addWidget(self.patch_btn)
        
        # Patch 统计
        self.patch_frame = QFrame()
        self.patch_frame.setStyleSheet(f"""
            background-color: rgba(16, 185, 129, 0.1);
            border-radius: 8px;
            border: 1px solid {get_color('border')};
        """)
        patch_stats_layout = QVBoxLayout(self.patch_frame)
        patch_stats_layout.setContentsMargins(16, 12, 16, 12)
        
        self.patch_count_label = QLabel(tr('label_patch_count', 0))
        self.patch_count_label.setStyleSheet(f"font-weight: bold; color: {get_color('accent')};")
        patch_stats_layout.addWidget(self.patch_count_label)
        
        self.patch_coverage_label = QLabel(tr('label_patch_coverage', 0, 0))
        self.patch_coverage_label.setStyleSheet(f"font-size: 12px; color: {get_color('text_muted')};")
        patch_stats_layout.addWidget(self.patch_coverage_label)
        
        patch_layout.addWidget(self.patch_frame)
        layout.addWidget(patch_group)
        
        # ========== BEM 导电率设置 ==========
        bem_group = QGroupBox(tr('bem_conductivity'))
        bem_layout = QVBoxLayout(bem_group)
        
        # 脑组织
        brain_layout = QHBoxLayout()
        brain_layout.addWidget(QLabel(f"{tr('bem_conductivity_brain')} (S/m):"))
        self.brain_cond_spin = QDoubleSpinBox()
        self.brain_cond_spin.setRange(0.1, 2.0)
        self.brain_cond_spin.setDecimals(3)
        self.brain_cond_spin.setValue(0.3)
        brain_layout.addWidget(self.brain_cond_spin)
        bem_layout.addLayout(brain_layout)
        
        # 颅骨
        skull_layout = QHBoxLayout()
        skull_layout.addWidget(QLabel(f"{tr('bem_conductivity_skull')} (S/m):"))
        self.skull_cond_spin = QDoubleSpinBox()
        self.skull_cond_spin.setRange(0.001, 0.1)
        self.skull_cond_spin.setDecimals(4)
        self.skull_cond_spin.setValue(0.00615)
        skull_layout.addWidget(self.skull_cond_spin)
        bem_layout.addLayout(skull_layout)
        
        # 头皮
        scalp_layout = QHBoxLayout()
        scalp_layout.addWidget(QLabel(f"{tr('bem_conductivity_scalp')} (S/m):"))
        self.scalp_cond_spin = QDoubleSpinBox()
        self.scalp_cond_spin.setRange(0.1, 2.0)
        self.scalp_cond_spin.setDecimals(3)
        self.scalp_cond_spin.setValue(0.3)
        scalp_layout.addWidget(self.scalp_cond_spin)
        bem_layout.addLayout(scalp_layout)
        
        # 生成按钮
        self.make_bem_btn = QPushButton(tr('bem_make_model'))
        self.make_bem_btn.setStyleSheet(get_primary_btn_style())
        self.make_bem_btn.clicked.connect(self._on_make_bem_model)
        bem_layout.addWidget(self.make_bem_btn)
        
        layout.addWidget(bem_group)
        
        # ========== 噪声设置 ==========
        noise_group = QGroupBox(tr('noise_settings'))
        noise_layout = QVBoxLayout(noise_group)
        
        self.manage_noise_btn = QPushButton(tr('btn_manage_noise'))
        self.manage_noise_btn.setStyleSheet(get_primary_btn_style())
        self.manage_noise_btn.clicked.connect(self._on_manage_noise)
        noise_layout.addWidget(self.manage_noise_btn)
        
        # 噪声统计
        self.noise_frame = QFrame()
        self.noise_frame.setStyleSheet(f"""
            background-color: rgba(100, 100, 100, 0.1);
            border-radius: 8px;
            border: 1px solid {get_color('border')};
        """)
        noise_stats_layout = QVBoxLayout(self.noise_frame)
        noise_stats_layout.setContentsMargins(16, 12, 16, 12)
        
        self.noise_count_label = QLabel(tr('noise_count_zero'))
        self.noise_count_label.setStyleSheet(f"font-weight: bold; color: {get_color('accent')};")
        noise_stats_layout.addWidget(self.noise_count_label)
        
        self.noise_type_label = QLabel(tr('noise_type_stats', 0, 0, 0, 0))
        self.noise_type_label.setStyleSheet(f"font-size: 12px; color: {get_color('text_muted')};")
        noise_stats_layout.addWidget(self.noise_type_label)
        
        self.noise_amp_label = QLabel(tr('noise_total_amp', 0))
        self.noise_amp_label.setStyleSheet(f"font-size: 12px; color: {get_color('text_muted')};")
        noise_stats_layout.addWidget(self.noise_amp_label)
        
        noise_layout.addWidget(self.noise_frame)
        layout.addWidget(noise_group)
        
        # ========== 耦合模型 ==========
        coupling_group = QGroupBox(tr('panel_coupling'))
        coupling_layout = QVBoxLayout(coupling_group)
        
        # MNE 耦合开关
        self.mne_coupling_check = QCheckBox(tr('label_use_mne_coupling'))
        self.mne_coupling_check.setChecked(True)
        self.mne_coupling_check.stateChanged.connect(self._on_mne_coupling_toggled)
        coupling_layout.addWidget(self.mne_coupling_check)
        
        # KNN 参数
        knn_layout = QHBoxLayout()
        knn_layout.addWidget(QLabel(tr('label_knn_k')))
        self.knn_spin = QSpinBox()
        self.knn_spin.setRange(1, 10)
        self.knn_spin.setValue(3)
        knn_layout.addWidget(self.knn_spin)
        coupling_layout.addLayout(knn_layout)
        
        # 衰减长度
        decay_layout = QHBoxLayout()
        decay_layout.addWidget(QLabel(tr('label_decay_length')))
        self.decay_spin = QDoubleSpinBox()
        self.decay_spin.setRange(0.001, 0.1)
        self.decay_spin.setDecimals(3)
        self.decay_spin.setValue(0.02)
        self.decay_spin.setSuffix(' m')
        decay_layout.addWidget(self.decay_spin)
        coupling_layout.addLayout(decay_layout)
        
        # 管理耦合按钮
        self.manage_coupling_btn = QPushButton(tr('btn_manage_coupling'))
        self.manage_coupling_btn.setStyleSheet(get_primary_btn_style())
        self.manage_coupling_btn.clicked.connect(self._on_manage_coupling)
        coupling_layout.addWidget(self.manage_coupling_btn)
        
        # 耦合统计
        self.coupling_frame = QFrame()
        self.coupling_frame.setStyleSheet(f"""
            background-color: rgba(100, 100, 100, 0.1);
            border-radius: 8px;
            border: 1px solid {get_color('border')};
        """)
        coupling_stats_layout = QVBoxLayout(self.coupling_frame)
        coupling_stats_layout.setContentsMargins(16, 12, 16, 12)
        
        self.coupling_count_label = QLabel(tr('coupling_count_zero'))
        self.coupling_count_label.setStyleSheet(f"font-weight: bold; color: {get_color('accent')};")
        coupling_stats_layout.addWidget(self.coupling_count_label)
        
        self.coupling_type_label = QLabel(tr('coupling_type_stats', 0, 0, 0))
        self.coupling_type_label.setStyleSheet(f"font-size: 12px; color: {get_color('text_muted')};")
        coupling_stats_layout.addWidget(self.coupling_type_label)
        
        coupling_layout.addWidget(self.coupling_frame)
        layout.addWidget(coupling_group)
        
        layout.addStretch()
    
    def _populate_src_combo(self):
        """填充src文件选择下拉框"""
        src_options = [
            ('sample-oct-6-src.fif', 'Oct-6'),
            ('sample-all-src.fif', 'All'),
            ('sample-oct-6-orig-src.fif', 'Oct-6 Orig'),
            ('volume-7mm-src.fif', 'Volume 7mm'),
            ('sample-fsaverage-ico-5-src.fif', 'FSAverage Ico-5'),
        ]
        for filename, display_name in src_options:
            self.src_combo.addItem(display_name, filename)
    
    def _on_load_sample_src(self):
        """加载MNE Sample数据集的源空间"""
        import mne
        import numpy as np
        from PyQt6.QtWidgets import QMessageBox
        
        try:
            data_path = mne.datasets.sample.data_path()
            subjects_dir = os.path.join(data_path, 'subjects')
            self.subject = 'sample'
            
            src_filename = self.src_combo.currentData()
            src_path = os.path.join(subjects_dir, self.subject, 'bem', src_filename)
            
            logger.info(f"开始加载源空间: {src_filename}")
            
            if not os.path.exists(src_path):
                QMessageBox.warning(self, tr('error'), tr('msg_file_not_exist', src_path))
                return
            
            self.loaded_src = mne.read_source_spaces(src_path)
            total_vertices = sum(s['nuse'] for s in self.loaded_src)
            logger.info(f"源空间加载成功: {src_filename}, 总顶点数: {total_vertices}")
            
            self._load_labels(subjects_dir, self.subject)
            self.parent_simulator.subjects_dir = subjects_dir
            self.parent_simulator.init_mne_coupling_engine(self.loaded_src, self.src_labels)
            
            self.src_info_label.setText(self._get_src_info_text(self.loaded_src))
            self.src_info_label.setStyleSheet(f"color: {get_color('accent')}; font-size: 12px;")
            
            # 自动加载匹配的正向模型
            fwd_mapping = {
                'sample-oct-6-src.fif': 'sample_audvis-eeg-oct-6-fwd.fif',  # 优先EEG
                'sample-all-src.fif': 'sample_audvis-eeg-oct-6-fwd.fif',
                'sample-oct-6-orig-src.fif': 'sample_audvis-eeg-oct-6-fwd.fif',
                'volume-7mm-src.fif': None,
                'sample-fsaverage-ico-5-src.fif': 'sample_audvis-meg-eeg-ico-5-fwd.fif',
            }
            fwd_filename = fwd_mapping.get(src_filename)
            if fwd_filename:
                fwd_path = os.path.join(data_path, 'MEG', 'sample', fwd_filename)
                if os.path.exists(fwd_path):
                    try:
                        self.parent_simulator.load_mne_data(fwd_path)
                    except Exception as fwd_e:
                        logger.warning(f"正向模型加载失败: {fwd_e}")
            
            QMessageBox.information(self, tr('success'),
                tr('msg_load_success', 'Sample', total_vertices))
            
        except Exception as e:
            logger.error(f"源空间加载失败: {str(e)}", exc_info=True)
            QMessageBox.critical(self, tr('error'), tr('msg_load_failed', str(e)))
    
    def _load_labels(self, subjects_dir, subject):
        """加载解剖学标签"""
        import mne
        import os
        
        self.src_labels = {'lh': {}, 'rh': {}}
        self.label_source_map = {'lh': {}, 'rh': {}}
        labels_dir = os.path.join(subjects_dir, subject, 'label')
        
        if not os.path.exists(labels_dir):
            return
        
        # 简化版标签加载逻辑
        # 实际实现可以参考 source_config.py 中的完整逻辑
        logger.info(f"加载标签: {labels_dir}")
    
    def _get_src_info_text(self, src):
        """获取源空间信息文本"""
        total = sum(s['nuse'] for s in src)
        lines = [tr('src_total_vertices', total)]
        for i, s in enumerate(src):
            if s['type'] == 'surf':
                hemi = tr('label_left') if i == 0 else tr('label_right')
                lines.append(f"  {hemi}: {s['nuse']} {tr('label_vertex')}")
        return "\n".join(lines)
    
    def _on_manage_patches(self):
        """打开Patch管理器"""
        from ..dialogs import PatchManagerDialog
        from PyQt6.QtWidgets import QMessageBox
        
        if self.loaded_src is None:
            QMessageBox.warning(self, tr('warning'), tr('msg_no_src_space'))
            return
        
        dialog = PatchManagerDialog(self.parent_simulator, parent=self)
        dialog.patch_created.connect(self._update_patch_stats)
        dialog.patch_modified.connect(self._update_patch_stats)
        dialog.patch_deleted.connect(self._update_patch_stats)
        dialog.exec()
    
    def _on_make_bem_model(self):
        """生成BEM模型"""
        import mne
        from PyQt6.QtWidgets import QMessageBox
        
        if not self.subject:
            QMessageBox.warning(self, tr('warning'), tr('msg_no_src_space'))
            return
        
        try:
            brain_cond = self.brain_cond_spin.value()
            skull_cond = self.skull_cond_spin.value()
            scalp_cond = self.scalp_cond_spin.value()
            conductivity = (brain_cond, skull_cond, scalp_cond)
            
            subjects_dir = self.parent_simulator.subjects_dir
            bem_model = mne.make_bem_model(
                subject=self.subject,
                ico=4,
                conductivity=conductivity,
                subjects_dir=subjects_dir,
            )
            
            self.parent_simulator.bem_model = bem_model
            self.parent_simulator.bem_conductivity = conductivity
            
            QMessageBox.information(self, tr('success'), tr('bem_model_created'))
            
        except Exception as e:
            QMessageBox.critical(self, tr('error'), tr('msg_bem_failed', str(e)))
    
    def _on_manage_noise(self):
        """打开噪声管理界面"""
        from ..dialogs import NoiseManagerDialog
        
        dialog = NoiseManagerDialog(
            existing_configs=self.active_noise_configs,
            parent=self
        )
        dialog.noise_config_changed.connect(self._on_noise_config_changed)
        dialog.exec()
    
    def _on_noise_config_changed(self, noise_configs):
        """噪声配置改变"""
        self.active_noise_configs = noise_configs
        self._update_noise_stats()
        if hasattr(self.parent_simulator, 'set_noise_configs'):
            self.parent_simulator.set_noise_configs(noise_configs)
    
    def _update_noise_stats(self):
        """更新噪声统计"""
        count = len(self.active_noise_configs)
        if count > 0:
            self.noise_count_label.setText(tr('noise_count_total', count))
            basic = sum(1 for c in self.active_noise_configs if c['type'] in ['white', 'pink', '1f', 'brown'])
            physio = sum(1 for c in self.active_noise_configs if c['type'] in ['eog', 'emg', 'ecg'])
            line = sum(1 for c in self.active_noise_configs if c['type'] == 'line')
            other = count - basic - physio - line
            self.noise_type_label.setText(tr('noise_type_stats', basic, physio, line, other))
            total_amp = sum(c['amplitude'] for c in self.active_noise_configs)
            self.noise_amp_label.setText(tr('noise_total_amp', total_amp))
        else:
            self.noise_count_label.setText(tr('noise_count_zero'))
            self.noise_type_label.setText(tr('noise_type_stats', 0, 0, 0, 0))
            self.noise_amp_label.setText(tr('noise_total_amp', 0))
    
    def _on_mne_coupling_toggled(self, state):
        """MNE耦合开关切换"""
        self.parent_simulator._use_mne_coupling = (state == 2)
    
    def _on_manage_coupling(self):
        """打开耦合管理"""
        from ..dialogs import CouplingManagerDialog
        
        dialog = CouplingManagerDialog(self.parent_simulator, parent=self)
        dialog.coupling_changed.connect(self._update_coupling_stats)
        dialog.exec()
    
    def _update_coupling_stats(self):
        """更新耦合统计"""
        couplings = self.parent_simulator.coupling_models
        count = len(couplings)
        if count > 0:
            self.coupling_count_label.setText(tr('coupling_count_total', count))
            linear = sum(1 for c in couplings.values() if c.type == 'linear')
            nonlinear = sum(1 for c in couplings.values() if c.type == 'nonlinear')
            delayed = sum(1 for c in couplings.values() if c.type == 'delayed')
            self.coupling_type_label.setText(tr('coupling_type_stats', linear, nonlinear, delayed))
        else:
            self.coupling_count_label.setText(tr('coupling_count_zero'))
            self.coupling_type_label.setText(tr('coupling_type_stats', 0, 0, 0))
    
    def _update_patch_stats(self, *args):
        """更新Patch统计"""
        patches = self.parent_simulator.patches
        patch_count = len(patches)
        total_dipoles = sum(p.get_dipole_count() for p in patches.values())
        self.patch_count_label.setText(tr('label_patch_count', patch_count))
        self.patch_coverage_label.setText(tr('label_patch_coverage', total_dipoles, total_dipoles))
    
    def update_theme(self):
        """更新主题颜色"""
        # 调用父类方法更新基础样式（标题、背景等）
        super().update_theme()
        
        # 更新源信息标签
        if hasattr(self, 'src_info_label'):
            self.src_info_label.setStyleSheet(f"color: {get_color('text_muted')}; font-size: 12px;")
        
        # 更新Patch统计标签
        if hasattr(self, 'patch_count_label'):
            self.patch_count_label.setStyleSheet(f"font-weight: bold; color: {get_color('accent')};")
        if hasattr(self, 'patch_coverage_label'):
            self.patch_coverage_label.setStyleSheet(f"font-size: 12px; color: {get_color('text_muted')};")
        
        # 更新噪声统计标签
        if hasattr(self, 'noise_count_label'):
            self.noise_count_label.setStyleSheet(f"font-weight: bold; color: {get_color('accent')};")
        if hasattr(self, 'noise_type_label'):
            self.noise_type_label.setStyleSheet(f"font-size: 12px; color: {get_color('text_muted')};")
        if hasattr(self, 'noise_amp_label'):
            self.noise_amp_label.setStyleSheet(f"font-size: 12px; color: {get_color('text_muted')};")
        
        # 更新耦合统计标签
        if hasattr(self, 'coupling_count_label'):
            self.coupling_count_label.setStyleSheet(f"font-weight: bold; color: {get_color('accent')};")
        if hasattr(self, 'coupling_type_label'):
            self.coupling_type_label.setStyleSheet(f"font-size: 12px; color: {get_color('text_muted')};")
        
        # 更新框架样式
        if hasattr(self, 'patch_frame'):
            self.patch_frame.setStyleSheet(f"border: 1px solid {get_color('border')};")
        if hasattr(self, 'noise_frame'):
            self.noise_frame.setStyleSheet(f"border: 1px solid {get_color('border')};")
        if hasattr(self, 'coupling_frame'):
            self.coupling_frame.setStyleSheet(f"border: 1px solid {get_color('border')};")
