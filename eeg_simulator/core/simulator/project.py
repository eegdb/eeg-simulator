"""项目保存、加载与 UI 数据同步。"""

import os
from datetime import datetime
from pathlib import Path

import mne
from PyQt6.QtWidgets import QMessageBox

from ...models import Patch, CouplingModel
from ...ui.themes import get_color
from ...ui.dialogs import NewProjectDialog
from ...ui.file_dialogs import get_existing_directory
from ...utils import tr, get_logger
from ...utils.project_manager import ProjectManager

logger = get_logger(__name__)


class SimulatorProject:
    """SimulatorProject 服务。"""

    def __init__(self, simulator):
        self._sim = simulator

    def _on_new_project(self):
        """新建项目"""
        from datetime import datetime
        from pathlib import Path

        dialog = NewProjectDialog(parent=self._sim)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return

        project_info = dialog.get_project_info()
        project_name = project_info['name']

        default_dir = self._sim.config.get('default_project_dir', str(Path.home() / 'EEGProjects'))
        Path(default_dir).mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        folder_name = f"{project_name}_{timestamp}"
        project_path = os.path.join(default_dir, folder_name)

        if ProjectManager.create_project(project_path, project_name):
            self._sim.current_project_path = project_path
            self._clear_all_data()
            self._update_window_title()
            QMessageBox.information(self._sim, tr('success'), tr('msg_project_created', project_name))

    def _project_dialog_start_dir(self) -> str:
        if self._sim.current_project_path:
            return self._sim.current_project_path
        default_dir = self._sim.config.get('default_project_dir', '')
        if default_dir and os.path.isdir(default_dir):
            return default_dir
        return str(Path.home())

    def _on_open_project(self):
        """打开项目"""
        project_dir = get_existing_directory(
            self._sim, tr('dlg_open_project'), self._project_dialog_start_dir()
        )
        if not project_dir:
            return

        if not ProjectManager.is_valid_project(project_dir):
            QMessageBox.warning(self._sim, tr('error'), tr('msg_invalid_project'))
            return

        self._load_project_data(project_dir)

    def _on_save_project(self):
        """保存项目"""
        if not self._sim.current_project_path:
            self._create_new_project_with_current_data()
        else:
            self._save_to_project(self._sim.current_project_path)

    def _create_new_project_with_current_data(self):
        """创建新项目并保存当前数据"""
        from datetime import datetime
        from pathlib import Path

        dialog = NewProjectDialog(parent=self._sim)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return

        project_info = dialog.get_project_info()
        project_name = project_info['name']

        default_dir = self._sim.config.get('default_project_dir', str(Path.home() / 'EEGProjects'))
        Path(default_dir).mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        folder_name = f"{project_name}_{timestamp}"
        project_path = os.path.join(default_dir, folder_name)

        if ProjectManager.create_project(project_path, project_name):
            self._sim.current_project_path = project_path
            self._save_to_project(project_path)
            self._sim.ui._update_status_bar()

    def _on_save_project_as(self):
        """另存为"""
        project_dir = get_existing_directory(
            self._sim, tr('dlg_save_project'), self._project_dialog_start_dir()
        )
        if not project_dir:
            return

        project_name = tr('project_untitled')
        if self._sim.current_project_path:
            project_name = ProjectManager.get_project_name(self._sim.current_project_path)

        project_path = os.path.join(project_dir, project_name)

        if not ProjectManager.is_valid_project(project_path):
            ProjectManager.create_project(project_path, project_name)

        self._sim.current_project_path = project_path
        self._save_to_project(project_path)

    def _save_to_project(self, project_path):
        """保存数据到项目"""
        logger.info(f"开始保存项目到: {project_path}")

        patches_data = {patch_id: patch.to_dict() for patch_id, patch in self._sim.patches.items()}
        couplings_data = {cid: c.to_dict() for cid, c in self._sim._coupling_models.items()}

        # 获取 Source Space 信息
        src_info = {}
        if hasattr(self._sim, 'source_page') and self._sim.source_page:
            src_info = {
                "src_filename": self._sim.source_page.src_combo.currentData() if hasattr(self._sim.source_page, 'src_combo') else None,
                "subject": self._sim.source_page.subject,
                "subjects_dir": getattr(self._sim, 'subjects_dir', None),
                "src_path": getattr(self._sim.source_page, 'loaded_src_path', None),
                "fwd_path": getattr(self._sim, 'mne_fwd_path', None),
                "src_labels": self._sim.source_page.src_labels,
                "label_source_map": self._sim.source_page.label_source_map
            }

        selected_channels = getattr(self._sim, 'selected_channels', [])
        electrode_montage = None
        if hasattr(self._sim, 'electrode_channels_page'):
            selected_channels = self._sim.electrode_channels_page.get_selected_channels()
            self._sim.selected_channels = selected_channels
            electrode_montage = self._sim.electrode_channels_page.get_montage_key()

        project_data = {
            "patches": patches_data,
            "couplings": couplings_data,
            "noise": self._sim.noise_configs,
            "bem": self._serialize_bem_config(),
            "config": {
                "sampling_rate": (
                    self._sim.output_page.sr_spin.value()
                    if hasattr(self._sim, 'output_page') else self._sim.sampling_rate
                ),
            },
            "selected_channels": selected_channels,
            "electrode_montage": electrode_montage,
            "source_space": src_info,
            "output": (
                self._sim.output_page.get_output_config()
                if hasattr(self._sim, 'output_page') else {}
            ),
            "signal_filter": (
                self._sim.signal_page.get_filter_params()
                if hasattr(self._sim, 'signal_page') else {}
            ),
            "mne_coupling": (
                self._sim.source_page.get_mne_coupling_settings()
                if hasattr(self._sim, 'source_page') else {}
            ),
        }

        if ProjectManager.save_project(project_path, project_data):
            self._update_window_title()
            logger.info(f"项目保存成功: {project_path}")
            QMessageBox.information(self._sim, tr('success'), tr('msg_project_saved'))
        else:
            logger.error(f"项目保存失败: {project_path}")
            QMessageBox.critical(self._sim, tr('error'), tr('msg_project_save_failed'))

    def _load_project_data(self, project_path):
        """加载项目数据"""
        logger.info(f"开始加载项目: {project_path}")

        data = ProjectManager.load_project(project_path)
        if data is None:
            QMessageBox.critical(self._sim, tr('error'), tr('msg_project_load_failed'))
            return

        self._sim.current_project_path = project_path
        self._clear_all_data()

        # 加载Patch
        patches_data = data.get("patches", {})
        if isinstance(patches_data, dict):
            for patch_id, p_data in patches_data.items():
                patch = Patch.from_dict(p_data)
                self._sim.patches[patch_id] = patch

        # 加载耦合模型（兼容字典和列表格式）
        couplings_data = data.get("couplings", {})
        if isinstance(couplings_data, dict):
            for cid, c_data in couplings_data.items():
                try:
                    coupling = CouplingModel.from_dict(c_data)
                    self._sim._coupling_models[cid] = coupling
                    self._sim._coupling_engine.add_coupling(coupling)
                except Exception as e:
                    logger.warning(f"Failed to load coupling {cid}: {e}")
        elif isinstance(couplings_data, list):
            for c_data in couplings_data:
                try:
                    coupling = CouplingModel.from_dict(c_data)
                    if coupling.id:
                        self._sim._coupling_models[coupling.id] = coupling
                        self._sim._coupling_engine.add_coupling(coupling)
                except Exception as e:
                    logger.warning(f"Failed to load coupling: {e}")

        self._sim.patch_ops._sync_entity_counters()

        # 加载其他数据
        self._sim.noise_configs = data.get("noise", [])
        self._sim.bem_conductivity = self._normalize_bem_conductivity(
            data.get("bem", {}).get("conductivity")
        )
        self._sim._saved_output_config = data.get("output") or {}
        self._sim._saved_signal_filter = data.get("signal_filter") or {}
        self._sim._saved_mne_coupling = data.get("mne_coupling") or {}
        if self._sim._saved_output_config.get('sampling_rate') is not None:
            self._sim.sampling_rate = float(self._sim._saved_output_config['sampling_rate'])
        else:
            self._sim.sampling_rate = data.get("config", {}).get("sampling_rate", 1000)
        self._sim.selected_channels = data.get("selected_channels", [])
        self._sim._saved_electrode_montage = (
            data.get("electrode_montage")
            or data.get("config", {}).get("montage")
        )

        # 加载 Source Space 信息
        src_info = data.get("source_space", {})
        if src_info and hasattr(self._sim, 'source_page') and self._sim.source_page:
            # 恢复 Source Space 选择
            src_filename = src_info.get("src_filename")
            if src_filename and hasattr(self._sim.source_page, 'src_combo'):
                # 找到对应的索引并设置
                for i in range(self._sim.source_page.src_combo.count()):
                    if self._sim.source_page.src_combo.itemData(i) == src_filename:
                        self._sim.source_page.src_combo.setCurrentIndex(i)
                        break
            # 恢复其他信息
            self._sim.source_page.subject = src_info.get("subject")
            self._sim.source_page.src_labels = src_info.get("src_labels", {'lh': {}, 'rh': {}})
            self._sim.source_page.label_source_map = src_info.get("label_source_map", {'lh': {}, 'rh': {}})
            # 更新 Source Space 信息显示
            if hasattr(self._sim.source_page, 'src_info_label'):
                if src_filename:
                    self._sim.source_page.src_info_label.setText(f"Config: {src_filename}")
                    self._sim.source_page.src_info_label.setStyleSheet(f"color: {get_color('accent')}; font-size: 12px;")
                else:
                    self._sim.source_page.src_info_label.setText(tr('not_loaded'))
                    self._sim.source_page.src_info_label.setStyleSheet(f"color: {get_color('text_muted')}; font-size: 12px;")
            # 尝试自动重新加载 Source Space
            if src_filename and self._sim.source_page.subject:
                self._reload_source_space(src_filename, self._sim.source_page.subject, src_info)

        self._update_ui_from_data()
        self._sim.buffers._init_signal_buffers()
        self._update_window_title()
        self._sim.ui._update_status_bar()

        QMessageBox.information(self._sim, tr('success'), 
            tr('msg_project_loaded', ProjectManager.get_project_name(project_path)))

    def _serialize_bem_config(self):
        """序列化 BEM 导电率（优先取 UI 当前值）"""
        if hasattr(self._sim, 'source_page') and hasattr(self._sim.source_page, 'get_bem_conductivity'):
            conductivity = self._sim.source_page.get_bem_conductivity()
            if conductivity:
                return {"conductivity": list(conductivity)}
        if self._sim.bem_conductivity:
            c = self._sim.bem_conductivity
            return {"conductivity": list(c) if isinstance(c, (tuple, list)) else c}
        return {}

    def _normalize_bem_conductivity(self, conductivity):
        """将 JSON 中的导电率转为 (brain, skull, scalp) 元组"""
        if not conductivity or len(conductivity) < 3:
            return None
        return (float(conductivity[0]), float(conductivity[1]), float(conductivity[2]))

    def _reload_source_space(self, src_filename, subject, source_space_info=None):
        """重新加载 Source Space（用于项目加载时）"""
        import mne
        import os

        source_space_info = source_space_info or {}

        try:
            src_path = source_space_info.get('src_path')
            if src_path and os.path.exists(src_path):
                pass
            else:
                subjects_dir = source_space_info.get('subjects_dir') or getattr(self._sim, 'subjects_dir', None)
                if not subjects_dir:
                    try:
                        data_path = mne.datasets.sample.data_path()
                        subjects_dir = os.path.join(data_path, 'subjects')
                    except Exception:
                        subjects_dir = None
                if subjects_dir and src_filename and subject:
                    src_path = os.path.join(subjects_dir, subject, 'bem', src_filename)
                else:
                    src_path = None

            if src_path and os.path.exists(src_path):
                self._sim.source_page.loaded_src = mne.read_source_spaces(src_path)
                self._sim.source_page.loaded_src_path = src_path
                if source_space_info.get('subjects_dir'):
                    self._sim.subjects_dir = source_space_info['subjects_dir']
                elif os.path.dirname(os.path.dirname(os.path.dirname(src_path))):
                    self._sim.subjects_dir = os.path.dirname(os.path.dirname(os.path.dirname(src_path)))
                self._sim.mne.init_mne_coupling_engine(self._sim.source_page.loaded_src, self._sim.source_page.src_labels)
                logger.info(f"自动重新加载 Source Space: {src_path}")

                fwd_path = source_space_info.get('fwd_path')
                if fwd_path and os.path.exists(fwd_path):
                    try:
                        self._sim.mne.load_mne_data(fwd_path)
                        logger.info(f"自动加载前向模型: {fwd_path}")
                    except Exception as e:
                        logger.warning(f"自动加载前向模型失败: {e}")
                elif src_filename:
                    fwd_mapping = {
                        'sample-oct-6-src.fif': 'sample_audvis-eeg-oct-6-fwd.fif',
                        'sample-oct-6-orig-src.fif': 'sample_audvis-eeg-oct-6-fwd.fif',
                        'sample-fsaverage-ico-5-src.fif': 'sample_audvis-eeg-ico-5-fwd.fif',
                    }
                    fwd_filename = fwd_mapping.get(src_filename)
                    if fwd_filename:
                        try:
                            data_path = mne.datasets.sample.data_path()
                            fwd_path = os.path.join(data_path, 'MEG', 'sample', fwd_filename)
                            if os.path.exists(fwd_path):
                                self._sim.mne.load_mne_data(fwd_path)
                                logger.info(f"自动加载前向模型: {fwd_filename}")
                        except Exception as e:
                            logger.warning(f"自动加载前向模型失败: {e}")
            else:
                logger.warning(f"Source Space 文件不存在: {src_path}")
        except Exception as e:
            logger.warning(f"自动重新加载 Source Space 失败: {e}")

    def _clear_all_data(self):
        """清除所有数据"""
        if self._sim.is_running:
            self._sim.simulation.stop_simulation()
        logger.info("清除所有数据")
        self._sim.patches.clear()
        self._sim._current_patch_id = None
        self._sim._patch_counter = 0
        self._sim._dipole_counter = 0
        self._sim._coupling_counter = 0
        self._sim.signal_buffer.clear()
        self._sim.noise_configs = []
        self._sim._coupling_models.clear()
        self._sim._coupling_engine.clear()
        self._sim.bem_model = None
        self._sim.bem_conductivity = None
        self._sim.selected_channels = []
        self._sim._saved_electrode_montage = None
        self._sim._saved_output_config = {}
        self._sim._saved_signal_filter = {}
        self._sim._saved_mne_coupling = {}
        self._update_ui_from_data()

    def _update_ui_from_data(self):
        """从数据更新UI"""
        # 更新源配置页面
        if hasattr(self._sim, 'source_page'):
            # 同步噪声配置
            if hasattr(self._sim, 'noise_configs'):
                self._sim.source_page.active_noise_configs = self._sim.noise_configs
            self._sim.source_page._update_patch_stats()
            self._sim.source_page._update_coupling_stats()
            self._sim.source_page._update_noise_stats()
            if self._sim.bem_conductivity and hasattr(self._sim.source_page, 'apply_bem_conductivity'):
                self._sim.source_page.apply_bem_conductivity(self._sim.bem_conductivity)
            saved_mne = getattr(self._sim, '_saved_mne_coupling', None)
            if saved_mne:
                self._sim.source_page.apply_mne_coupling_settings(saved_mne)

        # 更新输出页面
        if hasattr(self._sim, 'output_page'):
            saved_output = getattr(self._sim, '_saved_output_config', None)
            if saved_output:
                self._sim.output_page.apply_output_config(saved_output)
                self._sim.sampling_rate = self._sim.output_page.sr_spin.value()
            else:
                self._sim.output_page.sr_spin.setValue(self._sim.sampling_rate)
            self._sim.buffers.sync_engines_sampling_rate()

        # 恢复信号滤波参数
        if hasattr(self._sim, 'signal_page'):
            saved_filter = getattr(self._sim, '_saved_signal_filter', None)
            if saved_filter:
                self._sim.signal_page.apply_filter_params(saved_filter)
            if not self._sim.is_running:
                self._sim.buffers._resize_signal_buffers()

        # 更新电极通道页面
        if hasattr(self._sim, 'electrode_channels_page'):
            montage_key = getattr(self._sim, '_saved_electrode_montage', None)
            if montage_key:
                self._sim.electrode_channels_page.set_montage_key(montage_key)
            self._sim.electrode_channels_page._update_channel_list()
            if self._sim.selected_channels:
                self._sim.electrode_channels_page.set_selected_channels(self._sim.selected_channels)
            self._sim.ui._sync_heatmap_montage()
            self._sim.buffers._update_plot_curves()

    def _update_window_title(self):
        """更新窗口标题"""
        if self._sim.current_project_path:
            project_name = ProjectManager.get_project_name(self._sim.current_project_path)
            self._sim.setWindowTitle(f"{tr('app_name')} - {project_name}")
        else:
            self._sim.setWindowTitle(tr('app_name'))
