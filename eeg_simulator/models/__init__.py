"""数据模型模块 - 定义所有核心数据结构"""

from .signal import SignalGenerator
from .coupling import CouplingModel, PatchCouplingEngine
from .patch import Patch, Dipole
from .mne_coupling import MNECouplingCalculator, MNECouplingEngine

__all__ = ['SignalGenerator', 'CouplingModel', 'PatchCouplingEngine', 'Patch', 'Dipole',
           'MNECouplingCalculator', 'MNECouplingEngine']
