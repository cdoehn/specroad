"""Actual abrupt-process Restore recovery, with synthetic host authorization."""
import os
import json
from pathlib import Path
import subprocess
import sys

import pytest

from specroad.changes._lock_files import LockFiles
from specroad.changes.lock_values import LockRecord
from specroad.changes.recovery_values import RecoveryAuthority
from specroad.model.canonical import canonical_json_bytes
from specroad.recovery import RestoreError
from specroad.recovery._execution_store import RestoreStore
from specroad.security import ProjectBoundary
from specroad.storage.operational_preflight import observe_operational_preflight
from support.model import put
from support.read_only import inventory, no_write_attempts
from support.restore import restore_case, plan_for
from support.project_locks import Probe
from test_restore_execution import ACTOR, execute, selected, files
from test_transaction_recovery_lock import child


def fixture(tmp_path):
    options, original, _ = restore_case(tmp_path)
    changed = sorted(p for p in original if p.startswith(('spec/documents/', 'spec/goals/')))
    assert len(changed) >= 2
    for i, path in enumerate(changed):
        put(options['project_root'], path, b'\xffbroken-' + str(i).encode())
    old = '.specroad/transactions/old'
    put(options['project_root'], old + '/journal.json', b'{damaged')
    (options['project_root'] / old / 'empty').mkdir()
    plan = plan_for(options)
    return options, plan, selected(plan, [old]), changed, old


def abrupt_restore(value):
    from specroad.recovery import RestorePlan
    plan = RestorePlan(canonical_json_bytes(value['plan']))
    selection = canonical_json_bytes(value['selection'])
    method, suffix, count = (value[k] for k in ('method', 'suffix', 'count'))
    seen = 0
    if method == 'replace':
        original = os.replace
        def crash(*args, **kwargs):
            nonlocal seen
            result = original(*args, **kwargs)
            seen += 1
            if seen == count: os._exit(87)
            return result
        os.replace = crash
    else:
        original = getattr(RestoreStore, method)
        def crash(self, *args):
            nonlocal seen
            result = original(self, *args)
            if suffix is None or args[0].endswith(suffix):
                seen += 1
                if seen == count: os._exit(87)
            return result
        setattr(RestoreStore, method, crash)
    if value['continuation']:
        continue_restore(plan, selection)
    else:
        execute(plan, affected_journals=selection)
    raise AssertionError('Crash boundary was not reached')


def interrupted(plan, selection, method, *, suffix=None, count=1, continuation=False):
    repo = Path(__file__).resolve().parents[1]
    code = '''
import sys, json
from pathlib import Path
sys.path[:0] = [str(Path(sys.argv[1]) / 'src'), str(Path(sys.argv[1]) / 'tests')]
from test_restore_execution_right import abrupt_restore
abrupt_restore(json.load(sys.stdin))
'''
    run = subprocess.run([sys.executable, '-I', '-B', '-c', code, str(repo)],
        input=json.dumps({'plan': plan.data, 'selection': json.loads(selection), 'method': method,
                          'suffix': suffix, 'count': count, 'continuation': continuation}),
        capture_output=True, text=True, check=False, timeout=180)
    assert run.returncode == 87, run.stderr


def continue_restore(plan, selection, **kwargs):
    with LockFiles(plan.data['project_root']) as access:
        owner = access.read_record()[0]
    takeover = {} if owner is None else {'force': True, 'expected_lock_sha256': owner.sha256,
                                        'reason': 'Synthetic explicit recovery after process exit'}
    return execute(plan, affected_journals=selection, **takeover, **kwargs).data


@pytest.mark.parametrize('boundary', ['intent', 'plan', 'manifest', 'staging', 'prepared', 'committing',
    'partial', 'partial-before-sync', 'full', 'full-before-sync', 'audit', 'archived-old', 'terminal'])
