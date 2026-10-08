"""Declared Annex O.1 work targets for diagnostics; never host quota promises.

The budget resolver/engine is a later implementation step. This projection does
not enforce a deadline, reject large work or claim a resumable work engine.
"""

_TARGETS = (
    ('cpu', 'ms', 30000, 120000),
    ('wall', 'ms', 60000, 300000),
    ('memory', 'bytes', 256 * 1024**2, 1024 * 1024**2),
    ('scratch', 'bytes', 512 * 1024**2, 4096 * 1024**2),
    ('graph', 'steps', 2000000, 10000000),
    ('relationship_paths', 'paths', 4096, 16384),
    ('inline_stdout', 'bytes', 16777216, 67108864),
    ('persistent_cache_read', 'bytes', 32 * 1024**2, 128 * 1024**2),
    ('io_transfer', 'bytes', 65536, 65536),
    ('step_cpu', 'ms', 5000, 30000),
    ('step_wall', 'ms', 10000, 60000),
)


def profile_targets(profile, *, source):
    if profile not in ('constrained', 'standard') or source not in ('default', 'cli'):
        raise ValueError('A declared profile and current selection origin are required')
    return {'policy_version': 'runtime-budget-v2', 'profile': profile, 'profile_source': source,
            'scope': 'declared_soft_work_targets', 'budget_engine_available': False,
            'effective_budgets': {name: {'value': small if profile == 'constrained' else large,
                'unit': unit, 'origin': 'profile:' + profile, 'limit_class': 'soft_work_target'}
                for name, unit, small, large in _TARGETS}}
