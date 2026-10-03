"""Terminal receipts and public cleanup after the original writer has exited."""
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

import pytest

from specroad.changes import (CommittedJournal, RecoveryAuthority, RecoveryError,
    RolledBackJournal, ProjectLockError, cleanup_recovered_transaction,
    complete_published_transaction, project_lock, read_transaction_completion,
    rollback_interrupted_transaction, transaction_receipt_path)
from specroad.storage.project import ProjectSource
from support.publication import TRANSACTION, files
from support.recovery import pending, discard, recovery_options as discard_options, tree
from test_transaction_recovery_completion import crash_after_last_target, recovery_options
from test_transaction_recovery_rollback import partial_commit

RECOVER = RecoveryAuthority('terminal-test-authorizer', '1', lambda request: True)


def terminal(root, outcome='rollback'):
    if outcome == 'rollback':
        model, plan, journal = partial_commit(root)
        action, cls = rollback_interrupted_transaction, RolledBackJournal
        expected = model.source_files
    else:
        model, plan, preflight, journal, expected = crash_after_last_target(root)
        action, cls = complete_published_transaction, CommittedJournal
    with project_lock(root, **recovery_options(journal)) as held:
        result = action(TRANSACTION, held_lock=held, authority=RECOVER,
                        expected_journal_sha256=journal.sha256)
    return cls(Path(root, journal.path).read_bytes()), expected, result


def cleanup(root, journal, *, authority=RECOVER, options=None, expected=None):
    with project_lock(root, **(options or recovery_options(journal))) as held:
        return cleanup_recovered_transaction(TRANSACTION, held_lock=held, authority=authority,
            expected_journal_sha256=expected or journal.sha256)


def writer(root):
    return project_lock(root, kind='writer', command='change apply', project_id='sample',
                        request_id='next-request', transaction_id='next-transaction')


def test_rollback_receipt_and_action_bind_exact_restored_basis(tmp_path):
    journal, expected, result = terminal(tmp_path)
    receipt = json.loads(Path(tmp_path, transaction_receipt_path(TRANSACTION)).read_bytes())
    assert receipt['outcome'] == 'rolled_back' and receipt['action'] == 'rollback'
    assert receipt['journal'] == journal.data
    assert receipt['journal_sha256'] == journal.sha256
    assert receipt['result_model_root_sha256'] == journal.data['base_model_root_sha256']
    ref = receipt['recovery_audit']
    raw = Path(tmp_path, ref['path']).read_bytes()
    assert sha256(raw).hexdigest() == ref['sha256']
    audit = json.loads(raw)
    assert audit['action'] == 'rollback' and audit['journal_sha256'] == journal.sha256
    assert audit['authority_id'] == RECOVER.authority_id
    assert result.data['receipt']['path'] == transaction_receipt_path(TRANSACTION)
    assert not Path(tmp_path, '.specroad/requests').exists()
    assert files(tmp_path) == expected


def test_complete_target_action_is_immutable_across_authorized_retries(tmp_path):
    journal, expected, result = terminal(tmp_path, 'complete')
    audit_path, = Path(tmp_path, '.specroad/recovery/transaction-audit').glob('*/complete.json')
    audit = json.loads(audit_path.read_bytes())
    assert audit['action'] == 'complete' and audit['outcome'] == 'committed'
    assert audit['journal_sha256'] == journal.sha256
    assert audit['result_model_root_sha256'] == journal.data['target_model_root_sha256']
    before, inode = tree(tmp_path), audit_path.stat().st_ino
    other = RecoveryAuthority('second-authorizer', '2', lambda request: True)
    with project_lock(tmp_path, **recovery_options(journal)) as held:
        repeated = complete_published_transaction(TRANSACTION, held_lock=held, authority=other,
                                                  expected_journal_sha256=journal.sha256)
    assert repeated.data['normative_writes'] == 0
    assert tree(tmp_path) == before and audit_path.stat().st_ino == inode
    assert files(tmp_path) == expected