def test_actual_process_exit_preserves_original_request_and_recovers_only_proven_state(tmp_path, boundary):
    options, plan, selection, changed, old = fixture(tmp_path)
    root = options['project_root']
    before = {p: (root / p).read_bytes() for p in changed}
    if boundary in ('intent', 'plan', 'manifest', 'prepared', 'committing'):
        interrupted(plan, selection, 'create', suffix='/' + boundary + '.json')
    elif boundary == 'staging':
        interrupted(plan, selection, 'create', suffix='/staging/0')
    elif boundary in ('partial-before-sync', 'full-before-sync'):
        interrupted(plan, selection, 'replace', count=1 if boundary.startswith('partial') else len(changed))
    elif boundary == 'audit':
        interrupted(plan, selection, 'create', suffix='/completed.json')
    elif boundary in ('archived-old', 'terminal'):
        interrupted(plan, selection, 'archive', count=1 if boundary == 'archived-old' else 2)
    else:
        interrupted(plan, selection, 'publish', count=1 if boundary == 'partial' else len(changed))
    # A full target must finish even though the original source has disappeared.
    (options['source_root'] / options['source_path']).unlink()
    result = continue_restore(plan, selection, actor={'actor_type': 'human', 'actor_id': 'synthetic-recovery-operator'})
    assert result['request']['actor'] == ACTOR
    assert result['source_observation']['status'] == 'unavailable_or_changed'
    if boundary in ('full', 'full-before-sync', 'audit', 'archived-old', 'terminal'):
        assert result['result'] == 'restored' and not result['recovery_required']
        assert all((root / p).read_bytes() == raw for p, raw in files(plan, 'target').items())
        assert not (root / old).exists()
    else:
        assert result['result'] == 'rolled_back' and result['recovery_required']
        assert {p: (root / p).read_bytes() for p in changed} == before
        assert (root / old / 'journal.json').read_bytes() == b'{damaged'
        assert observe_operational_preflight(ProjectBoundary(root))['recovery_required']
    snapshot = inventory(root)
    replay = continue_restore(plan, selection)
    assert replay['result'] == result['result'] and replay['replayed']
    assert inventory(root) == snapshot


@pytest.mark.parametrize('fault', ['backup', 'intent', 'foreign', 'target', 'selection', 'ordinary-owner'])
def test_unproven_partial_state_is_never_overwritten_by_recovery(tmp_path, fault):
    options, plan, selection, changed, old = fixture(tmp_path)
    root = options['project_root']
    interrupted(plan, selection, 'publish', count=1)
    if fault == 'backup':
        next((root / '.specroad/recovery/archive').glob('*/objects/*')).write_bytes(b'foreign')
    elif fault == 'intent':
        path = next((root / '.specroad/recovery').glob('restore-*/intent.json'))
        value = json.loads(path.read_bytes()); value['own_directories'].append('.specroad/recovery/foreign')
        path.write_bytes(canonical_json_bytes(value))
    elif fault == 'foreign':
        path = next((root / '.specroad/recovery/archive').iterdir()) / 'extra'
        path.write_bytes(b'foreign')
    elif fault == 'target':
        (root / changed[0]).write_bytes(b'foreign')
    elif fault == 'ordinary-owner':
        path = root / '.specroad/locks/project.json'
        value = json.loads(path.read_bytes())
        value.update(kind='writer', command='change apply', transaction_id='old', request_id='unrelated')
        path.write_bytes(canonical_json_bytes(value))
    else:
        selection = None
    before = inventory(root)
    with no_write_attempts(), pytest.raises(RestoreError) as failure:
        continue_restore(plan, selection)
    assert failure.value.exit_code == (5 if fault == 'selection' else 6)
    assert failure.value.recovery_required
    assert not failure.value.mutation_possible and inventory(root) == before


@pytest.mark.parametrize('fault', ['missing_force', 'missing_hash', 'missing_reason', 'risk_without_force', 'hash_type'])
def test_incomplete_takeover_arguments_are_usage_errors_before_any_write(tmp_path, fault):
    options, plan, selection, _, _ = fixture(tmp_path)
    kwargs = {'force': True, 'expected_lock_sha256': 'a' * 64, 'reason': 'Synthetic reason'}
    if fault == 'missing_force': kwargs.pop('force')
    elif fault == 'missing_hash': kwargs.pop('expected_lock_sha256')
    elif fault == 'missing_reason': kwargs.pop('reason')
    elif fault == 'hash_type': kwargs['expected_lock_sha256'] = True
    else: kwargs = {'accept_remote_risk': True}
    before = inventory(options['project_root'])
    with no_write_attempts(), pytest.raises(RestoreError) as failure:
        execute(plan, affected_journals=selection, **kwargs)
    assert failure.value.exit_code == 2 and not failure.value.mutation_possible
    assert inventory(options['project_root']) == before


