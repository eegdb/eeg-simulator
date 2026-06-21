"""SimulationOutputSink 单元测试（不依赖 PyQt）"""

import os
import tempfile

import numpy as np
import pytest

from eeg_simulator.core.output_sink import SimulationOutputSink


def test_validate_edf_requires_dir_and_filename():
    ok, key = SimulationOutputSink.validate('edf', ['Fp1'], None, '')
    assert not ok
    assert key == 'msg_output_dir_required'

    with tempfile.TemporaryDirectory() as d:
        ok, key = SimulationOutputSink.validate('edf', ['Fp1'], d, '')
        assert not ok
        assert key == 'msg_output_filename_required'

        ok, key = SimulationOutputSink.validate('edf', ['Fp1'], d, 'test')
        assert ok


def test_edf_write_and_read():
    channels = ['Fp1', 'Fp2']
    sfreq = 256.0
    n_samples = 256  # 一整条 EDF data record（1 秒）

    with tempfile.TemporaryDirectory() as d:
        sink = SimulationOutputSink(
            fmt='edf',
            channel_names=channels,
            sampling_rate=sfreq,
            output_dir=d,
            filename='sim_test',
        )
        sink.start()

        t = np.arange(n_samples) / sfreq
        batch = {
            'Fp1': 10.0 * np.sin(2 * np.pi * 10 * t),
            'Fp2': 5.0 * np.cos(2 * np.pi * 10 * t),
        }
        sink.write_batch(batch)
        path = sink.stop()

        assert path is not None
        assert os.path.isfile(path)

        import pyedflib

        reader = pyedflib.EdfReader(path)
        try:
            assert reader.signals_in_file == 2
            assert reader.getSampleFrequency(0) == sfreq
            data0 = reader.readSignal(0)
            assert len(data0) == n_samples
        finally:
            reader.close()


def test_fif_write():
    channels = ['Cz']
    sfreq = 512.0
    n_samples = 64

    with tempfile.TemporaryDirectory() as d:
        sink = SimulationOutputSink(
            fmt='fif',
            channel_names=channels,
            sampling_rate=sfreq,
            output_dir=d,
            filename='sim_test',
        )
        sink.start()
        sink.write_batch({'Cz': np.ones(n_samples, dtype=np.float64)})
        path = sink.stop()

        assert path is not None
        import mne

        raw = mne.io.read_raw_fif(path, preload=True, verbose=False)
        assert raw.info['sfreq'] == sfreq
        assert raw.n_times == n_samples
        assert raw.ch_names == channels


def test_fif_chunked_write_multiple_batches():
    channels = ['Fp1', 'Fp2']
    sfreq = 256.0

    with tempfile.TemporaryDirectory() as d:
        sink = SimulationOutputSink(
            fmt='fif',
            channel_names=channels,
            sampling_rate=sfreq,
            output_dir=d,
            filename='sim_chunk',
        )
        sink.start()
        for i in range(5):
            n = 32
            sink.write_batch({
                'Fp1': np.full(n, float(i), dtype=np.float64),
                'Fp2': np.full(n, float(i) * 2, dtype=np.float64),
            })
        path = sink.stop()

        import mne

        raw = mne.io.read_raw_fif(path, preload=True, verbose=False)
        assert raw.n_times == 160
        data, _ = raw[:, :32]
        assert np.allclose(data[0], 0.0)
        data, _ = raw[:, 128:160]
        assert np.allclose(data[0], 4.0e-6)


def test_needs_duration_confirmation():
    assert not SimulationOutputSink.needs_duration_confirmation('lsl', 0)
    assert not SimulationOutputSink.needs_duration_confirmation('lsl', 7200)
    assert SimulationOutputSink.needs_duration_confirmation('edf', 0)
    assert SimulationOutputSink.needs_duration_confirmation('fif', 0)
    assert not SimulationOutputSink.needs_duration_confirmation('edf', 3600)
    assert SimulationOutputSink.needs_duration_confirmation('edf', 3601)


@pytest.mark.skipif(
    __import__('importlib').util.find_spec('pylsl') is None,
    reason='pylsl not installed',
)
def test_lsl_start_and_push():
    channels = ['Fp1']
    sink = SimulationOutputSink(
        fmt='lsl',
        channel_names=channels,
        sampling_rate=256.0,
        device_name='TestEEG',
    )
    sink.start()
    sink.write_batch({'Fp1': np.array([1.0, 2.0, 3.0], dtype=np.float64)})
    assert sink._sample_count == 3
    sink.stop()