@pytest.mark.parametrize('state', ['building', 'prepared'])
def test_discard_persists_canonical_receipt_bound_to_preserved_audit(tmp_path, state):
    model, plan, preflight, journal = pending(tmp_path, state=state)
    with project_lock(tmp_path, **discard_options(preflight)) as held:
        result = discard(preflight, journal, held)
    ref = result.data['receipt']
    raw = Path(tmp_path, ref['path']).read_bytes()
    receipt = json.loads(raw)
    assert ref['path'] == transaction_receipt_path(TRANSACTION)
    assert sha256(raw).hexdigest() == ref['sha256']
    assert receipt['outcome'] == 'rolled_back' and receipt['action'] == 'discard'
    assert receipt['journal_sha256'] == result.data['journal_sha256']
    audit_ref = receipt['recovery_audit']
    assert sha256(Path(tmp_path, audit_ref['path']).read_bytes()).hexdigest() == audit_ref['sha256']
    archived = Path(tmp_path, result.data['archive_path'], 'journal.json')
    assert sha256(archived.read_bytes()).hexdigest() == receipt['journal_sha256']
    assert files(tmp_path) == model.source_files
    with writer(tmp_path):
        pass


@pytest.mark.parametrize('outcome', ['rollback', 'complete'])
def test_explicit_cleanup_archives_all_work_and_allows_new_writer(tmp_path, outcome):
    journal, expected, result = terminal(tmp_path, outcome)
    work = Path(tmp_path, journal.path).parent
    before = {p.relative_to(work).as_posix(): p.read_bytes() for p in work.rglob('*') if p.is_file()}
    receipts = {p: raw for p, raw in tree(tmp_path).items() if '/receipts/' in p or '/requests/' in p}
    with pytest.raises(ProjectLockError):
        with writer(tmp_path):
            pass
    cleaned = cleanup(tmp_path, journal).data
    assert cleaned['cleanup_completed'] and not cleaned['cleanup_required']
    assert cleaned['normative_writes'] == 0 and not cleaned['normal_operation_started']
    assert cleaned['remaining_active_paths'] == [] and not cleaned['recovery_required']
    assert not work.exists()
    archive = Path(tmp_path, cleaned['archive_path'])
    assert {p.relative_to(archive).as_posix(): p.read_bytes() for p in archive.rglob('*') if p.is_file()} == before
    intent_raw = (archive.parent / 'intent.json').read_bytes()
    intent = json.loads(intent_raw)
    completed = json.loads((archive.parent / 'completed.json').read_bytes())
    assert intent['action'] == 'cleanup' and intent['authority_id'] == RECOVER.authority_id
    assert completed['intent_sha256'] == sha256(intent_raw).hexdigest()
    assert completed['journal_sha256'] == journal.sha256 and completed['phase'] == 'completed'
    assert {entry['path']: entry['sha256'] for entry in intent['work_files']} == {
        path: sha256(raw).hexdigest() for path, raw in before.items()}
    assert all(Path(tmp_path, path).read_bytes() == raw for path, raw in receipts.items())
    assert files(tmp_path) == expected
    with writer(tmp_path):
        pass
    if outcome == 'complete':
        proof = read_transaction_completion(ProjectSource(tmp_path), TRANSACTION).data
        assert proof['commit_completed'] and proof['cleanup_completed']


@pytest.mark.parametrize('outcome', ['rollback', 'complete'])
def test_cleanup_repeat_checks_archive_without_writes(tmp_path, outcome):
    journal, expected, result = terminal(tmp_path, outcome)
    first = cleanup(tmp_path, journal)
    before = tree(tmp_path)
    with project_lock(tmp_path, **recovery_options(journal)) as held:
        with patch('os.rename', side_effect=AssertionError('second rename')), \
             patch('specroad.changes._staging_files.os.write', side_effect=AssertionError('second write')):
            second = cleanup_recovered_transaction(TRANSACTION, held_lock=held, authority=RECOVER,
                                                    expected_journal_sha256=journal.sha256)
    assert second.data == first.data
    assert tree(tmp_path) == before and files(tmp_path) == expected


