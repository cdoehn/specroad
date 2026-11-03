"""Private configurable storage limit, independent of hash-bound development settings."""
from decimal import Decimal, ROUND_CEILING
import math
from specroad_control.toml_compat import tomllib
from .errors import ControlError
from .local import read_private, write_private

GB = 1_000_000_000


def limits_path(paths):
    return paths.config.with_suffix('.limits.toml')

def minimum_bytes(value):
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= 1_000_000:
        raise ValueError('A finite positive GB limit of at most 1000000 is required.')
    return int((Decimal(str(value)) * GB).to_integral_value(rounding=ROUND_CEILING))

def read_limits(paths):
    path = limits_path(paths)
    configured = True
    try:
        doc = tomllib.loads(read_private(path).decode())
    except FileNotFoundError:
        configured = False
        doc = {'format_version': 1, 'min_free_gb': 10}
    except (ValueError, UnicodeError):
        raise ControlError('invalid_disk_limits', 'The external storage limit is invalid; no work is authorized.') from None
    try:
        if set(doc) != {'format_version', 'min_free_gb'} or type(doc['format_version']) is not int or doc['format_version'] != 1:
            raise ValueError
        threshold = minimum_bytes(doc['min_free_gb'])
    except (ValueError, TypeError, KeyError, OverflowError):
        raise ControlError('invalid_disk_limits', 'Storage limits require format_version=1 and a positive numeric min_free_gb.') from None
    return {'config_path': str(path), 'configured': configured,
            'min_free_gb': doc['min_free_gb'], 'min_free_bytes': threshold}

def set_limit(paths, value):
    from .commands import offline
    try:
        minimum_bytes(value)
    except (ValueError, TypeError, OverflowError):
        raise ControlError('invalid_disk_limits', 'Specify a finite positive GB limit, at most 1000000.') from None
    with offline(paths):
        write_private(limits_path(paths), ('format_version = 1\nmin_free_gb = ' + repr(value) + '\n').encode())
        result = read_limits(paths)
    return {**result, 'saved': True, 'service_started': False, 'model_called': False}
