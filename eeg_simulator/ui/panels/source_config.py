"""源空间配置面板 - 左侧主面板"""

import os
import numpy as np
import mne

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFrame,
                             QPushButton, QLabel, QFileDialog, QMessageBox, QDoubleSpinBox,
                             QComboBox)
from PyQt6.QtCore import Qt

from ..themes import get_color
from ...utils import tr, get_logger

# 获取日志器
logger = get_logger(__name__)


"""源空间配置面板

本模块负责加载MNE源空间数据并配置偶极子源。

坐标系说明（重要）：
- 所有位置使用RAS坐标系（神经影像学标准）
  * R (X轴+): 向右
  * A (Y轴+): 向前（朝向面部）
  * S (Z轴+): 向上（朝向头顶）
  * 原点(0,0,0): 大脑解剖学中心
- 单位：米(m)
- 典型坐标范围：
  * X: -0.07 ~ +0.07 m（左到右，约14cm）
  * Y: -0.10 ~ +0.08 m（后到前，约18cm）
  * Z: -0.06 ~ +0.09 m（下到上，约15cm）

源空间数据结构：
- loaded_src: MNE源空间列表，通常[左半球, 右半球]
- src['rr']: 顶点坐标数组 (N x 3)，单位米
- src['vertno']: 实际使用的顶点索引列表
"""


