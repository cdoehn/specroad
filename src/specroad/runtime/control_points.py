"""Pure bounded progress signals; no clocks, callbacks or scheduling authority."""
from dataclasses import dataclass
import json
from types import MappingProxyType

INTERVALS = MappingProxyType({'graph_steps': 128, 'srx_steps': 512, 'payload_bytes': 65536})
PHASES = frozenset(('srx_validation', 'srx_evaluation', 'srx_result', 'graph_views', 'graph_load',
                    'payload_hash', 'publication', 'spool_unit'))


@dataclass(frozen=True)
class ControlPoint:
    metric: str
    completed: int

    def __post_init__(self):
        if (type(self.metric) is not str or self.metric not in INTERVALS or type(self.completed) is not int
                or self.completed < 1 or self.completed % INTERVALS[self.metric]):
            raise ValueError('A complete control interval is required')
        json.dumps(self.completed)


@dataclass(frozen=True)
class PhaseBoundary:
    phase: str
    edge: str

    def __post_init__(self):
        if (type(self.phase) is not str or self.phase not in PHASES
                or type(self.edge) is not str or self.edge not in ('start', 'end')):
            raise ValueError('A known phase boundary is required')


class ControlIntervals:
    """Counts actual units inside one pure operation, independent of budgets."""
    def __init__(self):
        self._counts = {name: 0 for name in INTERVALS}

    def remaining(self, metric):
        return INTERVALS[metric] - self._counts[metric] % INTERVALS[metric]

    def advance(self, metric, count=1):
        if type(metric) is not str or metric not in INTERVALS or type(count) is not int or not 0 <= count <= self.remaining(metric):
            raise ValueError('A control boundary must not be skipped')
        self._counts[metric] += count
        if count and self._counts[metric] % INTERVALS[metric] == 0:
            return ControlPoint(metric, self._counts[metric])
        return None


def complete_steps(steps):
    """Drain the same pure computation without observing operational signals."""
    while True:
        try:
            next(steps)
        except StopIteration as completed:
            return completed.value
