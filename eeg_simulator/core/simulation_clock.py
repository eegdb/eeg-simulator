"""Sample-based simulation time and monotonic wall-clock scheduling."""

import time


class SimulationClock:
    def __init__(self, sampling_rate: float):
        self.sampling_rate = float(sampling_rate)
        self.consumed_samples = 0
        self.origin = None

    @property
    def simulation_time(self) -> float:
        return self.consumed_samples / self.sampling_rate

    def start(self) -> None:
        self.consumed_samples = 0
        self.origin = time.monotonic()

    def target_time(self) -> float:
        if self.origin is None:
            return 0.0
        return max(0.0, time.monotonic() - self.origin)

    def advance(self, sample_count: int) -> float:
        if sample_count < 0:
            raise ValueError('sample_count must be non-negative')
        self.consumed_samples += sample_count
        return self.simulation_time
