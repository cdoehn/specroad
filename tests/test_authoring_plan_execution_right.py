"""Native failures retain evidence; one real authoring chain survives retries."""
import json
import os
from unittest.mock import patch

import pytest

from specroad.authoring import execution
from specroad.authoring.creation import _draft
from specroad.authoring.inputs import normalize_artifact_create_input
from specroad.authoring.update import normalize_artifact_update_input
from specroad.authoring.lifecycle import normalize_retire_input
from specroad.changes import ChangeOperation, PublicationAuthority, prepare_change_plan
from specroad.changes.relation_inputs import normalize_relation_add_input, _addition
from specroad.changes.reviews import review_context, prepare_review_record
from specroad.model.canonical import canonical_json_bytes
from specroad.model.identities import ArtifactIdentity
from specroad.model.identity_tokens import encode128
from specroad.model.paths import artifact_path
from specroad.model.relation_values import RelationIdentity
from specroad.validation import ModelGate
from support.read_only import inventory as file_inventory, no_write_attempts
from test_artifact_creation import project
from test_authoring_inputs import fields
from test_negative_relation_review_right import current
from support.authoring_execution import (ACTOR, ALLOW, scenario, preview, saved,
    execute, assert_failed, retained_review_gates)


@pytest.mark.parametrize('actor_type,request_id,code', [('ai', None, 2), ('ai', 'ai-request', 7), ('ci', None, 2)])
def test_refused_actor_has_owned_failure_audit_without_io(tmp_path, actor_type, request_id, code):
    root = tmp_path / 'project'; model, command, op, options, _, _ = scenario(root, 'update')
    options.update(actor={'actor_type': actor_type, 'actor_id': 'untrusted'}, request_id=request_id)
    plan = saved(preview(model, command, op, options)); before = file_inventory(root)
    with no_write_attempts(): result = execute(plan, model, command)
    assert_failed(result, plan, code)
    assert not result['recovery_required'] and file_inventory(root) == before


@pytest.mark.parametrize('command', ['artifact.create', 'relation.review', 'init', 'relation.status'])
def test_failure_report_cannot_reclassify_saved_operation(tmp_path, command):
    root = tmp_path / 'project'; model, original, op, options, _, _ = scenario(root, 'update')
    plan = saved(preview(model, original, op, options)); before = file_inventory(root)
    with no_write_attempts(): result = execute(plan, model, command)
    assert_failed(result, plan, 2)
    assert result['command_id'] == (command if command in ('artifact.create', 'relation.review') else None)
    assert file_inventory(root) == before


@pytest.mark.parametrize('raises', [False, True])
def test_authority_refusal_or_failure_never_invents_completion(tmp_path, raises):
    root = tmp_path / 'project'; model, command, op, options, _, _ = scenario(root, 'update')
    plan = saved(preview(model, command, op, options)); before = file_inventory(root)
    def authorize(request):
        if raises: raise RuntimeError('host failure')
        return False
    result = execute(plan, model, command, authority=PublicationAuthority('deny', '1', authorize))
    assert_failed(result, plan, 7)
    assert result['diagnostics'][0]['reason'] == ('publication_authority_failed' if raises else 'publication_authorization_denied')
    assert file_inventory(root) == before


def test_stale_live_bytes_report_failure_without_erasing_external_change(tmp_path):
    root = tmp_path / 'project'; model, command, op, options, _, _ = scenario(root, 'update')
    plan = saved(preview(model, command, op, options))
    path = root / artifact_path('requirement', op.data['target'], 'SR')
    path.write_bytes(path.read_bytes() + b'\n'); before = file_inventory(root)
    result = execute(plan, model, command,
        authority=PublicationAuthority('unused', '1', lambda request: pytest.fail('stale input authorized')))
    assert result['status'] == 'failed' and result['exit_code'] == 6
    assert result['completion'] is None and not result['current_target_verified']
    assert file_inventory(root) == before


