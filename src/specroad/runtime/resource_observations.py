"""Optional, qualified resource observations, separate from required prerequisites."""
from .limits import current_limits


def resource_observations():
    """Observe current limits without inferring host capacity or write authority."""
    # A process address-space ceiling is not available RAM or an allocation promise.
    limits = current_limits()
    memory = limits['process_address_space_bytes']['soft']
    known_memory = memory['state'] == 'known'
    observations = {
        'cpu_capacity': {'value': None, 'unit': 'cores', 'source': 'not_observed',
                         'state': 'unknown', 'scope': 'current_process_allocation'},
        'memory_limit': {'value': memory['value'] if known_memory else None, 'unit': 'bytes',
                         'source': 'getrlimit.RLIMIT_AS' if known_memory else 'not_observed',
                         'state': 'observed' if known_memory else 'unknown',
                         'scope': 'process_address_space_ceiling'},
        'storage_capacity': {'value': None, 'unit': 'bytes', 'source': 'not_observed',
                             'state': 'unknown', 'scope': 'current_process_storage_quota'}}
    return observations
