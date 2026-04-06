"""面板模块 - 配置面板"""

from .source_config import SourceConfigPanel
from .signal_card import SignalGeneratorCard
from .coupling_card import CouplingModelCard

# NavigationView 页面
from .source_config_page import SourceConfigPage
from .electrode_channels_page import ElectrodeChannelsPage
from .output_page import OutputPage
from .signal_page import SignalPage

__all__ = [
    'SourceConfigPanel', 'SignalGeneratorCard', 'CouplingModelCard',
    'SourceConfigPage', 'ElectrodeChannelsPage', 'OutputPage', 'SignalPage'
]
