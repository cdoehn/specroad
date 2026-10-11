"""Coupled review/withdrawal bytes, saved-plan binding and native receipts.

Owned synthetic history and an explicitly supplied host gate are fixtures;
they do not authenticate real reviewers or claim complete approval integration.
"""
import json
from unittest.mock import patch

import pytest

from specroad.authoring import negative_reviews as service
from specroad.authoring.negative_reviews import record_negative_relation_review
from specroad.changes import (AuthoringError, ChangeOperation, ChangePlanError,
    PublicationAuthority, PublicationCheckError, TargetError, TargetModel,
    assess_change_target, prepare_change_target)
from specroad.changes.idempotency_values import RequestIdConflict
from specroad.changes.negative_reviews import (WITHDRAWAL_GATE,
    required_review_withdrawals, prepare_negative_review_record, prepare_negative_review_gates)
from specroad.changes.reviews import review_context, review_time
from specroad.graph.relations import SourceRelations
from specroad.graph.review_status import RelationReviewStatuses
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.model.identity_values import ArtifactIdentity
from specroad.model.identity_tokens import encode128
from specroad.model.identities import IdentityInventory
from specroad.model.paths import artifact_path
from specroad.validation import ModelDocument, ModelGate
from support.domain import approved_value
from support.model import put
from support.read_only import inventory as file_inventory, no_write_attempts
from support.records import record_value
from support.relations import aid, edge
from test_artifact_creation import project
from test_relation_authoring import receipt, stored_project
from test_relation_review_status import review

ACTOR = {'actor_type': 'human', 'actor_id': 'negative-reviewer'}
TIME = '2026-10-11T02:30:00Z'
OLD_TIME = '2026-10-10T23:40:00Z'
REASON = 'The relation does not accurately justify this requirement.'
ENTROPY = b'\x71' * 16
REVIEW_ID = 'SR-RREV-' + encode128(ENTROPY)


def negative_project(root):
    base, _ = project(root); goal = base.artifacts[0]
    test = record_value('test', id=aid('test', 1))
    source = approved_value('requirement', id=aid(), revision=4,
        relations=[edge('addresses', goal['id'], number=10),
                   edge('verified_by', test['id'], number=11)])
    history = []
    for position, target in enumerate((goal, test)):
        ordered = [source['relations'][position], source['relations'][1 - position]]
        value = review({**source, 'relations': ordered}, target,
            number=20 + position, time=OLD_TIME)
        value['source_artifact_sha256'] = canonical_json_sha256(source)
        history.append(value)
    values = [goal, test, source, *history]
    docs = [ModelDocument(artifact_path(a['artifact_type'], a['id'], 'SR'),
                         json.dumps(a, indent=3).encode() + b'\n') for a in values]
    model = TargetModel(base.configuration_bytes, base.binding, docs,
        profile=base.profile, resource_files=base.resource_files)
    for path, raw in model.source_files.items(): put(root, path, raw)
    (root / artifact_path('requirement', source['id'], 'SR')).chmod(0o640)
    # Explicit trusted host-service fixture checks the unchanged draft test.
    # The tested contract is coupled publication, not evidence authenticity.
    def evidence(context):
        assert context.subjects == (test['id'],)
        assert context.artifact(test['id']) == test
        return context.result()
    gate = ModelGate('evidence_currentness', 'owned-unchanged-test-fixture-v1',
        lambda c: c.dependency_result({key: list(c.all_ids) for key in c.subjects}), evidence)
    return model, source, history, (gate,)


def options(model, gates=()):
    return dict(inventory=IdentityInventory('SR', [a['id'] for a in model.artifacts], (), ()),
        actor=ACTOR, planned_at=TIME, change_plan_id='CP-negative', transaction_id='txn-negative',
        request_id='negative-1', authority=PublicationAuthority('owned-negative-host', '1', lambda request: True),
        gates=gates)