def test_conflicting_request_preserves_original_completion_and_all_bytes(tmp_path):
    root = tmp_path / 'project'; model, command, op, options, _, _ = scenario(root, 'update')
    plan = saved(preview(model, command, op, options)); first = execute(plan, model, command)
    assert first['status'] == 'success'
    fresh = current(root, model); source = next(a for a in fresh.artifacts if a['id'] == op.data['target'])
    changed = normalize_artifact_update_input(source, expected_revision=8,
        options=[('--set', '/statement="A conflicting second request."')])
    conflict = saved(preview(fresh, command, changed, {**options, 'change_plan_id': 'CP-conflict'}))
    before = file_inventory(root)
    with no_write_attempts(): result = execute(conflict, fresh, command)
    assert_failed(result, conflict, 6)
    assert result['diagnostics'][0]['reason'] == 'request_operations_conflict'
    assert result['diagnostics'][0]['existing_request_committed'] and not result['recovery_required']
    with no_write_attempts(): repeated = execute(plan, fresh, command)
    assert repeated['status'] == 'success' and repeated['replayed']
    assert repeated['completion']['receipts'] == first['completion']['receipts']
    assert file_inventory(root) == before


def test_retry_reports_original_actor_time_and_plan_not_new_envelope(tmp_path):
    root = tmp_path / 'project'; model, command, op, options, _, _ = scenario(root, 'update')
    plan = saved(preview(model, command, op, options)); first = execute(plan, model, command)
    value = plan.data; value.pop('change_plan_sha256')
    value.update(actor={'actor_type': 'human', 'actor_id': 'later-human'},
                 planned_at='2027-01-01T00:00:00Z', change_plan_id='CP-later')
    retry = prepare_change_plan(value); before = file_inventory(root)
    with no_write_attempts(): repeated = execute(retry, current(root, model), command)
    assert repeated['status'] == 'success' and repeated['replayed']
    assert repeated['audit'] == {**first['audit'], 'replayed': True}
    assert repeated['plan_sha256'] == plan.sha256 != retry.sha256
    assert not repeated['completion']['current_target_verified'] and file_inventory(root) == before


def test_required_host_gate_survives_mutation_during_source_read(tmp_path):
    root = tmp_path / 'project'; model, command, op, options, _, _ = scenario(root, 'retire')
    plan = saved(preview(model, command, op, options)); before = file_inventory(root); checks = []
    def deny(context):
        checks.append(context.subjects)
        return context.result([{'reason': 'host_lifecycle_denied', 'severity': 'error'}])
    supplied = [ModelGate('lifecycle', 'host-denial-v1',
        lambda c: c.dependency_result({key: list(c.all_ids) for key in c.subjects}), deny)]
    native = execution.ProjectSource
    def read(*args, **kwargs):
        supplied.clear()
        return native(*args, **kwargs)
    with patch.object(execution, 'ProjectSource', side_effect=read):
        result = execute(plan, model, command, gates=supplied)
    assert supplied == [] and checks
    assert result['status'] == 'failed' and result['diagnostics'][0]['reason'] == 'complete_target_validation_required'
    assert result['completion'] is None and file_inventory(root) == before


@pytest.mark.parametrize('moved', [False, True])
def test_failed_replace_preserves_real_bytes_and_unacknowledged_recovery(tmp_path, moved):
    root = tmp_path / 'project'; model, command, op, options, _, _ = scenario(root, 'retire')
    report = preview(model, command, op, options); plan = saved(report)
    identity = op.data['target']; path = root / artifact_path('requirement', identity, 'SR')
    original = path.read_bytes(); native_replace = os.replace; calls = []
    def replace(src, dst, **kwargs):
        if str(dst) == identity + '.json':
            calls.append(str(dst))
            if moved: native_replace(src, dst, **kwargs)
            raise OSError('injected replace failure')
        return native_replace(src, dst, **kwargs)
    with patch.object(os, 'replace', side_effect=replace): result = execute(plan, model, command)
    assert_failed(result, plan, 5, state='unknown')
    assert calls == [identity + '.json'] and result['recovery_required']
    assert result['diagnostics'][0]['reason'] == 'publication_io_failure'
    assert result['diagnostics'][0]['published_count_acknowledged'] == 0
    expected = canonical_json_bytes(report['plan']['result_artifacts'][0]['artifact']) if moved else original
    assert path.read_bytes() == expected
    journal = json.loads((root / '.specroad/transactions/txn-execution/journal.json').read_bytes())
    assert journal['state'] == 'committing' and journal['published_count'] == 0
    retained = file_inventory(root); retry = execute(plan, model, command, transaction_id='txn-retry')
    assert retry['status'] == 'failed' and retry['diagnostics'][0]['reason'] == 'transaction_journal_blocks_lock'
    assert file_inventory(root) == retained


