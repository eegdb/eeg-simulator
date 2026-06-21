"""源配置页面 - NavigationView 布局"""

import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
                             QPushButton, QLabel, QComboBox, QDoubleSpinBox,
                             QFrame, QCheckBox, QSpinBox, QMessageBox,
                             QApplication, QProgressDialog)
from PyQt6.QtCore import Qt

from ..themes import get_color
from ..widgets.navigation_view import NavigationPage
from ..widgets.head_layout import HeadLayoutWidget
from ...utils.mne_loader import resolve_standard_montage
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


class SourceConfigPage(NavigationPage):
    """源配置页面"""
    
    def __init__(self, parent_simulator, parent=None):
        self.parent_simulator = parent_simulator
        super().__init__(
            title=tr('nav_source_config'),
            subtitle=tr('nav_source_config_subtitle'),
            parent=parent
        )
        
        self.loaded_src = None
        self.loaded_src_path = None
        self.src_labels = {'lh': {}, 'rh': {}}
        self.label_source_map = {'lh': {}, 'rh': {}}
        self.subject = None
        self.active_noise_configs = []
        self._montage_key = 'standard_1020'
        self._montage = resolve_standard_montage(self._montage_key)
        
        self._setup_content()
    
    def _setup_content(self):
        """设置页面内容"""
        layout = self.get_content_layout()
        
        # ========== 源空间加载 ==========
        self.mne_group = QGroupBox(tr('panel_source_space'))
        src_layout = QVBoxLayout(self.mne_group)
        
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
        
        layout.addWidget(self.mne_group)

        # ========== 电极 Montage ==========
        self.montage_group = QGroupBox(tr('panel_electrode_montage'))
        montage_layout = QVBoxLayout(self.montage_group)

        montage_row = QHBoxLayout()
        self.montage_label = QLabel(tr('label_electrode_layout'))
        montage_row.addWidget(self.montage_label)
        self.montage_combo = QComboBox()
        self.montage_combo.setToolTip(tr('tooltip_select_montage'))
        self._populate_montage_combo()
        self.montage_combo.currentIndexChanged.connect(self._on_montage_combo_changed)
        montage_row.addWidget(self.montage_combo, 1)
        montage_layout.addLayout(montage_row)

        self.montage_hint_label = QLabel(tr('montage_select_hint'))
        self.montage_hint_label.setWordWrap(True)
        self.montage_hint_label.setStyleSheet(f"color: {get_color('text_muted')}; font-size: 12px;")
        montage_layout.addWidget(self.montage_hint_label)

        layout.addWidget(self.montage_group)

        # ========== 前向模型 ==========
        self.fwd_group = QGroupBox(tr('panel_forward_model'))
        fwd_layout = QVBoxLayout(self.fwd_group)

        self.fwd_workflow_frame = QFrame()
        self.fwd_workflow_frame.setStyleSheet(f"""
            background-color: {get_color('bg_input')};
            border-radius: 8px;
            border: 1px solid {get_color('border')};
        """)
        fwd_workflow_inner = QVBoxLayout(self.fwd_workflow_frame)
        fwd_workflow_inner.setContentsMargins(12, 10, 12, 10)
        self.fwd_workflow_label = QLabel(tr('fwd_workflow_hint'))
        self.fwd_workflow_label.setWordWrap(True)
        self.fwd_workflow_label.setStyleSheet(f"color: {get_color('blue')}; font-size: 12px;")
        fwd_workflow_inner.addWidget(self.fwd_workflow_label)
        fwd_layout.addWidget(self.fwd_workflow_frame)

        self.compute_fwd_btn = QPushButton(tr('btn_compute_forward'))
        self.compute_fwd_btn.setStyleSheet(get_primary_btn_style())
        self.compute_fwd_btn.setToolTip(tr('tooltip_compute_forward'))
        self.compute_fwd_btn.clicked.connect(self._on_compute_forward)
        fwd_layout.addWidget(self.compute_fwd_btn)

        self.fwd_info_label = QLabel(tr('fwd_not_loaded'))
        self.fwd_info_label.setStyleSheet(f"color: {get_color('text_muted')}; font-size: 12px;")
        self.fwd_info_label.setWordWrap(True)
        fwd_layout.addWidget(self.fwd_info_label)

        layout.addWidget(self.fwd_group)

        # ========== Patch 管理 ==========
        self.patch_group = QGroupBox(tr('panel_patch'))
        patch_layout = QVBoxLayout(self.patch_group)
        
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
        layout.addWidget(self.patch_group)
        
        # ========== BEM 导电率设置 ==========
        self.bem_group = QGroupBox(tr('bem_conductivity'))
        bem_layout = QVBoxLayout(self.bem_group)
        
        # 脑组织
        brain_layout = QHBoxLayout()
        self.brain_cond_label = QLabel(f"{tr('bem_conductivity_brain')} (S/m):")
        brain_layout.addWidget(self.brain_cond_label)
        self.brain_cond_spin = QDoubleSpinBox()
        self.brain_cond_spin.setRange(0.1, 2.0)
        self.brain_cond_spin.setDecimals(3)
        self.brain_cond_spin.setValue(0.3)
        brain_layout.addWidget(self.brain_cond_spin)
        bem_layout.addLayout(brain_layout)
        
        # 颅骨
        skull_layout = QHBoxLayout()
        self.skull_cond_label = QLabel(f"{tr('bem_conductivity_skull')} (S/m):")
        skull_layout.addWidget(self.skull_cond_label)
        self.skull_cond_spin = QDoubleSpinBox()
        self.skull_cond_spin.setRange(0.001, 0.1)
        self.skull_cond_spin.setDecimals(4)
        self.skull_cond_spin.setValue(0.00615)
        skull_layout.addWidget(self.skull_cond_spin)
        bem_layout.addLayout(skull_layout)
        
        # 头皮
        scalp_layout = QHBoxLayout()
        self.scalp_cond_label = QLabel(f"{tr('bem_conductivity_scalp')} (S/m):")
        scalp_layout.addWidget(self.scalp_cond_label)
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
        
        layout.addWidget(self.bem_group)
        
        # ========== 噪声设置 ==========
        self.noise_group = QGroupBox(tr('noise_settings'))
        noise_layout = QVBoxLayout(self.noise_group)
        
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
        layout.addWidget(self.noise_group)
        
        # ========== 耦合模型 ==========
        self.coupling_group = QGroupBox(tr('panel_coupling'))
        coupling_layout = QVBoxLayout(self.coupling_group)
        
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
        layout.addWidget(self.coupling_group)
        
        layout.addStretch()

        self.knn_spin.valueChanged.connect(self._on_mne_coupling_params_changed)
        self.decay_spin.valueChanged.connect(self._on_mne_coupling_params_changed)

    def _populate_montage_combo(self):
        """填充 montage 下拉框"""
        current = self._montage_key
        self.montage_combo.blockSignals(True)
        self.montage_combo.clear()
        for key, name in HeadLayoutWidget.get_available_montage_options().items():
            self.montage_combo.addItem(name, key)
        idx = self.montage_combo.findData(current)
        if idx >= 0:
            self.montage_combo.setCurrentIndex(idx)
        self.montage_combo.blockSignals(False)

    def _on_montage_combo_changed(self, _index: int):
        key = self.montage_combo.currentData()
        if key and key != self._montage_key:
            self.set_montage_key(key)

    def get_montage_key(self) -> str | None:
        return self._montage_key

    def get_current_montage(self):
        return self._montage

    def set_montage_key(self, montage_key: str, sync_combo: bool = True):
        """设置 montage 并同步到电极预览页"""
        if not montage_key:
            return
        try:
            self._montage = resolve_standard_montage(montage_key)
            self._montage_key = montage_key
        except Exception as e:
            logger.warning(f"加载 montage 失败 {montage_key}: {e}")
            return
        if sync_combo:
            self.montage_combo.blockSignals(True)
            idx = self.montage_combo.findData(montage_key)
            if idx >= 0:
                self.montage_combo.setCurrentIndex(idx)
            self.montage_combo.blockSignals(False)
        self.sync_montage_to_electrode_page()

    def sync_montage_to_electrode_page(self):
        """将当前 montage 同步到电极页预览与通道列表"""
        sim = self.parent_simulator
        if hasattr(sim, 'electrode_channels_page'):
            ep = sim.electrode_channels_page
            if hasattr(ep, 'head_selector'):
                ep.head_selector.apply_montage_key(self._montage_key)
            ep._update_channel_list()
        if getattr(sim, 'mne_fwd', None) is not None and hasattr(sim, 'mne'):
            sim.mne.refresh_channel_mapping()
        self.update_forward_status()
        if hasattr(sim, 'ui'):
            sim.ui._sync_heatmap_montage()
    
    def _on_mne_coupling_params_changed(self):
        if hasattr(self.parent_simulator, 'signal'):
            self.parent_simulator.signal.invalidate_mne_coupling_cache()
    
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
            self.loaded_src_path = src_path
            total_vertices = sum(s['nuse'] for s in self.loaded_src)
            logger.info(f"源空间加载成功: {src_filename}, 总顶点数: {total_vertices}")
            
            self._load_labels(subjects_dir, self.subject)
            self.parent_simulator.subjects_dir = subjects_dir
            self.parent_simulator.mne.init_mne_coupling_engine(self.loaded_src, self.src_labels)
            
            self.src_info_label.setText(self._get_src_info_text(self.loaded_src))
            self.src_info_label.setStyleSheet(f"color: {get_color('accent')}; font-size: 12px;")

            if src_filename == 'sample-all-src.fif':
                QMessageBox.warning(
                    self,
                    tr('warning'),
                    tr('msg_all_src_no_fwd', src_filename),
                )

            QMessageBox.information(self, tr('success'),
                tr('msg_load_success', 'Sample', total_vertices))
            
        except Exception as e:
            logger.error(f"源空间加载失败: {str(e)}", exc_info=True)
            QMessageBox.critical(self, tr('error'), tr('msg_load_failed', str(e)))

    def _on_compute_forward(self):
        """根据当前 montage 计算前向模型"""
        if self.loaded_src is None:
            QMessageBox.warning(self, tr('warning'), tr('msg_no_src_space'))
            return

        montage_key = self.get_montage_key()
        if not montage_key:
            QMessageBox.warning(self, tr('warning'), tr('msg_select_montage_first'))
            return

        progress = QProgressDialog(tr('msg_computing_forward'), None, 0, 0, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.show()
        QApplication.processEvents()

        try:
            save_dir = self.parent_simulator.current_project_path
            fwd_path = self.parent_simulator.mne.compute_forward_from_montage(save_dir)
            import mne
            fwd = self.parent_simulator.mne_fwd
            n_eeg = len(mne.pick_types(fwd['info'], meg=False, eeg=True, exclude=[]))
            QMessageBox.information(
                self,
                tr('success'),
                tr('msg_fwd_computed', os.path.basename(fwd_path), montage_key, n_eeg),
            )
        except Exception as e:
            logger.error(f"前向模型计算失败: {e}", exc_info=True)
            QMessageBox.critical(self, tr('error'), tr('msg_fwd_compute_failed', str(e)))
        finally:
            progress.close()

    def update_forward_status(self):
        """更新前向模型状态标签"""
        text, color = self._forward_status_text()
        self.fwd_info_label.setText(text)
        self.fwd_info_label.setStyleSheet(f"color: {color}; font-size: 12px;")

    def _forward_status_text(self) -> tuple[str, str]:
        import mne
        sim = self.parent_simulator
        path = getattr(sim, 'mne_fwd_path', None)
        fwd = getattr(sim, 'mne_fwd', None)
        if fwd is None or not path:
            return tr('fwd_not_loaded'), get_color('text_muted')

        n_eeg = len(mne.pick_types(fwd['info'], meg=False, eeg=True, exclude=[]))
        lines = [tr('fwd_loaded_info', os.path.basename(path), n_eeg)]

        montage_key = ''
        if hasattr(sim, 'source_page'):
            montage_key = sim.source_page.get_montage_key() or ''
        if montage_key:
            lines.append(tr('fwd_status_montage', montage_key))

        return '\n'.join(lines), get_color('accent')
    
    def _load_labels(self, subjects_dir, subject):
        """加载解剖学标签"""
        from ...utils.mne_loader import build_label_source_map

        labels_dir = os.path.join(subjects_dir, subject, 'label')
        if not os.path.exists(labels_dir):
            logger.warning(f"标签目录不存在: {labels_dir}")
            return

        self.src_labels, self.label_source_map = build_label_source_map(
            self.loaded_src, subjects_dir, subject
        )

        lh_labels = list(self.label_source_map.get('lh', {}).keys())
        rh_labels = list(self.label_source_map.get('rh', {}).keys())
        a2009s_count = sum(1 for name in lh_labels + rh_labels if name.lower().startswith('a2009s.'))
        aparc_count = len(lh_labels) + len(rh_labels) - a2009s_count

        logger.info(f"标签加载完成: LH={len(lh_labels)}, RH={len(rh_labels)}, aparc={aparc_count}, a2009s={a2009s_count}")
    
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

    def get_bem_conductivity(self):
        """读取当前 UI 中的 BEM 导电率"""
        return (
            self.brain_cond_spin.value(),
            self.skull_cond_spin.value(),
            self.scalp_cond_spin.value(),
        )

    def apply_bem_conductivity(self, conductivity):
        """将保存的导电率恢复到 UI"""
        if not conductivity or len(conductivity) < 3:
            return
        self.brain_cond_spin.setValue(float(conductivity[0]))
        self.skull_cond_spin.setValue(float(conductivity[1]))
        self.scalp_cond_spin.setValue(float(conductivity[2]))
    
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
        if hasattr(self.parent_simulator, 'patch_ops'):
            self.parent_simulator.patch_ops.set_noise_configs(noise_configs)
    
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

    def get_mne_coupling_settings(self) -> dict:
        return {
            'use_mne': self.mne_coupling_check.isChecked(),
            'knn_k': self.knn_spin.value(),
            'decay_length': self.decay_spin.value(),
        }

    def apply_mne_coupling_settings(self, settings: dict):
        if not settings:
            return
        if 'use_mne' in settings:
            self.mne_coupling_check.setChecked(bool(settings['use_mne']))
            self.parent_simulator._use_mne_coupling = bool(settings['use_mne'])
        if 'knn_k' in settings:
            self.knn_spin.setValue(int(settings['knn_k']))
        if 'decay_length' in settings:
            self.decay_spin.setValue(float(settings['decay_length']))
        if hasattr(self.parent_simulator, 'signal'):
            self.parent_simulator.signal.invalidate_mne_coupling_cache()
    
    def _on_manage_coupling(self):
        """打开耦合管理"""
        from ..dialogs import CouplingManagerDialog
        
        dialog = CouplingManagerDialog(self.parent_simulator, parent=self)
        dialog.coupling_changed.connect(self._update_coupling_stats)
        dialog.exec()
    
    def _update_coupling_stats(self):
        """更新耦合统计"""
        couplings = self.parent_simulator.patch_ops.coupling_models
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
        
        from ..themes import get_color
        
        # 更新各组样式
        for group in [self.mne_group, self.montage_group, self.fwd_group, self.patch_group, self.bem_group, 
                      self.noise_group, self.coupling_group]:
            if group:
                group.setStyleSheet(f"""
                    QGroupBox {{
                        background-color: {get_color('bg_card')};
                        color: {get_color('text_main')};
                        border: 1px solid {get_color('border')};
                        margin-top: 10px;
                        border-radius: 8px;
                        padding-top: 10px;
                        font-weight: bold;
                    }}
                """)
        
        # 更新按钮样式
        for btn in [self.sample_btn, self.compute_fwd_btn, self.patch_btn, self.make_bem_btn,
                    self.manage_noise_btn, self.manage_coupling_btn]:
            if btn:
                btn.setStyleSheet(f"""
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
        
        # 更新标签颜色
        if self.loaded_src:
            self.src_info_label.setStyleSheet(f"color: {get_color('accent')}; font-size: 12px;")
        else:
            self.src_info_label.setStyleSheet(f"color: {get_color('text_muted')}; font-size: 12px;")
        if hasattr(self, 'fwd_workflow_frame'):
            self.fwd_workflow_frame.setStyleSheet(f"""
                background-color: {get_color('bg_input')};
                border-radius: 8px;
                border: 1px solid {get_color('border')};
            """)
            self.fwd_workflow_label.setStyleSheet(f"color: {get_color('blue')}; font-size: 12px;")
        self.update_forward_status()
        self.patch_count_label.setStyleSheet(f"font-weight: bold; color: {get_color('accent')};")
        self.patch_coverage_label.setStyleSheet(f"font-size: 12px; color: {get_color('text_muted')};")
        self.noise_count_label.setStyleSheet(f"font-weight: bold; color: {get_color('accent')};")
        self.noise_type_label.setStyleSheet(f"font-size: 12px; color: {get_color('text_muted')};")
        self.noise_amp_label.setStyleSheet(f"font-size: 12px; color: {get_color('text_muted')};")
        self.coupling_count_label.setStyleSheet(f"font-weight: bold; color: {get_color('accent')};")
        self.coupling_type_label.setStyleSheet(f"font-size: 12px; color: {get_color('text_muted')};")
        
        # 更新统计框架样式
        if hasattr(self, 'patch_frame'):
            self.patch_frame.setStyleSheet(f"""
                background-color: rgba(16, 185, 129, 0.1);
                border-radius: 8px;
                border: 1px solid {get_color('border')};
            """)
        if hasattr(self, 'noise_frame'):
            self.noise_frame.setStyleSheet(f"""
                background-color: rgba(100, 100, 100, 0.1);
                border-radius: 8px;
                border: 1px solid {get_color('border')};
            """)
        if hasattr(self, 'coupling_frame'):
            self.coupling_frame.setStyleSheet(f"""
                background-color: rgba(100, 100, 100, 0.1);
                border-radius: 8px;
                border: 1px solid {get_color('border')};
            """)
    
    def update_texts(self):
        """更新界面文本"""
        # 更新标题
        self.set_title(tr('nav_source_config'))
        self.set_subtitle(tr('nav_source_config_subtitle'))
        
        # 更新组标题
        self.mne_group.setTitle(tr('panel_source_space'))
        self.montage_group.setTitle(tr('panel_electrode_montage'))
        self.montage_label.setText(tr('label_electrode_layout'))
        self.montage_combo.setToolTip(tr('tooltip_select_montage'))
        self.montage_hint_label.setText(tr('montage_select_hint'))
        self._populate_montage_combo()
        self.fwd_group.setTitle(tr('panel_forward_model'))
        self.patch_group.setTitle(tr('panel_patch'))
        self.bem_group.setTitle(tr('bem_conductivity'))
        self.noise_group.setTitle(tr('noise_settings'))
        self.coupling_group.setTitle(tr('panel_coupling'))
        
        # 更新 BEM 标签
        self.brain_cond_label.setText(f"{tr('bem_conductivity_brain')} (S/m):")
        self.skull_cond_label.setText(f"{tr('bem_conductivity_skull')} (S/m):")
        self.scalp_cond_label.setText(f"{tr('bem_conductivity_scalp')} (S/m):")
        
        # 更新按钮文本
        self.sample_btn.setText(tr('btn_load_sample'))
        self.fwd_workflow_label.setText(tr('fwd_workflow_hint'))
        self.compute_fwd_btn.setText(tr('btn_compute_forward'))
        self.compute_fwd_btn.setToolTip(tr('tooltip_compute_forward'))
        self.patch_btn.setText(tr('btn_manage_patches'))
        self.make_bem_btn.setText(tr('bem_make_model'))
        self.manage_noise_btn.setText(tr('btn_manage_noise'))
        self.manage_coupling_btn.setText(tr('btn_manage_coupling'))
        
        # 更新源空间信息
        if self.loaded_src:
            self.src_info_label.setText(self._get_src_info_text(self.loaded_src))
        else:
            self.src_info_label.setText(tr('not_loaded'))

        self.update_forward_status()
        
        # 更新统计信息
        self._update_patch_stats()
        self._update_noise_stats()
        self._update_coupling_stats()
