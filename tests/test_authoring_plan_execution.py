"""Saved preview plans, real native publication, original audit and replay."""
from unittest.mock import patch

import pytest

from specroad.authoring.execution import apply_authoring_plan
from specroad.authoring import execution
from specroad.authoring.update import normalize_artifact_update_input
from specroad.changes import (AuthoringError, ChangePlanError, PublicationAuthority,
    PublicationCheckError, inspect_project_lock)
from specroad.model.paths import artifact_path
from specroad.changes.receipt_values import TransactionReceipt
from support.read_only import inventory as file_inventory, no_write_attempts
from support.authoring_execution import (ACTOR, TIME, ENTROPY, KINDS,
    scenario, preview, saved, assert_effects)


@pytest.mark.parametrize('kind', KINDS)
def test_saved_preview_matches_native_files_receipt_and_replay(tmp_path, kind):
    root = tmp_path / 'project'; model, command, op, options, _, _ = scenario(root, kind)
    before = file_inventory(root)
    with no_write_attempts(), patch('secrets.token_bytes', side_effect=AssertionError('no allocation')):
        report = preview(model, command, op, options, fail_on_change=True)
    assert file_inventory(root) == before
    assert report['dry_run'] and report['would_change'] and report['exit_code'] == 1
    assert report['write_state'] == 'not_committed' and report['backend_receipt'] is None
    assert report['audit']['operations'] == [op.data] and not report['audit']['approval_granted']
    plan = saved(report); seen = []
    def authorize(request):
        assert inspect_project_lock(root).data['record']['kind'] == 'writer'
        assert request.plan.source_bytes == plan.source_bytes
        seen.append(request.plan.sha256)
        return True
    authority = PublicationAuthority('owned-plan-host', '1', authorize)
    with patch('secrets.token_bytes', side_effect=AssertionError('saved IDs only')):
        result = apply_authoring_plan(plan, model, command_id=command, transaction_id='txn-preview',
            authority=authority, gates=options['gates'])
    assert seen and set(seen) == {report['plan_sha256']}
    assert result['write_state'] == 'committed' and result['exit_code'] == 0 and not result['replayed']
    assert result['target_model_root_sha256'] == report['expected_model_root']
    assert result['audit'] == {**report['audit'], 'dry_run': False, 'write_state': 'committed'}
    assert result['completion']['current_target_verified'] and result['completion']['cleanup_completed']
    ref = result['completion']['receipts']['transaction']
    receipt = TransactionReceipt((root / ref['path']).read_bytes()).data
    assert receipt['journal']['plan_sha256'] == plan.sha256 and receipt['operations'] == [op.data]
    assert_effects(root, before, report, kind)
    before_retry = file_inventory(root)
    with no_write_attempts(), patch.object(execution, 'assess_change_target', side_effect=AssertionError('no replan')), \
            patch.object(execution, 'project_lock', side_effect=AssertionError('no lock')):
        repeated = apply_authoring_plan(plan, model, command_id=command, transaction_id='txn-retry',
            authority=authority, gates=options['gates'])
    assert repeated['replayed'] and repeated['audit'] == {**result['audit'], 'replayed': True}
    assert repeated['completion']['receipts'] == result['completion']['receipts']
    assert not repeated['completion']['current_target_verified'] and file_inventory(root) == before_retry


@pytest.mark.parametrize('kind', KINDS)
def test_existing_direct_adapter_builds_the_identical_saveable_plan(tmp_path, kind):
    root = tmp_path / 'project'; model, command, op, options, direct, entropy = scenario(root, kind)
    before = file_inventory(root)
    with no_write_attempts(): report = preview(model, command, op, options)
    plan = saved(report); seen = []
    def authorize(request):
        assert request.plan.source_bytes == plan.source_bytes
        seen.append(request.plan.sha256); return True
    with patch('secrets.token_bytes', return_value=entropy):
        result = direct({**options, 'transaction_id': 'txn-direct',
            'authority': PublicationAuthority('owned-direct-host', '1', authorize)})
    assert seen and set(seen) == {report['plan_sha256']}
    assert result['completion']['target_model_root_sha256'] == report['expected_model_root']
    assert_effects(root, before, report, kind)


