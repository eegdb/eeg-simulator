"""Patch 模型 - 表示一组相邻的偶极子，共享相同的波形设置

Patch 是EEG信号仿真的高级抽象，用于表示大脑中一个功能区域。
一个 Patch 包含:
1. 一个中心偶极子（anchor）
2. 一个距离范围内的所有偶极子
3. 共享的波形设置

坐标系说明：
- 使用RAS坐标系（神经影像学标准）
- 单位：米(m)
"""

import numpy as np
from typing import List, Dict, Any, Optional


class Dipole:
    """偶极子定义 - 表示脑电信号源的位置和方向
    
    注意：偶极子不再单独管理波形，波形由所属的 Patch 统一管理。
    
    属性:
        id: 偶极子唯一标识符
        position: np.array([x, y, z]) 位置坐标，单位米，RAS坐标系
        orientation: np.array([nx, ny, nz]) 方向向量（单位向量）
        hemi: 半球标识 'lh'(左), 'rh'(右), 'vol'(体积)，可选
        vertno: 顶点编号（来自源空间），可选
        src_idx: 源空间索引，可选
    """
    
    def __init__(self, id, position, orientation,
                 hemi=None, vertno=None, src_idx=None):
        """
        Args:
            id: 偶极子唯一标识
            position: [x, y, z] 位置坐标，单位米，RAS坐标系
            orientation: [nx, ny, nz] 方向向量（会自动归一化）
            hemi: 半球标识 'lh'(左), 'rh'(右), 'vol'(体积)，可选
            vertno: 顶点编号（来自源空间），可选
            src_idx: 源空间索引，可选
        """
        self.id = id
        self.position = np.array(position)
        self.orientation = np.array(orientation)
        # 确保方向向量归一化
        norm = np.linalg.norm(self.orientation)
        if norm > 0:
            self.orientation = self.orientation / norm
        
        self.hemi = hemi
        self.vertno = vertno
        self.src_idx = src_idx
    
    def distance_to(self, other_position) -> float:
        """计算到另一个位置的距离"""
        return np.linalg.norm(self.position - np.array(other_position))
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            'id': self.id,
            'position': self.position.tolist(),
            'orientation': self.orientation.tolist(),
            'hemi': self.hemi,
            'vertno': self.vertno,
            'src_idx': self.src_idx
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Dipole':
        """从字典反序列化"""
        return cls(
            id=data['id'],
            position=data['position'],
            orientation=data['orientation'],
            hemi=data.get('hemi'),
            vertno=data.get('vertno'),
            src_idx=data.get('src_idx')
        )
    
    def __repr__(self):
        return f"Dipole({self.id}, pos=({self.position[0]:.3f}, {self.position[1]:.3f}, {self.position[2]:.3f}))"


