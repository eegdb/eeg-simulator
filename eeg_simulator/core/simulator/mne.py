"""MNE 前向模型、耦合引擎与通道映射。"""

from collections import defaultdict

import mne
import numpy as np

from ...models import MNECouplingEngine
from ...utils import tr, get_logger
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
                # 更新通道映射
                self._update_eeg_channel_mapping(self._sim.mne_fwd)
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
                self._sim.signal_page.set_montage_from_info(self._sim.mne_info)
                self._sim.electrode_channels_page._update_channel_list()

                # 更新通道映射（标准10-20命名 -> MNE前向模型命名）
                self._update_eeg_channel_mapping(fwd)

                logger.info(f"正向模型加载成功: {len(fwd['info']['ch_names'])} 通道")
            else:
                raw = mne.io.read_raw_fif(file_path, preload=True)
                self._sim.mne_info = raw.info
                logger.info(f"原始数据加载成功: {len(raw.info['ch_names'])} 通道")

        except Exception as e:
            logger.error(f"MNE数据加载失败: {e}", exc_info=True)
            raise

    def _update_eeg_channel_mapping(self, fwd):
        """根据前向模型创建通道名称映射

        将标准10-20命名（如Cz, Pz等）映射到MNE前向模型的通道命名（如EEG 001等）
        同时添加直接名称匹配作为回退
        """
        try:
            import numpy as np
            from collections import defaultdict

            info = fwd['info']
            ch_names = info['ch_names']

            # 获取标准10-20 montage
            montage_1020 = mne.channels.make_standard_montage('standard_1020')
            montage_positions = montage_1020.get_positions()['ch_pos']

            # 创建反向映射: 标准命名 -> MNE通道
            mne_by_distance = defaultdict(list)  # std_name -> [(mne_ch, distance), ...]

            for i, mne_ch in enumerate(ch_names):
                loc = np.array(info['chs'][i]['loc'][:3])

                # 找到最近的标准电极
                min_dist = float('inf')
                closest_std = None

                for std_name, std_pos in montage_positions.items():
                    dist = np.linalg.norm(loc - std_pos)
                    if dist < min_dist:
                        min_dist = dist
                        closest_std = std_name

                if min_dist < 0.07 and closest_std:  # 7cm阈值
                    mne_by_distance[closest_std].append((mne_ch, min_dist))

            # 为每个标准命名选择距离最近的MNE通道
            self._sim.eeg_channel_mapping = {}
            for std_name, candidates in mne_by_distance.items():
                best_match = min(candidates, key=lambda x: x[1])
                self._sim.eeg_channel_mapping[std_name] = best_match[0]

            # 添加直接名称匹配：如果MNE通道名本身就是标准命名，直接映射
            for ch_name in ch_names:
                if ch_name in montage_positions and ch_name not in self._sim.eeg_channel_mapping:
                    self._sim.eeg_channel_mapping[ch_name] = ch_name

            logger.info(f"EEG通道映射创建成功: {len(self._sim.eeg_channel_mapping)} 个通道")
            # 记录一些映射示例
            sample_items = list(self._sim.eeg_channel_mapping.items())[:5]
            for std_name, mne_ch in sample_items:
                logger.debug(f"  {std_name} -> {mne_ch}")

        except Exception as e:
            logger.error(f"创建通道映射失败: {e}")
            self._sim.eeg_channel_mapping = {}
