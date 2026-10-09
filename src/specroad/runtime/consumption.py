"""Explicit in-process consumption; no scheduler, persistence or write authority."""
from copy import deepcopy
from dataclasses import dataclass
import json
import sys
from threading import Lock
import time

from .budget_policy import resolve_resource_policy


class ConsumptionError(ValueError):
    exit_code = 2


def _count(value):
    if type(value) is not int or value < 0:
        raise ConsumptionError('A nonnegative integer byte count is required')
    try:
        json.dumps(value)
    except ValueError as error:
        raise ConsumptionError('The byte count must be representable as JSON') from error
    return value


@dataclass(frozen=True)
class CounterSample:
    cpu_ns: int | None
    wall_ns: int | None
    rss_peak_bytes: int | None
    cpu_source: str = 'time.process_time_ns'
    wall_source: str = 'time.monotonic_ns'
    rss_source: str = 'resource.getrusage.RUSAGE_SELF.ru_maxrss:linux_kib'

    def __post_init__(self):
        for name in ('cpu_ns', 'wall_ns', 'rss_peak_bytes'):
            value = getattr(self, name)
            if value is not None:
                _count(value)
        for name in ('cpu_source', 'wall_source', 'rss_source'):
            value = getattr(self, name)
            if type(value) is not str or not value:
                raise ConsumptionError('A measurement source is required')
            value.encode('utf-8')


def _reading(reader):
    try:
        value = reader()
        return value if type(value) is int and value >= 0 else None
    except (AttributeError, ImportError, OSError, OverflowError, TypeError, ValueError):
        return None


def native_sample():
    """CPU is process-wide; Linux RSS is a lifetime peak, never free capacity."""
    cpu = _reading(time.process_time_ns)
    wall = _reading(time.monotonic_ns)
    rss = None
    if sys.platform.startswith('linux'):
        from .limits import _resource_api
        api = _resource_api()
        if api is not None:
            value = _reading(lambda: api.getrusage(api.RUSAGE_SELF).ru_maxrss)
            rss = None if value is None else value * 1024
    return CounterSample(cpu, wall, rss)


def _metric(value, unit, source, scope, *, kind='measured'):
    return {'value': value, 'unit': unit, 'source': source, 'scope': scope,
            'measurement_kind': 'unknown' if value is None else kind}


def _sum(previous, current):
    return None if previous is None or current is None else previous + current


def _peak(previous, current):
    return None if previous is None or current is None else max(previous, current)


class WorkConsumption:
    """One explicitly owned sequential work ledger, reusable across API calls.

    A fresh invocation always gets a fresh window. Cumulative counters never
    authorize, pause or refuse work. Accounted bytes are explicit registrations,
    not measurements of all Python objects or filesystem use. Outstanding owned
    byte registrations survive an invocation boundary until explicitly released.
    """
    def __init__(self, *, sampler=None):
        if sampler is not None and not callable(sampler):
            raise ConsumptionError('A trusted measurement sampler is required')
        self._sampler = native_sample if sampler is None else sampler
        self._lock = Lock()
        self._active = None
        self._calls = 0
        self._totals = {'cpu_ns': 0, 'wall_ns': 0, 'rss_peak_bytes': 0}
        self._sources = {name: None for name in self._totals}
        self._current = {'memory': 0, 'scratch': 0}
        self._peaks = dict(self._current)

    def _sample(self):
        try:
            value = self._sampler()
            if type(value) is not CounterSample:
                raise ConsumptionError('A typed counter sample is required')
            return value
        except Exception:
            # An unavailable optional observer cannot turn work into a failure.
            return CounterSample(None, None, None, 'unavailable', 'unavailable', 'unavailable')

    def begin(self, resource_options=None):
        policy = resolve_resource_policy(resource_options)
        with self._lock:
            if self._active is not None:
                raise ConsumptionError('The previous invocation is still active')
            call = InvocationConsumption(self, policy, self._sample(), dict(self._current))
            self._active = call
            return call


