"""Import input replay, semantic duplicates and native interrupted-set recovery."""
import json
import os
from unittest.mock import patch

import pytest

from specroad.authoring.evidence_import import resolve_generic_import_request
from specroad.authoring.execution import execute_authoring_plan
from specroad.changes import (CommittingJournal, CommittedJournal, RolledBackJournal,
    LockRecord, RecoveryAuthority, project_lock, transaction_recovery_lock,
    complete_published_transaction, rollback_interrupted_transaction,
    cleanup_recovered_transaction, TargetModel)
from specroad.changes.evidence_import import (
    diagnose_generic_import_duplicates, EvidenceImportDuplicate)
from specroad.model.canonical import canonical_json_bytes
from specroad.model.errors import ModelError
from specroad.model.paths import artifact_path
from specroad.storage.project import ProjectSource
from specroad.validation import ModelDocument
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import inventory, no_write_attempts
from support.records import ref
from test_evidence_import_transaction import import_project, saved, preview, apply, SOURCE
from test_evidence_recording import ACTOR, ALLOW, extend

RECOVER = RecoveryAuthority('import-recovery-test', '1', lambda request: True)


def retry(root, raw, **extra):
    options = dict(source_bytes=raw, source_path=SOURCE, policy='abort_import',
        title='Imported measurement', actor=ACTOR, request_id='import-1')
    options.update(extra)
    return resolve_generic_import_request(ProjectSource(root), **options)


def current(model, plan):
    return TargetModel(model.configuration_bytes, model.binding, (*model.documents,
        *(ModelDocument(artifact_path('evidence', op['evidence']['id'], 'SR'),
            canonical_json_bytes(op['evidence'])) for op in plan.data['operations'])),
        profile=model.profile, resource_files=model.resource_files,
        attachments=model.attachment_descriptors)


def test_input_retry_precedes_ids_plans_and_current_subject_validation(tmp_path):
    root = tmp_path / 'project'; model = import_project(root, configured=True)
    raw = model.source_files[SOURCE]; plan = saved(model); first = apply(plan, model)
    # Historical replay needs no fresh TargetModel or intact current subjects.
    subject = next(d for d in model.documents if ref() in d.path)
    (root / subject.path).write_bytes(b'current subject is no longer parseable')
    before = inventory(root)
    with no_write_attempts(), patch('secrets.token_bytes', side_effect=AssertionError('allocation')), \
            patch('specroad.changes.evidence_import._input', side_effect=AssertionError('new preparation')), \
            patch('specroad.authoring.execution.project_lock', side_effect=AssertionError('writer lock')):
        result = retry(root, raw, configuration_id=ref('CFG'),
            actor={'actor_type': 'human', 'actor_id': 'later-observer'})
    assert result['replayed'] and result['audit'] == {**first['audit'], 'replayed': True}
    assert result['audit']['created_ids'] == [ref('EVD', '1'), ref('EVD', '2')]
    assert not result['completion']['current_target_verified']
    assert inventory(root) == before
    result['audit']['operations'].clear()
    assert len(retry(root, raw, configuration_id=ref('CFG'))['audit']['operations']) == 2


@pytest.mark.parametrize('field', ['bytes', 'mapping', 'run', 'configuration', 'tool',
    'environment', 'result', 'source_path', 'policy', 'title', 'configuration_id'])
