"""Ordered identities, complete plan binding and real native target reconstruction."""
from copy import deepcopy

import pytest

from specroad.changes import prepare_change_plan
from specroad.model.canonical import canonical_json_bytes
from specroad.model.errors import ModelError
from specroad.model.identity_tokens import encode128
from specroad.proposals import ProposalChanges, prepare_proposal
from specroad.proposals.values import SPECIFICATION_SCOPE
from support.change_plans import document, operation, result
from support.read_only import no_write_attempts
from support.records import ref
from test_proposal_data import IDENTITY


def explanation(label='A'):
    return {'rationale': 'Synthetic change ' + label, 'requirement_or_issue_ids': [],
            'sources': [], 'assumptions': [], 'confidence': None}


def create(label):
    op = operation()
    op['artifact']['id'] = op['result_id'] = ref('GOAL', str(ord(label) - ord('A')))
    op['artifact']['statement'] = label
    return op


def plan(operations):
    values = document(operations, [result(op['artifact']) for op in operations])
    values['base']['scope_descriptor'] = deepcopy(SPECIFICATION_SCOPE)
    if not operations:
        values['expected_result'] = {'model_root_sha256': values['base']['model_root_sha256']}
    return prepare_change_plan(values)


def sequence(labels='AB'):
    native = plan([create(label) for label in labels])
    rows = [{**explanation(label), 'change_id': 'CHG-' + encode128(index.to_bytes(16, 'big')),
             'targets': [create(label)['result_id']]} for index, label in enumerate(labels)]
    proposal = prepare_proposal(identity=IDENTITY, title='Ordered changes', rationale='Synthetic',
                                change_plan=native, changes=rows)
    return proposal, ProposalChanges(proposal)


def names(changes):
    return ''.join(op['artifact']['statement'] for op in changes.change_plan.data['operations'])


@pytest.mark.parametrize('position,expected', [(None, 'ABC'), (0, 'CAB'), (1, 'ACB'), (2, 'ABC')])
def test_append_and_insert_follow_normative_vector_and_keep_existing_identities(position, expected, monkeypatch):
    proposal, source = sequence()
    original = proposal.source_bytes
    monkeypatch.setattr('secrets.token_bytes', lambda size: bytes([7]) * size)
    with no_write_attempts():
        edited = source.add(plan([create(label) for label in expected]),
                            explanation=explanation('C'), position=position)
    assert names(edited) == expected
    assert len(edited.change_ids) == len(set(edited.change_ids)) == 3
    added, = edited.changed_change_ids
    assert added == 'CHG-' + encode128(bytes([7]) * 16)
    assert edited.get(added)['operation']['artifact']['statement'] == 'C'
    assert edited.get(added)['explanation']['rationale'] == 'Synthetic change C'
    for identity in source.change_ids:
        assert edited.get(identity) == source.get(identity)
    assert proposal.source_bytes == original and names(source) == 'AB'
    assert edited.write_authorized is edited.change_plan.execution_ready is False


@pytest.mark.parametrize('source_index,position,expected', [(0, 2, 'BCA'), (2, 0, 'CAB'),
    (0, 1, 'BAC'), (1, 2, 'ACB'), (1, 0, 'BAC'), (2, 1, 'ACB'), (1, 1, 'ABC')])
def test_move_uses_index_after_removal_and_preserves_every_operation_explanation(source_index, position, expected):
    proposal, source = sequence('ABC')
    identity = source.change_ids[source_index]
    rebound = source.change_plan if source_index == position else plan([create(label) for label in expected])
    with no_write_attempts():
        edited = source.move(identity, position, change_plan=rebound)
    assert names(edited) == expected
    assert sorted(edited.change_ids) == sorted(source.change_ids)
    assert edited.changed_change_ids == (() if source_index == position else (identity,))
    assert [row['targets'][0] for row in edited.changes] == [create(label)['result_id'] for label in expected]
    for identity in source.change_ids:
        assert edited.get(identity) == source.get(identity)
    assert proposal.data['changes'] == source.changes


