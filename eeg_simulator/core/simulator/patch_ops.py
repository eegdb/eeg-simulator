"""Patch、偶极子与耦合模型管理。"""

import numpy as np

from ...models import Dipole, CouplingModel, Patch
from ...utils import get_logger

logger = get_logger(__name__)


class SimulatorPatchOps:
    """SimulatorPatchOps 服务。"""

    def __init__(self, simulator):
        self._sim = simulator

    def _sync_entity_counters(self):
        """从已有 Patch/偶极子/耦合 ID 同步自增计数器（加载项目后避免 ID 冲突）"""
        max_patch = getattr(self._sim, '_patch_counter', 0)
        max_dipole = getattr(self._sim, '_dipole_counter', 0)
        max_coupling = getattr(self._sim, '_coupling_counter', 0)

        for patch_id, patch in self._sim.patches.items():
            if patch_id.startswith('patch_'):
                try:
                    max_patch = max(max_patch, int(patch_id.rsplit('_', 1)[-1]))
                except ValueError:
                    pass
            for dipole in patch.dipoles:
                if dipole.id.startswith('dipole_'):
                    try:
                        max_dipole = max(max_dipole, int(dipole.id.rsplit('_', 1)[-1]))
                    except ValueError:
                        pass

        for cid in getattr(self._sim, '_coupling_models', {}):
            if cid.startswith('coupling_'):
                try:
                    max_coupling = max(max_coupling, int(cid.rsplit('_', 1)[-1]))
                except ValueError:
                    pass

        self._sim._patch_counter = max_patch
        self._sim._dipole_counter = max_dipole
        self._sim._coupling_counter = max_coupling

    def _invalidate_signal_dependent_caches(self):
        self._sim.signal.invalidate_mne_coupling_cache()
        self._sim.signal.invalidate_heatmap_forward_cache()

    def create_patch(self, position, orientation, radius=0.0, label_name=None, hemi=None, 
                     name=None, waveform_type='sin', waveform_params=None, vertno=None, src_idx=None,
                     anchor_dipole=None):
        """创建Patch

        Args:
            anchor_dipole: 可选，已存在的中心偶极子。如果提供，则直接使用该偶极子而不是创建新的。
        """
        self._sim._patch_counter += 1
        patch_id = f"patch_{self._sim._patch_counter}"

        patch = Patch(id=patch_id, label_name=label_name, hemi=hemi, name=name,
                     waveform_type=waveform_type, waveform_params=waveform_params)

        # 如果提供了已存在的中心偶极子，直接使用；否则创建新的
        if anchor_dipole is not None:
            patch.add_dipole(anchor_dipole)
            patch.set_anchor(anchor_dipole)
            logger.info(f"创建Patch: {patch_id}, 使用已有中心偶极子: {anchor_dipole.id}")
        else:
            self._sim._dipole_counter += 1
            new_dipole = Dipole(id=f"dipole_{self._sim._dipole_counter}", position=position,
                               orientation=orientation, hemi=hemi, vertno=vertno, src_idx=src_idx)
            patch.add_dipole(new_dipole)
            patch.set_anchor(new_dipole)
            self._sim.signal_buffer[new_dipole.id] = np.zeros(self._sim.buffer_size)
            logger.info(f"创建Patch: {patch_id}, 新建中心偶极子: {new_dipole.id}")

        patch.set_radius(radius)
        self._sim.patches[patch_id] = patch
        self._sim._current_patch_id = patch_id
        self._invalidate_signal_dependent_caches()

        return patch_id

    def delete_patch(self, patch_id):
        """删除Patch"""
        if patch_id not in self._sim.patches:
            return

        patch = self._sim.patches[patch_id]
        for dipole in patch.dipoles:
            if dipole.id in self._sim.signal_buffer:
                del self._sim.signal_buffer[dipole.id]

        del self._sim.patches[patch_id]
        if self._sim._current_patch_id == patch_id:
            self._sim._current_patch_id = None

        logger.info(f"删除Patch: {patch_id}")
        self._invalidate_signal_dependent_caches()

    def modify_patch(self, patch_id, name=None, waveform_type=None, waveform_params=None, radius=None):
        """修改 Patch

        Args:
            patch_id: Patch ID
            name: 新名称（可选）
            waveform_type: 新波形类型（可选）
            waveform_params: 新波形参数（可选）
            radius: 新半径（可选）
        """
        if patch_id not in self._sim.patches:
            return

        patch = self._sim.patches[patch_id]
        if name is not None:
            patch.name = name
        if waveform_type is not None:
            patch.waveform_type = waveform_type
        if waveform_params is not None:
            patch.waveform_params = waveform_params
        if radius is not None:
            patch.radius = radius

        logger.info(f"修改Patch: {patch_id}")
        self._invalidate_signal_dependent_caches()

    def create_dipole(self, position, orientation, hemi=None, vertno=None, src_idx=None):
        """创建偶极子（不放入任何 Patch，用于 PatchManager 中临时创建）

        Args:
            position: [x, y, z] 位置坐标，单位米，RAS坐标系
            orientation: [nx, ny, nz] 方向向量
            hemi: 半球标识 'lh'(左), 'rh'(右)，可选
            vertno: 顶点编号，可选
            src_idx: 源空间索引，可选

        Returns:
            Dipole: 创建的偶极子对象
        """
        self._sim._dipole_counter += 1
        dipole_id = f"dipole_{self._sim._dipole_counter}"

        dipole = Dipole(
            id=dipole_id,
            position=position,
            orientation=orientation,
            hemi=hemi,
            vertno=vertno,
            src_idx=src_idx
        )

        logger.info(f"创建偶极子: {dipole_id}, 位置: ({position[0]:.4f}, {position[1]:.4f}, {position[2]:.4f})")
        return dipole

    def _get_forward_active_verts(self):
        """前向模型中实际参与投影的 (hemi, vertno) 集合；未加载前向模型时返回 None"""
        mne_sim = getattr(self._sim, '_mne_simulator', None)
        if mne_sim is not None:
            return mne_sim._get_forward_src_verts()

        fwd = getattr(self._sim, 'mne_fwd', None)
        if fwd is None:
            return None

        verts = set()
        for hemi_idx, s in enumerate(fwd['src']):
            hemi = 'lh' if hemi_idx == 0 else 'rh'
            for vertno in s.get('vertno', ()):
                verts.add((hemi, int(vertno)))
        return verts

    def find_dipoles_in_radius(self, center_position, radius, src=None, label_source_map=None, hemi=None):
        """查找半径内的顶点（若已加载前向模型，仅返回其中有效源点）"""
        nearby_vertices = []

        if src is None:
            src = getattr(self._sim.source_page, 'loaded_src', None)

        if src is None:
            return nearby_vertices

        forward_verts = self._get_forward_active_verts()
        center_pos = np.array(center_position)

        for src_idx, s in enumerate(src):
            if s['type'] != 'surf':
                continue

            current_hemi = 'lh' if src_idx == 0 else 'rh'
            if hemi is not None and current_hemi != hemi:
                continue

            for vertno in s['vertno']:
                if forward_verts is not None and (current_hemi, int(vertno)) not in forward_verts:
                    continue

                pos = s['rr'][vertno]
                dist = np.linalg.norm(pos - center_pos)

                if dist <= radius:
                    orientation = s['nn'][vertno] if 'nn' in s else [0, 0, 1]
                    nearby_vertices.append({
                        'vertno': vertno, 'position': pos.tolist(),
                        'orientation': orientation.tolist() if isinstance(orientation, np.ndarray) else list(orientation),
                        'hemi': current_hemi, 'src_idx': src_idx, 'distance': float(dist)
                    })

        nearby_vertices.sort(key=lambda x: x['distance'])
        return nearby_vertices

    @property
    def coupling_models(self):
        """获取耦合模型字典"""
        return self._sim._coupling_models

    @property
    def dipole_definitions(self):
        """获取所有偶极子（兼容旧代码）"""
        result = {}
        for patch in self._sim.patches.values():
            for dipole in patch.dipoles:
                result[dipole.id] = dipole
        return result

    def set_noise_configs(self, configs):
        """设置噪声配置"""
        self._sim.noise_configs = configs
        self._sim.signal.invalidate_heatmap_forward_cache()

    def add_coupling_model(self, source_patch_id, target_patch_id, type='linear', strength=0.5, delay=0):
        """添加耦合模型"""
        if source_patch_id not in self._sim.patches or target_patch_id not in self._sim.patches:
            return None
        if source_patch_id == target_patch_id:
            return None

        self._sim._coupling_counter += 1
        coupling_id = f"coupling_{self._sim._coupling_counter}"

        coupling = CouplingModel(id=coupling_id, source_patch_id=source_patch_id,
                                target_patch_id=target_patch_id, type=type,
                                strength=strength, delay=delay, sampling_rate=self._sim.sampling_rate)

        self._sim._coupling_models[coupling_id] = coupling
        self._sim._coupling_engine.add_coupling(coupling)

        logger.info(f"创建耦合模型: {coupling_id}")
        self._invalidate_signal_dependent_caches()
        return coupling_id

    def delete_coupling_model(self, coupling_id):
        """删除耦合模型"""
        if coupling_id in self._sim._coupling_models:
            del self._sim._coupling_models[coupling_id]
            self._sim._coupling_engine.remove_coupling(coupling_id)
            logger.info(f"删除耦合模型: {coupling_id}")
            self._invalidate_signal_dependent_caches()

    def modify_coupling_model(self, coupling_id, strength=None, delay=None, type=None):
        """修改已有耦合模型的参数（保持 ID 不变）"""
        coupling = self._sim._coupling_models.get(coupling_id)
        if coupling is None:
            return False

        if strength is not None:
            coupling.strength = strength
        if delay is not None:
            coupling.delay = delay
            coupling.set_sampling_rate(self._sim.sampling_rate)
        if type is not None and type in CouplingModel.VALID_TYPES:
            coupling.type = type
            coupling.reset_history()

        logger.info(f"修改耦合模型: {coupling_id}")
        self._invalidate_signal_dependent_caches()
        return True

    def clear_coupling_models(self):
        """清除所有耦合模型"""
        self._sim._coupling_models.clear()
        self._sim._coupling_engine.clear()
        self._invalidate_signal_dependent_caches()
        logger.info("已清除所有耦合模型")