@pytest.mark.parametrize('obstacle', ['receipt', 'work', 'image', 'live', 'symlink'])
def test_cleanup_refuses_unproved_bytes_without_moving_any_work(tmp_path, obstacle):
    journal, expected, result = terminal(tmp_path)
    work = Path(tmp_path, journal.path).parent
    if obstacle == 'receipt':
        Path(tmp_path, transaction_receipt_path(TRANSACTION)).write_bytes(b'{"foreign":true}')
    elif obstacle == 'work':
        (work / 'foreign.bin').write_bytes(b'preserve me')
    elif obstacle == 'image':
        Path(tmp_path, journal.data['files'][0]['before_image_path']).write_bytes(b'wrong before')
    elif obstacle == 'live':
        Path(tmp_path, journal.data['files'][0]['path']).write_bytes(b'changed after completion')
    else:
        image = Path(tmp_path, journal.data['files'][0]['before_image_path'])
        image.unlink()
        image.symlink_to(Path(tmp_path, journal.data['files'][0]['path']))
    before = tree(tmp_path)
    with pytest.raises(RecoveryError):
        cleanup(tmp_path, journal)
    assert tree(tmp_path) == before and work.exists()


@pytest.mark.parametrize('case', ['denied', 'command', 'request', 'hash'])
def test_cleanup_requires_explicit_authority_and_exact_lock_and_journal(tmp_path, case):
    journal, expected, result = terminal(tmp_path)
    before = tree(tmp_path)
    options = recovery_options(journal)
    if case == 'command':
        options['command'] = 'recover discard'
    if case == 'request':
        options['request_id'] = 'foreign-request'
    authority = RecoveryAuthority('denied', '1', lambda request: False) if case == 'denied' else RECOVER
    with pytest.raises(RecoveryError) as failure:
        cleanup(tmp_path, journal, authority=authority, options=options,
                expected='0' * 64 if case == 'hash' else None)
    assert not failure.value.mutation_possible
    assert tree(tmp_path) == before


def test_cleanup_preserves_other_active_blockers(tmp_path):
    journal, expected, result = terminal(tmp_path)
    foreign = Path(tmp_path, '.specroad/transactions/foreign')
    foreign.mkdir()
    (foreign / 'journal.json').write_bytes(b'foreign unproved journal')
    cleaned = cleanup(tmp_path, journal).data
    assert cleaned['cleanup_completed'] and cleaned['recovery_required']
    assert cleaned['remaining_active_paths'] == ['.specroad/transactions/foreign']
    assert (foreign / 'journal.json').read_bytes() == b'foreign unproved journal'
    with pytest.raises(ProjectLockError):
        with writer(tmp_path):
            pass


def test_rollback_retry_preserves_receipt_and_original_authority(tmp_path):
    journal, expected, result = terminal(tmp_path)
    before = tree(tmp_path)
    with project_lock(tmp_path, **recovery_options(journal)) as held:
        again = rollback_interrupted_transaction(TRANSACTION, held_lock=held,
            authority=RecoveryAuthority('second-authorizer', '2', lambda request: True),
            expected_journal_sha256=journal.sha256)
    assert again.data['normative_writes'] == 0 and again.data['receipt'] == result.data['receipt']
    assert tree(tmp_path) == before and files(tmp_path) == expected


def test_cleanup_cannot_remove_an_unfinished_transaction(tmp_path):
    model, plan, journal = partial_commit(tmp_path)
    before = tree(tmp_path)
    with pytest.raises(RecoveryError) as failure:
        cleanup(tmp_path, journal)
    assert failure.value.reason == 'recovery_terminal_state_required'
    assert not failure.value.mutation_possible and tree(tmp_path) == before


def test_cleanup_rechecks_work_after_authorization(tmp_path):
    journal, expected, result = terminal(tmp_path)
    foreign = Path(tmp_path, journal.path).with_name('foreign.bin')
    before = tree(tmp_path)
    def authorize(request):
        assert request['action'] == 'cleanup'
        foreign.write_bytes(b'foreign work during authorization')
        return True
    with pytest.raises(RecoveryError) as failure:
        cleanup(tmp_path, journal, authority=RecoveryAuthority('mutating-host', '1', authorize))
    assert not failure.value.mutation_possible
    assert tree(tmp_path) == {**before, foreign.relative_to(tmp_path).as_posix(): foreign.read_bytes()}


def test_conflicting_recovery_action_is_never_replaced(tmp_path):
    journal, expected, result = terminal(tmp_path, 'complete')
    audit_path, = Path(tmp_path, '.specroad/recovery/transaction-audit').glob('*/complete.json')
    value = json.loads(audit_path.read_bytes())
    value['journal_sha256'] = '0' * 64
    audit_path.write_text(json.dumps(value))
    before = tree(tmp_path)
    with project_lock(tmp_path, **recovery_options(journal)) as held:
        with pytest.raises(RecoveryError) as failure:
            complete_published_transaction(TRANSACTION, held_lock=held, authority=RECOVER,
                                            expected_journal_sha256=journal.sha256)
    assert failure.value.reason == 'recovery_action_conflict'
    assert tree(tmp_path) == before and files(tmp_path) == expected


