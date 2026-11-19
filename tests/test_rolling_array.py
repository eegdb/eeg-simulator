import numpy as np

from eeg_simulator.core.rolling_array import RollingArray


def test_append_preserves_chronological_window_and_tail():
    window = RollingArray(5)
    window.append([1, 2])
    np.testing.assert_array_equal(window[:], [0, 0, 0, 1, 2])
    window.append([3, 4, 5, 6])
    np.testing.assert_array_equal(window[:], [2, 3, 4, 5, 6])
    np.testing.assert_array_equal(window[-3:], [4, 5, 6])
    window.append([7, 8, 9, 10, 11, 12])
    np.testing.assert_array_equal(window[:], [8, 9, 10, 11, 12])


def test_direct_assignment_used_by_warmup():
    window = RollingArray(4)
    window[:] = [1, 2, 3, 4]
    window.append([5])
    np.testing.assert_array_equal(window[:], [2, 3, 4, 5])
    window.fill(0)
    np.testing.assert_array_equal(window[:], [0, 0, 0, 0])
