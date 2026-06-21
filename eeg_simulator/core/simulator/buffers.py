"""信号缓冲区与采样率/时间窗口同步。"""

import numpy as np

from ...utils import tr, get_logger

logger = get_logger(__name__)


class SimulatorBuffers:
    """SimulatorBuffers 服务。"""

    def __init__(self, simulator):
        self._sim = simulator

    def _on_sr_changed_from_page(self, value):
        """从输出页面改变采样率"""
        self._sim.sampling_rate = value
        self.sync_engines_sampling_rate()
        self._resize_signal_buffers()
        self._sim.ui._update_status_bar()

    def sync_engines_sampling_rate(self):
        """将各引擎采样率与 self._sim.sampling_rate 同步"""
        sr = self._sim.sampling_rate
        self._sim.samples_per_update = max(1, int(sr / 30))
        self._sim.signal_engine.sampling_rate = sr
        self._sim._coupling_engine.set_sampling_rate(sr)
        for coupling in self._sim._coupling_models.values():
            coupling.set_sampling_rate(sr)
        if self._sim._mne_simulator is not None:
            self._sim._mne_simulator.sampling_rate = sr

    def _on_time_window_changed(self, _value):
        """时间窗口改变时同步环形缓冲区大小"""
        self._resize_signal_buffers()

    def _compute_buffer_size(self) -> int:
        """按显示时间窗口与采样率计算缓冲区长度"""
        time_window = 10.0
        if hasattr(self._sim, 'signal_page'):
            time_window = self._sim.signal_page.time_window_spin.value()
        return max(int(time_window * self._sim.sampling_rate), 256)

    def _resize_signal_buffers(self):
        """重建环形缓冲区（运行中不重设，避免打断仿真）"""
        if self._sim.is_running:
            return
        new_size = self._compute_buffer_size()
        if new_size == self._sim.buffer_size and self._sim.time_buffer.size == new_size:
            return
        self._sim.buffer_size = new_size
        self._sim.time_buffer = np.zeros(self._sim.buffer_size)
        for ch in list(self._sim.eeg_buffer.keys()):
            self._sim.eeg_buffer[ch] = np.zeros(self._sim.buffer_size)
        for dipole_id in list(self._sim.signal_buffer.keys()):
            self._sim.signal_buffer[dipole_id] = np.zeros(self._sim.buffer_size)
        logger.debug(f"信号缓冲区已调整为 {self._sim.buffer_size} 点")

    def _on_layout_changed(self, layout_key):
        """电极布局改变时"""
        logger.info(f"切换电极布局: {layout_key}")
        self._sim.electrode_channels_page._update_channel_list()

        # 同步电极布局到实时信号页面的热力图
        montage = self._sim.electrode_channels_page.get_current_montage()
        if montage:
            self._sim.signal_page.set_montage(montage)
        self._sim.signal_page.clear_heatmap()

        if self._sim.mne_fwd is not None:
            self._sim.mne.refresh_channel_mapping()

        self._update_plot_curves()

    def _update_plot_curves(self):
        """更新图表曲线"""
        if self._sim.is_running:
            self._sim.simulation.stop_simulation()
            self._sim.simulation.start_simulation()

    def init_simulation(self):
        """初始化仿真"""
        logger.info("仿真系统初始化")
        self._init_signal_buffers()
        self._sim.electrode_channels_page._update_channel_list()
        logger.info("仿真系统初始化完成")

    def _init_signal_buffers(self):
        """初始化信号缓冲区"""
        self._sim.buffer_size = self._compute_buffer_size()
        self._sim.time_buffer = np.zeros(self._sim.buffer_size)
        self._sim.signal_buffer.clear()
        for patch in self._sim.patches.values():
            for dipole in patch.dipoles:
                self._sim.signal_buffer[dipole.id] = np.zeros(self._sim.buffer_size)
