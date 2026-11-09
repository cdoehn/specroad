"""Boundary, repeated-edit and adversarial complete-plan cases for ordered changes."""
from copy import deepcopy

import pytest

from specroad.changes import prepare_change_plan
from specroad.model.errors import ModelError
from specroad.model.identity_tokens import encode128
from specroad.proposals import ProposalChanges, prepare_proposal
from support.read_only import no_write_attempts
from test_proposal_changes import sequence, plan, create, names, explanation
from test_proposal_data import inputs


@pytest.mark.parametrize('position', [-1, 3, True, False, 0.0, 1.5, '1', [], {}])
def test_invalid_add_positions_fail_without_entropy_or_source_changes(position, monkeypatch):
    proposal, source = sequence()
    def forbidden(size):
        raise AssertionError('No identity allocation for an invalid position')
    monkeypatch.setattr('secrets.token_bytes', forbidden)
    with no_write_attempts(), pytest.raises(ModelError) as error:
        source.add(plan([create(v) for v in 'ABC']), position=position, explanation=explanation('C'))
    assert error.value.exit_code == 2
    assert source.changes == proposal.data['changes'] and names(source) == 'AB'


@pytest.mark.parametrize('labels,position', [('A', 1), ('AB', 2), ('ABC', 3),
    ('AB', -1), ('AB', None), ('AB', True), ('AB', 0.0), ('AB', '0')])
def test_move_rejects_old_list_end_and_noninteger_indices(labels, position):
    proposal, source = sequence(labels)
    with no_write_attempts(), pytest.raises(ModelError) as error:
        source.move(source.change_ids[0], position, change_plan=source.change_plan)
    assert error.value.exit_code == 2
    assert source.changes == proposal.data['changes']


@pytest.mark.parametrize('labels', ['ABC', 'ACB', 'BAC', 'BCA', 'CAB', 'CBA'])
@pytest.mark.parametrize('source_index,destination,order', [
    (0, 0, (0, 1, 2)), (0, 1, (1, 0, 2)), (0, 2, (1, 2, 0)),
    (1, 0, (1, 0, 2)), (1, 1, (0, 1, 2)), (1, 2, (0, 2, 1)),
    (2, 0, (2, 0, 1)), (2, 1, (0, 2, 1)), (2, 2, (0, 1, 2))])
def test_full_move_matrix_keeps_identity_operation_and_explanation_together(labels, source_index, destination, order):
    _, source = sequence(labels)
    expected = ''.join(labels[index] for index in order)
    moved = source.move(source.change_ids[source_index], destination,
        change_plan=source.change_plan if source_index == destination else plan([create(v) for v in expected]))
    assert names(moved) == expected
    assert moved.change_ids == tuple(source.change_ids[index] for index in order)
    assert moved.changes == [source.changes[index] for index in order]
    assert len(set(moved.change_ids)) == 3
    for identity in source.change_ids:
        assert source.get(identity) == moved.get(identity)


@pytest.mark.parametrize('position', [None, 0])
def test_empty_add_and_singleton_same_position_roundtrip(position, monkeypatch):
    _, empty = sequence('')
    monkeypatch.setattr('secrets.token_bytes', lambda n: b'\xff' * n)
    with no_write_attempts():
        single = empty.add(plan([create('A')]), explanation=explanation(), position=position)
        moved = single.move(single.change_ids[0], 0, change_plan=single.change_plan)
    assert names(moved) == 'A' and moved.change_ids == single.change_ids
    assert moved.change_ids[0] == 'CHG-7ZZZZZZZZZZZZZZZZZZZZZZZZZ'
    assert moved.changed_change_ids == ()
    assert moved.change_plan.source_bytes == single.change_plan.source_bytes
    with pytest.raises(ModelError):
        empty.move(single.change_ids[0], 0, change_plan=empty.change_plan)


def test_repeated_moves_and_noops_never_allocate_or_lose_a_change(monkeypatch):
    proposal, value = sequence('ABC')
    original_ids = value.change_ids
    def forbidden(size):
        raise AssertionError('Moving and updating do not allocate identities')
    monkeypatch.setattr('secrets.token_bytes', forbidden)
    with no_write_attempts():
        for label, destination, expected in [('A', 2, 'BCA'), ('A', 2, 'BCA'),
                ('A', 0, 'ABC'), ('C', 0, 'CAB'), ('C', 2, 'ABC')]:
            identity = original_ids['ABC'.index(label)]
            rebound = value.change_plan if names(value) == expected else plan([create(v) for v in expected])
            value = value.move(identity, destination, change_plan=rebound)
            assert names(value) == expected and set(value.change_ids) == set(original_ids)
        unchanged = value.update(original_ids[0], change_plan=value.change_plan, explanation=explanation('A'))
    assert unchanged.changed_change_ids == () and unchanged.changes == proposal.data['changes']
    assert unchanged.change_plan.canonical_bytes == value.change_plan.canonical_bytes


