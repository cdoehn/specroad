"""Table 9.6.3: observable candidates, no output or documentation expectations."""
from copy import deepcopy
import pytest
from specroad.changes import prepare_change_lifecycle, lifecycle_content_sha256, LifecycleError
from specroad.model.canonical import canonical_json_sha256
from support.folds import goal, edit, create, add_relation, remove_relation
from support.domain import approved_value

ACTOR = {'actor_type': 'human', 'actor_id': 'planner'}
TIME = '2026-07-01T00:00:00Z'


def approved(number=0, **kwargs):
    return {**approved_value('goal'), **goal(number), 'maturity': 'approved',
            'success_criterion': ['Observable success'], **kwargs}


def prepare(artifacts, operations, **kwargs):
    return prepare_change_lifecycle(artifacts, operations, **{
        'metadata_policy_version': 'change-metadata-v1', 'actor': ACTOR, 'planned_at': TIME, **kwargs})


def transition(a, to, **kwargs):
    return {'op': 'transition', 'target': a['id'], 'from': a['maturity'], 'to': to,
            'metadata': {'reason': 'Explicit lifecycle choice'}, **kwargs}


def retire(a):
    return {'op': 'retire', 'target': a['id'], 'expected_revision': a['revision'], 'reason': 'No longer needed'}


def test_approved_content_change_proposed_once_before_hashing():
    a = approved(revision=9)
    out = prepare([a], [edit(a, 'First'), edit(a, 'Final')])
    b = out.artifacts[0]
    assert (b['maturity'], b['revision']) == ('proposed', 10)
    assert b['updated_by'] == ACTOR and b['updated_at'] == TIME
    assert b['created_at'] == a['created_at'] and b['created_by'] == a['created_by']
    assert out.candidates[0].candidate_sha256 == canonical_json_sha256(b)
    assert out.decisions[0]['approval_withdrawn'] is True
    assert out.candidates[0].operation_indices == (0, 1)


def test_pure_retirement_has_no_following_reset_or_invented_fields():
    a = approved(revision=4)
    out = prepare([a], [retire(a)])
    b = out.artifacts[0]
    assert (b['maturity'], b['revision']) == ('retired', 5)
    assert lifecycle_content_sha256(a) == lifecycle_content_sha256(b)
    assert out.decisions[0]['approval_withdrawn'] is False
    assert out.transition_events[0]['metadata']['reason'] == 'No longer needed'
    assert out.transition_events[0]['actor'] == ACTOR and 'reason' not in b


def test_pure_transition_to_proposed_is_one_revision():
    a = approved(revision=8)
    b = prepare([a], [transition(a, 'proposed')]).artifacts[0]
    assert b['maturity'] == 'proposed' and b['revision'] == 9
    assert lifecycle_content_sha256(a) == lifecycle_content_sha256(b)


@pytest.mark.parametrize('order', [0, 1])
def test_content_plus_explicit_proposed_is_one_revision_in_both_orders(order):
    a = approved(revision=3); ops = [edit(a, 'Changed'), transition(a, 'proposed')]
    if order: ops.reverse()
    b = prepare([a], ops).artifacts[0]
    assert b['revision'] == 4 and b['maturity'] == 'proposed'


def test_pure_supersession_requires_incoming_same_type_successor():
    a, b = approved(), goal(1)
    b['relations'] = [add_relation(b, a)['relation']]
    out = prepare([a, b], [transition(a, 'superseded')])
    assert out.artifacts[0]['maturity'] == 'superseded'
    assert out.artifacts[1] == b
    assert out.artifacts[0]['revision'] == a['revision'] + 1


def test_successor_can_be_created_later_in_the_same_plan():
    a, b = approved(), goal(1)
    b['relations'] = [add_relation(b, a)['relation']]
    out = prepare([a], [transition(a, 'superseded'), create(b)])
    assert len(out.artifacts) == 2 and out.artifacts[0]['maturity'] == 'superseded'


def test_missing_successor_is_a_failure_not_partial_success():
    a = approved()
    with pytest.raises(LifecycleError) as err: prepare([a], [transition(a, 'superseded')])
    assert err.value.reason == 'successor_required_in_final_model'
    assert err.value.diagnostic()['partial_result_available'] is False


