"""MNE 前向模型、耦合引擎与通道映射。"""

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
            k = self._sim.source_page.knn_spin.value() if hasattr(self._sim, 'source_page') else 3
            decay_length = self._sim.source_page.decay_spin.value() if hasattr(self._sim, 'source_page') else 0.02

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

    def load_mne_data(self, file_path):
        """加载MNE数据"""
        try:
            logger.info(f"加载MNE数据: {file_path}")

            if 'fwd' in file_path.lower():
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

                logger.info(f"正向模型加载成功: {len(fwd['info']['ch_names'])} 通道")
            else:
                raw = mne.io.read_raw_fif(file_path, preload=True)
                self._sim.mne_info = raw.info
                logger.info(f"原始数据加载成功: {len(raw.info['ch_names'])} 通道")

        except Exception as e:
            logger.error(f"MNE数据加载失败: {e}", exc_info=True)
            raise

    def _get_ui_montage(self):
        """当前 UI 选中的电极 montage，无则回退 10-20"""
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
                self._sim.electrode_channels_page.get_montage_key()
                if hasattr(self._sim, 'electrode_channels_page') else 'standard_1020'
            )

            self._sim.eeg_channel_mapping = build_eeg_channel_mapping(fwd, montage)
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