def test_changed_bound_input_is_conflict_six_before_any_planning(tmp_path, field):
    root = tmp_path / 'project'; model = import_project(root); raw = model.source_files[SOURCE]
    apply(saved(model), model)
    options = {}
    value = json.loads(raw)
    if field == 'bytes': raw += b'\n'
    elif field == 'mapping': value['results'][0]['check_id'] = 'other'
    elif field == 'run': value['run']['run_id'] = 'synthetic-meter:other'
    elif field == 'configuration': value['configuration_policy'] = 'bound'
    elif field == 'tool': value['tool']['version'] = '2'
    elif field == 'environment': value['environment']['platform'] = 'other'
    elif field == 'result': value['results'][0]['result'] = 'passed'
    else:
        options[field] = {'source_path': 'attachments/other.json',
            'policy': 'skip_invalid_with_diagnostic', 'title': 'Different title',
            'configuration_id': ref('CFG')}[field]
    if field in ('mapping', 'run', 'configuration', 'tool', 'environment', 'result'):
        raw = canonical_json_bytes(value)
    before = inventory(root)
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        retry(root, raw, **options)
    assert caught.value.reason == 'request_operations_conflict' and caught.value.exit_code == 6
    assert caught.value.diagnostic()['write_state'] == 'not_committed'
    assert inventory(root) == before


@pytest.mark.parametrize('request_id', [None, 'unknown-request'])
def test_absent_confirmed_input_retry_is_read_only_and_grants_no_write(tmp_path, request_id):
    root = tmp_path / 'project'; model = import_project(root); before = inventory(root)
    with no_write_attempts():
        assert retry(root, model.source_files[SOURCE], request_id=request_id) is None
    assert inventory(root) == before


@pytest.mark.parametrize('actor_type', ['ai', 'ci'])
def test_input_retry_retains_native_request_policy_before_receipt_lookup(tmp_path, actor_type):
    root = tmp_path / 'project'; model = import_project(root); before = inventory(root)
    with no_write_attempts(), patch('specroad.authoring.evidence_import._read_confirmed_request',
            side_effect=AssertionError('policy precedes disk receipt')), pytest.raises(ModelError):
        retry(root, model.source_files[SOURCE], request_id=None,
            actor={'actor_type': actor_type, 'actor_id': 'declared-client'})
    assert inventory(root) == before


def test_request_used_by_another_operation_is_not_an_import_replay(tmp_path):
    from test_evidence_recording import measurement, plan_for, apply as apply_record
    root = tmp_path / 'project'; model = import_project(root)
    plan = plan_for(model, measurement(model), request_id='import-1')
    apply_record(plan, model)
    before = inventory(root)
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        retry(root, model.source_files[SOURCE])
    assert caught.value.reason == 'request_operations_conflict' and caught.value.exit_code == 6
    assert inventory(root) == before


@pytest.mark.parametrize('mutation', ['request', 'transaction', 'marker', 'symlink'])
def test_damaged_completion_is_neither_replay_nor_new_request(tmp_path, mutation):
    root = tmp_path / 'project'; model = import_project(root)
    apply(saved(model), model)
    if mutation in ('request', 'symlink'):
        path, = (root / '.specroad/requests').rglob('*.json')
    elif mutation == 'transaction':
        path, = (root / '.specroad/transactions/receipts').rglob('transaction.json')
    else:
        path, = (root / '.specroad/transactions/receipts').rglob('committed.json')
    if mutation == 'symlink':
        copy = tmp_path / 'outside-receipt.json'; copy.write_bytes(path.read_bytes())
        path.unlink(); path.symlink_to(copy)
    else: path.write_bytes(b'{}')
    before = inventory(root)
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        retry(root, model.source_files[SOURCE])
    if mutation == 'symlink':
        assert caught.value.exit_code == 7
        assert caught.value.reason == 'unsafe_evidence_import_receipt'
    assert inventory(root) == before


def test_receipt_io_failure_has_diagnostic_code_and_is_not_an_absence(tmp_path):
    root = tmp_path / 'project'; model = import_project(root); before = inventory(root)
    with no_write_attempts(), patch('specroad.authoring.evidence_import._read_confirmed_request',
            side_effect=OSError(5, 'untrusted host details')), pytest.raises(ModelError) as caught:
        retry(root, model.source_files[SOURCE])
    diagnostic = caught.value.diagnostic()
    assert diagnostic['exit_code'] == 5 and diagnostic['reason'] == 'evidence_import_receipt_io_failure'
    assert diagnostic['recovery_required'] and diagnostic['write_state'] == 'unknown'
    assert 'untrusted host details' not in json.dumps(diagnostic)
    assert inventory(root) == before


