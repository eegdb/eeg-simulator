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
        update_hz = getattr(self._sim, '_simulation_update_hz', 20)
        self._sim.samples_per_update = max(1, int(sr / update_hz))
        self._sim.signal_engine.sampling_rate = sr
        self._sim._coupling_engine.set_sampling_rate(sr)
        for coupling in self._sim._coupling_models.values():
            coupling.set_sampling_rate(sr)
        if self._sim._mne_simulator is not None:
            self._sim._mne_simulator.sampling_rate = sr

    def _on_time_window_changed(self, _value):
        """时间窗口改变时同步环形缓冲区并立即刷新波形"""
        preserve = self._sim.is_running
        self._resize_signal_buffers(preserve_recent=preserve)
        if hasattr(self._sim, 'simulation'):
            self._sim.simulation._update_plots()

    def _compute_buffer_size(self) -> int:
        """按显示时间窗口与采样率计算缓冲区长度"""
        time_window = 10.0
        if hasattr(self._sim, 'signal_page'):
            time_window = self._sim.signal_page.time_window_spin.value()
        return max(int(time_window * self._sim.sampling_rate), 256)

    @staticmethod
    def _resize_array_preserve_tail(old: np.ndarray, new_size: int) -> np.ndarray:
        """调整数组长度，保留末尾最近的数据"""
        new_arr = np.zeros(new_size)
        if old.size > 0:
            keep = min(old.size, new_size)
            new_arr[-keep:] = old[-keep:]
        return new_arr

    def _resize_signal_buffers(self, preserve_recent: bool = False):
        """重建环形缓冲区；运行中可保留最近数据以支持实时改时间窗"""
        new_size = self._compute_buffer_size()
        if new_size == self._sim.buffer_size and self._sim.time_buffer.size == new_size:
            return

        if preserve_recent and self._sim.time_buffer.size > 0:
            self._sim.time_buffer = self._resize_array_preserve_tail(
                self._sim.time_buffer, new_size)
            for ch in list(self._sim.eeg_buffer.keys()):
                self._sim.eeg_buffer[ch] = self._resize_array_preserve_tail(
                    self._sim.eeg_buffer[ch], new_size)
            for dipole_id in list(self._sim.signal_buffer.keys()):
                self._sim.signal_buffer[dipole_id] = self._resize_array_preserve_tail(
                    self._sim.signal_buffer[dipole_id], new_size)
        else:
            self._sim.time_buffer = np.zeros(new_size)
            for ch in list(self._sim.eeg_buffer.keys()):
                self._sim.eeg_buffer[ch] = np.zeros(new_size)
            for dipole_id in list(self._sim.signal_buffer.keys()):
                self._sim.signal_buffer[dipole_id] = np.zeros(new_size)

        self._sim.buffer_size = new_size
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
