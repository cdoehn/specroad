"""Native orphan access binds owner, root, journal and explicit host authority."""
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

import pytest

from specroad.changes import (CommittedJournal, CommittingJournal, LockRecord,
    ProjectLockError, RecoveryAuthority, RecoveryError, project_lock,
    inspect_project_lock, recover_project_lock, transaction_recovery_lock,
    complete_published_transaction, rollback_interrupted_transaction,
    cleanup_recovered_transaction)
from specroad.model.canonical import canonical_json_bytes
from support.publication import TRANSACTION, files
from support.targets import ACTOR
from support.recovery import tree
from support.project_locks import Probe
from test_terminal_recovery import RECOVER, writer
from test_transaction_recovery_completion import recovery_options


def child(root, code, *args, exit_code=0):
    repo = Path(__file__).resolve().parents[1]
    bootstrap = 'import sys, os, json\nfrom pathlib import Path\n'
    bootstrap += 'sys.path[:0] = [str(Path(sys.argv[1])/"src"), str(Path(sys.argv[1])/"tests")]\n'
    bootstrap += 'root = Path(sys.argv[2])\n'
    run = subprocess.run([sys.executable, '-I', '-B', '-c', bootstrap + code,
                          str(repo), str(root), *args], capture_output=True, text=True, check=False)
    assert run.returncode == exit_code, run.stderr
    return run.stdout


def orphan_writer(root, mode='partial'):
    output = child(root, '''
from hashlib import sha256
from unittest.mock import patch
from specroad.changes import CommitPublicationError
from support.receipts import published, finish
from support.committing import staged, publish
from support.publication import files
from support.folds import goal, edit
if sys.argv[3] == 'partial':
    a, b = goal(1), goal(2)
    with staged(root, artifacts=[a, b], operations=[edit(a, 'A'), edit(b, 'B')]) as (model, plan, check, held, journal):
        print(json.dumps({p: sha256(raw).hexdigest() for p, raw in model.source_files.items()}), flush=True)
        native = os.replace
        targets = []
        def interrupt(src, dst, **kw):
            if dst != 'journal.json' and targets: raise OSError(5, 'interrupt publication')
            result = native(src, dst, **kw)
            if dst != 'journal.json': targets.append(dst)
            return result
        with patch('os.replace', side_effect=interrupt):
            try: publish(check, journal, held)
            except CommitPublicationError: os._exit(23)
        raise AssertionError('publication interruption missing')
else:
    with published(root) as (model, plan, check, held, journal):
        if sys.argv[3] == 'committed': finish(check, held, journal)
        print(json.dumps({p: sha256(raw).hexdigest() for p, raw in files(root).items()}), flush=True)
        os._exit(23)
''', mode, exit_code=23)
    lock = LockRecord(Path(root, '.specroad/locks/project.json').read_bytes())
    raw = Path(root, '.specroad/transactions', TRANSACTION, 'journal.json').read_bytes()
    cls = CommittedJournal if json.loads(raw)['state'] == 'committed' else CommittingJournal
    return lock, cls(raw), json.loads(output)


def takeover(root, lock, journal, **overrides):
    options = dict(project_id=journal.data['project_id'], request_id=journal.data['request_id'],
        expected_lock_sha256=lock.sha256, expected_journal_sha256=journal.sha256,
        authority=RECOVER, actor=ACTOR, reason='Explicit recovery of stopped fixture writer', force=True)
    options.update(overrides)
    return transaction_recovery_lock(root, TRANSACTION, **options)


def complete(held, journal):
    if type(journal) is CommittedJournal:
        return journal
    action = (rollback_interrupted_transaction if journal.data['published_count'] < len(journal.data['files'])
              else complete_published_transaction)
    action(TRANSACTION, held_lock=held, authority=RECOVER, expected_journal_sha256=journal.sha256)


