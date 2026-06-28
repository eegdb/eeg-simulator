"""仿真启停、主循环与输出 sink。"""

import time

import numpy as np
from PyQt6.QtCore import QObject, Qt, QThread, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import QApplication, QMessageBox

from ...ui.styles import COLORS
from ...utils import tr, get_logger
from ..output_sink import SimulationOutputSink, OutputSinkError

logger = get_logger(__name__)


class SimulationWorker(QObject):
    request_generate = pyqtSignal(float, int)
    batch_ready = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, simulator):
        super().__init__()
        self._sim = simulator
        self.request_generate.connect(
            self.generate_batch,
            Qt.ConnectionType.QueuedConnection,
        )

    @pyqtSlot(float, int)
    def generate_batch(self, t_start: float, n_samples: int):
        try:
            dt = 1.0 / self._sim.sampling_rate
            t_end = t_start + n_samples * dt
            t = np.linspace(t_start, t_end, n_samples, endpoint=False)

            patch_signals = self._sim.signal._generate_patch_signals_batch(t, n_samples)
            patch_signals = self._sim.signal._apply_coupling_batch(patch_signals, t, n_samples)
            eeg_data = self._sim.signal._project_to_electrodes_batch(patch_signals, n_samples)

            if self._sim.noise_configs:
                eeg_data = self._sim.signal._add_noise_batch(eeg_data, t, n_samples)

            self.batch_ready.emit({
                't': t,
                't_end': t_end,
                'n_samples': n_samples,
                'patch_signals': patch_signals,
                'eeg_data': eeg_data,
            })
        except Exception as e:
            logger.error(f"后台生成数据失败: {e}", exc_info=True)
            self.failed.emit(str(e))


