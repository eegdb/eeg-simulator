"""仿真启停、主循环与输出 sink。"""

import time
from collections import deque

import numpy as np
from PyQt6.QtCore import QObject, Qt, QThread, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import QApplication, QMessageBox

from ...ui.styles import COLORS
from ...utils import tr, get_logger
from ..output_sink import SimulationOutputSink, OutputSinkError

logger = get_logger(__name__)

_PERF_SUMMARY_INTERVAL = 5.0
_PERF_WARN_WORKER_MS = 1000.0
_PERF_WARN_QUEUE_LOW_S = 0.3
_PERF_WARN_HZ_TOLERANCE = 0.05
_PERF_WARN_COOLDOWN_S = 5.0
_PERF_STARTUP_GRACE_S = 3.0
_PERF_WORKER_WARN_COOLDOWN_S = 10.0


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
            timings = {}
            t0 = time.perf_counter()
            dt = 1.0 / self._sim.sampling_rate
            t_end = t_start + n_samples * dt
            t = np.linspace(t_start, t_end, n_samples, endpoint=False)

            section = time.perf_counter()
            patch_signals = self._sim.signal._generate_patch_signals_batch(t, n_samples)
            patch_signals = self._sim.signal._apply_coupling_batch(patch_signals, t, n_samples)
            timings['source_ms'] = (time.perf_counter() - section) * 1000.0

            section = time.perf_counter()
            eeg_data, forward_series = self._sim.signal._project_to_electrodes_batch(
                patch_signals,
                n_samples,
                start_time=t_start,
                return_all_data=True,
            )
            timings['project_ms'] = (time.perf_counter() - section) * 1000.0

            heatmap_result = None
            if forward_series is not None:
                section = time.perf_counter()
                heatmap_result = self._sim.signal.compute_heatmap_band_powers_from_forward_series(
                    forward_series
                )
                timings['heatmap_power_ms'] = (time.perf_counter() - section) * 1000.0

            if self._sim.noise_configs:
                section = time.perf_counter()
                eeg_data = self._sim.signal._add_noise_batch(eeg_data, t, n_samples)
                timings['noise_ms'] = (time.perf_counter() - section) * 1000.0

            timings['worker_total_ms'] = (time.perf_counter() - t0) * 1000.0
            self.batch_ready.emit({
                't': t,
                't_end': t_end,
                'n_samples': n_samples,
                'patch_signals': patch_signals,
                'eeg_data': eeg_data,
                'heatmap_result': heatmap_result,
                'timings': timings,
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
        self._pending_batches = deque()
        self._generated_until = 0.0
        self._chunk_seconds = 1.0
        self._prefill_seconds = 1.5
        self._max_queue_seconds = 3.0
        self._latest_heatmap_result = None
        self._perf_window_start = None
        self._perf_last_warn = {}
        self._perf = None
        self._perf_grace_until = 0.0
        self._consume_sample_carry = 0.0

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
        self._pending_batches.clear()
        self._latest_heatmap_result = None
        if self._worker_thread is not None:
            self._worker_thread.quit()
            self._worker_thread.wait()
        self._worker = None
        self._worker_thread = None

    def _queued_seconds(self) -> float:
        return max(0.0, self._generated_until - self._sim.simulation_time)

    def _compute_consume_samples(self, target_time: float, update_hz: int) -> int:
        """按墙钟追赶仿真进度，避免定时器抖动导致有效输出低于采样率。"""
        sr = float(self._sim.sampling_rate)
        nominal = sr / update_hz
        self._consume_sample_carry += nominal
        n = int(self._consume_sample_carry)
        self._consume_sample_carry -= n

        lag_s = max(0.0, target_time - self._sim.simulation_time)
        if lag_s > 0:
            lag_samples = int(round(lag_s * sr))
            max_burst = max(n, int(round(sr * 0.25)))
            n = min(max(n, lag_samples, 1), max_burst)

        return max(1, n)

    def _request_generation_if_needed(self, target_time: float | None = None):
        if self._worker is None or self._worker_busy:
            return

        target_time = self._sim.simulation_time if target_time is None else target_time
        queued = self._generated_until - self._sim.simulation_time
        if queued >= self._prefill_seconds:
            return
        if queued >= self._max_queue_seconds:
            return

        t_start = max(self._generated_until, self._sim.simulation_time)
        if target_time > t_start + self._max_queue_seconds:
            t_start = self._generated_until
        n_samples = max(1, int(round(self._chunk_seconds * self._sim.sampling_rate)))
        self._worker_busy = True
        self._worker.request_generate.emit(t_start, n_samples)

    def _pop_generated_samples(self, n_samples: int) -> tuple[np.ndarray, dict]:
        if n_samples <= 0 or not self._pending_batches:
            return np.array([]), {}

        t_parts = []
        channel_parts = {}
        remaining = n_samples

        while remaining > 0 and self._pending_batches:
            batch = self._pending_batches[0]
            pos = int(batch.get('pos', 0))
            total = int(batch['n_samples'])
            available = total - pos
            if available <= 0:
                self._pending_batches.popleft()
                continue

            take = min(remaining, available)
            end = pos + take
            t_parts.append(batch['t'][pos:end])
            for ch_name, data in batch['eeg_data'].items():
                channel_parts.setdefault(ch_name, []).append(data[pos:end])

            batch['pos'] = end
            remaining -= take
            if end >= total:
                self._pending_batches.popleft()

        if not t_parts:
            return np.array([]), {}

        t = np.concatenate(t_parts) if len(t_parts) > 1 else t_parts[0]
        eeg_data = {
            ch_name: np.concatenate(parts) if len(parts) > 1 else parts[0]
            for ch_name, parts in channel_parts.items()
        }
        return t, eeg_data

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
        self._pending_batches.clear()
        self._generated_until = 0.0
        self._latest_heatmap_result = None
        self._init_perf_tracker()

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
        self._request_generation_if_needed(self._prefill_seconds)

        # 启动定时器
        update_hz = max(5, int(getattr(self._sim, '_simulation_update_hz', 20)))
        update_interval = int(1000 / update_hz)
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
        self._flush_perf_summary(force=True)
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

            update_hz = max(5, int(getattr(self._sim, '_simulation_update_hz', 20)))
            target_time = max(
                0.0,
                current_time - getattr(self._sim, '_run_time_origin', current_time),
            )
            n_samples = self._compute_consume_samples(target_time, update_hz)
            if n_samples <= 0:
                return

            self._request_generation_if_needed(target_time)
            if not self._pending_batches:
                self._perf_record_stall()
                return

            t, eeg_data = self._pop_generated_samples(n_samples)
            if t.size == 0 or not eeg_data:
                self._perf_record_stall()
                return

            ui_t0 = time.perf_counter()
            consumed = int(t.size)
            section = time.perf_counter()
            self._sim.signal._update_buffers_batch(t, {}, eeg_data, consumed)
            buffer_ms = (time.perf_counter() - section) * 1000.0
            self._sim.simulation_time = float(t[-1] + 1.0 / self._sim.sampling_rate)

            plot_ms = 0.0
            if (self._sim.simulation_time - self._sim._last_waveform_update_time
                    >= self._sim._waveform_update_interval):
                section = time.perf_counter()
                self._update_plots()
                plot_ms = (time.perf_counter() - section) * 1000.0
                self._sim._last_waveform_update_time = self._sim.simulation_time

            heatmap_ms = 0.0
            if (QApplication.activeModalWidget() is None
                    and self._sim.signal_page.is_heatmap_enabled()
                    and self._sim.simulation_time - self._sim._last_heatmap_update_time >= self._sim.heatmap_refresh_interval):
                section = time.perf_counter()
                self._update_heatmap_from_simulation()
                heatmap_ms = (time.perf_counter() - section) * 1000.0
                self._sim._last_heatmap_update_time = self._sim.simulation_time

            total_ui_ms = (time.perf_counter() - ui_t0) * 1000.0
            self._perf_record_ui(consumed, total_ui_ms, buffer_ms, plot_ms, heatmap_ms)

            duration_limit = self._sim.output_page.get_output_config().get('duration', 0)
            if duration_limit > 0 and self._sim.simulation_time >= duration_limit:
                logger.info(f"达到设定时长 {duration_limit}s，自动停止仿真")
                self.stop_simulation()
        except Exception as e:
            logger.error(f"仿真更新失败: {e}", exc_info=True)
            self.stop_simulation()
            QMessageBox.critical(self._sim, tr('error'), tr('msg_simulation_failed', str(e)))

    def _on_worker_batch_ready(self, batch: dict):
        if not self._sim.is_running:
            self._worker_busy = False
            return

        try:
            batch['pos'] = 0
            self._pending_batches.append(batch)
            self._generated_until = max(self._generated_until, float(batch['t_end']))
            if batch.get('heatmap_result') is not None:
                self._latest_heatmap_result = batch['heatmap_result']
            self._perf_record_worker(batch, batch.get('timings') or {})
        except Exception as e:
            logger.error(f"处理后台数据失败: {e}", exc_info=True)
            self.stop_simulation()
            QMessageBox.critical(self._sim, tr('error'), tr('msg_simulation_failed', str(e)))

        finally:
            self._worker_busy = False
            if self._sim.is_running:
                self._request_generation_if_needed()

    @staticmethod
    def _new_perf_stats() -> dict:
        return {
            'generated_samples': 0,
            'generated_batches': 0,
            'worker_ms_total': 0.0,
            'worker_ms_max': 0.0,
            'project_ms_total': 0.0,
            'project_ms_max': 0.0,
            'consumed_samples': 0,
            'consumed_ticks': 0,
            'stall_ticks': 0,
            'queue_min': float('inf'),
            'queue_max': 0.0,
            'queue_sum': 0.0,
            'queue_samples': 0,
            'ui_ms_total': 0.0,
            'ui_ms_max': 0.0,
            'buffer_ms_max': 0.0,
            'plot_ms_max': 0.0,
            'heatmap_ms_max': 0.0,
        }

    def _init_perf_tracker(self):
        self._perf_window_start = time.time()
        self._perf_last_warn = {}
        self._perf = self._new_perf_stats()
        self._perf_grace_until = self._perf_window_start + _PERF_STARTUP_GRACE_S
        self._consume_sample_carry = 0.0

    def _reset_perf_window(self):
        self._perf_window_start = time.time()
        self._perf = self._new_perf_stats()

    def _perf_warn(self, key: str, message: str, cooldown: float = _PERF_WARN_COOLDOWN_S):
        now = time.time()
        last = self._perf_last_warn.get(key, 0.0)
        if now - last < cooldown:
            return
        self._perf_last_warn[key] = now
        logger.warning(message)

    def _perf_record_queue(self):
        if self._perf is None:
            return
        queued = self._queued_seconds()
        perf = self._perf
        perf['queue_min'] = min(perf['queue_min'], queued)
        perf['queue_max'] = max(perf['queue_max'], queued)
        perf['queue_sum'] += queued
        perf['queue_samples'] += 1
        if 0 < queued < _PERF_WARN_QUEUE_LOW_S:
            self._perf_warn(
                'queue_low',
                f"实时落后: 队列缓冲不足 queued={queued:.2f}s < {_PERF_WARN_QUEUE_LOW_S:.1f}s",
            )

    def _perf_record_stall(self):
        if self._perf is None:
            return
        self._perf['stall_ticks'] += 1
        queued = self._queued_seconds()
        if time.time() >= self._perf_grace_until:
            self._perf_warn(
                'stall',
                f"实时落后: 空队列跳过，无样本可输出 queued={queued:.2f}s",
            )
        self._perf_record_queue()
        self._maybe_flush_perf_summary()

    def _perf_record_worker(self, batch: dict, timings: dict):
        if self._perf is None:
            return
        worker_ms = float(timings.get('worker_total_ms', 0.0))
        n_samples = int(batch['n_samples'])
        perf = self._perf
        perf['generated_samples'] += n_samples
        perf['generated_batches'] += 1
        perf['worker_ms_total'] += worker_ms
        perf['worker_ms_max'] = max(perf['worker_ms_max'], worker_ms)
        project_ms = float(timings.get('project_ms', 0.0))
        perf['project_ms_total'] += project_ms
        perf['project_ms_max'] = max(perf['project_ms_max'], project_ms)
        self._perf_record_queue()
        if worker_ms > _PERF_WARN_WORKER_MS:
            self._perf_warn(
                'worker_slow',
                f"实时落后: worker单批={worker_ms:.1f}ms > {_PERF_WARN_WORKER_MS:.0f}ms "
                f"(project={project_ms:.1f} source={float(timings.get('source_ms', 0.0)):.1f} "
                f"heatmap_power={float(timings.get('heatmap_power_ms', 0.0)):.1f} "
                f"noise={float(timings.get('noise_ms', 0.0)):.1f} queued={self._queued_seconds():.2f}s)",
                cooldown=_PERF_WORKER_WARN_COOLDOWN_S,
            )
        self._maybe_flush_perf_summary()

    def _perf_record_ui(self, consumed: int, total_ui_ms: float, buffer_ms: float,
                        plot_ms: float, heatmap_ms: float):
        if self._perf is None:
            return
        perf = self._perf
        perf['consumed_samples'] += consumed
        perf['consumed_ticks'] += 1
        perf['ui_ms_total'] += total_ui_ms
        perf['ui_ms_max'] = max(perf['ui_ms_max'], total_ui_ms)
        perf['buffer_ms_max'] = max(perf['buffer_ms_max'], buffer_ms)
        perf['plot_ms_max'] = max(perf['plot_ms_max'], plot_ms)
        perf['heatmap_ms_max'] = max(perf['heatmap_ms_max'], heatmap_ms)
        self._perf_record_queue()
        self._maybe_flush_perf_summary()

    def _maybe_flush_perf_summary(self):
        if self._perf_window_start is None:
            return
        elapsed = time.time() - self._perf_window_start
        if elapsed < _PERF_SUMMARY_INTERVAL:
            return
        self._flush_perf_summary(force=False)

    def _flush_perf_summary(self, force: bool = False):
        if self._perf is None or self._perf_window_start is None:
            return
        elapsed = time.time() - self._perf_window_start
        if not force and elapsed < _PERF_SUMMARY_INTERVAL:
            return

        perf = self._perf
        has_activity = (
            perf['consumed_ticks'] > 0
            or perf['generated_batches'] > 0
            or perf['stall_ticks'] > 0
        )
        if not has_activity:
            self._reset_perf_window()
            return

        target_hz = float(self._sim.sampling_rate)
        effective_hz = perf['consumed_samples'] / elapsed if elapsed > 0 else 0.0
        worker_avg = (
            perf['worker_ms_total'] / perf['generated_batches']
            if perf['generated_batches'] else 0.0
        )
        project_avg = (
            perf['project_ms_total'] / perf['generated_batches']
            if perf['generated_batches'] else 0.0
        )
        if perf['queue_samples'] > 0:
            queue_min = perf['queue_min'] if perf['queue_min'] != float('inf') else 0.0
            queue_avg = perf['queue_sum'] / perf['queue_samples']
            queue_str = f"{queue_min:.1f}~{perf['queue_max']:.1f}s(avg={queue_avg:.1f})"
        else:
            queue_str = "n/a"
        ui_avg = perf['ui_ms_total'] / perf['consumed_ticks'] if perf['consumed_ticks'] else 0.0
        behind = False
        if perf['consumed_samples'] > 0 and target_hz > 0:
            deviation = abs(effective_hz - target_hz) / target_hz
            behind = deviation > _PERF_WARN_HZ_TOLERANCE
        status = '落后' if (behind or perf['stall_ticks'] > 0) else '正常'

        logger.info(
            "实时性能[%.0fs] 状态=%s: 生成=%d批(avg=%.0fms,max=%.0fms) 消费=%dtick 输出=%d点(%.1f/%.0fHz) "
            "队列=%s 空队列跳过=%d次 project(avg=%.0fms,max=%.0fms) "
            "UI=avg=%.0fms(max=%.0fms,heatmap_max=%.0fms)",
            elapsed,
            status,
            perf['generated_batches'],
            worker_avg,
            perf['worker_ms_max'],
            perf['consumed_ticks'],
            perf['consumed_samples'],
            effective_hz,
            target_hz,
            queue_str,
            perf['stall_ticks'],
            project_avg,
            perf['project_ms_max'],
            ui_avg,
            perf['ui_ms_max'],
            perf['heatmap_ms_max'],
        )

        if perf['stall_ticks'] > 0:
            logger.warning(
                "实时落后: 过去%.0fs内空队列跳过=%d次，有效输出=%.1fHz",
                elapsed,
                perf['stall_ticks'],
                effective_hz,
            )

        self._reset_perf_window()

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

        max_points = max(200, int(getattr(self._sim, '_waveform_display_max_points', 1200)))
        stride = max(1, int(np.ceil(n_samples / max_points)))
        t_window = self._sim.time_buffer[-n_samples:] if len(self._sim.time_buffer) >= n_samples else self._sim.time_buffer
        t_display = t_window[::stride]

        channel_data = {}
        for ch_name in self._sim.selected_channels:
            if ch_name in self._sim.eeg_buffer and ch_name in self._sim.signal_page.plot_curves:
                data_window = self._sim.eeg_buffer[ch_name][-n_samples:]
                channel_data[ch_name] = data_window[::stride]
        if channel_data:
            self._sim.signal_page.update_waveform_plots(t_display, channel_data)

        # 更新FFT频谱（节流，降低 CPU 占用）
        if (self._sim.signal_page.is_fft_enabled()
                and self._sim.simulation_time - self._sim._last_fft_update_time >= self._sim._fft_update_interval):
            self._sim.signal._update_fft_spectrum(n_samples)
            self._sim._last_fft_update_time = self._sim.simulation_time

    def _update_heatmap_from_simulation(self):
        """根据仿真结果更新热力图（全 montage 频带功率）"""
        current_band = self._sim.signal_page.get_heatmap_band()
        if (
            self._latest_heatmap_result is not None
            and self._latest_heatmap_result.get('band') == current_band
        ):
            self._sim.signal_page.update_heatmap_result(self._latest_heatmap_result)
            return
        if self._latest_heatmap_result is not None and self._sim._mne_simulator is not None:
            return

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
