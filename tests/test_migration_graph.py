"""16.a positive kernel contracts; no product 0.1 or migration CLI claim."""
from dataclasses import FrozenInstanceError, replace

import pytest

from specroad.migration import (MigrationError, MigrationRegistry, ResolvedStep,
                                TestVector as Vector, builtin_registry, execute_step, verify_vectors)
from support.migration import chain, contract, identity_step
from support.read_only import no_write_attempts


def test_multiple_real_transformations_match_independent_vectors_and_return():
    registry, data = chain()
    a, b, c = registry.contracts
    with no_write_attempts():
        path = registry.resolve(a, c)
        assert [(edge.source, edge.target, edge.reverse) for edge in path] == [(a, b, False), (b, c, False)]
        reverse = registry.resolve(c, a)
        assert [(edge.source, edge.target, edge.reverse) for edge in reverse] == [(c, b, True), (b, a, True)]
        verify_vectors(registry)
        for row in data['vectors']:
            intermediate = execute_step(path[0], row['a'])
            assert intermediate == row['b']
            result = execute_step(path[1], intermediate)
            assert result == row['c']
            assert execute_step(reverse[1], execute_step(reverse[0], result)) == row['a']
    assert data['vectors'][0]['a'] == {'id': 'one', 'label': 'café', 'tags': ['é', 'a']}


def test_admission_and_resolution_never_invoke_any_provider():
    registry, _ = chain()
    def forbidden(*args):
        pytest.fail('graph resolution invoked an implementation')
    steps = [replace(step, forward=replace(step.forward, precondition=forbidden, transform=forbidden,
                                          postcondition=forbidden),
                     backward=replace(step.backward, precondition=forbidden, transform=forbidden,
                                      postcondition=forbidden)) for step in registry.steps]
    with no_write_attempts():
        graph = MigrationRegistry(registry.contracts, steps)
        assert len(graph.resolve(graph.contracts[0], graph.contracts[-1])) == 2
        assert len(graph.resolve(graph.contracts[-1], graph.contracts[0])) == 2
    assert tuple(steps) == graph.steps


@pytest.mark.parametrize('side', ['source', 'target', 'both'])
def test_unknown_contracts_are_not_noops(side):
    registry, _ = chain()
    a, _, c = registry.contracts
    unknown = contract('99.0.0')
    with pytest.raises(MigrationError) as caught:
        registry.resolve(unknown if side != 'target' else a, unknown if side != 'source' else c)
    assert caught.value.reason == ('unknown_target' if side == 'target' else 'unknown_source')
    assert registry.resolve(a, a) == ()


def test_known_but_disconnected_contract_is_unsupported():
    registry, _ = chain()
    unknown = contract('99.0.0')
    graph = MigrationRegistry((*registry.contracts, unknown), registry.steps)
    with pytest.raises(MigrationError) as caught:
        graph.resolve(graph.contracts[0], unknown)
    assert caught.value.reason == 'unsupported_path'


def test_equal_schema_label_with_different_provenance_needs_an_actual_step():
    a = contract('90.0.0', specification='1.0.0')
    b = contract('90.0.0', specification='1.0.1')
    graph = MigrationRegistry((a, b), ())
    with pytest.raises(MigrationError) as caught:
        graph.resolve(a, b)
    assert caught.value.reason == 'unsupported_path'
    step = identity_step(a, b)
    assert MigrationRegistry((a, b), (step,)).resolve(a, b) == (ResolvedStep(step),)


def test_required_inverse_is_explicit_for_every_edge():
    registry, _ = chain()
    forward_only = replace(registry.steps[0], reversible=False, backward=None)
    graph = MigrationRegistry(registry.contracts, (forward_only, registry.steps[1]))
    assert len(graph.resolve(graph.contracts[0], graph.contracts[-1])) == 2
    with pytest.raises(MigrationError) as caught:
        graph.resolve(graph.contracts[-1], graph.contracts[0])
    assert caught.value.reason == 'reverse_not_implemented'


def test_vector_and_registry_inputs_cannot_be_mutated_after_admission():
    value = {'tags': ['a']}
    vector = Vector('detached', value, value)
    value['tags'].clear()
    vector.before['tags'].append('b')
    assert vector.before == vector.after == {'tags': ['a']}
    registry, _ = chain()
    nodes, steps = list(registry.contracts), list(registry.steps)
    graph = MigrationRegistry(nodes, steps)
    nodes.clear(); steps.clear()
    assert len(graph.resolve(graph.contracts[0], graph.contracts[-1])) == 2
    with pytest.raises(FrozenInstanceError):
        graph.contracts = ()


@pytest.mark.parametrize('direction', ['forward', 'reverse'])
def test_real_preconditions_prevent_field_loss_and_invalid_derived_values(direction):
    registry, data = chain()
    if direction == 'forward':
        edge, value = registry.resolve(*registry.contracts[::2])[0], {**data['vectors'][0]['a'], 'extra': 1}
    else:
        edge, value = registry.resolve(registry.contracts[2], registry.contracts[1])[0], {**data['vectors'][0]['c'], 'title_length': 99}
    original = value.copy()
    with pytest.raises(MigrationError) as caught:
        execute_step(edge, value)
    assert caught.value.reason == 'precondition_failed'
    assert value == original


def test_synthetic_registry_never_advertises_a_product_legacy_path():
    registry, _ = chain()
    verify_vectors(registry)
    product = builtin_registry()
    assert product.contracts == product.steps == ()
    with pytest.raises(MigrationError) as caught:
        product.resolve(contract('0.1.0'), contract('0.2.0'))
    assert caught.value.reason == 'unknown_source'
