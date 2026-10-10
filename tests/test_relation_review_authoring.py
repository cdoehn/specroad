"""Exact human review observations, native publication and immutable replay."""
import json
from unittest.mock import patch

import pytest

from specroad.authoring import reviews
from specroad.authoring.reviews import record_relation_review
from specroad.changes import (AuthoringError, ChangeOperation, ChangePlanError,
    PublicationAuthority, PublicationCheckError, TargetError, TargetModel,
    inspect_project_lock, prepare_change_target, assess_change_target, prepare_change_plan)
from specroad.changes.reviews import (review_context, prepare_review_record,
    prepare_review_gates, review_time)
from specroad.changes.idempotency_values import RequestIdConflict
from specroad.graph.review_context_values import EndpointReviewContext
from specroad.graph.relations import SourceRelations
from specroad.graph._review_projection import relation_content_sha256
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.model.identities import IdentityInventory
from specroad.model.identity_tokens import encode128
from specroad.model.identity_values import ArtifactIdentity
from specroad.model.paths import artifact_path
from specroad.validation import ModelDocument
from support.read_only import inventory as file_inventory, no_write_attempts
from test_relation_authoring import stored_project, receipt

ACTOR = {'actor_type': 'human', 'actor_id': 'reviewer'}
TIME = '2026-10-10T21:20:00Z'
REASON = 'The stored relation matches both endpoint statements.'
ENTROPY = b'\x61' * 16
REVIEW_ID = 'SR-RREV-' + encode128(ENTROPY)


def inventory(model, *, archived=(), reserved=()):
    return IdentityInventory('SR', [a['id'] for a in model.artifacts], archived, reserved)


def options(model, **overrides):
    return dict(inventory=inventory(model), actor=ACTOR, planned_at=TIME,
        change_plan_id='CP-review', transaction_id='txn-review', request_id='review-1',
        authority=PublicationAuthority('owned-review-host', '1', lambda request: True),
        **overrides)


def call(model, source, arguments, **intent):
    value = dict(decision='confirmed', reason=REASON, expected_revision=source['revision'])
    value.update(intent)
    return record_relation_review(model, source['id'], source['relations'][0]['relation_id'],
                                  **value, **arguments)


def planned(model, source, *, comment=None):
    context = review_context(model.artifacts, source['id'], source['relations'][0]['relation_id'])
    identity = ArtifactIdentity(REVIEW_ID, 'random128-v1', 'relation_review', 'SR')
    record = prepare_review_record(context, identity, actor=ACTOR, planned_at=TIME,
                                  decision='confirmed', reason=REASON, comment=comment)
    operation = ChangeOperation({'op': 'relation_review_record', 'source': source['id'],
        'target': context.target.artifact_id, 'record': record, 'approval_withdrawals': [],
        'expected_revision': source['revision']})
    gates = prepare_review_gates(model, operation, actor=ACTOR, planned_at=TIME)
    checked = prepare_change_target(model, [operation.data], change_plan_id='CP-review',
        request_id='review-1', actor=ACTOR, planned_at=TIME, scope_descriptor=reviews._SCOPE,
        metadata_policy_version='change-metadata-v1', policy=reviews._POLICY, gates=gates)
    return checked, gates


@pytest.mark.parametrize('guard', ['revision', 'hash', 'both'])
@pytest.mark.parametrize('comment', [None, 'Inspected against the complete source and target.'])
def test_record_binds_exact_review_and_publishes_one_new_immutable_artifact(tmp_path, guard, comment):
    root = tmp_path / 'project'; model, source, goals = stored_project(root, with_edges=True)
    before = file_inventory(root); draws = []
    def entropy(size):
        state = inspect_project_lock(root).data
        assert state['record']['kind'] == 'writer'
        assert state['record']['transaction_id'] == 'txn-review'
        draws.append(size)
        return ENTROPY
    guards = {}
    if guard in ('revision', 'both'): guards['expected_revision'] = source['revision']
    if guard in ('hash', 'both'): guards['expected_sha256'] = canonical_json_sha256(source)
    with patch('secrets.token_bytes', side_effect=entropy):
        result = record_relation_review(model, source['id'], source['relations'][0]['relation_id'],
            decision='confirmed', reason=REASON, comment=comment, **guards, **options(model))
    record = json.loads((root / result['path']).read_bytes())
    assert result['review_id'] == record['id'] == REVIEW_ID and draws == [16]
    assert record['review_state'] == 'recorded' and record['maturity'] == 'approved'
    assert record['revision'] == 1 and record['id_scheme'] == 'random128-v1'
    assert record['created_at'] == record['updated_at'] == record['reviewed_at'] == TIME
    assert record['created_by'] == record['updated_by'] == record['reviewer'] == ACTOR
    assert record['decision'] == 'confirmed' and record['reason'] == REASON
    assert record['relations'] == [] and record['extensions'] == {}
    assert record.get('comment') == comment and ('comment' in record) == (comment is not None)
    stored = SourceRelations(canonical_json_bytes(source))
    assert record['relation_content_sha256'] == relation_content_sha256(stored.relations[0])
    assert record['context_hash_algorithm'] == 'relation_context_hash-v1'
    for name, endpoint in (('source', source), ('target', goals[0])):
        assert record[name + '_id'] == endpoint['id']
        assert record[name + '_revision'] == endpoint['revision']
        assert record[name + '_artifact_sha256'] == canonical_json_sha256(endpoint)
        observation = EndpointReviewContext(SourceRelations(canonical_json_bytes(endpoint)))
        assert record[name + '_context_sha256'] == observation.context_sha256
    assert (root / result['path']).read_bytes() == canonical_json_bytes(record)
    assert result['completion']['commit_completed'] and result['completion']['cleanup_completed']
    assert result['completion']['current_target_verified'] and result['write_state'] == 'committed'
    assert not result['replayed']
    proof = receipt(root, result)
    assert proof['created_ids'] == [REVIEW_ID]
    operation = proof['operations'][0]
    assert operation['op'] == 'relation_review_record' and operation['record'] == record
    assert {k: operation[k] for k in guards} == guards and operation['approval_withdrawals'] == []
    after = {row[0]: row[1:] for row in file_inventory(root)}
    for name, *original in before: assert after[name] == tuple(original)
    assert not (root / '.specroad/locks/project.json').exists()
    assert all(a['id'] != REVIEW_ID for a in model.artifacts)


