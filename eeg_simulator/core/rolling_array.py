"""Fixed-size chronological array with constant-time batch append."""

import numpy as np


class RollingArray:
    def __init__(self, size, values=None):
        self._data = np.zeros(size, dtype=float)
        self._next = 0
        if values is not None:
            self[:] = values

    @property
    def size(self):
        return self._data.size

    def __len__(self):
        return self.size

    def __array__(self, dtype=None):
        return np.asarray(self[:], dtype=dtype)

    def __getitem__(self, key):
        ordered = np.concatenate((self._data[self._next:], self._data[:self._next]))
        return ordered[key]

    def __setitem__(self, key, value):
        ordered = self[:]
        ordered[key] = value
        self._data[:] = ordered
        self._next = 0

    def fill(self, value):
        self._data.fill(value)

    def append(self, values):
        values = np.asarray(values, dtype=float).ravel()
        count = len(values)
        if count >= self.size:
            self._data[:] = values[-self.size:]
            self._next = 0
            return
        end = self._next + count
        first = min(count, self.size - self._next)
        self._data[self._next:self._next + first] = values[:first]
        if end > self.size:
            self._data[:end - self.size] = values[first:]
        self._next = end % self.size
