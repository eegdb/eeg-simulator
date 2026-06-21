"""耦合模型 - 定义 Patch 之间的连接关系

耦合模型用于表示两个 Patch 之间的信号连接关系。
支持线性耦合、非线性耦合和延迟耦合。
"""

import numpy as np
from typing import Optional, Dict, Any


class CouplingModel:
    """耦合模型 - 表示两个 Patch 之间的连接
    
    属性:
        id: 耦合模型唯一标识
        source_patch_id: 源 Patch ID
        target_patch_id: 目标 Patch ID
        type: 耦合类型 ('linear', 'nonlinear', 'delayed')
        strength: 耦合强度
        delay: 延迟（秒）
        delay_samples: 延迟对应的采样点数
    """
    
    # 支持的耦合类型
    TYPE_LINEAR = 'linear'
    TYPE_NONLINEAR = 'nonlinear'
    TYPE_DELAYED = 'delayed'
    
    VALID_TYPES = [TYPE_LINEAR, TYPE_NONLINEAR, TYPE_DELAYED]
    
    def __init__(self, id: str, source_patch_id: str, target_patch_id: str, 
                 type: str, strength: float, delay: float = 0,
                 sampling_rate: float = 1000):
        """
        Args:
            id: 耦合模型唯一标识
            source_patch_id: 源 Patch ID
            target_patch_id: 目标 Patch ID
            type: 耦合类型 ('linear', 'nonlinear', 'delayed')
            strength: 耦合强度
            delay: 延迟（秒）
            sampling_rate: 采样率（用于计算延迟采样数）
        """
        self.id = id
        self.source_patch_id = source_patch_id
        self.target_patch_id = target_patch_id
        self.type = type if type in self.VALID_TYPES else self.TYPE_LINEAR
        self.strength = strength
        self.delay = delay
        self.sampling_rate = sampling_rate
        self._history: Optional[np.ndarray] = None
        self._write_idx = 0
        self._update_delay_samples()
        
    def _update_delay_samples(self):
        """根据延迟时间和采样率计算延迟采样数"""
        self.delay_samples = int(self.delay * self.sampling_rate)
        self._history = None
        self._write_idx = 0
        
    def set_sampling_rate(self, sampling_rate: float):
        """更新采样率，重新计算延迟采样数"""
        self.sampling_rate = sampling_rate
        self._update_delay_samples()

    def reset_history(self):
        """清空延迟耦合历史缓冲（仿真重启时调用）"""
        self._history = None
        self._write_idx = 0
        
    def apply_coupling(self, source_signal: float, target_signal: float,
                       current_time: float) -> float:
        """应用耦合效果到目标信号
        
        Args:
            source_signal: 源 Patch 的信号值
            target_signal: 目标 Patch 的当前信号值
            current_time: 当前时间（用于延迟耦合）
            
        Returns:
            float: 耦合后的信号值
        """
        if self.type == self.TYPE_LINEAR:
            # 线性耦合: target += strength * source
            return target_signal + self.strength * source_signal
            
        elif self.type == self.TYPE_NONLINEAR:
            # 非线性耦合: target += strength * tanh(source)
            return target_signal + self.strength * np.tanh(source_signal)
            
        elif self.type == self.TYPE_DELAYED:
            # 延迟耦合: 使用延迟后的源信号
            delayed_source = self._get_delayed_signal(source_signal)
            return target_signal + self.strength * delayed_source
            
        return target_signal

    def mne_contribution(self, source_signal: float, factor: float) -> float:
        """MNE 几何权重下的耦合增量（factor 已含 strength × 几何项）"""
        if self.type == self.TYPE_NONLINEAR:
            return factor * np.tanh(source_signal)
        if self.type == self.TYPE_DELAYED:
            return factor * self._get_delayed_signal(source_signal)
        return factor * source_signal
    
    def _ensure_history_buffer(self):
        """初始化或调整延迟耦合的历史缓冲区"""
        size = max(self.delay_samples + 1, 2)
        if self._history is None or len(self._history) != size:
            self._history = np.zeros(size)
            self._write_idx = 0

    def _get_delayed_signal(self, source_signal: float) -> float:
        """获取延迟后的源信号
        
        Args:
            source_signal: 当前源信号值
            
        Returns:
            float: 延迟后的信号值
        """
        if self.delay_samples <= 0:
            return source_signal

        self._ensure_history_buffer()
        read_idx = (self._write_idx - self.delay_samples) % len(self._history)
        delayed = float(self._history[read_idx])

        self._history[self._write_idx] = source_signal
        self._write_idx = (self._write_idx + 1) % len(self._history)

        return delayed
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            'id': self.id,
            'source_patch_id': self.source_patch_id,
            'target_patch_id': self.target_patch_id,
            'type': self.type,
            'strength': self.strength,
            'delay': self.delay,
            'sampling_rate': self.sampling_rate
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CouplingModel':
        """从字典反序列化"""
        return cls(
            id=data['id'],
            source_patch_id=data['source_patch_id'],
            target_patch_id=data['target_patch_id'],
            type=data.get('type', 'linear'),
            strength=data.get('strength', 0.5),
            delay=data.get('delay', 0),
            sampling_rate=data.get('sampling_rate', 1000)
        )
    
    def __repr__(self):
        return f"Coupling({self.id}, {self.source_patch_id} -> {self.target_patch_id}, type={self.type}, strength={self.strength})"