class InvocationConsumption:
    """One measured window; finish exactly once, including after a failed action."""
    def __init__(self, work, policy, start, peaks):
        self._work, self._policy, self._start = work, policy, start
        self._peaks = peaks

    def account_bytes(self, kind, count, *, release=False):
        count = _count(count)
        if kind not in ('memory', 'scratch') or type(release) is not bool:
            raise ConsumptionError('An explicit memory or scratch registration is required')
        work = self._work
        with work._lock:
            if work._active is not self:
                raise ConsumptionError('The invocation is no longer active')
            value = work._current[kind] + (-count if release else count)
            _count(value)
            work._current[kind] = value
            self._peaks[kind] = max(self._peaks[kind], value)

    def finish(self):
        work = self._work
        with work._lock:
            if work._active is not self:
                raise ConsumptionError('The invocation is no longer active')
            end = work._sample()
            values, sources = {}, {}
            for metric, source in (('cpu_ns', 'cpu_source'), ('wall_ns', 'wall_source'),
                                   ('rss_peak_bytes', 'rss_source')):
                before, after = getattr(self._start, metric), getattr(end, metric)
                same_source = getattr(self._start, source) == getattr(end, source)
                sources[metric] = getattr(end, source) if same_source else 'changed_measurement_source'
                values[metric] = (after if metric == 'rss_peak_bytes' else after - before) if (
                    same_source and before is not None and after is not None and after >= before) else None
                combine = _peak if metric == 'rss_peak_bytes' else _sum
                work._totals[metric] = combine(work._totals[metric], values[metric])
                previous_source = work._sources[metric]
                work._sources[metric] = sources[metric] if previous_source is None else (
                    previous_source if previous_source == sources[metric] else 'mixed_measurement_sources')
            for kind in self._peaks:
                work._peaks[kind] = max(work._peaks[kind], self._peaks[kind])
            work._calls += 1
            work._active = None
            scopes = {'cpu_ns': 'current_process_all_threads_interval',
                      'wall_ns': 'monotonic_interval', 'rss_peak_bytes': 'current_process_lifetime_peak'}

            def measured(current, *, cumulative=False):
                return {name: _metric(value, 'bytes' if name == 'rss_peak_bytes' else 'ns',
                    work._sources[name] if cumulative else sources[name], scopes[name])
                    for name, value in current.items()}

            def accounted(peaks):
                return {kind + '_peak_bytes': _metric(value, 'bytes', 'explicit_byte_registrations',
                    'registered_own_bytes_only', kind='accounted') for kind, value in peaks.items()}

            events = []
            for target, observed, factor in (
                ('cpu', values['cpu_ns'], 1000000), ('wall', values['wall_ns'], 1000000),
                ('step_cpu', values['cpu_ns'], 1000000), ('step_wall', values['wall_ns'], 1000000),
                ('memory', self._peaks['memory'], 1), ('scratch', self._peaks['scratch'], 1)):
                budget = self._policy['effective_budgets'][target]
                if observed is not None and observed > budget['value'] * factor:
                    events.append({'metric': target, 'target': budget['value'], 'target_unit': budget['unit'],
                                   'observed': observed, 'observed_unit': 'ns' if factor > 1 else 'bytes'})
            return {'format_version': 'runtime-consumption-v1', 'policy_version': self._policy['policy_version'],
                    'profile': self._policy['profile'], 'effective_budgets': deepcopy(self._policy['effective_budgets']),
                    'invocations_recorded': work._calls,
                    'invocation': {'measured': measured(values), 'accounted': accounted(self._peaks)},
                    'cumulative': {'measured': measured(work._totals, cumulative=True),
                                   'accounted': accounted(work._peaks)},
                    'soft_budget_exceeded': bool(events), 'events': events,
                    'observation_scope': 'explicit_in_process_invocations',
                    'includes_child_processes': False, 'host_capacity_known': False,
                    'persistent_work_available': False, 'checkpoint': None}
