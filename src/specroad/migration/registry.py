"""Pure graph admission/resolution and explicit in-memory transformation.

Construct registries only in trusted Core code. No project representation is
deserialized into functions. Resolving a path never invokes a provider.
"""
from collections import deque
from dataclasses import dataclass
import json
from types import MappingProxyType

from .contracts import (DataContract, MigrationError, MigrationStep, ResolvedStep,
                        _encoded, _version)


def _topological(nodes, edges):
    degree = dict.fromkeys(nodes, 0)
    for rows in edges.values():
        for row in rows:
            degree[row.target] += 1
    pending = deque(node for node in nodes if degree[node] == 0)
    ordered = []
    while pending:
        node = pending.popleft()
        ordered.append(node)
        for row in edges[node]:
            degree[row.target] -= 1
            if degree[row.target] == 0:
                pending.append(row.target)
    if len(ordered) != len(nodes):
        raise MigrationError('cycle')
    return tuple(ordered)


def _forward_order(step):
    source, target = step.source, step.target
    first, last = _version(source.schema_version), _version(target.schema_version)
    a, b = source.specification_version, target.specification_version
    if last < first or (a is not None and b is not None and _version(b) < _version(a)):
        raise MigrationError('backward_as_forward', step_id=step.step_id)
    if first == last and (a is None or b is None or _version(a) >= _version(b)):
        raise MigrationError('unordered_contracts', step_id=step.step_id)


def _paths(source, target, edges, order):
    """Return at most two concrete DAG paths; no unbounded recursion."""
    found = []
    pending = [(source, ())]
    while pending and len(found) < 2:
        node, path = pending.pop()
        if node == target:
            found.append(path)
        else:
            pending.extend((edge.target, (*path, edge)) for edge in edges[node])
    if len(found) > 1:
        raise MigrationError('ambiguous_path')
    return found[0] if found else None


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
        if _paths(target, source, self._forward, self._order) is not None:
            raise MigrationError('reverse_not_implemented')
        raise MigrationError('unsupported_path')


def execute_step(resolved, value):
    """Invoke one trusted implementation on detached JSON values; never publish."""
    if type(resolved) is not ResolvedStep:
        raise MigrationError('invalid_step')
    program = resolved.transformation
    before = _encoded(value)
    phase = 'precondition'
    try:
        if program.precondition(json.loads(before)) is not True:
            raise MigrationError('precondition_failed', step_id=resolved.step.step_id)
        phase = 'transformation'
        after = _encoded(program.transform(json.loads(before)))
        phase = 'postcondition'
        if program.postcondition(json.loads(before), json.loads(after)) is not True:
            raise MigrationError('postcondition_failed', step_id=resolved.step.step_id)
    except MigrationError:
        raise
    except Exception as error:
        raise MigrationError(phase + '_failed', step_id=resolved.step.step_id) from error
    return json.loads(after)


def verify_vectors(registry):
    """Explicit behavior verification, used by Apply tests; never during admission."""
    if type(registry) is not MigrationRegistry:
        raise MigrationError('invalid_registry')
    for step in registry.steps:
        for reverse in (False, True) if step.backward is not None else (False,):
            edge = ResolvedStep(step, reverse)
            for vector in edge.transformation.vectors:
                actual = execute_step(edge, vector.before)
                if _encoded(actual) != vector._after:
                    raise MigrationError('vector_mismatch', step_id=step.step_id)
                if reverse:
                    restored = execute_step(ResolvedStep(step), actual)
                    if _encoded(restored) != vector._before:
                        raise MigrationError('reverse_not_lossless', step_id=step.step_id)
    return None


def builtin_registry():
    """No supported migration path until real source contracts/providers exist.

    Test registries cannot modify this fixed Core entrypoint. Current native
    0.2 loading remains independent; this does not register a 0.1 reader.
    """
    return MigrationRegistry((), ())
