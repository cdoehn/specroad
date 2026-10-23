"""Import refusals and real interrupted multi-object publication/recovery."""
from hashlib import sha256
import json
import os
from unittest.mock import patch

import pytest

from specroad.authoring import execution as writer
from specroad.changes import (CommittingJournal, PublicationAuthority, RecoveryAuthority,
    RecoveryError, TargetPolicy, TransactionReceipt, project_lock,
    complete_published_transaction, rollback_interrupted_transaction)
from specroad.changes.receipt_values import transaction_receipt_path, request_receipt_path
from specroad.exchange import execute_import_plan, prepare_import_plan
from specroad.exchange import execution
from specroad.mappings import ExchangeMapping
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.model.paths import artifact_path
from specroad.security import SafetyViolation
from specroad.storage.read_only import validate_project_read_only
from support.folds import goal
from support.import_execution import ALLOW, candidates, inputs, project
from support.import_planning import BASE, LOCAL, candidate, imported
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import inventory, no_write_attempts
from support.targets import gate
from test_import_execution import assert_native_files


def execute(model, values, resource, *, saved=False, options=None, **runtime):
    args = inputs(resource) | (options or {})
    raw = prepare_import_plan(model, values, **args).canonical_bytes if saved else None
    return execute_import_plan(model, values, **args,
        **(dict(plan_bytes=raw, transaction_id='txn-import', authority=ALLOW) | runtime))


def failed(result, code, *, phase, state):
    assert result['status'] == 'failed' and result['exit_code'] == code
    assert result['failure_phase'] == phase and result['write_state'] == state
    assert result['execution'] is None and not result['current_target_verified']
    assert not any(result[k] for k in ('retry_safe', 'automatic_retry', 'automatic_rollback',
                                     'approval_granted', 'input_parsed'))
    report = result['submitted_import_plan']
    if report is None:
        assert result['submitted_import_plan_sha256'] is None
    else:
        assert result['submitted_import_plan_sha256'] == canonical_json_sha256(report)
        assert not report['import_completed'] and not report['write_authorized']


@pytest.mark.parametrize('saved', [False, True], ids=['fresh', 'saved'])
@pytest.mark.parametrize('case', ['publish', 'noop', 'replay'])
def test_success_adapter_preserves_native_completion_and_historical_replay(tmp_path, saved, case):
    root = tmp_path / 'project'; m, resource = project(root)
    values = [] if case == 'noop' else candidates()
    first = execute(m, values, resource, saved=saved)
    assert first['status'] == 'success' and first['exit_code'] == 0
    assert first['execution']['no_change'] == (case == 'noop')
    if case == 'noop':
        assert first['execution']['completion'] is None
    else:
        assert_native_files(root, m, first['submitted_import_plan'])
        assert first['execution']['completion']['current_target_verified']
    if case == 'replay':
        before = inventory(root)
        with no_write_attempts():
            retry = execute(m, values, resource, saved=saved,
                options={'change_plan_id': 'CP-current-attempt'}, transaction_id='txn-retry')
        assert retry['status'] == 'success' and retry['execution']['replayed']
        assert retry['execution']['completion']['receipts'] == first['execution']['completion']['receipts']
        assert retry['execution']['audit'] == {**first['execution']['audit'], 'replayed': True}
        assert not retry['execution']['completion']['current_target_verified']
        assert retry['submitted_import_plan']['change_plan_id'] == 'CP-current-attempt'
        assert not retry['submitted_import_plan']['import_completed'] and inventory(root) == before


