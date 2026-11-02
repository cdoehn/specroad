"""Graph/contract failure boundaries; all providers are explicit test code."""
from dataclasses import replace
from itertools import permutations

import pytest

from specroad.migration import (DataContract, MigrationError, MigrationRegistry, ResolvedStep,
                                TestVector as Vector, execute_step, verify_vectors)
from support.migration import chain, contract, identity_step
from support.read_only import no_write_attempts


def refusal(reason, function, *args, **kwargs):
    with pytest.raises(MigrationError) as caught:
        function(*args, **kwargs)
    assert caught.value.reason == reason
    return caught.value


@pytest.mark.parametrize('kind', ['self', 'long', 'disconnected'])
def test_all_forward_cycles_are_rejected_before_publication(kind):
    nodes = [contract('90.' + str(i) + '.0') for i in range(4)]
    pairs = [(0, 0)] if kind == 'self' else [(0, 1), (1, 2), (2, 0)] if kind == 'long' else [(1, 2), (2, 3), (3, 1)]
    steps = [identity_step(nodes[a], nodes[b], 'edge-' + str(i) + '.v1') for i, (a, b) in enumerate(pairs)]
    for ordered in permutations(steps):
        refusal('cycle', MigrationRegistry, nodes, ordered)
    assert len(MigrationRegistry(nodes, ()).contracts) == 4


@pytest.mark.parametrize('kind,reason', [('node', 'duplicate_contract'), ('step', 'duplicate_step'),
    ('edge', 'duplicate_edge'), ('endpoint', 'unknown_endpoint'), ('placeholder', 'invalid_step')])
def test_entire_registry_rejects_conflicts_and_placeholders(kind, reason):
    a, b, c = [contract('90.' + str(i) + '.0') for i in range(3)]
    nodes, steps = [a, b], [identity_step(a, b)]
    if kind == 'node': nodes.append(a)
    elif kind == 'step': steps.append(steps[0])
    elif kind == 'edge': steps.append(replace(steps[0], step_id='duplicate.v1'))
    elif kind == 'endpoint': steps.append(identity_step(b, c, 'next.v1'))
    else: steps.append({'source': b, 'target': c, 'transform': 'arbitrary.module'})
    refusal(reason, MigrationRegistry, nodes, steps)
    assert len(steps) == (1 if kind == 'node' else 2)


@pytest.mark.parametrize('length', ['equal', 'unequal'])
@pytest.mark.parametrize('reverse', [False, True])
def test_all_multiple_paths_are_ambiguous_regardless_of_order_or_length(length, reverse):
    nodes = [contract('90.' + str(i) + '.0') for i in range(4)]
    pairs = [(0, 1), (1, 3), (0, 2), (2, 3)] if length == 'equal' else [(0, 1), (1, 3), (0, 3)]
    steps = [identity_step(nodes[a], nodes[b], 'edge-' + str(i) + '.v1', reversible=True)
             for i, (a, b) in enumerate(pairs)]
    for ordered in permutations(steps):
        graph = MigrationRegistry(nodes, ordered)
        first, last = (nodes[3], nodes[0]) if reverse else (nodes[0], nodes[3])
        refusal('ambiguous_path', graph.resolve, first, last)


def test_many_ambiguous_dead_ends_do_not_hide_a_unique_target_path():
    # Fibonacci-like dead-end paths must be counted, not enumerated. No timing oracle.
    nodes = [contract('90.' + str(i) + '.0') for i in range(160)]
    target = contract('91.0.0')
    steps = [identity_step(nodes[i], nodes[j], f'edge-{i}-{j}.v1')
             for i in range(len(nodes)) for j in (i + 1, i + 2) if j < len(nodes)]
    direct = identity_step(nodes[0], target, 'only.v1')
    graph = MigrationRegistry((*nodes, target), (*steps, direct))
    with no_write_attempts():
        assert graph.resolve(nodes[0], target) == (ResolvedStep(direct),)
        refusal('ambiguous_path', graph.resolve, nodes[0], nodes[-1])


def test_long_unique_chain_avoids_recursion_and_preserves_all_step_order():
    nodes = [contract('90.' + str(i) + '.0') for i in range(1200)]
    steps = [identity_step(a, b, f'edge-{i}.v1', reversible=True)
             for i, (a, b) in enumerate(zip(nodes, nodes[1:]))]
    graph = MigrationRegistry(nodes, reversed(steps))
    assert [edge.step for edge in graph.resolve(nodes[0], nodes[-1])] == steps
    assert [edge.step for edge in graph.resolve(nodes[-1], nodes[0])] == list(reversed(steps))


def test_unavailable_inverse_is_not_confused_with_forward_ambiguity():
    a, b, c = [contract('90.' + str(i) + '.0') for i in range(3)]
    steps = [identity_step(a, b), identity_step(b, c, 'second.v1'), identity_step(a, c, 'direct.v1')]
    graph = MigrationRegistry((a, b, c), steps)
    refusal('reverse_not_implemented', graph.resolve, c, a)
    refusal('ambiguous_path', graph.resolve, a, c)


def test_mixed_forward_reverse_route_is_not_a_missing_reverse_fallback():
    a, b, c = [contract('90.' + str(i) + '.0') for i in range(3)]
    graph = MigrationRegistry((a, b, c), (identity_step(a, b), identity_step(a, c, 'branch.v1', reversible=True)))
    refusal('unsupported_path', graph.resolve, c, b)


@pytest.mark.parametrize('field', ['precondition', 'transform', 'postcondition', 'vectors', 'lossless'])
def test_complete_executable_step_contract_is_mandatory(field):
    registry, _ = chain()
    value = () if field == 'vectors' else 'external.module:function'
    refusal('incomplete_transformation', replace, registry.steps[0].forward, **{field: value})