def test_add_retries_collisions_and_owns_all_returned_values(monkeypatch):
    proposal, source = sequence()
    draws = iter([0, 1, 128])
    calls = []
    def entropy(size):
        calls.append(size)
        return next(draws).to_bytes(size, 'big')
    monkeypatch.setattr('secrets.token_bytes', entropy)
    note = explanation('C')
    edited = source.add(plan([create(v) for v in 'ACB']), explanation=note, position=1)
    assert calls == [16, 16, 16]
    assert edited.change_ids == (source.change_ids[0], 'CHG-' + encode128((128).to_bytes(16, 'big')),
                                 source.change_ids[1])
    note['assumptions'].append('Mutated by caller')
    edited.changes[0]['rationale'] = 'Mutated projection'
    edited.get(source.change_ids[0])['operation']['artifact']['statement'] = 'Forged'
    assert edited.get(source.change_ids[0]) == source.get(source.change_ids[0])
    assert edited.changes[1]['assumptions'] == [] and proposal.data['changes'] == source.changes


def test_entropy_failure_has_no_partial_result_or_source_mutation(monkeypatch):
    proposal, source = sequence()
    def failed(size):
        raise OSError('Synthetic entropy failure')
    monkeypatch.setattr('secrets.token_bytes', failed)
    with no_write_attempts(), pytest.raises(ModelError) as error:
        source.add(plan([create(v) for v in 'ABC']), explanation=explanation('C'))
    assert error.value.exit_code == 5
    assert source.changes == proposal.data['changes'] and names(source) == 'AB'


@pytest.mark.parametrize('identity', [None, 0, True, [], {}, '1', 'CHG-',
    'CHG-' + '8' * 26, 'CHG-' + 'o' * 26, 'CHG-' + '0' * 26 + '\n'])
def test_invalid_identity_never_addresses_by_position_or_alias(identity):
    _, source = sequence()
    for call in (lambda: source.get(identity),
                 lambda: source.move(identity, 0, change_plan=source.change_plan),
                 lambda: source.remove(identity, change_plan=source.change_plan),
                 lambda: source.update(identity, change_plan=source.change_plan, explanation=explanation())):
        with no_write_attempts(), pytest.raises(ModelError):
            call()


@pytest.mark.parametrize('fault', ['order', 'basis', 'rationale', 'ai_confidence', 'injected_id', 'duplicate_requirement'])
def test_invalid_new_change_fails_before_identity_allocation(fault, monkeypatch):
    supplied = inputs(actor_type='ai')
    source = ProposalChanges(prepare_proposal(**supplied))
    values = source.change_plan.data
    values.pop('change_plan_sha256')
    extra = create('C')
    values['operations'].append(extra)
    from support.change_plans import result
    values['result_artifacts'].append(result(extra['artifact']))
    note = explanation('C'); note['confidence'] = 0.5
    if fault == 'order':
        values['operations'].reverse()
    elif fault == 'basis':
        values['base']['model_root_sha256'] = 'c' * 64
    elif fault == 'rationale':
        note['rationale'] = ''
    elif fault == 'ai_confidence':
        note['confidence'] = None
    elif fault == 'duplicate_requirement':
        from support.records import ref
        note['requirement_or_issue_ids'] = [ref('REQ'), ref('REQ')]
    else:
        note['change_id'] = 'CHG-' + '2' * 26
    def forbidden(size):
        raise AssertionError('Invalid request must not allocate an identity')
    monkeypatch.setattr('secrets.token_bytes', forbidden)
    with no_write_attempts(), pytest.raises(ModelError):
        source.add(prepare_change_plan(values), explanation=note)


def test_same_position_cannot_smuggle_a_new_complete_plan():
    _, source = sequence()
    values = source.change_plan.data
    values.pop('change_plan_sha256')
    values['planned_at'] = '2026-01-02T00:00:00Z'
    with no_write_attempts(), pytest.raises(ModelError, match='proposal_noop_plan_changed'):
        source.move(source.change_ids[0], 0, change_plan=prepare_change_plan(values))


def test_representation_only_change_binds_managed_path_and_preserves_identity_on_move():
    supplied = inputs(representation=True)
    source = ProposalChanges(prepare_proposal(**supplied))
    with no_write_attempts():
        moved = source.move(source.change_ids[0], 0, change_plan=source.change_plan)
    assert moved.get(moved.change_ids[0])['explanation']['targets'] == [
        moved.change_plan.operations[0].data['path']]
    assert moved.change_ids == source.change_ids and moved.changed_change_ids == ()