class Patch:
    """Patch 定义 - 表示一组相邻偶极子的波形源
    
    Patch 现在直接包含 Dipole 对象，不再引用外部的 dipole_definitions。
    
    属性:
        id: Patch 唯一标识符
        name: Patch 名称（可选）
        anchor_dipole: 中心偶极子对象
        dipoles: 属于该 Patch 的所有偶极子对象列表
        radius: 距离范围（单位：米）
        label_name: 所属解剖学label名称（可选）
        hemi: 半球 'lh'(左), 'rh'(右)
        
        # 波形设置
        waveform_type: 波形类型
        waveform_params: 波形参数字典
    """
    
    # 支持的波形类型
    WAVEFORM_SIN = 'sin'
    WAVEFORM_COS = 'cos'
    WAVEFORM_ERP = 'erp'
    WAVEFORM_GAUSSIAN = 'gaussian'
    WAVEFORM_GAMMA = 'gamma'
    WAVEFORM_OSCILLATION = 'oscillation'
    WAVEFORM_CUSTOM = 'custom'
    
    VALID_WAVEFORMS = [WAVEFORM_SIN, WAVEFORM_COS, WAVEFORM_ERP, 
                       WAVEFORM_GAUSSIAN, WAVEFORM_GAMMA, WAVEFORM_OSCILLATION, WAVEFORM_CUSTOM]
    
    def __init__(self, id: str, 
                 label_name: Optional[str] = None,
                 hemi: Optional[str] = None,
                 name: Optional[str] = None,
                 waveform_type: str = 'sin',
                 waveform_params: Optional[Dict[str, Any]] = None):
        """
        Args:
            id: Patch 唯一标识
            label_name: 所属解剖学label名称
            hemi: 半球 'lh' 或 'rh'
            name: Patch 名称
            waveform_type: 波形类型
            waveform_params: 波形参数字典
        """
        self.id = id
        self.name = name or f"Patch_{id}"
        self.label_name = label_name
        self.hemi = hemi
        
        # 偶极子列表 - Patch 直接管理自己的偶极子
        self.dipoles: List[Dipole] = []
        self.anchor_dipole: Optional[Dipole] = None
        self.radius: float = 0.0
        
        # 波形类型和参数
        self.waveform_type = waveform_type if waveform_type in self.VALID_WAVEFORMS else self.WAVEFORM_SIN
        self.waveform_params = waveform_params or self._get_default_waveform_params(self.waveform_type)
        
        # MNE 仿真幅度因子（默认 1e-9，对应约 10 nAm）
        self.amplitude_scale: float = 1e-9
    
    def _get_default_waveform_params(self, waveform_type: str) -> Dict[str, Any]:
        """获取默认波形参数"""
        defaults = {
            self.WAVEFORM_SIN: {
                'amplitude': 10.0,
                'frequency': 10.0,
                'phase': 0.0,
                'offset': 0.0,
                'onset': 0.0,
                'duration': 0.0
            },
            self.WAVEFORM_COS: {
                'amplitude': 10.0,
                'frequency': 10.0,
                'phase': 90.0,
                'offset': 0.0,
                'onset': 0.0,
                'duration': 0.0
            },
            self.WAVEFORM_ERP: {
                'amplitude': 10.0,
                'frequency': 1.0,
                'latency': 0.1,
                'width': 0.05,
                'polarity': 'positive'
            },
            self.WAVEFORM_GAUSSIAN: {
                'amplitude': 10.0,
                'frequency': 10.0,
                'sigma': 0.1,
                'center': 0.5
            },
            self.WAVEFORM_GAMMA: {
                'amplitude': 10.0,
                'frequency': 10.0,
                'alpha': 2.0,
                'beta': 0.1
            },
            self.WAVEFORM_OSCILLATION: {
                'freq': 10.0,
                'phase': 0.0,
                'amp': 20.0,
                'center': 0.5,
                'width': 0.1
            },
            self.WAVEFORM_CUSTOM: {
                'amplitude': 10.0,
                'frequency': 10.0,
                'data': []
            }
        }
        return defaults.get(waveform_type, {})
    
    def add_dipole(self, dipole: Dipole):
        """添加偶极子到 Patch"""
        if dipole not in self.dipoles:
            self.dipoles.append(dipole)
    
    def remove_dipole(self, dipole: Dipole):
        """从 Patch 移除偶极子"""
        if dipole in self.dipoles:
            self.dipoles.remove(dipole)
        # 如果移除的是中心点，重新指定
        if self.anchor_dipole == dipole and self.dipoles:
            self.anchor_dipole = self.dipoles[0]
    
    def set_anchor(self, dipole: Dipole):
        """设置中心偶极子"""
        if dipole in self.dipoles:
            self.anchor_dipole = dipole
    
    def set_radius(self, radius: float):
        """设置半径"""
        self.radius = radius
    
    def find_dipoles_in_radius(self, center_dipole: Dipole, radius: float) -> List[Dipole]:
        """查找指定半径内的所有偶极子"""
        nearby = [center_dipole]  # 包含中心点
        center_pos = center_dipole.position
        
        for dipole in self.dipoles:
            if dipole == center_dipole:
                continue
            dist = np.linalg.norm(dipole.position - center_pos)
            if dist <= radius:
                nearby.append(dipole)
        
        return nearby
    
    def set_waveform(self, waveform_type: str, params: Optional[Dict[str, Any]] = None):
        """设置波形"""
        if waveform_type in self.VALID_WAVEFORMS:
            self.waveform_type = waveform_type
            self.waveform_params = params or self._get_default_waveform_params(waveform_type)
    
    def get_dipole_count(self) -> int:
        """获取 Patch 中的偶极子数量"""
        return len(self.dipoles)
    
    def get_all_dipoles(self) -> List[Dipole]:
        """获取所有偶极子"""
        return self.dipoles.copy()
    
    def get_dipole_by_id(self, dipole_id: str) -> Optional[Dipole]:
        """通过 ID 获取偶极子"""
        for dipole in self.dipoles:
            if dipole.id == dipole_id:
                return dipole
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            'id': self.id,
            'name': self.name,
            'anchor_dipole': self.anchor_dipole.to_dict() if self.anchor_dipole else None,
            'dipoles': [d.to_dict() for d in self.dipoles],
            'radius': self.radius,
            'label_name': self.label_name,
            'hemi': self.hemi,
            'waveform_type': self.waveform_type,
            'waveform_params': self.waveform_params,
            'amplitude_scale': self.amplitude_scale,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Patch':
        """从字典反序列化"""
        patch = cls(
            id=data['id'],
            label_name=data.get('label_name'),
            hemi=data.get('hemi'),
            name=data.get('name'),
            waveform_type=data.get('waveform_type', 'sin'),
            waveform_params=data.get('waveform_params', {})
        )
        
        # 恢复偶极子
        for d_data in data.get('dipoles', []):
            dipole = Dipole.from_dict(d_data)
            patch.add_dipole(dipole)
        
        # 恢复中心点
        anchor_data = data.get('anchor_dipole')
        if anchor_data:
            for dipole in patch.dipoles:
                if dipole.id == anchor_data['id']:
                    patch.set_anchor(dipole)
                    break
        
        patch.radius = data.get('radius', 0.0)
        patch.amplitude_scale = data.get('amplitude_scale', 1e-9)
        return patch
    
    def __repr__(self):
        return f"Patch({self.id}, anchor={self.anchor_dipole.id if self.anchor_dipole else None}, dipoles={len(self.dipoles)}, radius={self.radius:.3f}m)"