def call(model, source, arguments, **intent):
    values = {'reason': REASON, 'expected_revision': source['revision'], **intent}
    return record_negative_relation_review(model, source['id'], source['relations'][0]['relation_id'],
                                           **values, **arguments)


def operation(model, source):
    context = review_context(model.artifacts, source['id'], source['relations'][0]['relation_id'])
    identity = ArtifactIdentity(REVIEW_ID, 'random128-v1', 'relation_review', 'SR')
    time = review_time(model.artifacts, context, TIME)
    record = prepare_negative_review_record(context, identity, actor=ACTOR, planned_at=time, reason=REASON)
    withdrawals = required_review_withdrawals(model.artifacts, source['id'], context.relation_id,
                                              profile=model.profile)
    return ChangeOperation({'op': 'relation_review_record', 'source': source['id'],
        'target': context.target.artifact_id, 'record': record, 'approval_withdrawals': withdrawals,
        'expected_revision': source['revision']})


def planned(model, source, gates=()):
    op = operation(model, source)
    all_gates = (*gates, *prepare_negative_review_gates(model, op, actor=ACTOR, planned_at=TIME))
    checked = prepare_change_target(model, [op.data], change_plan_id='CP-negative',
        request_id='negative-1', actor=ACTOR, planned_at=TIME, scope_descriptor=service._SCOPE,
        metadata_policy_version='change-metadata-v1', policy=service._POLICY, gates=all_gates)
    return checked, all_gates


@pytest.mark.parametrize('guard', ['revision', 'hash', 'both'])
@pytest.mark.parametrize('strict', [False, True])
def test_negative_review_and_single_revision_withdrawal_share_native_receipt(tmp_path, guard, strict):
    root = tmp_path / 'project'; model, source, history, gates = negative_project(root)
    before = file_inventory(root); guards = {}
    if guard in ('revision', 'both'): guards['expected_revision'] = 4
    if guard in ('hash', 'both'): guards['expected_sha256'] = canonical_json_sha256(source)
    with patch('secrets.token_bytes', return_value=ENTROPY):
        result = record_negative_relation_review(model, source['id'], source['relations'][0]['relation_id'],
            reason=REASON, **guards, strict=strict, **options(model, gates))
    path = artifact_path('requirement', source['id'], 'SR')
    expected = {**source, 'maturity': 'proposed', 'revision': 5, 'updated_at': TIME, 'updated_by': ACTOR}
    assert (root / path).read_bytes() == canonical_json_bytes(expected)
    assert (root / path).stat().st_mode & 0o777 == 0o640
    record = json.loads((root / result['path']).read_bytes())
    assert record['id'] == REVIEW_ID and record['decision'] == 'rejected'
    assert (record['review_state'], record['maturity'], record['revision']) == ('recorded', 'approved', 1)
    assert record['source_revision'] == 4 and record['source_artifact_sha256'] == canonical_json_sha256(source)
    assert record['reviewer'] == ACTOR and record['reason'] == REASON
    assert result['write_state'] == 'committed' and result['assessment_status'] == 'failed'
    assert result['assessment_scope'] == 'recorded_review_outcome_only'
    assert result['diagnostics'][0]['code'] == 'SRV027' and result['diagnostics'][0]['severity'] == 'error'
    assert result['diagnostics'][0]['category'] == 'review_outcome'
    assert result['approval_withdrawals'] == [{'artifact_id': source['id'], 'base_revision': 4,
        'target_revision': 5, 'from': 'approved', 'to': 'proposed',
        'relation_id': source['relations'][0]['relation_id'], 'review_id': REVIEW_ID,
        'reason': 'mandatory_relation_not_current'}]
    proof = receipt(root, result)
    assert proof['created_ids'] == [REVIEW_ID]
    assert proof['result_object']['exit_code'] == 0 and proof['result_object']['status'] == 'success'
    assert set(proof['result_object']['published_paths']) == {path, result['path']}
    assert proof['journal']['plan_sha256'] == result['plan_sha256']
    assert proof['journal']['target_model_root_sha256'] == result['target_model_root_sha256']
    assert proof['operations'][0]['approval_withdrawals'] == [{'target': source['id'],
        'reason': 'mandatory_relation_not_current', 'expected_revision': 4,
        'expected_sha256': canonical_json_sha256(source)}]
    after = {row[0]: row[1:] for row in file_inventory(root)}
    for name, *original in before:
        if name != path: assert after[name] == tuple(original)
    values = [expected if a['id'] == source['id'] else a for a in model.artifacts] + [record]
    statuses = RelationReviewStatuses(tuple(SourceRelations(canonical_json_bytes(a)) for a in values))
    observed = statuses.for_relation(source['id'], record['relation_id'])
    assert observed.status == 'invalid' and observed.selected_review_id == REVIEW_ID
    assert all(a in model.artifacts for a in history)
    assert result['completion']['commit_completed'] and result['completion']['cleanup_completed']


