"""Pure runtime-budget-v2 resolution, separate from semantic request identity.

This selects declared work targets and classifies explicitly supplied constraints.
It neither measures consumption nor grants capacity, write authority or resume.
"""
from collections.abc import Mapping
import json
import re

from ._budget_values import RuntimeResourceOptions, SemanticResourceConstraints


_OVERRIDES = {
    '--cpu-budget-ms': ('cpu', 1),
    '--wall-budget-ms': ('wall', 1),
    '--memory-budget-mib': ('memory', 1024**2),
    '--scratch-budget-mib': ('scratch', 1024**2),
    '--step-cpu-ms': ('step_cpu', 1),
    '--step-wall-ms': ('step_wall', 1),
}
RESOURCE_OPTIONS = frozenset(('--resource-profile', *_OVERRIDES))
_SCOPE_LIMITS = frozenset(('query_default_limit', 'trace_depth'))


class ResourcePolicyError(ValueError):
    exit_code = 2


def _positive(value):
    if type(value) is str and re.fullmatch(r'[0-9]+', value):
        try:
            value = int(value)
        except ValueError as error:
            raise ResourcePolicyError('Positive integer work target required') from error
    if type(value) is not int or value <= 0:
        raise ResourcePolicyError('Positive integer work target required')
    return value


def _classes(resource_limits, scope_descriptor, observations):
    from ..model.semantic_configuration import SOFT_LIMITS, SEMANTIC_LIMITS
    groups = {name: {} for name in ('soft_work_target', 'semantic_scope',
                                  'hard_safety_or_format', 'observed_host_limit')}
    limits = {} if resource_limits is None else resource_limits
    if not isinstance(limits, Mapping):
        raise ResourcePolicyError('Explicit resource-limit mapping required')
    for name, value in limits.items():
        if type(name) is not str or name not in SOFT_LIMITS | SEMANTIC_LIMITS:
            raise ResourcePolicyError('Unclassified resource limit')
        kind = ('soft_work_target' if name in SOFT_LIMITS else
                'semantic_scope' if name in _SCOPE_LIMITS else 'hard_safety_or_format')
        if type(value) is not int or value < (0 if kind == 'semantic_scope' else 1):
            raise ResourcePolicyError('Invalid declared resource limit')
        groups[kind][name] = {'value': value, 'origin': 'project:resource_limits/' + name}
    if scope_descriptor is not None:
        from ..graph.scope_descriptors import ScopeDescriptor
        if type(scope_descriptor) is not ScopeDescriptor:
            raise ResourcePolicyError('Validated scope descriptor required')
        groups['semantic_scope']['scope_descriptor'] = {
            'value': scope_descriptor.data, 'origin': 'request', 'sha256': scope_descriptor.sha256}
    observed = {} if observations is None else observations
    if not isinstance(observed, Mapping):
        raise ResourcePolicyError('Explicit host observations required')
    for name, item in observed.items():
        if (name not in ('cpu_capacity', 'memory_limit', 'storage_capacity')
                or not isinstance(item, Mapping)
                or set(item) != {'value', 'unit', 'source', 'state', 'scope'}
                or any(type(item[k]) is not str or not item[k] for k in ('unit', 'source', 'scope'))
                or item['state'] not in ('observed', 'unknown')
                or (item['state'] == 'unknown' and item['value'] is not None)
                or (item['state'] == 'observed' and
                    (type(item['value']) is not int or item['value'] < 0))):
            raise ResourcePolicyError('Qualified host observation required')
        groups['observed_host_limit'][name] = dict(item)
    return (groups['soft_work_target'],
            SemanticResourceConstraints(groups['semantic_scope'], groups['hard_safety_or_format']),
            groups['observed_host_limit'])


def _runtime_options(options):
    options = {} if options is None else options
    if not isinstance(options, Mapping) or set(options) - RESOURCE_OPTIONS:
        raise ResourcePolicyError('Only declared runtime resource options are accepted')
    profile = options.get('--resource-profile', 'constrained')
    if type(profile) is not str or profile not in ('constrained', 'standard'):
        raise ResourcePolicyError('Unknown runtime resource profile')
    source = 'cli' if '--resource-profile' in options else 'default'
    overrides = []
    for flag, (metric, factor) in _OVERRIDES.items():
        if flag in options:
            overrides.append((metric, _positive(options[flag]) * factor, 'cli:' + flag))
    return RuntimeResourceOptions(profile, source, tuple(overrides))


def resolve_resource_policy(options=None, *, resource_limits=None,
                            scope_descriptor=None, observations=None):
    """Resolve owned values without changing the supplied scope or configuration.

    CLI values are decimal strings; embedded callers may supply positive ints.
    Only the six declared soft targets are overridable. A step window is never
    clamped to its parent target. Supplied host observations remain independent.
    """
    result = _runtime_options(options).report()
    soft_targets, semantic, observed_hosts = _classes(resource_limits, scope_descriptor, observations)
    # The existing explicit SRX graph target takes precedence over a profile default.
    if 'srx_graph_steps' in soft_targets:
        result['effective_budgets']['graph'].update(soft_targets['srx_graph_steps'])
    result['classified_limits'] = {'soft_work_target': soft_targets, **semantic.classes(),
                                   'observed_host_limit': observed_hosts}
    try:
        # Unit conversion must still produce a representable machine report.
        # This checks the active JSON encoder, not a maximum work/host budget.
        json.dumps(result, ensure_ascii=False, allow_nan=False).encode('utf-8')
    except (ValueError, OverflowError) as error:
        raise ResourcePolicyError('Resource policy cannot be represented as JSON') from error
    return result