class PatchCouplingEngine:
    """Patch 耦合引擎 - 管理所有 Patch 间的耦合计算
    
    用于在仿真过程中计算和应用 Patch 之间的耦合效果。
    """
    
    def __init__(self, sampling_rate: float = 1000):
        self.sampling_rate = sampling_rate
        self.coupling_models: Dict[str, CouplingModel] = {}
        
    def add_coupling(self, coupling: CouplingModel):
        """添加耦合模型"""
        self.coupling_models[coupling.id] = coupling
        
    def remove_coupling(self, coupling_id: str):
        """移除耦合模型"""
        if coupling_id in self.coupling_models:
            del self.coupling_models[coupling_id]
            
    def clear(self):
        """清除所有耦合模型"""
        self.coupling_models.clear()

    def reset_histories(self):
        """重置所有延迟耦合的历史缓冲"""
        for coupling in self.coupling_models.values():
            coupling.reset_history()
        
    def compute_coupled_signals(self, patch_signals: Dict[str, float], 
                                current_time: float) -> Dict[str, float]:
        """计算耦合后的 Patch 信号
        
        Args:
            patch_signals: {patch_id: signal_value} Patch 原始信号
            current_time: 当前仿真时间
            
        Returns:
            Dict[str, float]: 耦合后的信号值
        """
        # 复制原始信号作为基础
        coupled_signals = patch_signals.copy()
        
        # 按顺序应用所有耦合
        for coupling in self.coupling_models.values():
            source_id = coupling.source_patch_id
            target_id = coupling.target_patch_id
            
            # 确保源和目标 Patch 都存在
            if source_id not in coupled_signals or target_id not in coupled_signals:
                continue
                
            source_signal = coupled_signals[source_id]
            target_signal = coupled_signals[target_id]
            
            # 应用耦合
            coupled_signals[target_id] = coupling.apply_coupling(
                source_signal, target_signal, current_time
            )
            
        return coupled_signals

    @staticmethod
    def apply_mne_factors(
        patch_signals: Dict[str, float],
        factors,
    ) -> Dict[str, float]:
        """应用 MNE 预计算耦合因子，并尊重 linear / nonlinear / delayed 类型

        factors: [(source_id, target_id, factor, CouplingModel), ...]
        """
        coupled_signals = patch_signals.copy()
        for source_id, target_id, factor, coupling in factors:
            if source_id not in coupled_signals or target_id not in coupled_signals:
                continue
            contrib = coupling.mne_contribution(coupled_signals[source_id], factor)
            coupled_signals[target_id] += contrib
        return coupled_signals
    
    def set_sampling_rate(self, sampling_rate: float):
        """更新采样率"""
        self.sampling_rate = sampling_rate
        for coupling in self.coupling_models.values():
            coupling.set_sampling_rate(sampling_rate)