def _process(root, code, *args):
    repo = Path(__file__).resolve().parents[1]
    bootstrap = 'import sys\nfrom pathlib import Path\nimport json\n'
    bootstrap += 'sys.path[:0] = [str(Path(sys.argv[1]) / "src"), str(Path(sys.argv[1]) / "tests")]\n'
    bootstrap += 'root = Path(sys.argv[2])\n'
    run = subprocess.run([sys.executable, '-I', '-B', '-c', bootstrap + code, str(repo), str(root), *args],
                         capture_output=True, text=True, check=False)
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout)


@pytest.mark.parametrize('mode', ['rollback', 'complete', 'normal_committed'])
def test_released_writer_completion_and_cleanup_work_in_independent_processes(tmp_path, mode):
    expected = _process(tmp_path, '''
from hashlib import sha256
from support.publication import files
from support.receipts import published, finish
from test_transaction_recovery_rollback import partial_commit
if sys.argv[3] == 'rollback':
    model, plan, journal = partial_commit(root)
    expected = model.source_files
else:
    with published(root) as (model, plan, preflight, held, journal):
        if sys.argv[3] == 'normal_committed':
            finish(preflight, held, journal)
    expected = files(root)
print(json.dumps({path: sha256(raw).hexdigest() for path, raw in expected.items()}))
''', mode)
    terminal_sha = _process(tmp_path, '''
from specroad.changes import (CommittingJournal, RecoveryAuthority, project_lock,
    rollback_interrupted_transaction, complete_published_transaction)
from support.publication import TRANSACTION
from test_transaction_recovery_completion import recovery_options
path = root / '.specroad/transactions' / TRANSACTION / 'journal.json'
authority = RecoveryAuthority('process-test-authorizer', '1', lambda request: True)
if sys.argv[3] != 'normal_committed':
    journal = CommittingJournal(path.read_bytes())
    action = rollback_interrupted_transaction if sys.argv[3] == 'rollback' else complete_published_transaction
    with project_lock(root, **recovery_options(journal)) as held:
        action(TRANSACTION, held_lock=held, authority=authority, expected_journal_sha256=journal.sha256)
from hashlib import sha256
print(json.dumps(sha256(path.read_bytes()).hexdigest()))
''', mode)
    observed = _process(tmp_path, '''
from hashlib import sha256
from specroad.changes import RecoveryAuthority, project_lock, cleanup_recovered_transaction
from specroad.storage.read_only import validate_project_read_only
from specroad.profiles import ProfileResource
from specroad.model.canonical import canonical_json_bytes
from support.profiles import profile_data
from support.publication import TRANSACTION, files
data = json.loads((root / '.specroad/transactions' / TRANSACTION / 'journal.json').read_bytes())
options = dict(kind='recovery', command='recover run', project_id=data['project_id'],
               request_id=data['request_id'], transaction_id=TRANSACTION)
with project_lock(root, **options) as held:
    result = cleanup_recovered_transaction(TRANSACTION, held_lock=held,
        authority=RecoveryAuthority('process-cleanup-authorizer', '1', lambda request: True),
        expected_journal_sha256=sys.argv[3])
profile = ProfileResource(canonical_json_bytes(profile_data(profile_id='core')))
read = validate_project_read_only(root, profile_resources=[profile], core_key=profile.key).data
with project_lock(root, kind='writer', command='change apply', project_id='sample',
                  request_id='new-request', transaction_id='new-transaction'):
    acquired = True
print(json.dumps({'cleanup': result.data, 'reader': read, 'writer_acquired': acquired,
    'files': {path: sha256(raw).hexdigest() for path, raw in files(root).items()}}))
''', terminal_sha)
    assert observed['cleanup']['cleanup_completed']
    assert observed['cleanup']['normative_writes'] == 0
    assert observed['reader']['exit_code'] == 0 and observed['reader']['model_loaded']
    assert observed['writer_acquired'] and observed['files'] == expected
