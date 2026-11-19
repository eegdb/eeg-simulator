"""Physical BioSignal Generator output for filtered EEG samples in microvolts."""

import queue
from types import SimpleNamespace

import numpy as np

from .output_sink import OutputSinkError


class BioSignalOutputSink:
    format = 'biosignal'

    def __init__(self, channel_names, sampling_rate, *, port='', output_range='±8.333 mV', mapping='', on_error=None):
        self.channel_names = list(channel_names)
        self.sampling_rate = float(sampling_rate)
        self.port = port.strip() or None
        self.output_range = output_range
        self.mapping = [name.strip() for name in mapping.split(',')] if mapping.strip() else list(channel_names)
        self.on_error = on_error
        self._notified_error = False
        self.device = None
        self._sent = 0

    def start(self):
        try:
            from eegdb_biosignal_generator import (
                BioSignalGenerator, OutputRangePreset, SUPPORTED_SAMPLE_RATES,
            )
        except ImportError as exc:
            raise OutputSinkError('请先安装 BioSignalGenerator Python SDK') from exc
        if self.sampling_rate not in SUPPORTED_SAMPLE_RATES:
            raise OutputSinkError(f'硬件采样率须为 {SUPPORTED_SAMPLE_RATES} Hz 之一')
        if not self.channel_names:
            raise OutputSinkError('未选择 EEG 通道')
        if len(set(self.mapping)) != len(self.mapping) or any(
            name not in self.channel_names for name in self.mapping
        ):
            raise OutputSinkError('端子映射必须是互不重复的已选 EEG 通道名')
        try:
            device = BioSignalGenerator.open(port=self.port)
            self.device = device
            if len(self.mapping) > device.info.channel_count:
                raise OutputSinkError(f'设备只有 {device.info.channel_count} 个输出通道')
            preset = OutputRangePreset(self.output_range)
            device.configure(sample_rate_hz=int(self.sampling_rate), output_range=preset,
                             on_error=self._on_sdk_error)
        except Exception:
            if self.device is not None:
                self.device.close()
                self.device = None
            raise

    def write_batch(self, channel_data_uV):
        if self.device is None:
            raise OutputSinkError('BioSignal Generator 未连接')
        status = self.device.stream_status
        if status is not None and status.error is not None:
            self._notify_once(f'硬件发送失败: {status.error}')
            return
        arrays = [np.asarray(channel_data_uV[name], dtype=np.float64).ravel() for name in self.mapping]
        if not arrays:
            return
        count = len(arrays[0])
        if any(len(values) != count for values in arrays):
            raise OutputSinkError('输出通道样本数不一致')
        if count == 0:
            return
        frames = np.zeros((count, self.device.info.channel_count), dtype=np.float64)
        for index, values in enumerate(arrays):
            frames[:, index] = values
        try:
            self.device.send_uv(frames, timeout=0)
        except queue.Full as exc:
            self._notify_once('主机发送缓冲已满，部分脑电样本未送入设备')
            return
        except Exception as exc:
            self._notify_once(f'硬件发送失败: {exc}')
            return
        self._sent += count

    def _notify_once(self, message):
        if not self._notified_error and self.on_error is not None:
            self._notified_error = True
            self.on_error(SimpleNamespace(message=message, port=self.port))

    def _on_sdk_error(self, error):
        self._notified_error = True
        if self.on_error is not None:
            self.on_error(error)

    def stop(self):
        if self.device is not None:
            device, self.device = self.device, None
            # 停止时丢弃主机端待发送帧；固件已接收的帧仍会继续播放。
            try:
                if device._buffered_stream is not None:
                    known_error = device.stream_status.error is not None
                    try:
                        device._buffered_stream.close(drain=False)
                    except RuntimeError:
                        if not known_error:
                            raise
            finally:
                device.close()
        return None
