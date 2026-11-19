import types
import sys

import numpy as np
import pytest

from eeg_simulator.core.biosignal_sink import BioSignalOutputSink
from eeg_simulator.core.output_sink import OutputSinkError


class FakeDevice:
    def __init__(self):
        self.info = types.SimpleNamespace(channel_count=4)
        self.stream_status = types.SimpleNamespace(error=None)
        self.frames = []
        self._buffered_stream = None

    def configure(self, **kwargs):
        self.configuration = kwargs

    def send_uv(self, frames, **kwargs):
        self.frames.extend(tuple(row) for row in frames)

    def close(self):
        pass


def test_hardware_frames_and_zero_filled_terminals(monkeypatch):
    device = FakeDevice()
    fake_sdk = types.SimpleNamespace(
        BioSignalGenerator=types.SimpleNamespace(open=lambda port=None: device),
        OutputRangePreset=lambda value: value,
        SUPPORTED_SAMPLE_RATES=(256, 512, 1024, 2048, 4096),
    )
    monkeypatch.setitem(sys.modules, 'eegdb_biosignal_generator', fake_sdk)
    errors = []
    sink = BioSignalOutputSink(['C3', 'C4'], 256, mapping='C4,C3', on_error=errors.append)
    sink.start()
    device.configuration['on_error']('USB failed')
    assert errors == ['USB failed']
    sink.write_batch({'C3': np.array([1.0, 2.0]), 'C4': np.array([3.0, 4.0])})
    assert device.frames == [(3.0, 1.0, 0.0, 0.0), (4.0, 2.0, 0.0, 0.0)]
    sink.stop()


def test_unsupported_rate_is_rejected(monkeypatch):
    monkeypatch.setitem(sys.modules, 'eegdb_biosignal_generator', types.SimpleNamespace(
        BioSignalGenerator=None, OutputRangePreset=None,
        SUPPORTED_SAMPLE_RATES=(256, 512, 1024, 2048, 4096),
    ))
    with pytest.raises(OutputSinkError):
        BioSignalOutputSink(['C3'], 250).start()


def test_background_error_skips_hardware_output_without_raising(monkeypatch):
    device = FakeDevice()
    device.stream_status.error = OSError('USB disconnected')
    monkeypatch.setitem(sys.modules, 'eegdb_biosignal_generator', types.SimpleNamespace(
        BioSignalGenerator=types.SimpleNamespace(open=lambda port=None: device),
        OutputRangePreset=lambda value: value,
        SUPPORTED_SAMPLE_RATES=(256, 512, 1024, 2048, 4096),
    ))
    errors = []
    sink = BioSignalOutputSink(['C3'], 256, on_error=errors.append)
    sink.start()
    sink.write_batch({'C3': np.array([1.0])})
    sink.write_batch({'C3': np.array([2.0])})
    assert len(errors) == 1
    assert not device.frames
