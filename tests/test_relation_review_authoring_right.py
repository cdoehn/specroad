"""Early structural rejection, exact saved bindings and real recovery evidence."""
import json
import os
from unittest.mock import patch

import pytest

from specroad.authoring import reviews
from specroad.authoring.reviews import record_relation_review
from specroad.changes import (AuthoringError, ChangePlanError, CommitPublicationError,
    ProjectLockError, PublicationCheckError, TargetError, TargetModel,
    assess_change_target, prepare_change_plan, inspect_project_lock)
from specroad.changes.reviews import review_context, review_time
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.model.identity_tokens import encode128
from specroad.model.paths import artifact_path
from specroad.validation import ModelDocument, ModelGate
from support.domain import domain_value
from support.model import put
from support.read_only import inventory as file_inventory, no_write_attempts
from support.relations import aid, edge, rid
from test_relation_authoring import stored_project, receipt
from test_relation_review_authoring import (ACTOR, TIME, REASON, ENTROPY, REVIEW_ID,
    inventory, options, call, planned)


def rebuild(root, model, values, **reservations):
    documents = [ModelDocument(artifact_path(v['artifact_type'], v['id'], 'SR'),
                              canonical_json_bytes(v)) for v in values]
    rebuilt = TargetModel(model.configuration_bytes, model.binding, documents,
        profile=model.profile, resource_files=model.resource_files,
        **{**model.reservations, **reservations})
    for document in documents: put(root, document.path, document.content)
    return rebuilt


@pytest.mark.parametrize('defect,reason', [
    ('missing_target', 'missing_relation_target'), ('self', 'self_relation_forbidden'),
    ('wrong_pair', 'relation_type_pair_forbidden'), ('duplicate_id', 'duplicate_relation_id'),
    ('noncanonical', 'noncanonical_symmetric_relation'), ('unrelated_fields', 'missing_field')])
def test_invalid_project_graph_is_rejected_before_lock_or_entropy(tmp_path, defect, reason):
    root = tmp_path / 'project'; model, source, goals = stored_project(root, with_edges=True)
    values = model.artifacts; subject = next(v for v in values if v['id'] == source['id'])
    if defect == 'missing_target': subject['relations'][0]['target'] = aid('goal', 999)
    elif defect == 'self': subject['relations'][0]['target'] = source['id']
    elif defect == 'wrong_pair': subject['relations'][0]['type'] = 'verified_by'
    elif defect == 'duplicate_id':
        next(v for v in values if v['id'] == goals[1]['id'])['relations'] = [
            edge('supersedes', goals[0]['id'], number=10)]
    elif defect == 'noncanonical':
        values.append(domain_value('requirement', id=aid('requirement', 99),
            relations=[edge('duplicates', source['id'], number=99)]))
    else: next(v for v in values if v['id'] == goals[1]['id']).pop('statement')
    model = rebuild(root, model, values); before = file_inventory(root)
    with no_write_attempts(), patch.object(reviews, 'project_lock', side_effect=AssertionError), \
            patch('secrets.token_bytes', side_effect=AssertionError), pytest.raises(ChangePlanError) as error:
        call(model, source, options(model))
    assert error.value.reason == reason and error.value.exit_code == 3
    assert file_inventory(root) == before


@pytest.mark.parametrize('guard,reason', [({'expected_revision': 99}, 'expected_revision_mismatch'),
                                       ({'expected_sha256': '0' * 64}, 'expected_hash_mismatch')])
def test_stale_guard_precedes_lock_and_unavailable_entropy(tmp_path, guard, reason):
    root = tmp_path / 'project'; model, source, _ = stored_project(root, with_edges=True)
    before = file_inventory(root)
    with no_write_attempts(), patch.object(reviews, 'project_lock', side_effect=AssertionError), \
            patch('secrets.token_bytes', side_effect=OSError('entropy unavailable')), \
            pytest.raises(ChangePlanError) as error:
        call(model, source, options(model), **guard)
    assert error.value.reason == reason and error.value.exit_code == 3
    assert file_inventory(root) == before


@pytest.mark.parametrize('missing', ['source', 'relation'])
def test_unknown_selected_source_or_relation_is_rejected_before_lock(tmp_path, missing):
    root = tmp_path / 'project'; model, source, _ = stored_project(root, with_edges=True)
    source_id = aid('requirement', 999) if missing == 'source' else source['id']
    relation_id = rid(999) if missing == 'relation' else source['relations'][0]['relation_id']
    before = file_inventory(root)
    with no_write_attempts(), patch.object(reviews, 'project_lock', side_effect=AssertionError), \
            pytest.raises(TargetError) as error:
        record_relation_review(model, source_id, relation_id, decision='confirmed',
            reason=REASON, expected_revision=7, **options(model))
    assert error.value.reason == 'review_' + missing + '_missing'
    assert file_inventory(root) == before