@pytest.mark.parametrize('mode', ['partial', 'target', 'committed'])
def test_real_crashed_writer_can_recover_and_cleanup_with_audited_transfer(tmp_path, mode):
    lock, journal, expected = orphan_writer(tmp_path, mode)
    assert inspect_project_lock(tmp_path).data['owner_state'] == 'dead'
    before = tree(tmp_path)
    with pytest.raises(ProjectLockError) as failure:
        recover_project_lock(tmp_path, project_id='sample', expected_lock_sha256=lock.sha256,
                             actor=ACTOR, reason='Journal must block ordinary lock removal', force=True)
    assert failure.value.reason == 'transaction_journal_blocks_lock' and tree(tmp_path) == before
    with takeover(tmp_path, lock, journal) as held:
        assert held.record.data['kind'] == 'recovery' and held.check()
        assert Path(tmp_path, journal.path).read_bytes() == journal.source_bytes
        complete(held, journal)
        current_sha = sha256(Path(tmp_path, journal.path).read_bytes()).hexdigest()
        cleaned = cleanup_recovered_transaction(TRANSACTION, held_lock=held, authority=RECOVER,
                                                 expected_journal_sha256=current_sha).data
    assert cleaned['cleanup_completed'] and cleaned['normative_writes'] == 0
    assert {path: sha256(raw).hexdigest() for path, raw in files(tmp_path).items()} == expected
    intent_path, = (tmp_path / '.specroad/recovery/transaction-audit').glob('*/takeover-*/intent.json')
    intent, done = json.loads(intent_path.read_bytes()), json.loads(intent_path.with_name('completed.json').read_bytes())
    assert intent['old_record'] == lock.data and intent['lock_sha256'] == lock.sha256
    assert intent['journal_sha256'] == journal.sha256 and intent['authority_id'] == RECOVER.authority_id
    assert intent['new_record']['root_identity'] == lock.data['root_identity']
    assert done['intent']['sha256'] == sha256(intent_path.read_bytes()).hexdigest()
    assert intent_path.with_name('journal.before.json').read_bytes() == journal.source_bytes
    with writer(tmp_path): pass


@pytest.mark.parametrize('case', ['hash', 'journal', 'request', 'project', 'force', 'authority', 'mutating_authority'])
def test_takeover_prechecks_are_write_free_and_transaction_bound(tmp_path, case):
    lock, journal, expected = orphan_writer(tmp_path)
    before = tree(tmp_path)
    def mutate(request):
        request['transaction_id'] = 'foreign'
        return True
    overrides = {
        'hash': {'expected_lock_sha256': '0' * 64},
        'journal': {'expected_journal_sha256': '0' * 64},
        'request': {'request_id': 'foreign'}, 'project': {'project_id': 'foreign'},
        'force': {'force': False},
        'authority': {'authority': RecoveryAuthority('denied', '1', lambda request: False)},
        'mutating_authority': {'authority': RecoveryAuthority('mutating', '1', mutate)},
    }[case]
    with pytest.raises((RecoveryError, ProjectLockError)) as failure:
        with takeover(tmp_path, lock, journal, **overrides): pytest.fail('unsafe takeover')
    assert not failure.value.mutation_possible and tree(tmp_path) == before


@pytest.mark.parametrize('state', ['alive', 'foreign', 'unverifiable', 'pid_reused'])
def test_takeover_preserves_existing_owner_risk_boundaries(tmp_path, state):
    lock, journal, expected = orphan_writer(tmp_path)
    owner = lock.owner
    probes = {'alive': Probe(owner.host_id, 'alive', owner.process_start_id),
              'foreign': Probe('another-host', 'absent'),
              'unverifiable': Probe(None, 'absent'),
              'pid_reused': Probe(owner.host_id, 'alive', 'another-start')}
    before = tree(tmp_path)
    with pytest.raises(ProjectLockError) as failure:
        with takeover(tmp_path, lock, journal, owner_probe=probes[state]): pytest.fail('unsafe owner')
    assert tree(tmp_path) == before
    if state == 'alive':
        with pytest.raises(ProjectLockError):
            with takeover(tmp_path, lock, journal, owner_probe=probes[state], accept_remote_risk=True):
                pytest.fail('live owner overridden')
    else:
        with takeover(tmp_path, lock, journal, owner_probe=probes[state], accept_remote_risk=True) as held:
            assert held.check()
        # Ownership transfer alone never completes or removes the transaction.
        assert Path(tmp_path, journal.path).read_bytes() == journal.source_bytes
        with pytest.raises(ProjectLockError):
            with writer(tmp_path): pass


def test_real_mutex_cannot_be_overridden_by_fabricated_dead_probe(tmp_path):
    from support.committing import staged
    with staged(tmp_path) as (model, plan, preflight, held, journal):
        before = tree(tmp_path)
        with pytest.raises(ProjectLockError) as failure:
            with takeover(tmp_path, held.record, journal,
                          owner_probe=Probe(held.record.owner.host_id, 'absent'), accept_remote_risk=True):
                pytest.fail('mutex bypassed')
        assert failure.value.reason == 'project_lock_busy'
        assert held.check() and tree(tmp_path) == before


def test_takeover_rechecks_journal_after_authorization(tmp_path):
    lock, journal, expected = orphan_writer(tmp_path)
    def mutate(request):
        Path(tmp_path, journal.path).write_bytes(b'changed journal')
        return True
    before = tree(tmp_path)
    with pytest.raises(RecoveryError):
        with takeover(tmp_path, lock, journal, authority=RecoveryAuthority('changing-host', '1', mutate)):
            pytest.fail('changed journal accepted')
    assert tree(tmp_path) == {**before, journal.path: b'changed journal'}


