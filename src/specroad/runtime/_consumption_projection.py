"""Owned operational metric documents, separate from native sampling and results."""
from types import MappingProxyType

_SCOPES = MappingProxyType({
    'cpu_ns': 'current_process_all_threads_interval',
    'wall_ns': 'monotonic_interval',
    'rss_peak_bytes': 'current_process_lifetime_peak',
})


def _metric(value, unit, source, scope, *, kind='measured'):
    return {'value': value, 'unit': unit, 'source': source, 'scope': scope,
            'measurement_kind': 'unknown' if value is None else kind}


def measured_metrics(current, sources):
    return {name: _metric(value, 'bytes' if name == 'rss_peak_bytes' else 'ns',
                         sources[name], _SCOPES[name]) for name, value in current.items()}


def accounted_metrics(peaks):
    return {kind + '_peak_bytes': _metric(value, 'bytes', 'explicit_byte_registrations',
            'registered_own_bytes_only', kind='accounted') for kind, value in peaks.items()}
