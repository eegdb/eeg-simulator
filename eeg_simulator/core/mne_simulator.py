"""MNE 完整仿真模块 - 使用 SourceEstimate 和前向投影

提供基于 MNE 的完整仿真流程：
1. 为 Patch/dipole 创建 SourceEstimate
2. 使用 mne.simulation.simulate_raw 进行前向投影
3. 支持耦合和噪声
"""

import numpy as np
from typing import Dict, List, Optional, Tuple, Union
import mne
from ..utils import get_logger

logger = get_logger(__name__)


class MNESimulator:
    """MNE 完整仿真器
    
    使用 MNE 的 SourceEstimate 和 forward model 进行真实的前向投影。
    """
    
    def __init__(self, fwd: mne.Forward, src: mne.SourceSpaces = None, 
                 sampling_rate: float = 1000):
        """
        Args:
            fwd: MNE 正向模型
            src: MNE 源空间，如果为 None 则从 fwd['src'] 获取
            sampling_rate: 采样率 (Hz)
        """
        self.fwd = fwd
        self.src = src if src is not None else fwd['src']
        self.sampling_rate = sampling_rate
        
        # 提取正向模型信息
        self._extract_forward_info()
        
        # 构建源点到顶点索引的映射
        self._build_source_mapping()
        self._logged_dipole_match = None
        self._loaded_src_verts = None
        self._log_source_space_alignment()
        
    def is_ready(self) -> bool:
        """检查仿真器是否准备就绪
        
        Returns:
            bool: 如果正向模型和源空间都正确加载则返回 True
        """
        return (self.fwd is not None and 
                self.forward_op is not None and 
                self.n_sources > 0)
        
    def _extract_forward_info(self):
        """从正向模型提取信息"""
        # 获取源空间信息
        self.src_space = self.fwd['src']
        
        # 获取转换后的正向算子
        self.forward_op = self.fwd['sol']['data']  # (n_sensors, n_sources)
        
        # 获取传感器信息
        self.info = self.fwd['info']
        self.ch_names = self.info['ch_names']
        
        # 获取源点信息
        self.n_sources = self.forward_op.shape[1]
        
        logger.info(f"正向模型: {len(self.ch_names)} 传感器, {self.n_sources} 源点")
        
    def _build_source_mapping(self):
        """构建源点到顶点索引的映射"""
        self.vert_to_source_idx = {'lh': {}, 'rh': {}}
        
        # 正向模型中的源点顺序
        source_idx = 0
        for hemi_idx, s in enumerate(self.src_space):
            hemi = 'lh' if hemi_idx == 0 else 'rh'
            for vertno in s['vertno']:
                self.vert_to_source_idx[hemi][vertno] = source_idx
                source_idx += 1
                
        logger.info(f"源点映射构建完成: LH={len(self.vert_to_source_idx['lh'])}, "
                   f"RH={len(self.vert_to_source_idx['rh'])}")

    def _get_loaded_src_verts(self):
        """UI 加载的源空间顶点集合，用于诊断与前向模型不一致"""
        if self._loaded_src_verts is not None:
            return self._loaded_src_verts
        verts = set()
        if self.src is None:
            self._loaded_src_verts = verts
            return verts
        for src_idx, s in enumerate(self.src):
            if s.get('type') != 'surf':
                continue
            hemi = 'lh' if src_idx == 0 else 'rh'
            for vertno in s.get('vertno', ()):
                verts.add((hemi, int(vertno)))
        self._loaded_src_verts = verts
        return verts

    def _get_forward_src_verts(self):
        """前向模型源空间顶点集合"""
        verts = set()
        for hemi_idx, s in enumerate(self.src_space):
            hemi = 'lh' if hemi_idx == 0 else 'rh'
            for vertno in s.get('vertno', ()):
                verts.add((hemi, int(vertno)))
        return verts

    def _log_source_space_alignment(self):
        """启动时对比 loaded_src 与前向模型源空间是否一致"""
        loaded = self._get_loaded_src_verts()
        if not loaded:
            return
        forward = self._get_forward_src_verts()
        only_loaded = loaded - forward
        only_forward = forward - loaded
        if only_loaded or only_forward:
            logger.warning(
                "源空间与前向模型顶点不完全一致: "
                f"loaded_src={len(loaded)}, forward_src={len(forward)}, "
                f"仅在 loaded_src 中={len(only_loaded)}, "
                f"仅在前向模型中={len(only_forward)}"
            )
        else:
            logger.info(
                f"源空间与前向模型顶点一致: {len(forward)} 个有效顶点"
            )

    def _describe_unmatched_dipole(self, hemi, vertno):
        """推断未匹配原因"""
        if hemi is None or vertno is None:
            missing = []
            if hemi is None:
                missing.append('hemi')
            if vertno is None:
                missing.append('vertno')
            return f"缺少 {', '.join(missing)}"

        loaded = self._get_loaded_src_verts()
        in_loaded = (hemi, int(vertno)) in loaded if loaded else None
        if in_loaded is True:
            return (
                f"{hemi}-v{vertno} 在 UI 加载的源空间中存在，"
                "但不在前向模型源空间中（请检查源空间与前向模型是否配套）"
            )
        if in_loaded is False:
            return (
                f"{hemi}-v{vertno} 在 UI 源空间与前向模型源空间中均不存在"
            )
        return f"{hemi}-v{vertno} 不在前向模型源空间中"

    def _log_unmatched_dipoles(self, matched_dipoles, total_dipoles, unmatched):
        """未匹配偶极子详情，仅在计数变化时记录一次"""
        match_key = (matched_dipoles, total_dipoles, tuple(
            (u['patch_id'], u['dipole_id'], u.get('hemi'), u.get('vertno'))
            for u in unmatched
        ))
        if match_key == self._logged_dipole_match:
            return
        self._logged_dipole_match = match_key

        logger.warning(
            f"SourceEstimate: {matched_dipoles}/{total_dipoles} 个偶极子匹配到源空间顶点"
        )
        for entry in unmatched:
            reason = self._describe_unmatched_dipole(entry.get('hemi'), entry.get('vertno'))
            logger.warning(
                "  未匹配: patch=%s, dipole=%s — %s",
                entry['patch_id'],
                entry['dipole_id'],
                reason,
            )
    
    def generate_source_estimate(self, patch_data: Dict, start_time: float, 
                                  n_samples: int) -> Optional[mne.SourceEstimate]:
        """生成 SourceEstimate
        
        将 Patch 的信号转换为 MNE SourceEstimate 格式。
        
        Args:
            patch_data: {patch_id: {'dipoles': [...], 'signals': array}}
            start_time: 起始时间
            n_samples: 样本数
            
        Returns:
            SourceEstimate 对象
        """
        # 顶点列表 - 使用源空间实际使用的顶点
        vertices = [self.src_space[0]['vertno'].copy(), 
                    self.src_space[1]['vertno'].copy()]
        
        # 计算总顶点数
        n_verts = len(vertices[0]) + len(vertices[1])
        
        # 创建源数据数组 (n_verts, n_times)
        source_data = np.zeros((n_verts, n_samples))
        
        # 构建从顶点到 source_data 索引的映射
        vert_to_idx = {}
        idx = 0
        for hemi_idx, vert_list in enumerate(vertices):
            hemi = 'lh' if hemi_idx == 0 else 'rh'
            for vertno in vert_list:
                vert_to_idx[(hemi, vertno)] = idx
                idx += 1
        
        # 填充源数据
        total_dipoles = 0
        matched_dipoles = 0
        unmatched_dipoles = []
        for patch_id, data in patch_data.items():
            signals = data.get('signals', np.zeros(n_samples))
            dipoles = data.get('dipoles', [])

            for dipole in dipoles:
                total_dipoles += 1
                dipole_id = getattr(dipole, 'id', '?')
                hemi = getattr(dipole, 'hemi', None)
                vertno = getattr(dipole, 'vertno', None)

                if hemi is None or vertno is None:
                    unmatched_dipoles.append({
                        'patch_id': patch_id,
                        'dipole_id': dipole_id,
                        'hemi': hemi,
                        'vertno': vertno,
                    })
                    continue

                data_idx = vert_to_idx.get((hemi, vertno))
                if data_idx is not None:
                    matched_dipoles += 1
                    amplitude = getattr(dipole, 'amplitude', 1.0)
                    patch_amp_scale = data.get('amplitude_scale', 1e-9)
                    source_data[data_idx, :] += signals * amplitude * patch_amp_scale
                else:
                    unmatched_dipoles.append({
                        'patch_id': patch_id,
                        'dipole_id': dipole_id,
                        'hemi': hemi,
                        'vertno': vertno,
                    })

        if total_dipoles > 0 and unmatched_dipoles:
            self._log_unmatched_dipoles(matched_dipoles, total_dipoles, unmatched_dipoles)
        
        # 创建时间数组
        tstep = 1.0 / self.sampling_rate
        times = start_time + np.arange(n_samples) * tstep
        
        # 创建 SourceEstimate
        stc = mne.SourceEstimate(
            data=source_data,
            vertices=vertices,
            tmin=times[0],
            tstep=tstep,
            subject=self.fwd.get('src', [{}])[0].get('subject_his_id', 'sample')
        )
        
        return stc
    
    def project_to_sensors(self, stc: mne.SourceEstimate) -> Optional[tuple]:
        """投影源信号到传感器空间
        
        使用 MNE 的 apply_forward 进行前向投影。
        
        Args:
            stc: SourceEstimate 对象
            
        Returns:
            (ch_names, sensor_data) 元组，其中 sensor_data 形状为 (n_channels, n_times)
        """
        try:
            from mne import apply_forward

            with mne.utils.use_log_level('error'):
                evoked = apply_forward(self.fwd, stc, self.info, verbose=False)
            
            # 获取传感器数据和通道名称
            sensor_data = evoked.data  # (n_channels, n_times)
            ch_names = evoked.ch_names  # 实际的通道名称列表
            
            return ch_names, sensor_data
            
        except Exception as e:
            logger.error(f"投影到传感器失败: {e}")
            return None
    
    def simulate(self, patch_data: Dict, start_time: float, 
                 n_samples: int) -> Optional[Dict[str, np.ndarray]]:
        """完整仿真流程
        
        Args:
            patch_data: Patch 数据字典
            start_time: 起始时间
            n_samples: 样本数
            
        Returns:
            {channel_name: signal_array}
        """
        # 1. 生成 SourceEstimate
        stc = self.generate_source_estimate(patch_data, start_time, n_samples)
        if stc is None:
            return None
        
        # 2. 投影到传感器空间
        proj_result = self.project_to_sensors(stc)
        if proj_result is None:
            return None
        
        ch_names, sensor_data = proj_result
        
        # 3. 转换为字典格式
        result = {}
        for i, ch_name in enumerate(ch_names):
            if i < sensor_data.shape[0]:
                result[ch_name] = sensor_data[i, :]
        
        return result