def test_draft_rejection_creates_no_source_revision_or_unjustified_withdrawal(tmp_path):
    root = tmp_path / 'project'; model, source, _ = stored_project(root, with_edges=True)
    path = artifact_path('requirement', source['id'], 'SR'); before = (root / path).read_bytes()
    result = call(model, source, options(model))
    assert result['approval_withdrawals'] == [] and (root / path).read_bytes() == before
    assert receipt(root, result)['result_object']['published_paths'] == [result['path']]


def test_saved_negative_plan_recomputes_coupled_target_and_preserves_error_assessment(tmp_path):
    model, source, _, gates = negative_project(tmp_path / 'project')
    before = file_inventory(tmp_path)
    with no_write_attempts():
        checked, all_gates = planned(model, source, gates)
        again = assess_change_target(checked.plan, model, policy=service._POLICY, gates=all_gates)
    assert checked.target_validated and again.data == checked.data
    assert checked.data['validation']['status'] == 'success'
    semantic = checked.data['review_assessment']
    assert semantic['status'] == 'failed' and semantic['exit_code'] == 1
    assert semantic['validation_scope'] == 'supplied_relation_review_status_only'
    assert semantic['diagnostics'][0]['code'] == 'SRV027' and semantic['diagnostics'][0]['severity'] == 'error'
    assert len(checked.plan.data['operations']) == 1 and len(checked.plan.data['result_artifacts']) == 2
    assert checked.data['lifecycle']['decisions'][0]['target_revision'] == 5
    assert file_inventory(tmp_path) == before


@pytest.mark.parametrize('defect', ['missing', 'wrong_reason', 'wrong_guard'])
def test_writer_recomputes_withdrawal_set_instead_of_trusting_operation_payload(tmp_path, defect):
    model, source, _, gates = negative_project(tmp_path / 'project'); op = operation(model, source).data
    if defect == 'missing': op['approval_withdrawals'] = []
    elif defect == 'wrong_reason': op['approval_withdrawals'][0]['reason'] = 'unrelated'
    else: op['approval_withdrawals'][0]['expected_revision'] = 99
    with no_write_attempts(), pytest.raises(TargetError) as error:
        prepare_change_target(model, [op], change_plan_id='CP-bad', request_id='bad', actor=ACTOR,
            planned_at=TIME, scope_descriptor=service._SCOPE, metadata_policy_version='change-metadata-v1',
            policy=service._POLICY, gates=gates)
    assert error.value.reason == 'review_withdrawal_set_mismatch'


def test_missing_required_negative_review_gate_never_admits_the_target(tmp_path):
    model, source, _, gates = negative_project(tmp_path / 'project'); checked, all_gates = planned(model, source, gates)
    reduced = tuple(g for g in all_gates if g.gate_id != WITHDRAWAL_GATE)
    result = assess_change_target(checked.plan, model, policy=service._POLICY, gates=reduced)
    assert not result.target_validated and WITHDRAWAL_GATE in result.data['missing_command_gates']