@pytest.mark.parametrize('saved', [False, True], ids=['fresh', 'saved'])
@pytest.mark.parametrize('case', ['loss', 'divergence', 'error-strategy', 'missing-gate', 'invalid-target'])
def test_refusal_retains_fresh_loss_conflict_and_target_diagnostics_without_writes(tmp_path, saved, case):
    root = tmp_path / 'project'
    m, resource = project(root, artifacts=[imported(local=LOCAL if case == 'divergence' else BASE)])
    values = candidates(); args = inputs(resource)
    if case == 'loss': values[0]['fields']['Unsupported'] = {'unmapped': [True, None]}
    elif case == 'error-strategy': args['strategy'] = 'error'
    elif case == 'missing-gate': args['policy'] = TargetPolicy('import', '1', ('extension:required',))
    elif case == 'invalid-target':
        args['gates'].append(gate(check=lambda c: c.result([{'reason': 'whole_target_denied', 'severity': 'error'}])))
    expected = prepare_import_plan(m, values, **args)
    assert not expected.plan_valid
    before = inventory(root)
    with no_write_attempts(), patch.object(writer, 'project_lock', side_effect=AssertionError('no invalid-plan writer')):
        result = execute(m, values, resource, options=args, saved=saved)
    failed(result, 3, phase='import_planning', state='not_committed')
    assert result['submitted_import_plan'] == expected.data
    assert result['diagnostics'][0]['reason'] == 'valid_import_plan_required'
    if case == 'loss': assert result['submitted_import_plan']['losses']
    if case == 'divergence': assert result['submitted_import_plan']['conflicts']
    if case == 'error-strategy':
        assert any(d['reason'] == 'known_identity' for d in result['submitted_import_plan']['diagnostics'])
        assert any(o['action'] == 'reject' for o in result['submitted_import_plan']['objects'])
    assert not result['recovery_required'] and inventory(root) == before


@pytest.mark.parametrize('field', ['input_bytes', 'mapping_resources', 'candidates', 'plan_valid', 'write_authorized'])
def test_untrusted_saved_report_never_becomes_failure_audit_authority(tmp_path, field):
    root = tmp_path / 'project'; m, resource = project(root); values = candidates(); args = inputs(resource)
    report = prepare_import_plan(m, values, **args); raw = report.canonical_bytes
    if field == 'input_bytes': args[field] += b'changed'
    elif field == 'mapping_resources': args[field] = [ExchangeMapping(json.dumps(resource.data, indent=2).encode())]
    elif field == 'candidates': values[0]['fields']['Text'] = 'Changed after planning.'
    else:
        data = report.data; data[field] = not data[field]; raw = canonical_json_bytes(data)
    before = inventory(root)
    with no_write_attempts(): result = execute(m, values, resource, options=args, plan_bytes=raw)
    failed(result, 3, phase='import_planning', state='not_committed')
    assert result['submitted_import_plan'] is None and not result['recovery_required']
    assert inventory(root) == before


@pytest.mark.parametrize('field,value', [('model', None), ('policy', {}), ('authority', True),
    ('gates', None), ('strict', 1), ('plan_bytes', 'not-bytes')])
def test_untyped_host_inputs_fail_without_trusting_submitted_fields(tmp_path, field, value):
    root = tmp_path / 'project'; m, resource = project(root); args = inputs(resource)
    runtime = {}
    if field == 'model': m = value
    elif field in ('authority', 'plan_bytes'): runtime[field] = value
    else: args[field] = value
    before = inventory(root)
    with no_write_attempts(): result = execute(m, candidates(), resource, options=args, **runtime)
    failed(result, 3, phase='import_planning', state='not_committed')
    assert result['submitted_import_plan'] is None and inventory(root) == before


@pytest.mark.parametrize('raises', [False, True])
def test_host_refusal_or_exception_keeps_native_exit_contract(tmp_path, raises):
    root = tmp_path / 'project'; m, resource = project(root); before = inventory(root)
    def deny(request):
        if raises: raise RuntimeError('private host detail')
        return False
    result = execute(m, candidates(), resource, authority=PublicationAuthority('denial', '1', deny))
    failed(result, 7, phase='native_execution', state='not_committed')
    assert result['diagnostics'][0]['reason'] == ('publication_authority_failed' if raises else 'publication_authorization_denied')
    assert not result['recovery_required'] and inventory(root) == before
    assert 'private host detail' not in json.dumps(result)


