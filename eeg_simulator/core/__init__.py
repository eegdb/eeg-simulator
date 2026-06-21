"""核心仿真模块"""

__all__ = ['EEGSimulator']


def __getattr__(name: str):
    if name == 'EEGSimulator':
        from .simulator_nav import EEGSimulator
        return EEGSimulator
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