@pytest.mark.parametrize('request_id', [None, 'different-request'])
def test_semantic_duplicate_reports_each_observation_and_original_ids(tmp_path, request_id):
    root = tmp_path / 'project'; model = import_project(root); plan = saved(model)
    apply(plan, model); updated = current(model, plan); before = inventory(root)
    with no_write_attempts():
        report = diagnose_generic_import_duplicates(updated, source_path=SOURCE, policy='abort_import')
        with pytest.raises(EvidenceImportDuplicate) as caught:
            preview(updated, request_id=request_id, evidence_ids=[ref('EVD', '3'), ref('EVD', '4')])
    assert report['duplicate_count'] == 2 and not report['write_authorized']
    assert report['format_version'] == 'evidence-semantic-duplicate-v1'
    assert [(m['candidate_index'], m['source_pointer'], m['evidence_ids']) for m in report['matches']] == [
        (0, '/results/0', [ref('EVD', '1')]), (1, '/results/1', [ref('EVD', '2')])]
    assert caught.value.diagnostic()['semantic_duplicates'] == report['matches']
    report['matches'].clear()
    assert len(caught.value.diagnostic()['semantic_duplicates']) == 2
    assert inventory(root) == before


def test_duplicate_detection_ignores_import_packaging_and_audit_but_retains_all_matches(tmp_path):
    root = tmp_path / 'project'; model = import_project(root); plan = saved(model)
    value = plan.data['operations'][0]['evidence']
    value.update(title='Other title', origin='recorded_manual', id=ref('EVD', '3'))
    value.pop('provenance'); value.pop('attachments')
    value['subjects'].reverse()
    updated = extend(model, value)
    updated = extend(updated, {**value, 'id': ref('EVD', '4')})
    before = inventory(root)
    with no_write_attempts():
        report = diagnose_generic_import_duplicates(updated, source_path=SOURCE, policy='abort_import')
    assert report['duplicate_count'] == 1
    assert report['matches'][0]['evidence_ids'] == [ref('EVD', '3'), ref('EVD', '4')]
    assert inventory(root) == before


@pytest.mark.parametrize('field', ['result', 'produced_at', 'run', 'product', 'producer',
                                 'tool', 'environment', 'configuration', 'subject'])
def test_distinct_measurements_are_not_silently_merged(tmp_path, field):
    root = tmp_path / 'project'; model = import_project(root); plan = saved(model)
    value = plan.data['operations'][0]['evidence']
    if field == 'result': value['result'] = 'passed'
    elif field == 'produced_at': value['produced_at'] = '2026-10-19T22:00:00Z'
    elif field == 'run': value['run_context']['run_id'] = 'synthetic-meter:other'
    elif field == 'product': value['run_context']['subject_state_sha256'] = 'b' * 64
    elif field == 'producer': value['producer']['producer_id'] = 'other'
    elif field == 'tool': value['tool']['version'] = 'other'
    elif field == 'environment': value['environment']['platform'] = 'other'
    elif field == 'configuration':
        value.update(configuration_policy='bound', configuration_hash='b' * 64)
    else: value['subjects'][0]['artifact_sha256'] = 'b' * 64
    report = diagnose_generic_import_duplicates(extend(model, value),
        source_path=SOURCE, policy='abort_import')
    assert report['duplicate_count'] == 0 and report['matches'] == []
    assert not report['current_target_verified'] and not report['approval_granted']


def test_equal_occurrences_in_one_new_source_remain_two_records(tmp_path):
    def repeated(value): value['results'][1] = dict(value['results'][0])
    root = tmp_path / 'project'; model = import_project(root, mutate=repeated)
    assert diagnose_generic_import_duplicates(model, source_path=SOURCE,
        policy='abort_import')['matches'] == []
    result = apply(saved(model), model)
    assert result['audit']['created_ids'] == [ref('EVD', '1'), ref('EVD', '2')]
    values = [op['evidence'] for op in result['audit']['operations']]
    assert values[0]['produced_at'] == values[1]['produced_at']
    assert len({v['provenance'][0]['extensions']['specroad.evidence-import']['source_pointer']
                for v in values}) == 2