def test_changed_owner_at_transfer_boundary_is_preserved(tmp_path, monkeypatch):
    import specroad.changes.recovery_lock as implementation
    lock, journal, expected = orphan_writer(tmp_path)
    foreign = dict(lock.data, lock_id='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa')
    foreign_bytes = LockRecord(canonical_json_bytes(foreign)).source_bytes
    path = tmp_path / '.specroad/locks/project.json'
    native_image = implementation._image
    def change_owner(*args, **kwargs):
        result = native_image(*args, **kwargs)
        path.write_bytes(foreign_bytes)
        return result
    monkeypatch.setattr(implementation, '_image', change_owner)
    before = files(tmp_path)
    with pytest.raises(RecoveryError) as failure:
        with takeover(tmp_path, lock, journal):
            pytest.fail('changed owner replaced')
    assert failure.value.reason == 'lock_owner_changed' and failure.value.mutation_possible
    assert path.read_bytes() == foreign_bytes and files(tmp_path) == before
    assert Path(tmp_path, journal.path).read_bytes() == journal.source_bytes
    intent, = (tmp_path / '.specroad/recovery/transaction-audit').glob('*/takeover-*/intent.json')
    assert json.loads(intent.read_bytes())['old_record'] == lock.data
    assert not intent.with_name('completed.json').exists()


@pytest.mark.parametrize('boundary', ['intent', 'owner', 'completed', 'archive'])
def test_repeated_real_process_stops_resume_without_removing_foreign_blockers(tmp_path, boundary):
    lock, journal, expected = orphan_writer(tmp_path, 'target')
    foreign = tmp_path / '.specroad/recovery/foreign.json'
    foreign.parent.mkdir(exist_ok=True)
    foreign.write_bytes(b'foreign journal')
    child(tmp_path, '''
from hashlib import sha256
from specroad.changes import (LockRecord, CommittingJournal, RecoveryAuthority,
    transaction_recovery_lock, complete_published_transaction, cleanup_recovered_transaction)
from support.publication import TRANSACTION
from support.targets import ACTOR
lock = LockRecord((root / '.specroad/locks/project.json').read_bytes())
path = root / '.specroad/transactions' / TRANSACTION / 'journal.json'
journal = CommittingJournal(path.read_bytes())
authority = RecoveryAuthority('stopped-recoverer', '1', lambda request: True)
native_sync, native_replace, native_rename = os.fsync, os.replace, os.rename
def sync(fd):
    native_sync(fd)
    name = Path(os.readlink('/proc/self/fd/' + str(fd)))
    if sys.argv[3] == 'intent' and name.name == 'intent.json': os._exit(24)
    if sys.argv[3] == 'completed' and name.name == 'completed.json': os._exit(24)
def replace(src, dst, **kw):
    result = native_replace(src, dst, **kw)
    if sys.argv[3] == 'owner' and dst == 'project.json': os._exit(24)
    return result
def rename(src, dst, **kw):
    result = native_rename(src, dst, **kw)
    if sys.argv[3] == 'archive': os._exit(24)
    return result
os.fsync, os.replace, os.rename = sync, replace, rename
with transaction_recovery_lock(root, TRANSACTION, project_id='sample', request_id=journal.data['request_id'],
        expected_lock_sha256=lock.sha256, expected_journal_sha256=journal.sha256,
        authority=authority, actor=ACTOR, reason='Explicit stopped-writer recovery', force=True) as held:
    complete_published_transaction(TRANSACTION, held_lock=held, authority=authority,
                                   expected_journal_sha256=journal.sha256)
    cleanup_recovered_transaction(TRANSACTION, held_lock=held, authority=authority,
                                   expected_journal_sha256=sha256(path.read_bytes()).hexdigest())
''', boundary, exit_code=24)
    current_lock = LockRecord((tmp_path / '.specroad/locks/project.json').read_bytes())
    active = tmp_path / journal.path
    if active.exists():
        raw = active.read_bytes()
    else:
        raw, = [path.read_bytes() for path in (tmp_path / '.specroad/transactions/receipts').glob('*/committed.json')]
    current = CommittedJournal(raw) if json.loads(raw)['state'] == 'committed' else CommittingJournal(raw)
    with takeover(tmp_path, current_lock, current) as held:
        if type(current) is CommittingJournal:
            complete(held, current)
            raw = active.read_bytes()
        cleaned = cleanup_recovered_transaction(TRANSACTION, held_lock=held, authority=RECOVER,
                                                 expected_journal_sha256=sha256(raw).hexdigest()).data
    assert cleaned['cleanup_completed'] and cleaned['recovery_required']
    assert cleaned['remaining_active_paths'] == ['.specroad/recovery/foreign.json']
    assert foreign.read_bytes() == b'foreign journal'
    assert {path: sha256(raw).hexdigest() for path, raw in files(tmp_path).items()} == expected
