"""面板模块 - NavigationView 配置页面"""

from .source_config_page import SourceConfigPage
from .signal_sources_page import SignalSourcesPage
from .noise_artifacts_page import NoiseArtifactsPage
from .electrode_channels_page import ElectrodeChannelsPage
from .output_page import OutputPage
from .signal_page import SignalPage

__all__ = [
    'SourceConfigPage', 'SignalSourcesPage', 'NoiseArtifactsPage',
    'ElectrodeChannelsPage', 'OutputPage', 'SignalPage',
]