@pytest.mark.parametrize('saved', [False, True], ids=['fresh', 'saved'])
@pytest.mark.parametrize('path', ['specroad.json', 'profiles/core.json', 'mappings/supplier.json',
    'attachments/supplier.bin', 'untouched-artifact'])
def test_stale_live_source_preserves_external_bytes_and_has_no_completion(tmp_path, saved, path):
    root = tmp_path / 'project'; m, resource = project(root)
    if path == 'untouched-artifact': path = artifact_path('goal', goal(2)['id'], 'SR')
    (root / path).write_bytes((root / path).read_bytes() + b' ')
    before = inventory(root)
    result = execute(m, candidates(), resource, saved=saved,
        authority=PublicationAuthority('unused', '1', lambda r: pytest.fail('stale basis authorized')))
    failed(result, 6, phase='native_execution', state='not_committed')
    assert not result['recovery_required'] and inventory(root) == before
    assert result['diagnostics'][0]['reason'] == ('publication_configuration_changed' if path == 'specroad.json' else 'publication_base_changed')


def test_complete_target_gate_is_rechecked_after_plan_validation(tmp_path):
    root = tmp_path / 'project'; m, resource = project(root); calls = []
    def check(context):
        calls.append(context.subjects)
        return context.result([] if len(calls) == 1 else [{'reason': 'expired_host_context', 'severity': 'error'}])
    args = inputs(resource); args['gates'].append(gate(check=check)); before = inventory(root)
    result = execute(m, candidates(), resource, options=args)
    failed(result, 3, phase='native_execution', state='unknown')
    assert result['diagnostics'][0]['reason'] == 'complete_target_validation_required'
    assert result['recovery_required']  # The native target error carries no write-state proof.
    assert len(calls) >= 2 and all(goal(2)['id'] in ids for ids in calls)
    assert result['submitted_import_plan']['plan_valid'] and inventory(root) == before


@pytest.mark.parametrize('phase', ['planning', 'writer'])
@pytest.mark.parametrize('error,code,reason', [(OSError('private path and bytes'), 5, 'import_execution_io_failure'),
    (SafetyViolation('private path and bytes'), 7, 'unsafe_import_execution')])
def test_unclassified_failures_do_not_leak_or_invent_rollback(tmp_path, phase, error, code, reason):
    root = tmp_path / 'project'; m, resource = project(root); before = inventory(root)
    module, name = (execution, 'prepare_import_plan') if phase == 'planning' else (writer, 'ProjectSource')
    with patch.object(module, name, side_effect=error): result = execute(m, candidates(), resource)
    failed(result, code, phase='import_planning' if phase == 'planning' else 'native_execution',
        state='not_committed' if phase == 'planning' else 'unknown')
    assert result['diagnostics'] == [{'reason': reason}]
    assert result['recovery_required'] == (phase == 'writer') and inventory(root) == before
    assert 'private path and bytes' not in json.dumps(result)


@pytest.mark.parametrize('error', [RuntimeError('bug'), AssertionError('bug'), TypeError('bug')])
def test_programming_errors_remain_exceptions(tmp_path, error):
    root = tmp_path / 'project'; m, resource = project(root); before = inventory(root)
    with patch.object(writer, 'ProjectSource', side_effect=error), pytest.raises(type(error)):
        execute(m, candidates(), resource)
    assert inventory(root) == before


def test_conflicting_request_cannot_replace_original_receipt(tmp_path):
    root = tmp_path / 'project'; m, resource = project(root)
    first = execute(m, candidates(), resource); before = inventory(root)
    with no_write_attempts(): result = execute(m, [candidate('Other operation.')], resource)
    failed(result, 6, phase='native_execution', state='not_committed')
    assert result['diagnostics'][0]['reason'] == 'request_operations_conflict'
    assert result['diagnostics'][0]['existing_request_committed'] and not result['recovery_required']
    receipt = first['execution']['completion']['receipts']['transaction']
    assert sha256((root / receipt['path']).read_bytes()).hexdigest() == receipt['sha256']
    assert inventory(root) == before


