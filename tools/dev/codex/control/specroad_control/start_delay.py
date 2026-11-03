"""Monotonic startup boundary, independent of transport and operating data."""
import time


class StartDelay:
    """One monotonic deadline per worker; events and resume cannot shorten it."""
    def __init__(self, seconds, *, clock=None):
        self.seconds = seconds
        self.clock = clock or time.monotonic
        self.deadline = self.clock() + seconds

    def remaining(self):
        return max(0.0, self.deadline - self.clock())

    def ready(self):
        return self.remaining() == 0

    def due(self, proposed):
        return max(self.deadline, proposed)

    def snapshot(self, *, stopping=False):
        remaining = 0.0 if stopping else self.remaining()
        return {'seconds': self.seconds, 'remaining_seconds': remaining,
                'waiting': remaining > 0}