def test_modified_completion_proof_is_not_a_successful_replay(tmp_path):
    root = tmp_path / 'project'; model, command, op, options, _, _ = scenario(root, 'update')
    plan = saved(preview(model, command, op, options)); first = execute(plan, model, command)
    ref = first['completion']['receipts']['transaction']; path = root / ref['path']
    path.write_bytes(path.read_bytes() + b'\n'); before = file_inventory(root)
    with no_write_attempts(): result = execute(plan, current(root, model), command)
    assert result['status'] == 'failed' and result['completion'] is None
    assert result['write_state'] == 'unknown' and result['recovery_required']
    assert file_inventory(root) == before


def test_mutating_detached_preview_cannot_retarget_saved_bytes(tmp_path):
    root = tmp_path / 'project'; model, command, op, options, _, _ = scenario(root, 'update')
    report = preview(model, command, op, options); plan = saved(report)
    expected = canonical_json_bytes(report['plan']['result_artifacts'][0]['artifact'])
    report['plan']['result_artifacts'][0]['artifact']['statement'] = 'Injected into detached output.'
    report['audit']['actor']['actor_id'] = 'injected'
    result = execute(plan, model, command)
    assert result['status'] == 'success' and result['audit']['actor'] == ACTOR
    assert (root / artifact_path('requirement', op.data['target'], 'SR')).read_bytes() == expected


def test_reparsed_plan_integrity_failure_has_no_trusted_plan_audit(tmp_path):
    root = tmp_path / 'project'; model, command, op, options, _, _ = scenario(root, 'update')
    plan = saved(preview(model, command, op, options)); value = plan.data
    value['change_plan_sha256'] = '0' * 64
    object.__setattr__(plan, 'source_bytes', canonical_json_bytes(value))
    before = file_inventory(root)
    with no_write_attempts(): result = execute(plan, model, command)
    assert result['status'] == 'failed' and result['exit_code'] == 3
    assert not result['audit']['plan_integrity_checked'] and result['plan_sha256'] is None
    assert result['audit']['planned_created_ids'] is None and result['completion'] is None
    assert result['diagnostics'][0]['reason'] == 'change_plan_hash_mismatch'
    assert file_inventory(root) == before


def test_unclassified_io_failure_does_not_leak_message_or_claim_rollback(tmp_path):
    root = tmp_path / 'project'; model, command, op, options, _, _ = scenario(root, 'update')
    plan = saved(preview(model, command, op, options)); before = file_inventory(root)
    with patch.object(execution, 'ProjectSource', side_effect=OSError('private submitted content')):
        result = execute(plan, model, command)
    assert_failed(result, plan, 5, state='unknown')
    assert result['diagnostics'] == [{'reason': 'authoring_execution_io_failure'}]
    assert result['recovery_required'] and file_inventory(root) == before