@pytest.mark.parametrize('kind,reason', [('duplicate', 'duplicate_vector'), ('conflict', 'vector_conflict')])
def test_contradictory_or_duplicate_vectors_are_not_admissible(kind, reason):
    registry, _ = chain()
    vector = registry.steps[0].forward.vectors[0]
    other = Vector(vector.name if kind == 'duplicate' else 'different', vector.before, {'wrong': True})
    refusal(reason, replace, registry.steps[0].forward, vectors=(vector, other))


@pytest.mark.parametrize('kind,reason', [('flag', 'reverse_not_implemented'), ('hidden', 'reversibility_conflict'),
    ('lossy', 'reverse_not_lossless'), ('unversioned', 'unversioned_step')])
def test_reversibility_and_step_version_are_explicit(kind, reason):
    registry, _ = chain()
    step = registry.steps[0]
    changes = {'flag': {'backward': None}, 'hidden': {'reversible': False},
               'lossy': {'backward': replace(step.backward, lossless=False)},
               'unversioned': {'step_id': 'rename'}}[kind]
    refusal(reason, replace, step, **changes)


@pytest.mark.parametrize('version', ['90', '090.0.0', '90.0.0-01', '90.0.0-', '90.0.0+'])
def test_contract_versions_must_be_valid_semver(version):
    refusal('invalid_version', contract, version)


@pytest.mark.parametrize('digest', ['', 'a' * 63, 'A' * 64, None])
def test_open_or_malformed_contract_binding_is_not_admitted(digest):
    refusal('invalid_contract_binding', DataContract, '90.0.0', digest)


@pytest.mark.parametrize('first,last', [('90.2.0', '90.10.0'), ('90.0.0-2', '90.0.0-10'),
    ('90.0.0-alpha.9', '90.0.0-alpha.10'), ('90.0.0-1', '90.0.0-alpha'), ('90.0.0-rc.1', '90.0.0')])
def test_semver_forward_order_is_numeric_and_prerelease_aware(first, last):
    a, b = contract(first), contract(last)
    step = identity_step(a, b)
    assert len(MigrationRegistry((a, b), (step,)).resolve(a, b)) == 1
    refusal('backward_as_forward', MigrationRegistry, (a, b), (identity_step(b, a),))


@pytest.mark.parametrize('kind,reason', [('relabel', 'unordered_contracts'), ('build', 'unordered_contracts'),
    ('older-draft', 'backward_as_forward'), ('equal-origin', 'unordered_contracts')])
def test_relabels_and_old_drafts_cannot_be_advertised_as_forward(kind, reason):
    a = contract('90.0.0', specification='1.0.1')
    if kind == 'relabel': b = replace(a, contract_sha256='a' * 64, specification_version=None)
    elif kind == 'build': b = contract('90.0.0+new', specification='1.0.1')
    elif kind == 'older-draft': b = contract('90.1.0', specification='1.0.0')
    else: b = replace(a, contract_sha256='b' * 64)
    refusal(reason, MigrationRegistry, (a, b), (identity_step(a, b),))


@pytest.mark.parametrize('phase', ['precondition', 'transformation', 'postcondition'])
def test_provider_exceptions_are_typed_and_original_data_is_detached(phase):
    registry, data = chain()
    step = registry.steps[0]
    def broken(*values):
        values[0].clear()
        raise RuntimeError('test failure')
    field = 'transform' if phase == 'transformation' else phase
    step = replace(step, forward=replace(step.forward, **{field: broken}))
    row = data['vectors'][0]
    original = row['a'].copy()
    error = refusal(phase + '_failed', execute_step, ResolvedStep(step), row['a'])
    assert error.step_id == 'rename.v1' and row['a'] == original


@pytest.mark.parametrize('kind,reason', [('postcondition', 'postcondition_failed'), ('nonjson', 'invalid_value'),
    ('truthy', 'precondition_failed'), ('vector', 'vector_mismatch')])
def test_declared_but_incorrect_transformations_cannot_pass_vectors(kind, reason):
    registry, _ = chain()
    step = registry.steps[0]
    if kind == 'postcondition': program = replace(step.forward, transform=lambda value: {'wrong': True})
    elif kind == 'nonjson': program = replace(step.forward, transform=lambda value: {'bad': object()})
    elif kind == 'truthy': program = replace(step.forward, precondition=lambda value: 1)
    else:
        vector = step.forward.vectors[0]
        program = replace(step.forward, vectors=(Vector('wrong', vector.before, {'wrong': True}),))
    graph = MigrationRegistry(registry.contracts, (replace(step, forward=program), registry.steps[1]))
    refusal(reason, verify_vectors, graph)


def test_claimed_lossless_reverse_must_restore_each_forward_vector_too():
    registry, _ = chain()
    step = registry.steps[0]
    original = step.backward.transform
    def lossy(value):
        result = original(value)
        if result['label'] == '': result['id'] = 'lost'
        return result
    # Reverse's own nonempty vectors pass, but the forward empty vector catches the lie.
    backward = replace(step.backward, transform=lossy, postcondition=lambda a, b: True,
                       vectors=(step.backward.vectors[0],))
    graph = MigrationRegistry(registry.contracts, (replace(step, backward=backward), registry.steps[1]))
    refusal('reverse_not_lossless', verify_vectors, graph)


def test_admission_failure_does_not_change_an_already_published_registry():
    original, _ = chain()
    retained = original.resolve(original.contracts[0], original.contracts[-1])
    refusal('duplicate_step', MigrationRegistry, original.contracts, (*original.steps, original.steps[-1]))
    assert original.resolve(original.contracts[0], original.contracts[-1]) == retained
    verify_vectors(original)