@pytest.mark.parametrize('fail_on_change', [False, True])
def test_noop_preview_and_fresh_native_authorization_create_no_receipt(tmp_path, fail_on_change):
    root = tmp_path / 'project'; model, _, _, options, _, _ = scenario(root, 'update')
    source = next(a for a in model.artifacts if a['artifact_type'] == 'requirement')
    op = normalize_artifact_update_input(source, patch=[], expected_revision=7)
    before = file_inventory(root); report = preview(model, 'artifact.update', op, options, fail_on_change=fail_on_change)
    assert report['exit_code'] == 0 and not report['would_change']
    calls = []
    result = apply_authoring_plan(saved(report), model, command_id='artifact.update', transaction_id='txn-noop',
        authority=PublicationAuthority('owned-noop-host', '1', lambda request: calls.append(request.plan.sha256) or True))
    assert calls and result['no_change'] and result['completion'] is None
    assert result['write_state'] == 'not_committed' and file_inventory(root) == before


@pytest.mark.parametrize('actor_type,request_id,exit_code', [('ai', None, 2), ('ai', 'ai-request', 7), ('ci', None, 2)])
def test_preview_does_not_grant_actor_write_authority(tmp_path, actor_type, request_id, exit_code):
    root = tmp_path / 'project'; model, command, op, options, _, _ = scenario(root, 'update')
    options.update(actor={'actor_type': actor_type, 'actor_id': 'external'}, request_id=request_id)
    before = file_inventory(root)
    with no_write_attempts(): report = preview(model, command, op, options)
    assert report['target_validated'] and report['write_state'] == 'not_committed'
    with no_write_attempts(), pytest.raises(AuthoringError) as error:
        apply_authoring_plan(saved(report), model, command_id=command, transaction_id='txn-denied',
            authority=PublicationAuthority('unused', '1', lambda request: pytest.fail('no authorization callback')))
    assert error.value.exit_code == exit_code and file_inventory(root) == before


@pytest.mark.parametrize('command', ['artifact.create', 'relation.review', 'init', 'relation.status'])
def test_wrong_or_unsupported_command_cannot_relabel_an_operation(tmp_path, command):
    root = tmp_path / 'project'; model, _, op, options, _, _ = scenario(root, 'update')
    before = file_inventory(root)
    with no_write_attempts(), pytest.raises(AuthoringError): preview(model, command, op, options)
    assert file_inventory(root) == before


def test_real_authority_denial_preserves_files_and_receipts(tmp_path):
    root = tmp_path / 'project'; model, command, op, options, _, _ = scenario(root, 'update')
    report = preview(model, command, op, options); before = file_inventory(root)
    with pytest.raises(PublicationCheckError) as error:
        apply_authoring_plan(saved(report), model, command_id=command, transaction_id='txn-denied',
            authority=PublicationAuthority('deny', '1', lambda request: False))
    assert error.value.exit_code == 7 and file_inventory(root) == before


def test_changed_live_input_after_preview_cannot_be_published(tmp_path):
    root = tmp_path / 'project'; model, command, op, options, _, _ = scenario(root, 'update')
    report = preview(model, command, op, options)
    path = root / artifact_path('requirement', op.data['target'], 'SR')
    path.write_bytes(path.read_bytes() + b'\n'); before = file_inventory(root)
    with pytest.raises(ChangePlanError):
        apply_authoring_plan(saved(report), model, command_id=command, transaction_id='txn-stale',
            authority=PublicationAuthority('unused', '1', lambda request: pytest.fail('stale input')))
    assert file_inventory(root) == before
