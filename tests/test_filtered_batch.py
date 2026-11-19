from types import SimpleNamespace
import threading

import numpy as np
from PyQt6.QtCore import QCoreApplication, QEventLoop, QThread, QTimer, Qt, QObject, pyqtSlot

from eeg_simulator.core.rolling_array import RollingArray
from eeg_simulator.core.simulator.signal import SimulatorSignal
from eeg_simulator.core.simulator.simulation import FilterWorker


def test_worker_filter_converts_volts_to_microvolts_once():
    sim = SimpleNamespace(
        sampling_rate=256, selected_channels=['C3'], buffer_size=5,
        time_buffer=RollingArray(5), eeg_buffer={}, _output_sink=None,
        _filter_coeffs={}, _filter_states={},
    )
    sim.signal = SimulatorSignal(sim)
    worker = FilterWorker(sim)
    received = []
    worker.ready.connect(received.append)
    worker.filter_batch({'t': np.array([0.0, 1 / 256]),
                         'eeg_data': {'C3': np.array([1e-6, 2e-6])},
                         'revision': 0})
    times, filtered, revision = received[0]
    sim.signal._update_buffers_batch(times, {}, filtered, len(times), filtered_uV=True)
    np.testing.assert_allclose(sim.eeg_buffer['C3'][-2:], [1.0, 2.0])
    assert revision == 0


def test_filter_result_returns_to_main_thread():
    app = QCoreApplication.instance() or QCoreApplication([])
    sim = SimpleNamespace(signal=SimpleNamespace(
        _filter_lock=threading.RLock(),
        _apply_filter=lambda values, name: values,
    ))
    worker = FilterWorker(sim)
    thread = QThread()
    worker.moveToThread(thread)
    loop = QEventLoop()
    main_thread = threading.get_ident()
    received = []

    class Receiver(QObject):
        @pyqtSlot(object)
        def accept(self, result):
            received.append((result, threading.get_ident()))
            loop.quit()

    receiver = Receiver()
    worker.ready.connect(receiver.accept, Qt.ConnectionType.QueuedConnection)
    thread.start()
    try:
        worker.request_filter.emit({'t': np.array([0.0]),
                                    'eeg_data': {'C3': np.array([1e-6])},
                                    'revision': 1})
        QTimer.singleShot(2000, loop.quit)
        loop.exec()
        assert len(received) == 1
        assert received[0][1] == main_thread
        np.testing.assert_allclose(received[0][0][1]['C3'], [1.0])
    finally:
        thread.quit()
        thread.wait()