class SourceConfigPanel(QWidget):
    """源空间配置面板 - 左侧主面板
    
    负责：
    1. 加载MNE Sample数据集的源空间
    2. 从源空间选择顶点创建偶极子
    3. 配置BEM模型导电率
    4. 管理噪声设置
    
    坐标系：RAS，单位：米
    """
    
    def __init__(self, parent_simulator, parent=None):
        super().__init__(parent)
        self.parent_simulator = parent_simulator
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(10)

        self.loaded_src = None      # MNE源空间对象列表
        self.src_labels = {'lh': {}, 'rh': {}}      # 解剖学标签字典
        self.label_source_map = {'lh': {}, 'rh': {}}  # 预计算的label-source映射
        self.subject = None         # 主题名称（如'sample'）

        self.init_mne_section()
        # Patch 区域已合并到源空间部分
        self.init_coupling_section()

        self.main_layout.addStretch()

    def init_mne_section(self):
        """初始化MNE源空间加载部分"""
        self.mne_group = QGroupBox(tr('panel_source_space'))
        layout = QVBoxLayout(self.mne_group)

        # 加载Sample数据集
        sample_layout = QVBoxLayout()
        
        # Src文件选择下拉框
        src_select_layout = QHBoxLayout()
        self.src_select_label = QLabel(tr('label_select_src'))
        src_select_layout.addWidget(self.src_select_label)
        
        self.src_combo = QComboBox()
        self.src_combo.setToolTip(tr('tooltip_select_src'))
        # 添加可用的src文件选项
        self._populate_src_combo()
        src_select_layout.addWidget(self.src_combo, 1)
        sample_layout.addLayout(src_select_layout)
        
        self.sample_btn = QPushButton(tr('btn_load_sample'))
        self.sample_btn.setObjectName("PrimaryBtn")
        self.sample_btn.setToolTip(tr('tooltip_load_sample'))
        self.sample_btn.clicked.connect(self._on_load_sample_src)
        sample_layout.addWidget(self.sample_btn)
        
        layout.addLayout(sample_layout)

        # 从文件加载 (暂时注释掉)
        # self.file_btn = QPushButton(tr('btn_load_from_file'))
        # self.file_btn.setObjectName("PrimaryBtn")
        # self.file_btn.clicked.connect(self._on_load_src_from_file)
        # layout.addWidget(self.file_btn)

        # 源空间信息
        self.src_info_label = QLabel(tr('not_loaded'))
        self.src_info_label.setStyleSheet(f"color: {get_color('text_muted')}; font-size: 11px;")
        self.src_info_label.setWordWrap(True)
        layout.addWidget(self.src_info_label)

        # Patch 管理按钮
        self.patch_group = QPushButton(tr('btn_manage_patches'))
        self.patch_group.setObjectName("PrimaryBtn")
        self.patch_group.clicked.connect(self._on_manual_select)
        layout.addWidget(self.patch_group)
        
        # Patch 统计信息区域
        patch_frame = QFrame()
        patch_frame.setStyleSheet("background-color: rgba(100, 100, 100, 0.1); border-radius: 4px;")
        patch_layout = QVBoxLayout(patch_frame)
        patch_layout.setContentsMargins(10, 8, 10, 8)
        
        # 统计信息
        self.patch_count_label = QLabel(tr('label_patch_count', 0))
        self.patch_count_label.setStyleSheet("font-weight: bold; color: #4CAF50;")
        patch_layout.addWidget(self.patch_count_label)
        
        self.patch_coverage_label = QLabel(tr('label_patch_coverage', 0, 0))
        self.patch_coverage_label.setStyleSheet("font-size: 11px; color: gray;")
        patch_layout.addWidget(self.patch_coverage_label)
        
        layout.addWidget(patch_frame)

        # BEM 导电率设置
        self.cond_group = QGroupBox(tr('bem_conductivity'))
        cond_layout = QVBoxLayout(self.cond_group)

        # Brain conductivity
        brain_layout = QHBoxLayout()
        self.brain_cond_label = QLabel(f"{tr('bem_conductivity_brain')} (S/m):")
        brain_layout.addWidget(self.brain_cond_label)
        self.brain_cond_spin = QDoubleSpinBox()
        self.brain_cond_spin.setRange(0.1, 2.0)
        self.brain_cond_spin.setDecimals(3)
        self.brain_cond_spin.setValue(0.3)
        brain_layout.addWidget(self.brain_cond_spin)
        cond_layout.addLayout(brain_layout)

        # Skull conductivity
        skull_layout = QHBoxLayout()
        self.skull_cond_label = QLabel(f"{tr('bem_conductivity_skull')} (S/m):")
        skull_layout.addWidget(self.skull_cond_label)
        self.skull_cond_spin = QDoubleSpinBox()
        self.skull_cond_spin.setRange(0.001, 0.1)
        self.skull_cond_spin.setDecimals(4)
        self.skull_cond_spin.setValue(0.00615)
        skull_layout.addWidget(self.skull_cond_spin)
        cond_layout.addLayout(skull_layout)

        # Scalp conductivity
        scalp_layout = QHBoxLayout()
        self.scalp_cond_label = QLabel(f"{tr('bem_conductivity_scalp')} (S/m):")
        scalp_layout.addWidget(self.scalp_cond_label)
        self.scalp_cond_spin = QDoubleSpinBox()
        self.scalp_cond_spin.setRange(0.1, 2.0)
        self.scalp_cond_spin.setDecimals(3)
        self.scalp_cond_spin.setValue(0.3)
        scalp_layout.addWidget(self.scalp_cond_spin)
        cond_layout.addLayout(scalp_layout)

        # 生成 BEM 模型按钮
        self.make_bem_btn = QPushButton(tr('bem_make_model'))
        self.make_bem_btn.setObjectName("PrimaryBtn")
        self.make_bem_btn.clicked.connect(self._on_make_bem_model)
        cond_layout.addWidget(self.make_bem_btn)

        layout.addWidget(self.cond_group)

        # 噪声设置（点击按钮打开管理界面）
        self.noise_group = QGroupBox(tr('noise_settings'))
        noise_layout = QVBoxLayout(self.noise_group)
        
        # 管理噪声按钮
        self.manage_noise_btn = QPushButton(tr('btn_manage_noise'))
        self.manage_noise_btn.setObjectName("PrimaryBtn")
        self.manage_noise_btn.clicked.connect(self._on_manage_noise)
        noise_layout.addWidget(self.manage_noise_btn)
        
        # 噪声统计信息框架
        stats_frame = QFrame()
        stats_frame.setStyleSheet("background-color: rgba(100, 100, 100, 0.1); border-radius: 4px;")
        stats_layout = QVBoxLayout(stats_frame)
        stats_layout.setContentsMargins(10, 8, 10, 8)
        
        # 总数量
        self.noise_count_label = QLabel(tr('noise_count_zero'))
        self.noise_count_label.setStyleSheet("font-weight: bold; color: #4CAF50;")
        stats_layout.addWidget(self.noise_count_label)
        
        # 各类噪声数量
        self.noise_type_label = QLabel(tr('noise_type_stats', 0, 0, 0, 0))
        self.noise_type_label.setStyleSheet("font-size: 11px; color: gray;")
        stats_layout.addWidget(self.noise_type_label)
        
        # 总幅度
        self.noise_amp_label = QLabel(tr('noise_total_amp', 0))
        self.noise_amp_label.setStyleSheet("font-size: 11px; color: gray;")
        stats_layout.addWidget(self.noise_amp_label)
        
        noise_layout.addWidget(stats_frame)
        
        # 存储当前噪声配置
        self.active_noise_configs = []

        layout.addWidget(self.noise_group)

        self.main_layout.addWidget(self.mne_group)

    def _populate_src_combo(self):
        """填充src文件选择下拉框"""
        # 预定义的src文件选项
        src_options = [
            ('sample-oct-6-src.fif', 'Oct-6'),
            ('sample-all-src.fif', 'All'),
            ('sample-oct-6-orig-src.fif', 'Oct-6 Orig'),
            ('volume-7mm-src.fif', 'Volume 7mm'),
            ('sample-fsaverage-ico-5-src.fif', 'FSAverage Ico-5'),
        ]
        
        for filename, display_name in src_options:
            self.src_combo.addItem(display_name, filename)
    
    def _get_matching_fwd_filename(self, src_filename):
        """根据源空间文件名获取匹配的正向模型文件名
        
        Args:
            src_filename: 源空间文件名，如 'sample-oct-6-src.fif'
            
        Returns:
            匹配的正向模型文件名，或 None 如果没有找到匹配的
        """
        # 源空间到正向模型的映射
        fwd_mapping = {
            'sample-oct-6-src.fif': 'sample_audvis-eeg-oct-6-fwd.fif',  # 优先EEG
            'sample-all-src.fif': 'sample_audvis-eeg-oct-6-fwd.fif',
            'sample-oct-6-orig-src.fif': 'sample_audvis-eeg-oct-6-fwd.fif',
            'volume-7mm-src.fif': None,  # volume需要重新生成
            'sample-fsaverage-ico-5-src.fif': 'sample_audvis-meg-eeg-ico-5-fwd.fif',
        }
        return fwd_mapping.get(src_filename)
    
    def _on_load_sample_src(self):
        """加载MNE Sample数据集的源空间"""
        try:
            data_path = mne.datasets.sample.data_path()
            subjects_dir = os.path.join(data_path, 'subjects')
            self.subject = 'sample'

            # 获取用户选择的src文件名
            src_filename = self.src_combo.currentData()
            src_path = os.path.join(subjects_dir, self.subject, 'bem', src_filename)
            
            logger.info(f"开始加载源空间: {src_filename}")

            if not os.path.exists(src_path):
                logger.error(f"源空间文件不存在: {src_path}")
                QMessageBox.warning(self, tr('error'),
                    tr('msg_file_not_exist', src_path))
                return

            self.loaded_src = mne.read_source_spaces(src_path)
            total_vertices = sum(s['nuse'] for s in self.loaded_src)
            logger.info(f"源空间加载成功: {src_filename}, 总顶点数: {total_vertices}")
            self._load_labels(subjects_dir, self.subject)
            
            # 保存 subjects_dir 用于后续 BEM 模型生成
            self.parent_simulator.subjects_dir = subjects_dir
            
            # 初始化 MNE 耦合引擎
            self.parent_simulator.init_mne_coupling_engine(
                self.loaded_src, 
                self.src_labels
            )

            self.src_info_label.setText(self._get_src_info_text(self.loaded_src, self.subject))
            self.src_info_label.setStyleSheet(f"color: {get_color('accent')}; font-size: 11px;")

            # 自动加载匹配的正向模型
            fwd_filename = self._get_matching_fwd_filename(src_filename)
            if fwd_filename:
                fwd_path = os.path.join(data_path, 'MEG', 'sample', fwd_filename)
                if os.path.exists(fwd_path):
                    logger.info(f"自动加载匹配的正向模型: {fwd_filename}")
                    try:
                        self.parent_simulator.load_mne_data(fwd_path)
                    except Exception as fwd_e:
                        logger.warning(f"正向模型加载失败（可能与源空间不匹配）: {fwd_e}")
                        QMessageBox.warning(self, tr('warning'),
                            tr('msg_fwd_mismatch', fwd_filename, str(fwd_e)))
                else:
                    logger.warning(f"匹配的正向模型文件不存在: {fwd_path}")
                    QMessageBox.warning(self, tr('warning'),
                        tr('msg_fwd_not_exist', fwd_path))
            else:
                logger.info(f"源空间 {src_filename} 没有预定义的正向模型匹配")
                QMessageBox.information(self, tr('info'),
                    tr('msg_fwd_manual_required', src_filename))

            QMessageBox.information(self, tr('success'),
                tr('msg_load_success', 'Sample', total_vertices))

        except Exception as e:
            logger.error(f"源空间加载失败: {str(e)}", exc_info=True)
            QMessageBox.critical(self, tr('error'), tr('msg_load_failed', str(e)))

    def _on_load_src_from_file(self):
        """从文件加载源空间"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, tr('dlg_select_src_file'), "",
            tr('filter_src_files')
        )
        if file_path:
            try:
                self.loaded_src = mne.read_source_spaces(file_path)

                self.src_info_label.setText(self._get_src_info_text(self.loaded_src, tr('not_loaded')))
                self.src_info_label.setStyleSheet(f"color: {get_color('accent')}; font-size: 11px;")

                self.manual_select_btn.setEnabled(True)

                QMessageBox.information(self, tr('success'),
                    tr('msg_load_success', '', sum(s['nuse'] for s in self.loaded_src)))

            except Exception as e:
                QMessageBox.critical(self, tr('error'), tr('msg_load_failed', str(e)))

    def _on_make_bem_model(self):
        """生成 BEM 模型"""
        if not hasattr(self, 'subject') or not self.subject:
            logger.warning("生成BEM模型失败: 未加载源空间")
            QMessageBox.warning(self, tr('warning'), 
                tr('msg_no_src_space'))
            return
        
        try:
            # 获取导电率值
            brain_cond = self.brain_cond_spin.value()
            skull_cond = self.skull_cond_spin.value()
            scalp_cond = self.scalp_cond_spin.value()
            
            logger.info(f"开始生成BEM模型: 脑组织={brain_cond}, 颅骨={skull_cond}, 头皮={scalp_cond}")
            
            # 获取 subjects_dir
            if hasattr(self.parent_simulator, 'subjects_dir'):
                subjects_dir = self.parent_simulator.subjects_dir
            else:
                # 尝试从 sample 数据路径获取
                data_path = mne.datasets.sample.data_path()
                subjects_dir = os.path.join(data_path, 'subjects')
            
            # 生成 BEM 模型
            conductivity = (brain_cond, skull_cond, scalp_cond)
            
            QMessageBox.information(self, tr('info'), 
                tr('msg_bem_creating').format(brain_cond, skull_cond, scalp_cond))
            
            # 实际生成 BEM 模型
            bem_model = mne.make_bem_model(
                subject=self.subject,
                ico=4,
                conductivity=conductivity,
                subjects_dir=subjects_dir,
            )
            
            # 保存到父仿真器
            self.parent_simulator.bem_model = bem_model
            self.parent_simulator.bem_conductivity = conductivity
            
            logger.info("BEM模型生成成功")
            QMessageBox.information(self, tr('success'), 
                tr('bem_model_created'))
            
        except Exception as e:
            logger.error(f"BEM模型生成失败: {str(e)}", exc_info=True)
            QMessageBox.critical(self, tr('error'), 
                tr('msg_bem_failed').format(str(e)))

    def _on_manage_noise(self):
        """打开噪声管理界面"""
        from ..dialogs import NoiseManagerDialog
        
        # 传递已有配置给对话框
        dialog = NoiseManagerDialog(existing_configs=self.active_noise_configs, parent=self)
        dialog.noise_config_changed.connect(self._on_noise_config_changed)
        
        dialog.exec()
    
    def update_noise_stats(self):
        """更新噪声统计信息显示"""
        count = len(self.active_noise_configs)
        if count > 0:
            self.noise_count_label.setText(tr('noise_count_total', count))
            self.noise_count_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
            
            # 统计各类噪声数量
            basic_count = sum(1 for c in self.active_noise_configs if c['type'] in ['white', 'pink', '1f', 'brown'])
            physio_count = sum(1 for c in self.active_noise_configs if c['type'] in ['eog', 'emg', 'ecg'])
            line_count = sum(1 for c in self.active_noise_configs if c['type'] == 'line')
            other_count = count - basic_count - physio_count - line_count
            
            self.noise_type_label.setText(tr('noise_type_stats', basic_count, physio_count, line_count, other_count))
            self.noise_type_label.setStyleSheet("font-size: 11px; color: #aaa;")
            
            # 总幅度
            total_amp = sum(c['amplitude'] for c in self.active_noise_configs)
            self.noise_amp_label.setText(tr('noise_total_amp', total_amp))
            self.noise_amp_label.setStyleSheet("font-size: 11px; color: #aaa;")
        else:
            self.noise_count_label.setText(tr('noise_count_zero'))
            self.noise_count_label.setStyleSheet("color: gray;")
            self.noise_type_label.setText(tr('noise_type_stats', 0, 0, 0, 0))
            self.noise_type_label.setStyleSheet("font-size: 11px; color: gray;")
            self.noise_amp_label.setText(tr('noise_total_amp', 0))
            self.noise_amp_label.setStyleSheet("font-size: 11px; color: gray;")

    def _on_noise_config_changed(self, noise_configs):
        """噪声配置改变时的回调"""
        self.active_noise_configs = noise_configs
        self.update_noise_stats()
        
        # 传递给父仿真器
        if hasattr(self.parent_simulator, 'set_noise_configs'):
            self.parent_simulator.set_noise_configs(noise_configs)

    def _load_labels(self, subjects_dir, subject):
        """加载解剖学标签，并预计算每个label对应的source"""
        from ...utils.mne_loader import build_label_source_map

        labels_dir = os.path.join(subjects_dir, subject, 'label')
        if not os.path.exists(labels_dir):
            return

        self.src_labels, self.label_source_map = build_label_source_map(
            self.loaded_src, subjects_dir, subject
        )

        lh_labels = list(self.label_source_map.get('lh', {}).keys())
        rh_labels = list(self.label_source_map.get('rh', {}).keys())
        all_labels = lh_labels + rh_labels
        a2009s_count = sum(1 for name in all_labels if name.lower().startswith('a2009s.'))
        aparc_count = len(all_labels) - a2009s_count

        logger.info(f"Label-source map loaded: LH={len(lh_labels)} labels, RH={len(rh_labels)} labels")
        logger.info(f"  - Desikan-Killiany (aparc): {aparc_count} labels")
        logger.info(f"  - Destrieux (a2009s): {a2009s_count} labels")
    
    def _get_src_info_text(self, src, subject):
        """获取源空间信息文本"""
        total = sum(s['nuse'] for s in src)
        lines = [tr('src_total_vertices', total)]

        for i, s in enumerate(src):
            if s['type'] == 'surf':
                hemi = tr('label_left') if i == 0 else tr('label_right')
                lines.append(f"  {hemi}: {s['nuse']} {tr('label_vertex')}")
            else:
                lines.append(f"  SourceSpace {i+1}: {s['nuse']} {tr('label_vertex')}")

        return "\n".join(lines)

    def _on_manual_select(self):
        """打开 Patch 管理器选择源
        
        使用 Patch 的方式选择源：在 Label 中选择源点，设置半径创建 Patch。
        这种方式更灵活，支持按解剖学区域分组管理。
        """
        if self.loaded_src is None:
            return

        from ..dialogs import PatchManagerDialog

        dialog = PatchManagerDialog(
            self.parent_simulator,
            parent=self
        )
        
        # 连接信号以更新主界面
        dialog.patch_created.connect(self._on_patch_changed)
        dialog.patch_modified.connect(self._on_patch_changed)
        dialog.patch_deleted.connect(self._on_patch_changed)
        
        dialog.exec()
    
    def _on_patch_changed(self, patch_id, data=None):
        """Patch 变化时更新界面"""
        self.update_dipole_stats()
        self.update_patch_stats()
        self.update_coupling_stats()

    def _on_add_dipole(self):
        """打开偶极子管理界面"""
        from ..dialogs import DipoleManagerDialog
        
        # 获取 subjects_dir
        subjects_dir = getattr(self.parent_simulator, 'subjects_dir', None)
        subject = self.subject
        
        if not subjects_dir:
            # 尝试从 sample 数据路径获取
            try:
                data_path = mne.datasets.sample.data_path()
                subjects_dir = os.path.join(data_path, 'subjects')
                if not subject:
                    subject = 'sample'
                print(f"Using sample data path: {subjects_dir}, subject: {subject}")
            except Exception as e:
                print(f"Could not get sample data path: {e}")
        
        print(f"Opening DipoleManager with subjects_dir={subjects_dir}, subject={subject}")
        print(f"Labels available: lh={len(self.src_labels.get('lh', {}))}, rh={len(self.src_labels.get('rh', {}))}")
        
        dialog = DipoleManagerDialog(
            self.parent_simulator.dipole_definitions,
            self.parent_simulator,
            src=self.loaded_src,
            labels=self.src_labels,
            subject=subject,
            subjects_dir=subjects_dir,
            parent=self
        )
        
        # 连接信号以更新主界面
        dialog.dipole_added.connect(self._on_dipole_list_changed)
        dialog.dipole_modified.connect(self._on_dipole_modified)
        dialog.dipole_deleted.connect(self._on_dipole_deleted)
        
        dialog.exec()
    
    def _on_dipole_list_changed(self, dipole_id, data):
        """Dipole 列表变化时更新"""
        print(f"_on_dipole_list_changed: {dipole_id}")
        self.update_dipole_stats()
    
    def _on_dipole_modified(self, dipole_id, data):
        """Dipole 被修改时更新"""
        print(f"_on_dipole_modified: {dipole_id}")
        self.parent_simulator.modify_dipole(
            dipole_id,
            position=data['position'],
            orientation=data['orientation']
        )
        self.update_dipole_stats()
    
    def _on_dipole_deleted(self, dipole_id):
        """Dipole 被删除时更新"""
        print(f"_on_dipole_deleted: {dipole_id}")
        self.parent_simulator.delete_dipole(dipole_id)
        self.update_dipole_stats()
        self.update_coupling_list()

    def update_dipole_stats(self):
        """更新偶极子统计信息"""
        dipoles = self.parent_simulator.dipole_definitions
        total = len(dipoles)
        
        # 统计半球分布
        lh_count = sum(1 for d in dipoles.values() if hasattr(d, 'hemi') and d.hemi == 'lh')
        rh_count = sum(1 for d in dipoles.values() if hasattr(d, 'hemi') and d.hemi == 'rh')
        
        # 统计来源（来自源空间 vs 手动添加）
        from_src = sum(1 for d in dipoles.values() if hasattr(d, 'vertno') and d.vertno is not None)
        manual = total - from_src
        
        print(f"Updating dipole stats: total={total}, lh={lh_count}, rh={rh_count}, src={from_src}, manual={manual}")
        
        # Dipole Definitions 区域已移除，保留统计日志用于调试
        pass

    def _on_patch_list_changed(self, patch_id, data=None):
        """Patch 列表变化时更新"""
        print(f"Patch list changed: {patch_id}")
        self.update_patch_stats()
        self.update_dipole_stats()  # Patch 变化也会影响偶极子统计
    
    def update_patch_stats(self):
        """更新 Patch 统计信息"""
        patches = self.parent_simulator.patches
        
        patch_count = len(patches)
        
        # 计算所有 Patch 中的偶极子总数
        # 注意：在新架构中，偶极子直接属于 Patch，不再单独统计
        total_dipoles = sum(p.get_dipole_count() for p in patches.values())
        
        self.patch_count_label.setText(tr('label_patch_count', patch_count))
        self.patch_coverage_label.setText(tr('label_patch_coverage', total_dipoles, total_dipoles))
        
        # 强制刷新UI
        self.patch_count_label.repaint()
        self.patch_coverage_label.repaint()

    def init_coupling_section(self):
        """初始化耦合模型部分"""
        self.coupling_group = QGroupBox(tr('panel_coupling'))
        layout = QVBoxLayout(self.coupling_group)

        # MNE 耦合模式开关
        from PyQt6.QtWidgets import QCheckBox
        self.mne_coupling_check = QCheckBox(tr('label_use_mne_coupling'))
        self.mne_coupling_check.setChecked(True)
        self.mne_coupling_check.setToolTip(tr('tooltip_mne_coupling'))
        self.mne_coupling_check.stateChanged.connect(self._on_mne_coupling_toggled)
        layout.addWidget(self.mne_coupling_check)
        
        # MNE 耦合参数设置
        from PyQt6.QtWidgets import QSpinBox
        
        # KNN 参数
        knn_layout = QHBoxLayout()
        knn_layout.addWidget(QLabel(tr('label_knn_k')))
        self.knn_spin = QSpinBox()
        self.knn_spin.setRange(1, 10)
        self.knn_spin.setValue(3)
        self.knn_spin.setToolTip(tr('tooltip_knn_k'))
        knn_layout.addWidget(self.knn_spin)
        layout.addLayout(knn_layout)
        
        # 衰减长度参数
        decay_layout = QHBoxLayout()
        decay_layout.addWidget(QLabel(tr('label_decay_length')))
        self.decay_spin = QDoubleSpinBox()
        self.decay_spin.setRange(0.001, 0.1)
        self.decay_spin.setDecimals(3)
        self.decay_spin.setValue(0.02)
        self.decay_spin.setSuffix(' m')
        self.decay_spin.setToolTip(tr('tooltip_decay_length'))
        decay_layout.addWidget(self.decay_spin)
        layout.addLayout(decay_layout)
        
        # MNE 耦合说明
        mne_info = QLabel(tr('label_mne_coupling_info'))
        mne_info.setStyleSheet("font-size: 10px; color: gray;")
        mne_info.setWordWrap(True)
        layout.addWidget(mne_info)

        # 管理耦合按钮
        self.manage_coupling_btn = QPushButton(tr('btn_manage_coupling'))
        self.manage_coupling_btn.setObjectName("PrimaryBtn")
        self.manage_coupling_btn.clicked.connect(self._on_manage_coupling)
        layout.addWidget(self.manage_coupling_btn)
        
        # 耦合统计信息框架
        stats_frame = QFrame()
        stats_frame.setStyleSheet("background-color: rgba(100, 100, 100, 0.1); border-radius: 4px;")
        stats_layout = QVBoxLayout(stats_frame)
        stats_layout.setContentsMargins(10, 8, 10, 8)
        
        # 总数量
        self.coupling_count_label = QLabel(tr('coupling_count_zero'))
        self.coupling_count_label.setStyleSheet("font-weight: bold; color: #4CAF50;")
        stats_layout.addWidget(self.coupling_count_label)
        
        # 耦合类型统计
        self.coupling_type_label = QLabel(tr('coupling_type_stats', 0, 0, 0))
        self.coupling_type_label.setStyleSheet("font-size: 11px; color: gray;")
        stats_layout.addWidget(self.coupling_type_label)
        
        # 简要列表（显示前几个耦合）
        self.coupling_preview_label = QLabel(tr('coupling_preview_none'))
        self.coupling_preview_label.setStyleSheet("font-size: 10px; color: #888;")
        self.coupling_preview_label.setWordWrap(True)
        stats_layout.addWidget(self.coupling_preview_label)
        
        layout.addWidget(stats_frame)

        self.main_layout.addWidget(self.coupling_group)
        self.update_coupling_stats()

    def _on_mne_coupling_toggled(self, state):
        """MNE 耦合开关切换"""
        use_mne = state == 2  # Qt.Checked = 2
        self.parent_simulator._use_mne_coupling = use_mne
        logger.info(f"MNE 耦合模式: {'启用' if use_mne else '禁用'}")

    def _on_manage_coupling(self):
        """打开耦合模型管理对话框"""
        from ..dialogs import CouplingManagerDialog
        
        dialog = CouplingManagerDialog(
            self.parent_simulator,
            parent=self
        )
        
        # 连接信号以更新主界面
        dialog.coupling_changed.connect(self.update_coupling_stats)
        
        dialog.exec()

    def update_coupling_stats(self):
        """更新耦合模型统计信息"""
        couplings = self.parent_simulator.coupling_models
        count = len(couplings)
        
        if count > 0:
            self.coupling_count_label.setText(tr('coupling_count_total', count))
            self.coupling_count_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
            
            # 统计各类耦合数量
            linear_count = sum(1 for c in couplings.values() if c.type == 'linear')
            nonlinear_count = sum(1 for c in couplings.values() if c.type == 'nonlinear')
            delayed_count = sum(1 for c in couplings.values() if c.type == 'delayed')
            
            self.coupling_type_label.setText(
                tr('coupling_type_stats', linear_count, nonlinear_count, delayed_count)
            )
            self.coupling_type_label.setStyleSheet("font-size: 11px; color: #aaa;")
            
            # 预览前3个耦合
            preview_text = []
            for i, (cid, c) in enumerate(couplings.items()):
                if i >= 3:
                    preview_text.append(f"... {tr('coupling_more', count - 3)}")
                    break
                source_name = self.parent_simulator.patches.get(c.source_patch_id, {}).name or c.source_patch_id
                target_name = self.parent_simulator.patches.get(c.target_patch_id, {}).name or c.target_patch_id
                preview_text.append(f"• {source_name[:15]}→{target_name[:15]}: {c.strength:.2f}")
            
            self.coupling_preview_label.setText("\n".join(preview_text))
        else:
            self.coupling_count_label.setText(tr('coupling_count_zero'))
            self.coupling_count_label.setStyleSheet("color: gray;")
            self.coupling_type_label.setText(tr('coupling_type_stats', 0, 0, 0))
            self.coupling_type_label.setStyleSheet("font-size: 11px; color: gray;")
            self.coupling_preview_label.setText(tr('coupling_preview_none'))

    def update_ui_texts(self):
        """更新所有界面文本（语言切换时调用）"""
        # 更新 MNE 源空间部分
        self.mne_group.setTitle(tr('panel_source_space'))
        self.src_select_label.setText(tr('label_select_src'))
        self.src_combo.setToolTip(tr('tooltip_select_src'))
        self.sample_btn.setText(tr('btn_load_sample'))
        self.sample_btn.setToolTip(tr('tooltip_load_sample'))
        # self.file_btn.setText(tr('btn_load_from_file'))
        if self.loaded_src is None:
            self.src_info_label.setText(tr('not_loaded'))
        self.patch_group.setText(tr('panel_patch'))
        
        # 更新 BEM 导电率部分
        self.cond_group.setTitle(tr('bem_conductivity'))
        self.brain_cond_label.setText(f"{tr('bem_conductivity_brain')} (S/m):")
        self.skull_cond_label.setText(f"{tr('bem_conductivity_skull')} (S/m):")
        self.scalp_cond_label.setText(f"{tr('bem_conductivity_scalp')} (S/m):")
        self.make_bem_btn.setText(tr('bem_make_model'))
        
        # 更新噪声设置部分
        self.noise_group.setTitle(tr('noise_settings'))
        self.manage_noise_btn.setText(tr('btn_manage_noise'))
        self.update_noise_stats()  # 这会更新噪声统计标签
        
        # 更新偶极子部分
        self.update_dipole_stats()  # 保留日志记录
        
        # 更新 Patch 按钮文本
        self.patch_group.setText(tr('btn_manage_patches'))
        self.update_patch_stats()  # 这会更新 Patch 统计标签
        
        # 更新耦合模型部分
        self.coupling_group.setTitle(tr('panel_coupling'))
        self.mne_coupling_check.setText(tr('label_use_mne_coupling'))
        self.mne_coupling_check.setToolTip(tr('tooltip_mne_coupling'))
        self.knn_spin.setToolTip(tr('tooltip_knn_k'))
        self.decay_spin.setToolTip(tr('tooltip_decay_length'))
        self.manage_coupling_btn.setText(tr('btn_manage_coupling'))
        self.update_coupling_stats()  # 更新耦合统计
