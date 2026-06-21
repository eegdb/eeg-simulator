"""仿真输出：LSL 流式传输、EDF / FIF 文件导出"""

import logging
import os
import tempfile
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

FILE_OUTPUT_MAX_DURATION_SEC = 3600  # 1 小时，超出需用户确认


class OutputSinkError(Exception):
    """输出初始化或写入失败"""


class SimulationOutputSink:
    """将仿真 EEG 数据写入 LSL 或文件"""

    def __init__(
        self,
        fmt: str,
        channel_names: List[str],
        sampling_rate: float,
        output_dir: Optional[str] = None,
        filename: str = '',
        device_name: str = 'EEGSimulator',
    ):
        self.format = fmt
        self.channel_names = list(channel_names)
        self.sampling_rate = float(sampling_rate)
        self.output_dir = output_dir
        self.filename = (filename or 'eeg_simulation').strip()
        self.device_name = (device_name or 'EEGSimulator').strip()
        self._edf_writer = None
        self._lsl_outlet = None
        self._fif_tmp_path: Optional[str] = None
        self._fif_channel_tmp: Dict[str, str] = {}
        self._fif_channel_handles: Dict[str, object] = {}
        self._edf_pending: Dict[str, List[float]] = {}
        self._edf_record_samples = 0
        self._output_path: Optional[str] = None
        self._sample_count = 0

    @staticmethod
    def needs_duration_confirmation(fmt: str, duration: float) -> bool:
        """文件输出在无限时长或超过 1 小时时需用户确认；LSL 无限制"""
        if fmt == 'lsl':
            return False
        if fmt in ('edf', 'fif'):
            return duration <= 0 or duration > FILE_OUTPUT_MAX_DURATION_SEC
        return False

    @staticmethod
    def validate(
        fmt: str,
        channel_names: List[str],
        output_dir: Optional[str],
        filename: str,
    ) -> Tuple[bool, str]:
        """返回 (是否有效, i18n 消息键)"""
        if not channel_names:
            return False, 'msg_no_channels_selected'
        if fmt in ('edf', 'fif'):
            if not output_dir:
                return False, 'msg_output_dir_required'
            if not os.path.isdir(output_dir):
                return False, 'msg_output_dir_invalid'
            if not (filename and filename.strip()):
                return False, 'msg_output_filename_required'
        if fmt == 'lsl':
            try:
                import pylsl  # noqa: F401
            except ImportError:
                return False, 'msg_pylsl_not_installed'
        return True, ''

    def start(self):
        if self.format == 'lsl':
            self._start_lsl()
        elif self.format == 'edf':
            self._start_edf()
        elif self.format == 'fif':
            self._start_fif()
        else:
            raise OutputSinkError(f'Unsupported output format: {self.format}')
        logger.info(f"输出已启动: format={self.format}, channels={len(self.channel_names)}")

    def write_batch(self, channel_data_uV: Dict[str, np.ndarray]):
        """写入一批已滤波的 EEG 样本（单位 μV）"""
        if not self.channel_names:
            return

        arrays = []
        for ch in self.channel_names:
            if ch not in channel_data_uV:
                return
            arrays.append(np.asarray(channel_data_uV[ch], dtype=np.float64).ravel())

        n_samples = len(arrays[0])
        if n_samples == 0 or any(len(a) != n_samples for a in arrays):
            return

        if self.format == 'lsl':
            data = np.array(arrays, dtype=np.float32)
            self._lsl_outlet.push_chunk(data)
        elif self.format == 'edf':
            for ch, arr in zip(self.channel_names, arrays):
                self._edf_pending[ch].extend(arr.tolist())
            self._flush_edf_records(allow_partial=False)
        elif self.format == 'fif':
            for ch, arr in zip(self.channel_names, arrays):
                self._fif_channel_handles[ch].write(
                    arr.astype(np.float64, copy=False).tobytes()
                )

        self._sample_count += n_samples

    def stop(self) -> Optional[str]:
        """结束输出并返回文件路径（若适用）"""
        path = self._output_path
        try:
            if self.format == 'edf' and self._edf_writer is not None:
                self._flush_edf_records(allow_partial=True)
                self._edf_writer.close()
                self._edf_writer = None
            elif self.format == 'fif':
                path = self._finalize_fif()
            elif self.format == 'lsl':
                self._lsl_outlet = None
        except Exception:
            self._cleanup_fif_tmp()
            raise
        finally:
            logger.info(
                f"输出已结束: format={self.format}, samples={self._sample_count}, path={path}"
            )
        return path

    def _start_lsl(self):
        from pylsl import StreamInfo, StreamOutlet

        info = StreamInfo(
            self.device_name,
            'EEG',
            len(self.channel_names),
            self.sampling_rate,
            'float32',
            'eegsim',
        )
        channels = info.desc().append_child('channels')
        for name in self.channel_names:
            ch = channels.append_child('channel')
            ch.append_child_value('label', name)
            ch.append_child_value('type', 'EEG')
            ch.append_child_value('unit', 'microvolts')

        self._lsl_outlet = StreamOutlet(info)

    def _start_edf(self):
        import pyedflib

        name = self.filename if self.filename.lower().endswith('.edf') else f'{self.filename}.edf'
        path = os.path.join(self.output_dir, name)
        writer = pyedflib.EdfWriter(
            path,
            len(self.channel_names),
            file_type=pyedflib.FILETYPE_EDFPLUS,
        )
        headers = []
        for ch in self.channel_names:
            headers.append({
                'label': ch[:16],
                'dimension': 'uV',
                'sample_frequency': self.sampling_rate,
                'physical_min': -5000.0,
                'physical_max': 5000.0,
                'digital_min': -32768,
                'digital_max': 32767,
                'transducer': '',
                'prefilter': '',
            })
        writer.setSignalHeaders(headers)
        self._edf_record_samples = max(1, int(round(self.sampling_rate)))
        writer.setDatarecordDuration(self._edf_record_samples / self.sampling_rate)
        self._edf_pending = {ch: [] for ch in self.channel_names}
        self._edf_writer = writer
        self._output_path = path

    def _flush_edf_records(self, allow_partial: bool):
        """按 EDF data record 边界写入样本"""
        if self._edf_writer is None or self._edf_record_samples <= 0:
            return

        n = self._edf_record_samples
        while all(len(self._edf_pending[ch]) >= n for ch in self.channel_names):
            samples = [
                np.asarray(self._edf_pending[ch][:n], dtype=np.float64)
                for ch in self.channel_names
            ]
            for ch in self.channel_names:
                del self._edf_pending[ch][:n]
            self._edf_writer.writeSamples(samples)

        if allow_partial and any(self._edf_pending.values()):
            pending_len = max(len(self._edf_pending[ch]) for ch in self.channel_names)
            if pending_len > 0:
                samples = []
                for ch in self.channel_names:
                    chunk = list(self._edf_pending[ch])
                    if len(chunk) < n:
                        chunk.extend([0.0] * (n - len(chunk)))
                    samples.append(np.asarray(chunk[:n], dtype=np.float64))
                    self._edf_pending[ch].clear()
                self._edf_writer.writeSamples(samples)

    def _fif_basename(self) -> str:
        name = self.filename
        lower = name.lower()
        if lower.endswith('_eeg.fif') or lower.endswith('raw.fif'):
            return name
        if lower.endswith('.fif'):
            return name[:-4] + '_eeg.fif'
        return f'{name}_eeg.fif'

    def _start_fif(self):
        self._output_path = os.path.join(self.output_dir, self._fif_basename())
        self._fif_channel_tmp = {}
        self._fif_channel_handles = {}
        for ch in self.channel_names:
            fd, path = tempfile.mkstemp(
                suffix='.dat',
                prefix=f'eegsim_{ch}_',
                dir=self.output_dir,
            )
            os.close(fd)
            self._fif_channel_tmp[ch] = path
            self._fif_channel_handles[ch] = open(path, 'wb')

    def _cleanup_fif_tmp(self):
        for handle in self._fif_channel_handles.values():
            try:
                handle.close()
            except OSError:
                pass
        self._fif_channel_handles = {}
        for path in self._fif_channel_tmp.values():
            if path and os.path.isfile(path):
                try:
                    os.remove(path)
                except OSError:
                    logger.warning(f"无法删除临时 FIFF 数据文件: {path}")
        self._fif_channel_tmp = {}
        self._fif_tmp_path = None

    def _finalize_fif(self) -> Optional[str]:
        if not self._output_path or not self._fif_channel_tmp:
            return None

        for handle in self._fif_channel_handles.values():
            try:
                handle.close()
            except OSError:
                pass
        self._fif_channel_handles = {}

        if self._sample_count <= 0:
            self._cleanup_fif_tmp()
            return None

        import mne

        n_times = self._sample_count
        try:
            rows = []
            for ch in self.channel_names:
                path = self._fif_channel_tmp[ch]
                rows.append(np.fromfile(path, dtype=np.float64))
            data = np.stack(rows, axis=0).reshape(len(self.channel_names), n_times)
            info = mne.create_info(self.channel_names, self.sampling_rate, ch_types='eeg')
            raw = mne.io.RawArray(data / 1e6, info)  # μV → V
            raw.save(self._output_path, overwrite=True)
        finally:
            self._cleanup_fif_tmp()

        return self._output_path
