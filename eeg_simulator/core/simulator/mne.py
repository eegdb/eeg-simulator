"""MNE 前向模型、耦合引擎与通道映射。"""

import os

import mne
import numpy as np

from ...models import MNECouplingEngine
from ...utils import tr, get_logger
from ...utils.mne_loader import build_eeg_channel_mapping, resolve_standard_montage
from ..mne_simulator import MNESimulator

logger = get_logger(__name__)


class SimulatorMNE:
    """SimulatorMNE 服务。"""

    def __init__(self, simulator):
        self._sim = simulator

    def init_mne_coupling_engine(self, src, labels=None):
        """初始化MNE耦合引擎"""
        if src is None:
            logger.warning("无法初始化MNE耦合引擎: 源空间为空")
            return

        try:
            coupling_page = getattr(self._sim, 'signal_sources_page', None)
            k = coupling_page.knn_spin.value() if coupling_page is not None else 3
            decay_length = coupling_page.decay_spin.value() if coupling_page is not None else 0.02

            self._sim._mne_coupling_engine = MNECouplingEngine(
                src=src, labels=labels, sampling_rate=self._sim.sampling_rate
            )
            logger.info("MNE耦合引擎初始化成功")
            self._sim.signal.invalidate_mne_coupling_cache()
        except Exception as e:
            logger.error(f"MNE耦合引擎初始化失败: {e}")
            self._sim._mne_coupling_engine = None

        if self._sim.mne_fwd is not None:
            try:
                self._sim._mne_simulator = MNESimulator(fwd=self._sim.mne_fwd, src=src, sampling_rate=self._sim.sampling_rate)
                logger.info("MNE仿真器初始化成功")
                self.refresh_channel_mapping()
            except Exception as e:
                logger.error(f"MNE仿真器初始化失败: {e}")
                self._sim._mne_simulator = None

    def load_forward_model(self, file_path):
        """加载前向模型（*-fwd.fif）"""
        try:
            logger.info(f"加载前向模型: {file_path}")
            fwd = mne.read_forward_solution(file_path)
            self._sim.mne_fwd = fwd
            self._sim.mne_fwd_path = file_path
            self._sim.mne_info = fwd['info']

            src = self._sim.source_page.loaded_src if hasattr(self._sim, 'source_page') else None
            self._sim._mne_simulator = MNESimulator(
                fwd, src=src, sampling_rate=self._sim.sampling_rate
            )
            self._sim.ui._sync_heatmap_montage()
            self._sim.electrode_channels_page._update_channel_list()

            self.refresh_channel_mapping()

            if self._sim.patches:
                self._warn_unmatched_patch_dipoles()

            logger.info(f"正向模型加载成功: {len(fwd['info']['ch_names'])} 通道")
            if hasattr(self._sim, 'source_page') and hasattr(self._sim.source_page, 'update_forward_status'):
                self._sim.source_page.update_forward_status()
        except Exception as e:
            logger.error(f"前向模型加载失败: {e}", exc_info=True)
            raise

    def _warn_unmatched_patch_dipoles(self):
        """前向模型与 Patch 顶点不一致时提示用户重新生成前向或调整 Patch"""
        sim = self._sim
        if sim._mne_simulator is None or not sim.patches:
            return
        unmatched = sim._mne_simulator.find_unmatched_patch_dipoles(sim.patches)
        if not unmatched:
            return
        examples = []
        for entry in unmatched[:3]:
            hemi = entry.get('hemi') or '?'
            vertno = entry.get('vertno')
            vert = f"{hemi}-v{vertno}" if vertno is not None else hemi
            examples.append(f"{entry['patch_id']}/{entry['dipole_id']} ({vert})")
        logger.warning(
            "有 %d 个偶极子不在当前前向模型源空间中（示例: %s）。"
            "请先在源配置页 Generate Forward，再基于有效顶点创建/编辑 Patch。",
            len(unmatched),
            ', '.join(examples),
        )

    def compute_forward_from_montage(self, save_dir: str | None = None) -> str:
        """根据当前 montage、源空间与 BEM 计算前向模型并加载。"""
        sim = self._sim
        src = sim.source_page.loaded_src if hasattr(sim, 'source_page') else None
        if src is None:
            raise ValueError(tr('msg_no_src_space'))

        montage_key = (
            sim.source_page.get_montage_key()
            if hasattr(sim, 'source_page') else None
        )
        montage = (
            sim.source_page.get_current_montage()
            if hasattr(sim, 'source_page') else None
        )
        if montage is None or not montage_key:
            raise ValueError(tr('msg_select_montage_first'))

        subject = getattr(sim.source_page, 'subject', None) or 'sample'
        subjects_dir = sim.subjects_dir
        if not subjects_dir:
            raise ValueError(tr('msg_no_subjects_dir'))

        if subject != 'sample':
            raise ValueError(tr('msg_compute_fwd_sample_only'))

        if sim.bem_model is not None:
            logger.info("使用 UI 生成的 BEM 模型（make_bem_solution）")
            bem = mne.make_bem_solution(sim.bem_model)
        else:
            bem_candidates = (
                f'{subject}-5120-5120-5120-bem-sol.fif',
                f'{subject}-5120-bem-sol.fif',
            )
            bem_path = None
            for name in bem_candidates:
                candidate = os.path.join(subjects_dir, subject, 'bem', name)
                if os.path.exists(candidate):
                    bem_path = candidate
                    break
            if not bem_path:
                raise ValueError(tr('msg_bem_sol_not_found', bem_candidates[0]))
            bem = mne.read_bem_solution(bem_path)

        data_path = mne.datasets.sample.data_path()
        trans_path = os.path.join(data_path, 'MEG', 'sample', 'sample_audvis_raw-trans.fif')
        if not os.path.exists(trans_path):
            raise ValueError(tr('msg_trans_not_found', trans_path))

        ch_names = list(montage.ch_names)
        info = mne.create_info(ch_names, sfreq=sim.sampling_rate, ch_types='eeg')
        info.set_montage(montage)

        logger.info(
            f"计算前向模型: montage={montage_key}, src={sim.source_page.loaded_src_path}, "
            f"n_channels={len(ch_names)}"
        )
        fwd = mne.make_forward_solution(
            info,
            trans_path,
            src,
            bem,
            eeg=True,
            meg=False,
            mindist=0.0,
            n_jobs=1,
            verbose=False,
        )

        if not save_dir:
            save_dir = sim.current_project_path or os.path.expanduser('~')
        os.makedirs(save_dir, exist_ok=True)

        src_stem = 'src'
        if sim.source_page.loaded_src_path:
            src_stem = os.path.splitext(os.path.basename(sim.source_page.loaded_src_path))[0]
        fwd_name = f'{montage_key}-{src_stem}-fwd.fif'
        fwd_path = os.path.join(save_dir, fwd_name)
        mne.write_forward_solution(fwd_path, fwd, overwrite=True, verbose=False)
        logger.info(f"前向模型已保存: {fwd_path}")

        self.load_forward_model(fwd_path)
        return fwd_path

    def load_mne_data(self, file_path):
        """加载 MNE 数据（前向模型或 raw）"""
        try:
            logger.info(f"加载MNE数据: {file_path}")

            if self._is_forward_file_path(file_path):
                self.load_forward_model(file_path)
            else:
                raw = mne.io.read_raw_fif(file_path, preload=True)
                self._sim.mne_info = raw.info
                logger.info(f"原始数据加载成功: {len(raw.info['ch_names'])} 通道")

        except Exception as e:
            logger.error(f"MNE数据加载失败: {e}", exc_info=True)
            raise

    @staticmethod
    def _is_forward_file_path(file_path: str) -> bool:
        """根据文件名判断是否为前向模型"""
        name = os.path.basename(file_path).lower()
        if name.endswith('-fwd.fif') or name.endswith('-fwd.fif.gz'):
            return True
        if '-fwd' in name:
            return True
        non_fwd_markers = ('-cov.', '-src.', '-bem.', '-trans.', '-eve.', '-ica.', 'raw.fif')
        if any(marker in name for marker in non_fwd_markers):
            return False
        return False

    def _get_ui_montage(self):
        """当前 UI 选中的电极 montage，无则回退 10-20"""
        if hasattr(self._sim, 'source_page'):
            montage = self._sim.source_page.get_current_montage()
            if montage is not None:
                return montage
        if hasattr(self._sim, 'electrode_channels_page'):
            montage = self._sim.electrode_channels_page.get_current_montage()
            if montage is not None:
                return montage
        return resolve_standard_montage('standard_1020')

    def refresh_channel_mapping(self):
        """根据当前 montage 与前向模型重建通道映射"""
        if self._sim.mne_fwd is None:
            return
        self._update_eeg_channel_mapping(self._sim.mne_fwd)

    def _update_eeg_channel_mapping(self, fwd):
        """根据前向模型 + 当前 UI montage 创建通道映射"""
        try:
            montage = self._get_ui_montage()
            montage_key = (
                self._sim.source_page.get_montage_key()
                if hasattr(self._sim, 'source_page') else
                (self._sim.electrode_channels_page.get_montage_key()
                 if hasattr(self._sim, 'electrode_channels_page') else 'standard_1020')
            )

            self._sim.eeg_channel_mapping = build_eeg_channel_mapping(
                fwd, montage, extra_channels=self._sim.selected_channels or []
            )
            self._sim._logged_missing_channels = set()

            logger.info(
                f"EEG通道映射: montage={montage_key}, "
                f"{len(self._sim.eeg_channel_mapping)} 个通道"
            )
            for ch in (self._sim.selected_channels or [])[:5]:
                mapped = self._sim.eeg_channel_mapping.get(ch)
                if mapped:
                    logger.debug(f"  {ch} -> {mapped}")

        except Exception as e:
            logger.error(f"创建通道映射失败: {e}")
            self._sim.eeg_channel_mapping = {}