def test_identity_lookup_and_update_remove_never_use_display_numbers():
    _, source = sequence()
    a, b = source.change_ids
    replacement = create('C')
    with no_write_attempts():
        updated = source.update(b, change_plan=plan([create('A'), replacement]), explanation=explanation('C'))
        remaining = updated.remove(a, change_plan=plan([replacement]))
        empty = remaining.remove(b, change_plan=plan([]))
    assert updated.change_ids == (a, b) and names(updated) == 'AC'
    assert updated.get(b)['explanation']['targets'] == [replacement['result_id']]
    assert remaining.change_ids == (b,) and remaining.get(b) == updated.get(b)
    assert empty.change_ids == () and empty.change_plan.data['operations'] == []
    assert empty.change_plan.data['expected_result'] == {
        'model_root_sha256': empty.change_plan.data['base']['model_root_sha256']}
    for invalid in (0, 1, '1', 'CHG-' + '7' * 26):
        with pytest.raises(ModelError):
            source.get(invalid)


@pytest.mark.parametrize('mutation', ['order', 'basis', 'lost_operation', 'control_target'])
def test_substituted_complete_plans_are_rejected_without_mutating_the_source(mutation):
    proposal, source = sequence()
    target = [create('B'), create('A')]
    if mutation == 'order':
        target.reverse()
    elif mutation == 'lost_operation':
        target.pop()
    values = plan(target).data
    values.pop('change_plan_sha256')
    if mutation == 'basis':
        values['base']['model_root_sha256'] = 'c' * 64
    if mutation == 'control_target':
        from support.records import record_value
        control = record_value('proposal')
        values['operations'] = [{'op': 'create', 'artifact': control, 'result_id': control['id']}]
        values['result_artifacts'] = [result(control)]
    with no_write_attempts(), pytest.raises(ModelError):
        source.move(source.change_ids[0], 1, change_plan=prepare_change_plan(values))
    assert source.changes == proposal.data['changes'] and names(source) == 'AB'


def test_native_target_reconstruction_observes_order_of_two_edits_to_one_artifact(tmp_path):
    from specroad.changes.lifecycle import prepare_change_lifecycle
    from specroad.changes._target_materialization import materialize_target
    from specroad.model.paths import artifact_path
    from specroad.proposals.context import ProposalContext, reconstruct_proposal_target, specification_manifest
    from specroad.validation import ModelDocument
    from support.folds import edit
    from support.languages import small_restore_registry
    from test_proposal_originals import draft
    model, original = draft(tmp_path, language_registry=small_restore_registry())
    goal = next(a for a in model.artifacts if a['artifact_type'] == 'goal')
    a, b = edit(goal, 'First result'), edit(goal, 'Second result')

    def rebound(operations):
        values = document(operations, [])
        folded = prepare_change_lifecycle(model.artifacts, operations,
            metadata_policy_version=values['metadata_policy_version'], actor=values['actor'],
            planned_at=values['planned_at'], source_files=model.source_files, **model.reservations)
        final = next(value for value in folded.artifacts if value['id'] == goal['id'])
        target = materialize_target(model, (ModelDocument(artifact_path('goal', goal['id'], 'SR'),
                                                         canonical_json_bytes(final)),))
        values['base'] = original['base']
        values['result_artifacts'] = [result(final)]
        values['expected_result']['model_root_sha256'] = specification_manifest(target).sha256
        return prepare_change_plan(values)

    rows = [{**explanation(label), 'change_id': 'CHG-' + encode128(index.to_bytes(16, 'big')),
             'targets': [goal['id']]} for index, label in enumerate('AB')]
    supplied = dict(identity=IDENTITY, title='Ordered native edits', rationale='Synthetic', changes=rows)
    with no_write_attempts():
        proposal = prepare_proposal(**supplied, change_plan=rebound([a, b]))
        before = reconstruct_proposal_target(ProposalContext(proposal.original, model))
        ordered = ProposalChanges(proposal)
        moved = ordered.move(rows[0]['change_id'], 1, change_plan=rebound([b, a]))
        # A declarative construction only: no lifecycle revision/write is claimed.
        supplied['changes'] = moved.changes
        candidate = prepare_proposal(**supplied, change_plan=moved.change_plan)
        after = reconstruct_proposal_target(ProposalContext(candidate.original, model))
    assert next(v for v in before.artifacts if v['id'] == goal['id'])['statement'] == 'Second result'
    final = next(v for v in after.artifacts if v['id'] == goal['id'])
    assert final['statement'] == 'First result' and final['revision'] == goal['revision'] + 1
    assert moved.change_ids == tuple(reversed(ordered.change_ids))
    assert proposal.source_bytes == prepare_proposal(**{**supplied, 'changes': rows},
                                                     change_plan=ordered.change_plan).source_bytes
    assert specification_manifest(before).sha256 != specification_manifest(after).sha256
