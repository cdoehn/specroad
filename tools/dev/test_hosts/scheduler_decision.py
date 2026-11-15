"""Transient forecast reuse; no IO, authority cache or cross-event state."""


class _SchedulingDecision:
    """Reuse estimates only during one controller-thread dispatch decision."""

    def __init__(self, scheduler):
        self.scheduler = scheduler
        self.delays, self.durations, self.speeds = {}, {}, {}

    def available(self, node):
        if node not in self.delays:
            self.delays[node] = self.scheduler.available(node)
        return self.delays[node]

    def duration(self, node, index):
        key = (node, index)
        if key not in self.durations:
            self.durations[key] = self.scheduler.duration(node, index)
        return self.durations[key]

    def speed(self, node):
        if node not in self.speeds:
            self.speeds[node] = self.scheduler.speed(node)
        return self.speeds[node]

    def assigned(self, node):
        # A new reservation changes this worker's delay immediately. Host
        # scales and measured durations cannot change within this decision.
        self.delays.pop(node, None)