@pytest.mark.parametrize('actor_type', ['ai', 'ci', 'tool'])
def test_nonhuman_actor_cannot_reach_even_structural_preflight(tmp_path, actor_type):
    root = tmp_path / 'project'; model, source, _ = stored_project(root, with_edges=True)
    args = {**options(model), 'actor': {**ACTOR, 'actor_type': actor_type}}
    before = file_inventory(root)
    with no_write_attempts(), patch.object(reviews, '_preflight_context', side_effect=AssertionError), \
            patch('secrets.token_bytes', side_effect=AssertionError), pytest.raises(AuthoringError) as error:
        call(model, source, args)
    assert error.value.reason == 'human_review_required' and error.value.exit_code == 7
    assert file_inventory(root) == before


def test_declared_historical_identity_must_be_in_the_allocation_inventory(tmp_path):
    root = tmp_path / 'project'; model, source, _ = stored_project(root, with_edges=True)
    model = rebuild(root, model, model.artifacts, previously_approved_ids=[REVIEW_ID])
    before = file_inventory(root)
    with no_write_attempts(), patch.object(reviews, 'project_lock', side_effect=AssertionError), \
            patch('secrets.token_bytes', side_effect=AssertionError), pytest.raises(AuthoringError) as error:
        call(model, source, options(model))
    assert error.value.reason == 'review_identity_inventory_mismatch' and error.value.exit_code == 6
    assert file_inventory(root) == before


def test_allocation_skips_known_archived_and_reserved_review_ids_under_the_lock(tmp_path):
    root = tmp_path / 'project'; model, source, _ = stored_project(root, with_edges=True)
    second = b'\x62' * 16; fresh = b'\x63' * 16
    reserved = 'SR-RREV-' + encode128(second)
    model = rebuild(root, model, model.artifacts, reserved_artifact_ids=[reserved],
                    previously_approved_ids=[REVIEW_ID])
    args = {**options(model), 'inventory': inventory(model, archived=[REVIEW_ID], reserved=[reserved])}
    draws = []
    def entropy(size):
        assert size == 16 and inspect_project_lock(root).data['record']['kind'] == 'writer'
        value = (ENTROPY, second, fresh)[len(draws)]; draws.append(value); return value
    with patch('secrets.token_bytes', side_effect=entropy): result = call(model, source, args)
    assert draws == [ENTROPY, second, fresh]
    assert result['review_id'] == 'SR-RREV-' + encode128(fresh)
    assert receipt(root, result)['created_ids'] == [result['review_id']]
    assert not (root / artifact_path('relation_review', REVIEW_ID, 'SR')).exists()
    assert not (root / artifact_path('relation_review', reserved, 'SR')).exists()


@pytest.mark.parametrize('endpoint', ['source', 'target'])
def test_actual_endpoint_byte_change_is_not_hidden_by_unchanged_context_fields(tmp_path, endpoint):
    root = tmp_path / 'project'; model, source, goals = stored_project(root, with_edges=True)
    artifact = source if endpoint == 'source' else goals[0]
    path = root / artifact_path(artifact['artifact_type'], artifact['id'], 'SR')
    # Tags do not belong to the J context, but actual full source bytes are bound.
    foreign = canonical_json_bytes({**artifact, 'tags': ['changed-after-observation']})
    path.write_bytes(foreign); before = file_inventory(root)
    with pytest.raises(PublicationCheckError) as error: call(model, source, options(model))
    assert error.value.reason == 'publication_base_changed' and error.value.exit_code == 6
    assert path.read_bytes() == foreign and file_inventory(root) == before


@pytest.mark.parametrize('field,new_value', [
    ('source_id', aid('goal', 2)), ('target_id', aid('goal', 2)),
    ('reviewed_at', '2027-01-01T00:00:00Z'), ('revision', 2),
    ('created_by', {'actor_type': 'human', 'actor_id': 'other-creator'}),
    ('updated_by', {'actor_type': 'human', 'actor_id': 'other-editor'}),
    ('title', 'Substituted review record')])
def test_saved_record_cannot_rebind_identity_audit_or_title(tmp_path, field, new_value):
    model, source, _ = stored_project(tmp_path / 'project', with_edges=True)
    checked, gates = planned(model, source)
    value = checked.plan.data; value.pop('change_plan_sha256')
    record = value['operations'][0]['record']; record[field] = new_value
    value['result_artifacts'][0] = {'artifact': record, 'sha256': canonical_json_sha256(record)}
    tampered = prepare_change_plan(value)
    with pytest.raises(TargetError) as error:
        assess_change_target(tampered, model, policy=reviews._POLICY, gates=gates)
    assert error.value.reason == 'review_record_binding_mismatch' and error.value.exit_code == 3