def test_tampered_completion_is_not_replayed_as_success(tmp_path):
    root = tmp_path / 'project'; m, resource = project(root)
    first = execute(m, candidates(), resource)
    ref = first['execution']['completion']['receipts']['transaction']; path = root / ref['path']
    path.write_bytes(path.read_bytes() + b'\n'); before = inventory(root)
    with no_write_attempts(): result = execute(m, candidates(), resource)
    failed(result, 6, phase='native_execution', state='unknown')
    assert result['recovery_required'] and inventory(root) == before


@pytest.mark.parametrize('saved', [False, True], ids=['fresh', 'saved'])
@pytest.mark.parametrize('fail_at,moved', [(1, False), (1, True), (2, False), (2, True)])
def test_interrupted_import_is_quarantined_then_recovers_exact_basis_or_full_target(tmp_path, saved, fail_at, moved):
    root = tmp_path / 'project'; m, resource = project(root); values = candidates()
    report = prepare_import_plan(m, values, **inputs(resource)); native_replace = os.replace; calls = []
    targets = {a['artifact']['id'] + '.json' for a in report.data['change_plan']['result_artifacts']}
    assert len(targets) == 2
    def replace(src, dst, **kwargs):
        if str(dst) in targets:
            calls.append(str(dst))
            if len(calls) == fail_at:
                if moved: native_replace(src, dst, **kwargs)
                raise OSError('synthetic interrupted import')
        return native_replace(src, dst, **kwargs)
    with patch.object(os, 'replace', side_effect=replace): result = execute(m, values, resource, saved=saved)
    failed(result, 5, phase='native_execution', state='unknown')
    assert len(calls) == fail_at and result['recovery_required']
    assert result['diagnostics'][0]['reason'] == 'publication_io_failure'
    path = '.specroad/transactions/txn-import/journal.json'
    journal = CommittingJournal((root / path).read_bytes())
    assert journal.data['published_count'] == fail_at - 1
    assert not (root / transaction_receipt_path('txn-import')).exists()
    assert not (root / request_receipt_path('import-execution-request')).exists()
    before = inventory(root)
    with no_write_attempts():
        read = validate_project_read_only(root, profile_resources=m.profile_resources, core_key=m.profile_resources[0].key)
    assert not read.passed and read.exit_code == 5 and not read.data['model_loaded']
    assert read.data['operational']['recovery_required'] and inventory(root) == before
    retry = execute(m, values, resource, transaction_id='txn-retry')
    assert retry['status'] == 'failed' and retry['diagnostics'][0]['reason'] == 'transaction_journal_blocks_lock'
    assert inventory(root) == before
    data = journal.data
    options = dict(kind='recovery', command='recover run', project_id=data['project_id'],
        request_id=data['request_id'], transaction_id=data['transaction_id'])
    authority = RecoveryAuthority('synthetic-explicit-recovery', '1', lambda r: True)
    full = fail_at == 2 and moved
    with project_lock(root, **options) as held:
        if full:
            with pytest.raises(RecoveryError) as caught:
                rollback_interrupted_transaction('txn-import', held_lock=held, authority=authority,
                    expected_journal_sha256=journal.sha256)
            assert caught.value.reason == 'recovery_full_target_requires_completion'
            recovered = complete_published_transaction('txn-import', held_lock=held, authority=authority,
                expected_journal_sha256=journal.sha256)
        else:
            recovered = rollback_interrupted_transaction('txn-import', held_lock=held, authority=authority,
                expected_journal_sha256=journal.sha256)
    if full:
        assert recovered.data['commit_completed'] and recovered.data['current_target_verified']
        assert recovered.data['normative_writes'] == 0
        assert_native_files(root, m, report.data)
        ref = recovered.data['receipts']['transaction']
        receipt = TransactionReceipt((root / ref['path']).read_bytes())
        assert receipt.sha256 == ref['sha256'] and receipt.data['operations'] == report.data['operations']
        with no_write_attempts(): repeated = execute(m, values, resource, saved=saved)
        assert repeated['status'] == 'success' and repeated['execution']['replayed']
        assert repeated['execution']['completion']['receipts'] == recovered.data['receipts']
    else:
        assert recovered.data['rollback_completed'] and recovered.data['state'] == 'rolled_back'
        for name, raw in m.source_files.items(): assert (root / name).read_bytes() == raw
        assert not (root / artifact_path('goal', values[1]['new_artifact']['id'], 'SR')).exists()
        ref = recovered.data['receipt']; raw = (root / ref['path']).read_bytes()
        receipt = json.loads(raw)
        assert ref['path'] == transaction_receipt_path('txn-import')
        assert sha256(raw).hexdigest() == ref['sha256']
        assert receipt['format_version'] == 'recovery-transaction-receipt-v1'
        assert receipt['action'] == 'rollback' and receipt['outcome'] == 'rolled_back'
        assert receipt['result_model_root_sha256'] == journal.data['base_model_root_sha256']
        assert receipt['journal'] == json.loads((root / path).read_bytes())
        assert receipt['journal_sha256'] == sha256((root / path).read_bytes()).hexdigest()
        audit = receipt['recovery_audit']; audit_raw = (root / audit['path']).read_bytes()
        assert sha256(audit_raw).hexdigest() == audit['sha256']
        assert json.loads(audit_raw)['authority_id'] == authority.authority_id
        assert not (root / request_receipt_path('import-execution-request')).exists()
    assert (root / 'foreign.bin').read_bytes() == b'Unmanaged bytes stay unchanged.\x00'