@pytest.mark.parametrize('boundary', ['owner-replace', 'owner-complete', 'rollback-intent',
                                     'rollback-publication', 'rollback-before-sync'])
def test_repeated_real_crashes_during_takeover_and_rollback_keep_original_bytes(tmp_path, boundary):
    options, plan, selection, changed, old = fixture(tmp_path)
    root = options['project_root']
    before = {p: (root / p).read_bytes() for p in changed}
    interrupted(plan, selection, 'publish', count=1)
    if boundary == 'owner-replace':
        interrupted(plan, selection, 'replace', continuation=True)
    elif boundary == 'rollback-publication':
        interrupted(plan, selection, 'publish', continuation=True)
    elif boundary == 'rollback-before-sync':
        interrupted(plan, selection, 'replace', continuation=True, count=2)
    else:
        suffix = {'owner-complete': '/completed.json', 'rollback-intent': '/rollback/intent.json'}[boundary]
        interrupted(plan, selection, 'create', suffix=suffix, continuation=True)
    result = continue_restore(plan, selection)
    assert result['result'] == 'rolled_back' and result['recovery_required']
    assert {p: (root / p).read_bytes() for p in changed} == before
    assert (root / old / 'journal.json').read_bytes() == b'{damaged'


def old_owner(plan, *, kind='recovery', changes=None):
    root = Path(plan.data['project_root'])
    child(root, '''
from specroad.changes import project_lock
with project_lock(root, kind='recovery', command='recover run', project_id=sys.argv[3],
                  transaction_id='old', request_id='original-old-request'):
    os._exit(87)
''', plan.data['project_id'], exit_code=87)
    raw = (root / '.specroad/locks/project.json').read_bytes()
    if kind != 'recovery' or changes:
        value = json.loads(raw)
        value.update(kind=kind, command='change apply' if kind == 'writer' else 'recover run')
        value.update(changes or {})
        raw = canonical_json_bytes(value)
        (root / '.specroad/locks/project.json').write_bytes(raw)
    return LockRecord(raw)


@pytest.mark.parametrize('kind', ['writer', 'recovery'])
def test_new_restore_explicitly_transfers_only_selected_old_owner_and_keeps_both_requests(tmp_path, kind):
    options, plan, selection, changed, old = fixture(tmp_path)
    root = options['project_root']
    owner = old_owner(plan, kind=kind)
    calls = []
    def check(request):
        calls.append(request)
        return True
    result = execute(plan, affected_journals=selection, force=True, expected_lock_sha256=owner.sha256,
        reason='Synthetic explicitly selected damaged transaction',
        authority=RecoveryAuthority('synthetic-owner-authority', '1', check)).data
    assert result['result'] == 'restored'
    takeovers = [r for r in calls if r['action'] == 'takeover']
    assert len(takeovers) == 2 and takeovers[0] == takeovers[1]
    assert takeovers[0]['lock_record']['request_id'] == 'original-old-request'
    assert takeovers[0]['restore_request']['request_id'] == 'restore-test'
    assert takeovers[0]['binding']['original_entry']['path'] == old
    assert takeovers[0]['observed_owner_state'] == 'dead'
    copies = list((root / '.specroad/recovery/transaction-audit').glob('restore-*/takeovers/*/owner.before.json'))
    assert len(copies) == 1 and copies[0].read_bytes() == owner.source_bytes
    assert all((root / p).read_bytes() == raw for p, raw in files(plan, 'target').items())


@pytest.mark.parametrize('fault', ['hash', 'project', 'root', 'transaction', 'restore_owner', 'corrupt',
                                 'alive', 'alive-with-risk', 'foreign', 'unknown', 'reused', 'denied', 'nonbool', 'mutated'])