@pytest.mark.parametrize('extra', ['update', 'relation_remove', 'transition'])
def test_saved_review_plan_cannot_mix_endpoint_or_relation_changes(tmp_path, extra):
    model, source, _ = stored_project(tmp_path / 'project', with_edges=True)
    checked, gates = planned(model, source); value = checked.plan.data; value.pop('change_plan_sha256')
    candidate = {**source, 'revision': 8, 'updated_at': TIME, 'updated_by': ACTOR}
    if extra == 'update':
        candidate['statement'] = 'Changed content in the review plan.'
        operation = {'op': extra, 'target': source['id'], 'expected_revision': 7,
            'patch': [{'op': 'replace', 'path': '/statement', 'value': candidate['statement']}]}
    elif extra == 'relation_remove':
        relation = source['relations'][0]; candidate['relations'] = source['relations'][1:]
        operation = {'op': extra, 'source': source['id'], 'relation_id': relation['relation_id'],
            'expected_sha256': canonical_json_sha256(relation), 'reason': 'Remove while reviewing.'}
    else:
        candidate['maturity'] = 'proposed'
        operation = {'op': extra, 'target': source['id'], 'from': 'draft', 'to': 'proposed', 'metadata': {}}
    value['operations'].append(operation)
    value['result_artifacts'].append({'artifact': candidate, 'sha256': canonical_json_sha256(candidate)})
    artifacts = [candidate if a['id'] == source['id'] else a for a in model.artifacts]
    artifacts.append(value['operations'][0]['record'])
    value['expected_result']['model_root_sha256'] = model.manifest(artifacts, reviews._SCOPE).sha256
    mixed = prepare_change_plan(value)
    with pytest.raises(TargetError) as error:
        assess_change_target(mixed, model, policy=reviews._POLICY, gates=gates)
    assert error.value.reason == 'review_requires_one_isolated_operation' and error.value.exit_code == 3


@pytest.mark.parametrize('field', ['relation_id', 'relation_content_sha256',
                                 'source_context_sha256', 'target_context_sha256'])
def test_unmatched_historical_context_does_not_shift_new_review_time(tmp_path, field):
    model, source, _ = stored_project(tmp_path / 'project', with_edges=True)
    checked, _ = planned(model, source); old = checked.plan.data['operations'][0]['record']
    old['reviewed_at'] = '2027-01-01T00:00:00Z'
    old[field] = rid(999) if field == 'relation_id' else '0' * 64
    raw = canonical_json_bytes(old)
    context = review_context(model.artifacts, source['id'], source['relations'][0]['relation_id'])
    assert review_time([*model.artifacts, old], context, TIME) == TIME
    assert canonical_json_bytes(old) == raw


def test_mutable_host_gate_list_cannot_remove_a_bound_denial(tmp_path):
    root = tmp_path / 'project'; model, source, _ = stored_project(root, with_edges=True)
    gate = ModelGate('extension:deny-review', '1',
        lambda c: c.dependency_result({key: [] for key in c.subjects}),
        lambda c: c.result([{'reason': 'explicit_host_denial', 'severity': 'error'}]))
    gates = [gate]; args = {**options(model), 'gates': gates}
    native = reviews.ProjectSource
    def open_source(*a, **kw):
        gates.clear()
        return native(*a, **kw)
    before = file_inventory(root)
    with patch.object(reviews, 'ProjectSource', side_effect=open_source), pytest.raises(TargetError) as error:
        call(model, source, args)
    assert not gates and error.value.reason == 'complete_target_validation_required'
    assert file_inventory(root) == before


@pytest.mark.parametrize('moved', [False, True])
def test_failed_native_record_replace_retains_actual_bytes_and_blocks_blind_retry(tmp_path, moved):
    root = tmp_path / 'project'; model, source, _ = stored_project(root, with_edges=True)
    path = root / artifact_path('relation_review', REVIEW_ID, 'SR')
    before = file_inventory(root); native_replace = os.replace; attempts = []
    def replace(src, dst, **kwargs):
        if str(dst) == REVIEW_ID + '.json':
            attempts.append(str(dst))
            if moved: native_replace(src, dst, **kwargs)
            raise OSError('injected review publication failure')
        return native_replace(src, dst, **kwargs)
    with patch('secrets.token_bytes', return_value=ENTROPY), patch.object(os, 'replace', side_effect=replace), \
            pytest.raises(CommitPublicationError) as error:
        call(model, source, options(model))
    assert attempts == [REVIEW_ID + '.json'] and error.value.reason == 'publication_io_failure'
    assert error.value.exit_code == 5 and error.value.write_state == 'unknown'
    assert error.value.mutation_possible and error.value.publication_possible and error.value.published_count == 0
    if moved:
        record = json.loads(path.read_bytes())
        assert record['id'] == REVIEW_ID and record['review_state'] == 'recorded'
        assert record['maturity'] == 'approved' and record['revision'] == 1
        assert record['source_artifact_sha256'] == canonical_json_sha256(source)
    else: assert not path.exists()
    journal = json.loads((root / '.specroad/transactions/txn-review/journal.json').read_bytes())
    assert journal['state'] == 'committing' and journal['published_count'] == 0
    after = {p: rest for p, *rest in file_inventory(root)}
    for p, *rest in before: assert after[p] == rest
    retained = file_inventory(root)
    with pytest.raises(ProjectLockError) as retry: call(model, source, options(model))
    assert retry.value.reason == 'transaction_journal_blocks_lock' and retry.value.exit_code == 5
    assert file_inventory(root) == retained