def test_another_gate_cannot_turn_an_error_into_an_exempt_review_outcome(tmp_path):
    model, source, _, gates = negative_project(tmp_path / 'project'); checked, all_gates = planned(model, source, gates)
    fake = ModelGate('extension:unrelated', '1',
        lambda c: c.dependency_result({key: list(c.all_ids) for key in c.subjects}),
        lambda c: c.result([{'reason': 'current_review_rejected', 'code': 'SRV027',
            'severity': 'error', 'category': 'review_outcome', 'artifact_id': source['id']}]))
    result = assess_change_target(checked.plan, model, policy=service._POLICY, gates=(*all_gates, fake))
    assert not result.target_validated and result.data['validation']['exit_code'] == 1


@pytest.mark.parametrize('actor_type', ['ai', 'ci', 'tool'])
def test_nonhuman_negative_review_is_refused_before_writes(tmp_path, actor_type):
    model, source, _, gates = negative_project(tmp_path / 'project'); before = file_inventory(tmp_path)
    arguments = {**options(model, gates), 'actor': {**ACTOR, 'actor_type': actor_type}}
    with no_write_attempts(), pytest.raises(AuthoringError) as error: call(model, source, arguments)
    assert error.value.exit_code == 7 and file_inventory(tmp_path) == before


@pytest.mark.parametrize('guard', [{'expected_revision': 9}, {'expected_sha256': '0' * 64}])
def test_stale_negative_source_is_refused_before_lock_or_entropy(tmp_path, guard):
    model, source, _, gates = negative_project(tmp_path / 'project'); before = file_inventory(tmp_path)
    with no_write_attempts(), patch.object(service, 'project_lock', side_effect=AssertionError), \
            patch('secrets.token_bytes', side_effect=AssertionError), pytest.raises(ChangePlanError):
        call(model, source, options(model, gates), **guard)
    assert file_inventory(tmp_path) == before


def test_denied_authority_preserves_both_original_source_and_review_history(tmp_path):
    model, source, _, gates = negative_project(tmp_path / 'project'); before = file_inventory(tmp_path)
    arguments = {**options(model, gates), 'authority': PublicationAuthority('deny', '1', lambda request: False)}
    with pytest.raises(PublicationCheckError) as error: call(model, source, arguments)
    assert error.value.exit_code == 7 and file_inventory(tmp_path) == before


def test_negative_retry_returns_same_receipt_without_second_review_or_revision(tmp_path):
    root = tmp_path / 'project'; model, source, _, gates = negative_project(root)
    first = call(model, source, options(model, gates)); before = file_inventory(root)
    arguments = {**options(model, gates), 'transaction_id': 'unused-retry', 'planned_at': '2027-01-01T00:00:00Z'}
    with no_write_attempts(), patch.object(service, 'project_lock', side_effect=AssertionError), \
            patch.object(service, 'required_review_withdrawals', side_effect=AssertionError), \
            patch('secrets.token_bytes', side_effect=AssertionError):
        again = call(model, source, arguments)
    assert again['replayed'] and again['review_id'] == first['review_id']
    assert again['completion']['receipts'] == first['completion']['receipts']
    assert again['approval_withdrawals'] == first['approval_withdrawals']
    assert again['plan_sha256'] == first['plan_sha256'] and file_inventory(root) == before


def test_reusing_negative_request_with_changed_reason_is_a_conflict(tmp_path):
    model, source, _, gates = negative_project(tmp_path / 'project')
    call(model, source, options(model, gates)); before = file_inventory(tmp_path)
    with no_write_attempts(), pytest.raises(RequestIdConflict):
        call(model, source, options(model, gates), reason='Different decision basis.')
    assert file_inventory(tmp_path) == before