def test_invalid_or_unauthorized_owner_takeover_is_write_free(tmp_path, fault):
    options, plan, selection, _, _ = fixture(tmp_path)
    root = options['project_root']
    changes = {}
    if fault == 'project': changes['project_id'] = 'other-project'
    elif fault == 'root': changes['root_identity'] = {'device': '1', 'inode': '1'}
    elif fault == 'transaction': changes['transaction_id'] = 'unselected'
    elif fault == 'restore_owner': changes['command'] = 'recover restore'
    owner = old_owner(plan, changes=changes)
    if fault == 'corrupt': (root / '.specroad/locks/project.json').write_bytes(b'{broken')
    kwargs = {}
    if fault.startswith('alive'):
        kwargs['owner_probe'] = Probe(owner.data['host_id'], 'alive', owner.data['process_start_id'])
        kwargs['accept_remote_risk'] = fault.endswith('with-risk')
    elif fault == 'foreign': kwargs['owner_probe'] = Probe('foreign-host', 'absent')
    elif fault == 'unknown': kwargs['owner_probe'] = Probe(None, 'absent')
    elif fault == 'reused': kwargs['owner_probe'] = Probe(owner.data['host_id'], 'alive', 'another-start')
    if fault in ('denied', 'nonbool', 'mutated'):
        def check(request):
            if request['action'] != 'takeover': return True
            if fault == 'mutated': request['force'] = False
            return False if fault == 'denied' else 1 if fault == 'nonbool' else True
        kwargs['authority'] = RecoveryAuthority('synthetic-denial', '1', check)
    before = inventory(root)
    with no_write_attempts(), pytest.raises(RestoreError) as failure:
        execute(plan, affected_journals=selection, force=True,
            expected_lock_sha256='0' * 64 if fault == 'hash' else owner.sha256,
            reason='Synthetic exact owner test', **kwargs)
    assert failure.value.exit_code == (3 if fault == 'corrupt' else 7 if fault in (
        'alive', 'alive-with-risk', 'foreign', 'unknown', 'reused', 'denied', 'nonbool', 'mutated') else 6)
    assert not failure.value.mutation_possible and inventory(root) == before


@pytest.mark.parametrize('state', ['foreign', 'unverifiable', 'pid_reused'])
def test_explicit_remote_risk_is_fresh_and_audited_for_nonlive_owner(tmp_path, state):
    options, plan, selection, _, _ = fixture(tmp_path)
    root = options['project_root']; owner = old_owner(plan)
    probe = {'foreign': Probe('another-host', 'absent'), 'unverifiable': Probe(None, 'absent'),
             'pid_reused': Probe(owner.data['host_id'], 'alive', 'another-start')}[state]
    result = execute(plan, affected_journals=selection, force=True, expected_lock_sha256=owner.sha256,
        reason='Explicit synthetic risk consent', accept_remote_risk=True, owner_probe=probe).data
    assert result['result'] == 'restored'
    intent = json.loads(next((root / '.specroad/recovery/transaction-audit').glob('restore-*/takeovers/*/intent.json')).read_bytes())
    assert intent['details']['request']['observed_owner_state'] == state
    assert intent['details']['request']['accept_remote_risk'] is True


@pytest.mark.parametrize('boundary', ['intent', 'owner-replace', 'completed'])
def test_new_restore_handoff_crash_before_execution_journal_never_starts_operation_on_retry(tmp_path, boundary):
    options, plan, selection, changed, old = fixture(tmp_path)
    root = options['project_root']; owner = old_owner(plan)
    before = {p: (root / p).read_bytes() for p in changed}
    if boundary == 'owner-replace':
        interrupted(plan, selection, 'replace', continuation=True)
    else:
        interrupted(plan, selection, 'create', suffix='/' + boundary + '.json', continuation=True)
    assert not list((root / '.specroad/recovery').glob('restore-*/intent.json'))
    result = continue_restore(plan, selection)
    assert result['result'] == 'rolled_back' and result['recovery_required']
    assert {p: (root / p).read_bytes() for p in changed} == before
    assert (root / old / 'journal.json').read_bytes() == b'{damaged'


