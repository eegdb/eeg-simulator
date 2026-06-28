"""脑电仿真器主窗口 — 组合各功能服务类。"""

import sys
from typing import Dict, Optional

import numpy as np
import mne

from PyQt6.QtWidgets import QMainWindow

from ...ui.themes import set_theme
from ...models import CouplingModel, PatchCouplingEngine, MNECouplingEngine
from ...utils import get_config, get_translator, tr, get_logger
from ...utils.resources import load_app_icon
from ..signal_engine import SignalEngine
from ..mne_simulator import MNESimulator
from ..output_sink import SimulationOutputSink

from .ui import SimulatorUI
from .buffers import SimulatorBuffers
from .simulation import SimulatorSimulation
from .signal import SimulatorSignal
from .mne import SimulatorMNE
from .project import SimulatorProject
from .patch_ops import SimulatorPatchOps

logger = get_logger(__name__)


class EEGSimulator(QMainWindow):
    """脑电仿真器主窗口 - NavigationView 布局

    状态数据保存在本类；行为逻辑委托给各服务类（ui / buffers / simulation 等）。
    """

    def __init__(self):
        super().__init__()

        logger.info("=" * 60)
        logger.info("EEG Simulator (NavigationView) 初始化开始")
        logger.info(f"Python版本: {sys.version}")
        logger.info(f"MNE版本: {mne.__version__}")
        logger.info(f"NumPy版本: {np.__version__}")

        self.config = get_config()
        self.translator = get_translator()
        logger.info(f"配置加载完成，主题: {self.config.get_theme()}, 语言: {self.config.get_language()}")

        theme = self.config.get_theme()
        set_theme(theme)

        lang = self.config.get_language()
        self.translator.set_language(lang)

        self.setWindowTitle(tr('app_name'))
        self.setMinimumSize(1400, 900)
        app_icon = load_app_icon()
        if not app_icon.isNull():
            self.setWindowIcon(app_icon)
        logger.info("窗口设置完成，最小尺寸: 1400x900")

        self.patches = {}
        self._current_patch_id = None

        self.mne_info = None
        self.mne_fwd = None

        self.bem_model = None
        self.bem_conductivity = None
        self.subjects_dir = None

        self.current_project_path = None

        self.sampling_rate = self.config.get('default_sampling_rate', 1000)
        self.simulation_time = 0.0
        self.is_running = False
        self.buffer_size = 5000
        self._simulation_update_hz = 20
        self.samples_per_update = max(1, int(self.sampling_rate / self._simulation_update_hz))

        self._signal_states = {}
        self._last_heatmap_update_time = 0.0
        self.heatmap_refresh_interval = self.config.get('heatmap_refresh_interval', 1000) / 1000.0

        self.time_buffer = np.zeros(self.buffer_size)
        self.signal_buffer = {}
        self.eeg_buffer = {}
        self._output_sink: Optional[SimulationOutputSink] = None

        self._filter_states = {}
        self._filter_coeffs = {}
        self._noise_states = {}

        self.mne_fwd_path = None
        self._mne_coupling_factor_cache = None
        self._mne_coupling_factor_cache_key = None
        self._last_fft_update_time = 0.0
        self._fft_update_interval = 0.5
        self._last_waveform_update_time = 0.0
        self._waveform_update_interval = 1.0 / 10.0
        self._waveform_display_max_points = 1200
        self.heatmap_analysis_window = 2.0

        self.selected_channels = []
        self._saved_electrode_montage = None
        self._saved_output_config = {}
        self._saved_signal_filter = {}
        self._saved_mne_coupling = {}

        self.eeg_channel_mapping = {}

        self._patch_counter = 0
        self._dipole_counter = 0

        self.noise_configs = []

        self._coupling_models: Dict[str, CouplingModel] = {}
        self._coupling_counter = 0
        self._coupling_engine = PatchCouplingEngine(self.sampling_rate)

        self._mne_coupling_engine: Optional[MNECouplingEngine] = None
        self._use_mne_coupling = True

        self._mne_simulator: Optional[MNESimulator] = None

        self.signal_engine = SignalEngine(self.sampling_rate)

        # 功能服务（组合，非 mixin 继承）
        self.ui = SimulatorUI(self)
        self.buffers = SimulatorBuffers(self)
        self.simulation = SimulatorSimulation(self)
        self.signal = SimulatorSignal(self)
        self.mne = SimulatorMNE(self)
        self.project = SimulatorProject(self)
        self.patch_ops = SimulatorPatchOps(self)

        self.ui.init_ui()
        self.buffers.init_simulation()