def test_confirmed_retry_reuses_proof_before_lock_allocation_or_context_replanning(tmp_path):
    root = tmp_path / 'project'; model, source, _ = stored_project(root, with_edges=True)
    first = call(model, source, options(model), comment='Reviewed.')
    before = file_inventory(root)
    arguments = {**options(model), 'planned_at': '2027-01-01T00:00:00Z',
        'change_plan_id': 'CP-retry', 'transaction_id': 'unused-retry',
        'actor': {**ACTOR, 'actor_id': 'retry-human'}}
    with no_write_attempts(), patch.object(reviews, 'project_lock', side_effect=AssertionError), \
            patch.object(reviews, 'review_context', side_effect=AssertionError), \
            patch('secrets.token_bytes', side_effect=AssertionError):
        replay = call(model, source, arguments, comment='Reviewed.')
    assert replay['replayed'] and replay['review_id'] == first['review_id']
    assert replay['completion']['transaction_id'] == 'txn-review'
    assert not replay['completion']['current_target_verified']
    assert receipt(root, replay)['journal']['actor'] == ACTOR
    assert file_inventory(root) == before


@pytest.mark.parametrize('changed', [{'reason': 'Different reason.'}, {'comment': 'Added comment.'},
                                    {'expected_revision': 8}])
def test_same_request_rejects_changed_intent_before_a_second_writer(tmp_path, changed):
    root = tmp_path / 'project'; model, source, _ = stored_project(root, with_edges=True)
    call(model, source, options(model)); before = file_inventory(root)
    with no_write_attempts(), pytest.raises(RequestIdConflict) as error:
        call(model, source, options(model), **changed)
    assert error.value.exit_code == 6 and file_inventory(root) == before


@pytest.mark.parametrize('actor_type', ['ai', 'ci', 'tool'])
def test_nonhuman_review_is_denied_before_any_write(tmp_path, actor_type):
    root = tmp_path / 'project'; model, source, _ = stored_project(root, with_edges=True)
    arguments = {**options(model), 'actor': {**ACTOR, 'actor_type': actor_type}}
    before = file_inventory(root)
    with no_write_attempts(), pytest.raises(AuthoringError) as error:
        call(model, source, arguments)
    assert error.value.exit_code == 7 and file_inventory(root) == before


@pytest.mark.parametrize('guards', [{}, {'expected_revision': None}, {'expected_revision': 0},
                                  {'expected_sha256': 'invalid'}])
def test_source_guard_is_explicit_before_io(tmp_path, guards):
    root = tmp_path / 'project'; model, source, _ = stored_project(root, with_edges=True)
    before = file_inventory(root)
    with no_write_attempts(), pytest.raises(AuthoringError) as error:
        record_relation_review(model, source['id'], source['relations'][0]['relation_id'],
            decision='confirmed', reason=REASON, **guards, **options(model))
    assert error.value.exit_code == 3 and file_inventory(root) == before


@pytest.mark.parametrize('intent', [{'expected_revision': 8}, {'expected_sha256': '0' * 64}])
def test_stale_source_guard_never_publishes_a_review(tmp_path, intent):
    root = tmp_path / 'project'; model, source, _ = stored_project(root, with_edges=True)
    before = file_inventory(root)
    with pytest.raises(ChangePlanError) as error: call(model, source, options(model), **intent)
    assert error.value.reason in ('expected_revision_mismatch', 'expected_hash_mismatch')
    assert file_inventory(root) == before