class SimulatorSimulation:
    """SimulatorSimulation 服务。"""

    def __init__(self, simulator):
        self._sim = simulator
        self._worker_thread = None
        self._worker = None
        self._worker_busy = False

    def _start_worker(self):
        self._stop_worker()
        self._worker_busy = False
        self._worker_thread = QThread(self._sim)
        self._worker = SimulationWorker(self._sim)
        self._worker.moveToThread(self._worker_thread)
        self._worker_thread.finished.connect(self._worker.deleteLater)
        self._worker.batch_ready.connect(self._on_worker_batch_ready)
        self._worker.failed.connect(self._on_worker_failed)
        self._worker_thread.start()

    def _stop_worker(self):
        self._worker_busy = False
        if self._worker_thread is not None:
            self._worker_thread.quit()
            self._worker_thread.wait()
        self._worker = None
        self._worker_thread = None

    def start_simulation(self):
        """开始仿真。成功返回 True，校验失败返回 False。"""
        if self._sim.is_running:
            return True

        logger.info("=" * 40)
        logger.info("开始仿真")

        # 检查是否有选中的通道
        if not self._sim.selected_channels:
            QMessageBox.warning(self._sim, tr('warning'), tr('msg_no_channels_selected'))
            return False

        if not self._sim.patches:
            QMessageBox.warning(self._sim, tr('warning'), tr('msg_no_patches'))
            return False

        output_config = self._sim.output_page.get_output_config()
        if not self._validate_output_config(output_config):
            return False
        if not self._confirm_file_output_duration(output_config):
            return False
        if not self._init_output_sink(output_config):
            return False

        if (self._sim._mne_simulator is None or not self._sim._mne_simulator.is_ready()):
            QMessageBox.warning(self._sim, tr('warning'), tr('msg_no_forward_model'))

        # 确保缓冲区尺寸与当前时间窗口一致（须在 is_running 置 True 之前）
        self._sim.buffers._resize_signal_buffers()

        # 更新状态
        self._sim.is_running = True
        self._sim.simulation_time = 0.0
        self._sim._run_start_time = time.time()
        self._sim._last_update_time = None

        # 重置信号生成状态，确保从初始相位开始
        self._sim._signal_states.clear()

        # 重置噪声状态
        self._sim._noise_states.clear()

        # 重置耦合延迟缓冲
        self._sim._coupling_engine.reset_histories()
        self._sim._last_fft_update_time = 0.0
        self._sim._last_waveform_update_time = 0.0
        self._sim._last_heatmap_update_time = -self._sim.heatmap_refresh_interval

        # 确保热力图 montage 与当前电极布局一致
        if hasattr(self._sim, 'ui'):
            self._sim.ui._sync_heatmap_montage()

        if self._sim.mne_fwd is not None and hasattr(self._sim, 'mne'):
            self._sim.mne.refresh_channel_mapping()

        # 更新UI
        self._sim.status_run.setText("● " + tr('status_running'))
        self._sim.status_run.setStyleSheet(f"color: {COLORS['accent']};")
        self._sim.output_page.update_simulation_status(True)

        # 初始化实时滤波状态，并预热显示缓冲区
        self._sim.signal._init_filter_states()
        self._sim.signal.warm_up_display_buffer()
        self._sim._run_time_origin = time.time() - self._sim.simulation_time

        # 初始化图表并立即绘制预热后的数据
        self._sim.signal_page.update_plots(self._sim.selected_channels)
        self._update_plots()
        self._start_worker()

        # 启动定时器
        update_interval = int(1000 / 30)  # 30fps
        self._sim.timer.start(update_interval)
        self._sim.status_timer.start(1000)

        logger.info(f"仿真参数: 采样率={self._sim.sampling_rate}Hz")
        logger.info(f"选中通道: {self._sim.selected_channels}")
        return True

    def stop_simulation(self):
        """停止仿真"""
        if not self._sim.is_running:
            return

        logger.info("停止仿真")

        self._sim.is_running = False
        self._sim.timer.stop()
        self._sim.status_timer.stop()
        self._stop_worker()
        self._close_output_sink()

        # 清除信号生成状态，下次启动时重新初始化
        self._sim._signal_states.clear()

        # 清除噪声状态
        self._sim._noise_states.clear()

        # 重置耦合延迟缓冲
        self._sim._coupling_engine.reset_histories()

        # 更新UI
        self._sim.status_run.setText("○ " + tr('status_stopped'))
        self._sim.status_run.setStyleSheet(f"color: {COLORS['text_muted']};")
        self._sim.output_page.update_simulation_status(False)

    def update_simulation(self):
        """更新仿真（定时器回调）"""
        if not self._sim.is_running:
            return

        try:
            # 计算时间
            current_time = time.time()
            self._sim._last_update_time = current_time

            # 计算样本数
            target_time = max(
                0.0,
                current_time - getattr(self._sim, '_run_time_origin', current_time),
            )
            backlog = max(0.0, target_time - self._sim.simulation_time)
            step_time = min(max(backlog, 1.0 / 30), 0.25)
            n_samples = int(round(step_time * self._sim.sampling_rate))
            if n_samples <= 0:
                return

            t_start = self._sim.simulation_time
            if self._worker is None or self._worker_busy:
                return
            self._worker_busy = True
            self._worker.request_generate.emit(t_start, n_samples)
        except Exception as e:
            logger.error(f"仿真更新失败: {e}", exc_info=True)
            self.stop_simulation()
            QMessageBox.critical(self._sim, tr('error'), tr('msg_simulation_failed', str(e)))

    def _on_worker_batch_ready(self, batch: dict):
        if not self._sim.is_running:
            self._worker_busy = False
            return

        try:
            t = batch['t']
            patch_signals = batch['patch_signals']
            eeg_data = batch['eeg_data']
            n_samples = int(batch['n_samples'])
            self._sim.signal._update_buffers_batch(t, patch_signals, eeg_data, n_samples)
            self._sim.simulation_time = float(batch['t_end'])

            if (self._sim.simulation_time - self._sim._last_waveform_update_time
                    >= self._sim._waveform_update_interval):
                self._update_plots()
                self._sim._last_waveform_update_time = self._sim.simulation_time

            if (QApplication.activeModalWidget() is None
                    and self._sim.signal_page.is_heatmap_enabled()
                    and self._sim.simulation_time - self._sim._last_heatmap_update_time >= self._sim.heatmap_refresh_interval):
                self._update_heatmap_from_simulation()
                self._sim._last_heatmap_update_time = self._sim.simulation_time

            duration_limit = self._sim.output_page.get_output_config().get('duration', 0)
            if duration_limit > 0 and self._sim.simulation_time >= duration_limit:
                logger.info(f"达到设定时长 {duration_limit}s，自动停止仿真")
                self.stop_simulation()
        except Exception as e:
            logger.error(f"处理后台数据失败: {e}", exc_info=True)
            self.stop_simulation()
            QMessageBox.critical(self._sim, tr('error'), tr('msg_simulation_failed', str(e)))

        finally:
            self._worker_busy = False

    def _on_worker_failed(self, message: str):
        self._worker_busy = False
        if not self._sim.is_running:
            return
        self.stop_simulation()
        QMessageBox.critical(self._sim, tr('error'), tr('msg_simulation_failed', message))

    def _validate_output_config(self, output_config: dict) -> bool:
        """校验输出目录、文件名等（EDF/FIFF 必填）"""
        fmt = output_config.get('format', 'lsl')
        ok, msg_key = SimulationOutputSink.validate(
            fmt,
            self._sim.selected_channels,
            output_config.get('output_dir'),
            output_config.get('filename', ''),
        )
        if not ok:
            QMessageBox.warning(self._sim, tr('warning'), tr(msg_key))
            return False
        return True

    def _confirm_file_output_duration(self, output_config: dict) -> bool:
        """文件输出时长超过 1 小时或为无限时请求用户确认；LSL 无限制"""
        fmt = output_config.get('format', 'lsl')
        duration = float(output_config.get('duration', 0))
        if not SimulationOutputSink.needs_duration_confirmation(fmt, duration):
            return True

        if duration <= 0:
            message = tr('msg_output_duration_unlimited_confirm')
        else:
            message = tr('msg_output_duration_long_confirm', self._format_duration_display(duration))

        reply = QMessageBox.question(
            self._sim,
            tr('msg_output_duration_confirm_title'),
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return reply == QMessageBox.StandardButton.Yes

    @staticmethod
    def _format_duration_display(seconds: float) -> str:
        total = int(seconds)
        hours, rem = divmod(total, 3600)
        minutes, secs = divmod(rem, 60)
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        return f"{minutes}:{secs:02d}"

    def _init_output_sink(self, output_config: dict) -> bool:
        """初始化 LSL / EDF / FIF 输出"""
        fmt = output_config.get('format', 'lsl')

        self._sim._output_sink = SimulationOutputSink(
            fmt=fmt,
            channel_names=self._sim.selected_channels,
            sampling_rate=self._sim.sampling_rate,
            output_dir=output_config.get('output_dir'),
            filename=output_config.get('filename', ''),
            device_name=output_config.get('device_name', 'EEGSimulator'),
        )
        try:
            self._sim._output_sink.start()
        except OutputSinkError as e:
            QMessageBox.warning(self._sim, tr('warning'), str(e))
            self._sim._output_sink = None
            return False
        except Exception as e:
            logger.exception("输出初始化失败")
            QMessageBox.warning(self._sim, tr('warning'), tr('msg_output_start_failed', str(e)))
            self._sim._output_sink = None
            return False
        return True

    def _close_output_sink(self):
        """结束输出并保存文件（若适用）"""
        sink = self._sim._output_sink
        self._sim._output_sink = None
        if sink is None:
            return
        try:
            path = sink.stop()
            if path and sink.format in ('edf', 'fif'):
                QMessageBox.information(self._sim, tr('info'), tr('msg_output_file_saved', path))
        except Exception as e:
            logger.exception("输出结束失败")
            QMessageBox.warning(self._sim, tr('warning'), tr('msg_output_stop_failed', str(e)))

    def _update_plots(self):
        """更新波形图 - 缓冲区已包含滤波后的数据，直接显示"""
        # 模态对话框打开时跳过刷新，避免 pyqtgraph 抢焦点导致输入框无法打字
        if QApplication.activeModalWidget() is not None:
            return

        time_window = self._sim.signal_page.time_window_spin.value()
        n_samples = int(time_window * self._sim.sampling_rate)

        t_display = self._sim.time_buffer[-n_samples:] if len(self._sim.time_buffer) >= n_samples else self._sim.time_buffer

        channel_data = {}
        for ch_name in self._sim.selected_channels:
            if ch_name in self._sim.eeg_buffer and ch_name in self._sim.signal_page.plot_curves:
                channel_data[ch_name] = self._sim.eeg_buffer[ch_name][-n_samples:].copy()
        if channel_data:
            self._sim.signal_page.update_waveform_plots(t_display, channel_data)

        # 更新FFT频谱（节流，降低 CPU 占用）
        if (self._sim.signal_page.is_fft_enabled()
                and self._sim.simulation_time - self._sim._last_fft_update_time >= self._sim._fft_update_interval):
            self._sim.signal._update_fft_spectrum(n_samples)
            self._sim._last_fft_update_time = self._sim.simulation_time

    def _update_heatmap_from_simulation(self):
        """根据仿真结果更新热力图（全 montage 频带功率）"""
        time_window = min(
            self._sim.signal_page.time_window_spin.value(),
            getattr(self._sim, 'heatmap_analysis_window', 2.0),
        )
        n_samples = int(time_window * self._sim.sampling_rate)
        result = self._sim.signal.compute_heatmap_band_powers_for_topomap(n_samples)
        powers = result.get('powers')
        if powers is None or len(powers) == 0:
            return

        self._sim.signal_page.update_heatmap_result(result)