@pytest.mark.parametrize('change_target', [False, True])
def test_source_changed_at_committing_publication_is_rejected_before_any_target_effect(tmp_path, monkeypatch, change_target):
    from specroad.recovery import _execution_store
    options, original, _ = restore_case(tmp_path)
    root = options['project_root']
    if change_target:
        path = next(p for p in original if p.startswith('spec/goals/'))
        put(root, path, b'broken')
    plan = plan_for(options)
    before = {p: (root / p).read_bytes() for p in original}
    native = _execution_store.write_recovery_file
    def write(directory, name, raw, *, before_publish):
        def check():
            if name == 'committing.json':
                put(options['source_root'], options['source_path'], b'changed source')
            before_publish()
        return native(directory, name, raw, before_publish=check)
    monkeypatch.setattr(_execution_store, 'write_recovery_file', write)
    with pytest.raises(RestoreError) as failure:
        execute(plan)
    assert failure.value.exit_code == 6 and failure.value.recovery_required
    assert {p: (root / p).read_bytes() for p in original} == before
    assert not list((root / '.specroad/recovery').glob('restore-*/committing.json'))


def test_force_does_not_override_the_real_native_mutex(tmp_path):
    from specroad.changes import project_lock
    options, plan, selection, _, _ = fixture(tmp_path)
    root = options['project_root']
    with project_lock(root, kind='recovery', command='recover run', project_id=plan.data['project_id'],
                      transaction_id='old', request_id='original-old-request') as held:
        before = inventory(root)
        with no_write_attempts(), pytest.raises(RestoreError) as failure:
            execute(plan, affected_journals=selection, force=True, expected_lock_sha256=held.record.sha256,
                    reason='Must remain blocked', accept_remote_risk=True)
        assert failure.value.exit_code == 5 and not failure.value.mutation_possible
        assert inventory(root) == before


@pytest.mark.parametrize('effect', ['create-with-directory', 'remove-original'])
def test_partial_recovery_reverses_creation_and_removal_with_exact_original_membership(tmp_path, effect):
    from support.records import record_value, ref
    from specroad.model.paths import artifact_path
    options, original, _ = restore_case(tmp_path)
    root = options['project_root']
    goal = next(p for p in original if p.startswith('spec/goals/'))
    put(root, goal, b'original damaged goal')
    if effect == 'create-with-directory':
        path = next(p for p in original if p.startswith('spec/documents/'))
        (root / path).unlink()
        (root / path).parent.rmdir()
        raw = None
        method = 'publish'
    else:
        value = record_value('document', id=ref('DOC', '1'))
        path = artifact_path('document', value['id'], 'SR')
        raw = canonical_json_bytes(value)
        assert path not in original
        put(root, path, raw)
        method = 'remove'
    plan = plan_for(options)
    selection = selected(plan, [])
    interrupted(plan, selection, method)
    assert (root / path).exists() == (effect == 'create-with-directory')
    result = continue_restore(plan, selection)
    assert result['result'] == 'rolled_back' and result['recovery_required']
    assert (root / goal).read_bytes() == b'original damaged goal'
    if raw is None:
        assert not (root / path).exists() and not (root / path).parent.exists()
    else:
        assert (root / path).read_bytes() == raw
    assert observe_operational_preflight(ProjectBoundary(root))['recovery_required']


@pytest.mark.parametrize('fault', ['missing-backup', 'denied-current-authority', 'changed-completed-target'])
def test_recovery_requires_complete_original_evidence_current_authority_and_actual_target(tmp_path, fault):
    options, plan, selection, changed, _ = fixture(tmp_path)
    root = options['project_root']
    if fault == 'changed-completed-target':
        execute(plan, affected_journals=selection)
        (root / changed[0]).write_bytes(b'new independent change')
        expected = 6
    else:
        interrupted(plan, selection, 'publish', count=1)
        expected = 7 if fault == 'denied-current-authority' else 3
        if fault == 'missing-backup':
            next((root / '.specroad/recovery/archive').glob('*/objects/*')).unlink()
    kwargs = {'authority': RecoveryAuthority('fresh-denial', '1', lambda _: False)} if expected == 7 else {}
    before = inventory(root)
    with no_write_attempts(), pytest.raises(RestoreError) as failure:
        continue_restore(plan, selection, **kwargs)
    assert failure.value.exit_code == expected and not failure.value.mutation_possible
    assert inventory(root) == before