def test_real_create_update_link_review_retire_chain_replays_without_new_ids(tmp_path):
    root = tmp_path / 'project'; model, _ = project(root)
    goal = model.artifacts[0]; original_goal = canonical_json_bytes(goal); history = []
    requirement_id = 'SR-REQ-' + encode128(b'\x41' * 16)
    relation_id = 'REL-' + encode128(b'\x42' * 16)
    review_id = 'SR-RREV-' + encode128(b'\x43' * 16)
    for index, kind in enumerate(('create', 'update', 'add', 'review', 'retire')):
        model = current(root, model); time = '2026-10-11T10:0' + str(index) + ':00Z'; gates = ()
        source = next((a for a in model.artifacts if a['id'] == requirement_id), None)
        if kind == 'create':
            artifact = _draft(normalize_artifact_create_input('requirement', fields('requirement')),
                ArtifactIdentity(requirement_id, 'random128-v1', 'requirement', 'SR'), ACTOR, time, model.configuration)
            op = ChangeOperation({'op': 'create', 'artifact': artifact, 'result_id': requirement_id})
            command = 'artifact.create'
        elif kind == 'update':
            op = normalize_artifact_update_input(source, expected_revision=1,
                options=[('--set', '/statement="The real chain preserves one identity."')])
            command = 'artifact.update'
        elif kind == 'add':
            op = _addition(normalize_relation_add_input(requirement_id, 'addresses', goal['id'], rationale='Reviewed chain.'),
                RelationIdentity(relation_id, 'random128-v1'), ACTOR, time)
            command = 'relation.add'
        elif kind == 'review':
            context = review_context(model.artifacts, requirement_id, relation_id)
            record = prepare_review_record(context, ArtifactIdentity(review_id, 'random128-v1', 'relation_review', 'SR'),
                actor=ACTOR, planned_at=time, decision='confirmed', reason='Inspected the linked statements.')
            op = ChangeOperation({'op': 'relation_review_record', 'source': requirement_id, 'target': goal['id'],
                'record': record, 'approval_withdrawals': [], 'expected_revision': 3})
            command = 'relation.review'
        else:
            gates = retained_review_gates(model, source, record, time)
            op = normalize_retire_input(source, expected_revision=3, reason='Chain complete.')
            command = 'lifecycle.transition'
        options = dict(actor=ACTOR, planned_at=time, change_plan_id='CP-chain-' + kind,
                       request_id='chain-' + kind, gates=gates)
        before = file_inventory(root)
        with no_write_attempts(), patch('secrets.token_bytes', side_effect=AssertionError('no new IDs')):
            report = preview(model, command, op, options)
        assert report['target_validated'] and file_inventory(root) == before
        plan = saved(report)
        with patch('secrets.token_bytes', side_effect=AssertionError('saved IDs only')):
            result = execute(plan, model, command, transaction_id='txn-chain-' + kind, gates=gates)
        assert result['status'] == 'success' and result['completion']['current_target_verified']
        assert result['target_model_root_sha256'] == report['expected_model_root']
        for item in report['plan']['result_artifacts']:
            value = item['artifact']; path = artifact_path(value['artifact_type'], value['id'], 'SR')
            assert (root / path).read_bytes() == canonical_json_bytes(value)
        fresh = current(root, model); retained = file_inventory(root)
        with no_write_attempts(), patch.object(execution, 'project_lock', side_effect=AssertionError('no retry lock')), \
                patch('secrets.token_bytes', side_effect=AssertionError('no retry allocation')):
            repeated = execute(plan, fresh, command, transaction_id='unused-retry', gates=gates)
        assert repeated['status'] == 'success' and repeated['replayed']
        assert repeated['audit'] == {**result['audit'], 'replayed': True}
        assert repeated['completion']['receipts'] == result['completion']['receipts']
        assert not repeated['completion']['current_target_verified'] and file_inventory(root) == retained
        requirement = next(a for a in fresh.artifacts if a['id'] == requirement_id)
        assert requirement['revision'] == (1, 2, 3, 3, 4)[index]
        assert requirement['maturity'] == ('retired' if kind == 'retire' else 'draft')
        assert {a['id'] for a in fresh.artifacts} == {goal['id'], requirement_id} | ({review_id} if index >= 3 else set())
        assert (root / artifact_path('goal', goal['id'], 'SR')).read_bytes() == original_goal
        history.append((plan, command, result))
    assert requirement['relations'][0]['relation_id'] == relation_id and len(requirement['relations']) == 1
    assert (root / artifact_path('relation_review', review_id, 'SR')).read_bytes() == canonical_json_bytes(record)
    plan, command, first = history[0]; before = file_inventory(root)
    with no_write_attempts(): historical = execute(plan, current(root, model), command)
    assert historical['status'] == 'success' and historical['audit'] == {**first['audit'], 'replayed': True}
    assert historical['audit']['created_ids'] == [requirement_id]
    assert not historical['completion']['current_target_verified'] and file_inventory(root) == before