def test_negative_outcome_remains_closed_without_the_withdrawal_service(tmp_path):
    root = tmp_path / 'project'; model, source, _ = stored_project(root, with_edges=True)
    before = file_inventory(root)
    with no_write_attempts(), pytest.raises(AuthoringError) as error:
        call(model, source, options(model), decision='rejected')
    assert error.value.reason == 'review_outcome_requires_specialized_service'
    assert file_inventory(root) == before


def test_denied_authority_leaves_every_original_file_unchanged(tmp_path):
    root = tmp_path / 'project'; model, source, _ = stored_project(root, with_edges=True)
    before = file_inventory(root)
    arguments = {**options(model), 'authority': PublicationAuthority('deny', '1', lambda request: False)}
    with pytest.raises(PublicationCheckError) as error: call(model, source, arguments)
    assert error.value.exit_code == 7 and file_inventory(root) == before


def test_first_review_gates_do_not_approve_unimplemented_history_selection(tmp_path):
    root = tmp_path / 'project'; model, source, _ = stored_project(root, with_edges=True)
    first = call(model, source, options(model))
    documents = [*model.documents, ModelDocument(first['path'], (root / first['path']).read_bytes())]
    current = TargetModel(model.configuration_bytes, model.binding, documents,
        profile=model.profile, resource_files=model.resource_files)
    before = file_inventory(root)
    arguments = {**options(current), 'request_id': 'second-review', 'transaction_id': 'txn-second'}
    with pytest.raises(TargetError) as error: call(current, source, arguments)
    assert error.value.reason == 'complete_target_validation_required'
    assert file_inventory(root) == before


def test_saved_plan_recomputes_exact_review_and_requires_actual_semantic_gates(tmp_path):
    model, source, _ = stored_project(tmp_path / 'project', with_edges=True)
    checked, gates = planned(model, source)
    assert checked.target_validated
    again = assess_change_target(checked.plan, model, policy=reviews._POLICY, gates=gates)
    assert again.target_validated and again.publication_documents == checked.publication_documents
    incomplete = assess_change_target(checked.plan, model, policy=reviews._POLICY)
    assert not incomplete.target_validated and not incomplete.data['checks_complete']


@pytest.mark.parametrize('field,new_value', [
    ('source_revision', 8), ('target_revision', 77), ('source_artifact_sha256', '0' * 64),
    ('target_artifact_sha256', '0' * 64), ('source_context_sha256', '0' * 64),
    ('target_context_sha256', '0' * 64), ('relation_content_sha256', '0' * 64),
    ('reviewer', {'actor_type': 'human', 'actor_id': 'different-reviewer'})])
def test_self_hashed_plan_cannot_substitute_review_observations(tmp_path, field, new_value):
    model, source, _ = stored_project(tmp_path / 'project', with_edges=True)
    checked, gates = planned(model, source)
    value = checked.plan.data; value.pop('change_plan_sha256')
    record = value['operations'][0]['record']; record[field] = new_value
    value['result_artifacts'][0] = {'artifact': record, 'sha256': canonical_json_sha256(record)}
    tampered = prepare_change_plan(value)
    with pytest.raises(TargetError) as error:
        assess_change_target(tampered, model, policy=reviews._POLICY, gates=gates)
    assert error.value.reason == 'review_record_binding_mismatch'


def test_new_review_time_is_after_existing_matching_review_without_restamping_history(tmp_path):
    model, source, _ = stored_project(tmp_path / 'project', with_edges=True)
    checked, _ = planned(model, source)
    old = checked.plan.data['operations'][0]['record']; raw = canonical_json_bytes(old)
    context = review_context(model.artifacts, source['id'], source['relations'][0]['relation_id'])
    assert review_time([*model.artifacts, old], context, TIME) == '2026-10-10T21:20:00.000001Z'
    assert canonical_json_bytes(old) == raw


@pytest.mark.parametrize('operation', ['create', 'update', 'transition'])
def test_review_keeps_all_generic_mutation_routes_closed(tmp_path, operation):
    model, source, _ = stored_project(tmp_path / 'project', with_edges=True)
    checked, _ = planned(model, source); record = checked.plan.data['operations'][0]['record']
    value = ({'op': 'create', 'artifact': record, 'result_id': record['id']} if operation == 'create'
        else {'op': 'update', 'target': record['id'], 'expected_revision': 1,
              'patch': [{'op': 'replace', 'path': '/decision', 'value': 'rejected'}]} if operation == 'update'
        else {'op': 'transition', 'target': record['id'], 'from': 'approved', 'to': 'retired',
              'metadata': {'reason': 'Attempt to mutate historical review.'}})
    with pytest.raises(ChangePlanError) as error: ChangeOperation(value)
    assert error.value.reason == 'specialized_operation_required'
