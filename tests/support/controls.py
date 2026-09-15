"""Explicit test-only time and entropy providers."""

from datetime import datetime, timedelta, timezone


class ManualClock:
    """Explicitly injected clock; never patches real time or sleeps."""

    def __init__(self, start=None):
        self._start = datetime(2020, 1, 1, tzinfo=timezone.utc) if start is None else start
        if not isinstance(self._start, datetime) or self._start.utcoffset() is None:
            raise ValueError("An aware datetime is required")
        self._elapsed = 0

    def monotonic_ns(self):
        return self._elapsed

    def utc_now(self):
        return self._start.astimezone(timezone.utc) + timedelta(microseconds=self._elapsed // 1000)

    def advance(self, nanoseconds):
        if type(nanoseconds) is not int or nanoseconds < 0:
            raise ValueError("Clock movement must be a non-negative integer")
        candidate = self._elapsed + nanoseconds
        # Reject overflow before changing the observable clock state.
        self._start.astimezone(timezone.utc) + timedelta(microseconds=candidate // 1000)
        self._elapsed = candidate


class ByteSequence:
    """Finite injected entropy, deliberately unsuitable for production IDs."""

    def __init__(self, chunks):
        self._chunks = tuple(chunks)
        if any(type(chunk) is not bytes for chunk in self._chunks):
            raise TypeError("Entropy fixtures require bytes")
        self._position = 0

    def __call__(self, count):
        if type(count) is not int or count <= 0:
            raise ValueError("Entropy request must be a positive integer")
        if self._position >= len(self._chunks):
            raise RuntimeError("Entropy fixture exhausted")
        chunk = self._chunks[self._position]
        if len(chunk) != count:
            raise ValueError("Unexpected entropy request size")
        self._position += 1
        return chunk