@pytest.mark.parametrize('stage', ['publish_prepared_journal', 'finalize_committing_journal', 'cleanup_completed_transaction'])
def test_late_failure_retains_real_journal_and_receipts_without_automatic_action(tmp_path, stage):
    root = tmp_path / 'project'; m, resource = project(root); values = candidates()
    with patch.object(writer, stage, side_effect=OSError('private interruption')) as call:
        result = execute(m, values, resource)
    failed(result, 5, phase='native_execution', state='unknown')
    assert call.call_count == 1 and result['recovery_required']
    state = json.loads((root / '.specroad/transactions/txn-import/journal.json').read_bytes())['state']
    expected = {'publish_prepared_journal': 'prepared', 'finalize_committing_journal': 'committing',
        'cleanup_completed_transaction': 'committed'}[stage]
    assert state == expected
    if state == 'prepared':
        for name, raw in m.source_files.items(): assert (root / name).read_bytes() == raw
        assert not (root / artifact_path('goal', values[1]['new_artifact']['id'], 'SR')).exists()
    else: assert_native_files(root, m, result['submitted_import_plan'])
    assert (root / transaction_receipt_path('txn-import')).exists() == (state == 'committed')
    assert (root / request_receipt_path('import-execution-request')).exists() == (state == 'committed')


@pytest.mark.parametrize('mode', ['core', 'pyz'])
def test_failure_adapter_is_available_without_site_packages(tmp_path, mode):
    body = 'import json\nfrom specroad.exchange import execute_import_plan\n'
    body += 'print(json.dumps(execute_import_plan(None, [], policy=None, authority=None, transaction_id="txn-test")))\n'
    if mode == 'core': result = run_core(body, tmp_path, capture=True)
    else:
        _, package = build_distribution(tmp_path / 'distribution')
        result = run_python(['-I', '-S', '-B', '-c', 'import sys;sys.path.insert(0,' + repr(str(package)) + ')\n' + body], tmp_path, capture=True)
    assert result.returncode == 0, result.stderr
    value = json.loads(result.stdout)
    failed(value, 3, phase='import_planning', state='not_committed')
    assert value['submitted_import_plan'] is None and not value['recovery_required']