@pytest.mark.parametrize('ops_kind', ['empty', 'same', 'reverted'])
def test_noop_and_reverted_content_keep_all_base_values(ops_kind):
    a = approved(revision=13)
    ops = {'empty': [], 'same': [edit(a, a['statement'])],
        'reverted': [edit(a, 'Temporary'), edit(a, a['statement'])]}[ops_kind]
    out = prepare([a], ops)
    assert out.artifacts == [a] and out.modified_ids == ()
    assert out.base_artifacts_sha256 == out.result_artifacts_sha256
    if out.decisions: assert out.decisions[0]['approval_withdrawn'] is False


def test_reverted_content_with_retirement_is_pure_lifecycle():
    a = approved()
    out = prepare([a], [edit(a, 'Temporary'), edit(a, a['statement']), retire(a)])
    assert out.artifacts[0]['maturity'] == 'retired'
    assert out.artifacts[0]['revision'] == a['revision'] + 1


@pytest.mark.parametrize('to', ['retired', 'superseded'])
def test_conflicting_content_and_target_is_rejected(to):
    a = approved()
    with pytest.raises(LifecycleError) as err: prepare([a], [edit(a, 'X'), transition(a, to)])
    assert err.value.reason == 'content_lifecycle_conflict' and err.value.exit_code == 2


def test_saved_request_conflict_is_model_error_three():
    a = approved()
    with pytest.raises(LifecycleError) as err:
        prepare([a], [edit(a, 'X'), retire(a)], input_kind='saved_plan')
    assert err.value.reason == 'content_lifecycle_conflict' and err.value.exit_code == 3


def test_relation_change_resets_approved_source_not_target():
    a, b = approved(), goal(1)
    out = prepare([a, b], [add_relation(a, b)])
    assert out.artifacts[0]['maturity'] == 'proposed' and out.artifacts[1] == b


def test_add_then_remove_relation_preserves_approval():
    a, b = approved(), goal(1); op = add_relation(a, b)
    out = prepare([a, b], [op, remove_relation(a, op['relation'])])
    assert out.artifacts == [a, b] and out.modified_ids == ()


@pytest.mark.parametrize('state', ['draft', 'proposed', 'in_review', 'rejected', 'superseded', 'retired'])
def test_content_edit_never_resurrects_nonapproved_status(state):
    a = goal(maturity=state)
    b = prepare([a], [edit(a, 'X')]).artifacts[0]
    assert b['maturity'] == state and b['revision'] == a['revision'] + 1


def test_missing_retirement_reason_fails():
    a = approved(); op = retire(a); op['reason'] = ' '
    with pytest.raises(Exception) as err: prepare([a], [op])
    assert hasattr(err.value, 'reason')


def test_rejection_requires_nonempty_reason():
    a = goal()
    with pytest.raises(LifecycleError): prepare([a], [transition(a, 'rejected', metadata={})])


def test_retired_cannot_transition_out():
    a = goal(maturity='retired')
    with pytest.raises(LifecycleError) as err: prepare([a], [transition(a, 'draft')])
    assert err.value.reason == 'invalid_lifecycle_transition'


def test_approval_not_granted_by_an_actor_label_or_transition_metadata():
    a = goal(maturity='in_review')
    with pytest.raises(LifecycleError) as err:
        prepare([a], [transition(a, 'approved', metadata={'human_review': True})])
    assert err.value.reason == 'approval_gate_required'


def test_new_draft_gets_revision_one_and_does_not_inherit_approval():
    a = goal(revision=22)
    out = prepare([], [create(a), edit(a, 'Revised')])
    assert out.artifacts[0]['revision'] == 1 and out.artifacts[0]['maturity'] == 'draft'
    with pytest.raises(LifecycleError): prepare([], [create(approved())])


def test_output_and_inputs_are_independent_no_write_or_grant():
    a = approved(); ops = [edit(a, 'X')]; old = deepcopy((a, ops))
    out = prepare([a], ops)
    assert (a, ops) == old
    out.artifacts[0]['maturity'] = 'approved'; out.decisions.clear()
    assert out.artifacts[0]['maturity'] == 'proposed' and out.decisions
    assert out.metadata_applied and out.lifecycle_checked
    assert not any((out.approval_granted, out.execution_ready, out.write_authorized,
                    out.history_complete, out.project_complete, out.expected_result_root_verified))


def test_different_artifacts_can_change_content_and_retire_independently():
    a, b = approved(), approved(1)
    out = prepare([a, b], [edit(a, 'X'), retire(b)])
    assert [(v['maturity'], v['revision']) for v in out.artifacts] == [('proposed', 2), ('retired', 2)]