def recover(root, journal, *, complete, crashed=False):
    options = dict(project_id=journal.data['project_id'], request_id='import-1')
    if crashed:
        lock = LockRecord((root / '.specroad/locks/project.json').read_bytes())
        context = transaction_recovery_lock(root, 'txn-import', **options,
            expected_lock_sha256=lock.sha256, expected_journal_sha256=journal.sha256,
            authority=RECOVER, actor=ACTOR, reason='Explicit stopped import recovery', force=True)
    else:
        context = project_lock(root, kind='recovery', command='recover run',
            transaction_id='txn-import', **options)
    with context as held:
        action = complete_published_transaction if complete else rollback_interrupted_transaction
        result = action('txn-import', held_lock=held, authority=RECOVER,
            expected_journal_sha256=journal.sha256)
        raw = (root / journal.path).read_bytes()
        terminal = (CommittedJournal if complete else RolledBackJournal)(raw)
        cleanup_recovered_transaction('txn-import', held_lock=held,
            authority=RECOVER, expected_journal_sha256=terminal.sha256)
    return result.data


def assert_recovered_set(root, model, plan, *, complete):
    for path, raw in model.source_files.items():
        assert (root / path).read_bytes() == raw
    if complete:
        result = retry(root, model.source_files[SOURCE])
        assert result['replayed']
    else:
        assert not list((root / 'spec').rglob('*EVD*.json'))
        assert retry(root, model.source_files[SOURCE]) is None
        result = apply(plan, model, transaction_id='txn-after-rollback')
        assert not result['replayed']
    assert result['audit']['created_ids'] == [ref('EVD', '1'), ref('EVD', '2')]
    for op in plan.data['operations']:
        value = op['evidence']; path = artifact_path('evidence', value['id'], 'SR')
        assert (root / path).read_bytes() == canonical_json_bytes(value)
    before = inventory(root)
    assert retry(root, model.source_files[SOURCE])['replayed']
    assert inventory(root) == before


@pytest.mark.parametrize('target_number,after_replace', [(1, False), (1, True), (2, False), (2, True)])
def test_partial_publication_remains_pending_until_native_recovery(tmp_path, target_number, after_replace):
    root = tmp_path / 'project'; model = import_project(root); plan = saved(model)
    native = os.replace; targets = {op['evidence']['id'] + '.json' for op in plan.data['operations']}
    attempted = []
    def replace(src, dst, **kwargs):
        if dst in targets:
            attempted.append(dst)
            if len(attempted) == target_number:
                if after_replace: native(src, dst, **kwargs)
                raise OSError(5, 'fixture interruption')
        return native(src, dst, **kwargs)
    with patch.object(os, 'replace', side_effect=replace):
        result = execute_authoring_plan(plan, model, command_id='evidence.import',
            transaction_id='txn-import', authority=ALLOW)
    assert result['status'] == 'failed' and result['exit_code'] == 5
    assert result['write_state'] == 'unknown' and result['recovery_required']
    assert not result['retry_safe'] and result['completion'] is None
    journal = CommittingJournal((root / '.specroad/transactions/txn-import/journal.json').read_bytes())
    before = inventory(root)
    with pytest.raises(ModelError):
        apply(plan, model, transaction_id='forbidden-retry')
    assert inventory(root) == before
    complete = target_number == 2 and after_replace
    recovered = recover(root, journal, complete=complete)
    if complete: assert recovered['normative_writes'] == 0
    assert_recovered_set(root, model, plan, complete=complete)


