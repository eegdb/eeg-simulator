from unittest.mock import patch

from eeg_simulator.core.simulation_clock import SimulationClock


def test_sample_time_does_not_follow_wall_clock_jumps():
    clock = SimulationClock(256)
    with patch('eeg_simulator.core.simulation_clock.time.monotonic', side_effect=[10.0, 10.5, 12.0]):
        clock.start()
        assert clock.target_time() == 0.5
        assert clock.advance(128) == 0.5
        assert clock.target_time() == 2.0
        assert clock.simulation_time == 0.5
