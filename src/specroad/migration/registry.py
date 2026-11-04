"""Atomic trusted registry admission and pure path resolution.

Construct registries only in trusted Core code. No project representation is
deserialized into functions. Resolving a path never invokes a provider.
"""
from dataclasses import dataclass
from types import MappingProxyType

from .contracts import (DataContract, MigrationError, MigrationStep, ResolvedStep,
                        _version)
from ._paths import _topological, _paths, _reachable


def _forward_order(step):
    source, target = step.source, step.target
    first, last = _version(source.schema_version), _version(target.schema_version)
    a, b = source.specification_version, target.specification_version
    if last < first or (a is not None and b is not None and _version(b) < _version(a)):
        raise MigrationError('backward_as_forward', step_id=step.step_id)
    if first == last and (a is None or b is None or _version(a) >= _version(b)):
        raise MigrationError('unordered_contracts', step_id=step.step_id)


@dataclass(frozen=True, init=False)
class MigrationRegistry:
    contracts: tuple[DataContract, ...]
    steps: tuple[MigrationStep, ...]
    _forward: object
    _backward: object
    _order: tuple

    def __init__(self, contracts, steps):
        contracts, steps = tuple(contracts), tuple(steps)
        if any(type(c) is not DataContract for c in contracts):
            raise MigrationError('invalid_contract')
        if len(set(contracts)) != len(contracts):
            raise MigrationError('duplicate_contract')
        forward, backward = {c: [] for c in contracts}, {c: [] for c in contracts}
        identities, endpoints = set(), set()
        for step in steps:
            if type(step) is not MigrationStep:
                raise MigrationError('invalid_step')
            if step.source not in forward or step.target not in forward:
                raise MigrationError('unknown_endpoint', step_id=step.step_id)
            if step.step_id in identities:
                raise MigrationError('duplicate_step', step_id=step.step_id)
            if (step.source, step.target) in endpoints:
                raise MigrationError('duplicate_edge', step_id=step.step_id)
            identities.add(step.step_id)
            endpoints.add((step.source, step.target))
            forward[step.source].append(ResolvedStep(step))
            if step.backward is not None:
                backward[step.target].append(ResolvedStep(step, True))
        order = _topological(contracts, forward)  # Every component, not only one request.
        for step in steps:
            _forward_order(step)
        # Publish only after complete admission; retain no caller-owned containers.
        object.__setattr__(self, 'contracts', contracts)
        object.__setattr__(self, 'steps', steps)
        object.__setattr__(self, '_order', order)
        for name, edges in (('_forward', forward), ('_backward', backward)):
            object.__setattr__(self, name, MappingProxyType({c: tuple(rows) for c, rows in edges.items()}))

    def resolve(self, source, target):
        if type(source) is not DataContract or source not in self._forward:
            raise MigrationError('unknown_source')
        if type(target) is not DataContract or target not in self._forward:
            raise MigrationError('unknown_target')
        if source == target:
            return ()
        path = _paths(source, target, self._forward, self._order)
        if path is not None:
            return path
        path = _paths(source, target, self._backward, tuple(reversed(self._order)))
        if path is not None:
            return path
        if _reachable(target, source, self._forward):
            raise MigrationError('reverse_not_implemented')
        raise MigrationError('unsupported_path')


def builtin_registry():
    """Only the newly defined, frozen reference contract is registered."""
    from .builtin_path import registered_step
    step = registered_step()
    return MigrationRegistry((step.source, step.target), (step,))