def child_model(model, plan):
    return '''import json, os
from pathlib import Path
from specroad.authoring.evidence_import import import_evidence
from specroad.changes import ChangePlan, TargetModel, PublicationAuthority
from specroad.model.attachments import AttachmentDescriptor
from specroad.model.language_registry import LanguageRegistry
from specroad.model.model_manifest import ProjectReadBinding
from specroad.profiles import ProfileResource, compose_profiles
from specroad.validation import ModelDocument
root=Path(''' + repr(model.binding.source_root) + ''')
configuration=(root/'specroad.json').read_bytes()
config=json.loads(configuration); binding=config['language_registry']
registry=LanguageRegistry((root/binding['path']).read_bytes(),
    expected_sha256=binding['sha256'],expected_version=binding['registry_version'])
profile=ProfileResource((root/'profiles/core.json').read_bytes())
effective=compose_profiles([profile],core_key=profile.key,language_registry=registry)
info=root.stat()
model=TargetModel(configuration,ProjectReadBinding(config['project_id'],str(root),(info.st_dev,info.st_ino)),
    [ModelDocument(n,(root/n).read_bytes()) for n in ''' + repr([d.path for d in model.documents]) + '''],
    profile=effective,
    resource_files=[ModelDocument(n,(root/n).read_bytes()) for n in ''' + repr([d.path for d in model.resource_files]) + '''],
    attachments=[AttachmentDescriptor.from_data(a) for a in ''' + repr([a.data for a in model.attachment_descriptors]) + '''])
plan=ChangePlan(''' + repr(plan.source_bytes) + ''')
'''


@pytest.mark.parametrize('target_number', [1, 2])
def test_real_process_exit_retains_partial_set_and_native_recovery_proof(tmp_path, target_number):
    root = tmp_path / 'project'; model = import_project(root); plan = saved(model)
    body = child_model(model, plan) + '''
native=os.replace
targets={op['evidence']['id']+'.json' for op in plan.data['operations']}
written=[]
def replace(src,dst,**kwargs):
    result=native(src,dst,**kwargs)
    if dst in targets:
        written.append(dst)
        if len(written)==''' + str(target_number) + ''': os._exit(39)
    return result
os.replace=replace
import_evidence(plan,model,transaction_id='txn-import',
    authority=PublicationAuthority('child','1',lambda request: True))
'''
    child = run_core(body, tmp_path, capture=True)
    assert child.returncode == 39, child.stderr
    journal = CommittingJournal((root / '.specroad/transactions/txn-import/journal.json').read_bytes())
    assert journal.data['published_count'] == target_number - 1
    before = inventory(root)
    with pytest.raises(ModelError):
        apply(plan, model, transaction_id='forbidden-after-crash')
    assert inventory(root) == before
    recover(root, journal, complete=target_number == 2, crashed=True)
    assert_recovered_set(root, model, plan, complete=target_number == 2)


@pytest.mark.parametrize('mode', ['core', 'pyz'])
def test_raw_input_replay_in_isolated_process_needs_no_plan_or_model(tmp_path, mode):
    root = tmp_path / 'project'; model = import_project(root); first = apply(saved(model), model)
    body = '''import json
from specroad.authoring.evidence_import import resolve_generic_import_request
from specroad.storage.project import ProjectSource
result=resolve_generic_import_request(ProjectSource(''' + repr(str(root)) + '''),
    source_bytes=''' + repr(model.source_files[SOURCE]) + ''',
    source_path='attachments/import.json',policy='abort_import',title='Imported measurement',
    actor={'actor_type':'human','actor_id':'later-process'},request_id='import-1')
print(json.dumps(result))
'''
    before = inventory(root)
    if mode == 'core': child = run_core(body, tmp_path, capture=True)
    else:
        _, package = build_distribution(tmp_path / 'distribution')
        child = run_python(['-I', '-S', '-B', '-c',
            'import sys;sys.path.insert(0,' + repr(str(package)) + ')\n' + body],
            tmp_path, capture=True)
    assert child.returncode == 0, child.stderr
    result = json.loads(child.stdout)
    assert result['replayed'] and result['audit']['created_ids'] == first['audit']['created_ids']
    assert not result['completion']['current_target_verified'] and inventory(root) == before
