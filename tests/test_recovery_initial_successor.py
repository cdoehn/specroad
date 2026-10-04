"""An interrupted initial rollback helper never exposes unbound partial bytes."""
from contextlib import ExitStack
import errno
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from specroad.changes import (
    LockRecord, RecoveryError, RolledBackJournal,
    cleanup_recovered_transaction, rollback_interrupted_transaction,
)
from specroad.changes import _recovery_rollback as rollback_impl
from support.publication import TRANSACTION, files
from test_terminal_recovery import cleanup, writer
from test_transaction_recovery_rollback import RECOVER, partial_commit, recover
from test_transaction_recovery_lock import child, takeover
from test_recovery_inventory import expected_basis


def snapshot(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob('*')
            if p.is_file() and p.relative_to(root).as_posix() != '.specroad/locks/project.json'}


class InitialFailure:
    """Interrupt native I/O after allocation, partial bytes, or publication."""
    def __init__(self, root, journal, phase):
        self.work = (root / journal.path).parent
        self.phase, self.fd, self.fired = phase, None, False
        self.partial = False
        self.linked = False
        self.open, self.write, self.fsync, self.link = os.open, os.write, os.fsync, os.link

    def opening(self, name, flags, *args, **kwargs):
        fd = self.open(name, flags, *args, **kwargs)
        parent = kwargs.get('dir_fd')
        anonymous = flags & getattr(os, 'O_TMPFILE', 0) == getattr(os, 'O_TMPFILE', -1)
        if parent is not None and (anonymous or name == 'journal.rollback'):
            if Path(os.readlink('/proc/self/fd/' + str(parent))) == self.work:
                self.fd = fd
        return fd

    def writing(self, fd, raw):
        if fd == self.fd and not self.fired and self.phase in ('empty', 'prefix'):
            if self.phase == 'prefix' and not self.partial:
                self.partial = True
                assert self.write(fd, raw[:17]) == 17
                return 17
            self.fired = True
            raise OSError(errno.EIO, 'interrupted initial successor write')
        return self.write(fd, raw)

    def syncing(self, fd):
        result = self.fsync(fd)
        if not self.fired and ((fd == self.fd and self.phase == 'file_sync')
                              or (self.linked and fd != self.fd and self.phase == 'parent_sync')):
            self.fired = True
            raise OSError(errno.EIO, 'lost successful synchronization response')
        return result

    def linking(self, src, dst, **kwargs):
        if dst == 'journal.rollback' and self.phase == 'link_before':
            self.fired = True
            raise OSError(errno.EIO, 'interrupted before link')
        result = self.link(src, dst, **kwargs)
        if dst == 'journal.rollback':
            self.linked = True
            if self.phase == 'link_after':
                self.fired = True
                raise OSError(errno.EIO, 'lost successful link response')
        return result

    def __enter__(self):
        self.stack = ExitStack()
        for name, call in (('open', self.opening), ('write', self.writing),
                           ('fsync', self.syncing), ('link', self.linking)):
            self.stack.enter_context(patch.object(os, name, side_effect=call))
        return self

    def __exit__(self, *exception):
        return self.stack.__exit__(*exception)


@pytest.mark.parametrize('phase', ['empty', 'prefix', 'file_sync', 'link_before', 'link_after', 'parent_sync'])
def test_initial_write_interruption_resumes_basis_without_second_effect(tmp_path, phase):
    model, plan, journal = partial_commit(tmp_path)
    expected_bytes, expected_root = expected_basis(model, plan)
    before = snapshot(tmp_path)
    pending = (tmp_path / journal.path).with_name('journal.rollback')
    with InitialFailure(tmp_path, journal, phase) as failure:
        with pytest.raises(RecoveryError) as error:
            recover(tmp_path, journal)
    assert failure.fired and error.value.mutation_possible
    assert error.value.normative_writes_by_recovery == 0
    if phase in ('link_after', 'parent_sync'):
        expected = rollback_impl._journal_successor(journal, initial=True).source_bytes
        assert snapshot(tmp_path) == {**before, pending.relative_to(tmp_path).as_posix(): expected}
        assert pending.stat().st_nlink == 1
    else:
        assert snapshot(tmp_path) == before
        assert not pending.exists()
    completed = recover(tmp_path, journal)
    assert completed.data['rollback_completed'] and completed.data['normative_writes'] == 1
    assert completed.data['base_model_root_sha256'] == expected_root
    assert files(tmp_path) == expected_bytes
    terminal = RolledBackJournal((tmp_path / journal.path).read_bytes())
    preserved = snapshot(tmp_path)
    with patch.object(os, 'replace', side_effect=AssertionError('second normative effect')):
        repeated = recover(tmp_path, terminal)
    assert repeated.data['normative_writes'] == 0 and snapshot(tmp_path) == preserved
    assert cleanup(tmp_path, terminal).data['cleanup_completed']
    with writer(tmp_path):
        pass
    assert files(tmp_path) == model.source_files


@pytest.mark.parametrize('kind', ['empty', 'prefix', 'conflict', 'extended', 'symlink', 'hardlink'])
def test_unbound_existing_initial_successor_is_preserved(tmp_path, kind):
    _, _, journal = partial_commit(tmp_path)
    pending = (tmp_path / journal.path).with_name('journal.rollback')
    expected = rollback_impl._journal_successor(journal, initial=True).source_bytes
    raw = {'empty': b'', 'prefix': expected[:17], 'conflict': b'foreign',
           'extended': expected + b'foreign'}.get(kind, expected)
    if kind in ('symlink', 'hardlink'):
        outside = tmp_path / 'retained-foreign-file'
        outside.write_bytes(raw)
        if kind == 'symlink':
            pending.symlink_to(outside)
        else:
            os.link(outside, pending)
    else:
        pending.write_bytes(raw)
    before, identity = snapshot(tmp_path), pending.lstat().st_ino
    with pytest.raises(RecoveryError):
        recover(tmp_path, journal)
    assert snapshot(tmp_path) == before and pending.lstat().st_ino == identity
    assert (tmp_path / journal.path).read_bytes() == journal.source_bytes


@pytest.mark.parametrize('same_prefix', [False, True])
def test_foreign_initial_successor_appearing_at_link_is_not_replaced(tmp_path, same_prefix):
    _, _, journal = partial_commit(tmp_path)
    pending = (tmp_path / journal.path).with_name('journal.rollback')
    raw = rollback_impl._journal_successor(journal, initial=True).source_bytes[:17] if same_prefix else b'foreign'
    before = snapshot(tmp_path)
    native = os.link
    def race(src, dst, **kwargs):
        if dst == 'journal.rollback':
            pending.write_bytes(raw)
        return native(src, dst, **kwargs)
    with patch.object(os, 'link', side_effect=race):
        with pytest.raises(RecoveryError) as error:
            recover(tmp_path, journal)
    assert error.value.reason == 'recovery_journal_successor_conflict'
    assert snapshot(tmp_path) == {**before, pending.relative_to(tmp_path).as_posix(): raw}
    with pytest.raises(RecoveryError):
        recover(tmp_path, journal)
    assert pending.read_bytes() == raw


@pytest.mark.parametrize('changed', ['journal', 'target'])
def test_initial_publication_rechecks_bound_inputs_after_staging(tmp_path, changed):
    _, _, journal = partial_commit(tmp_path)
    path = tmp_path / (journal.path if changed == 'journal' else journal.data['files'][0]['path'])
    before = snapshot(tmp_path)
    native, fired = os.fsync, []
    def mutate(fd):
        result = native(fd)
        if os.fstat(fd).st_nlink == 0 and not fired:
            fired.append(True)
            path.write_bytes(b'foreign changed input')
        return result
    with patch.object(os, 'fsync', side_effect=mutate):
        with pytest.raises(RecoveryError) as error:
            recover(tmp_path, journal)
    assert fired and error.value.exit_code == 6
    assert snapshot(tmp_path) == {**before, path.relative_to(tmp_path).as_posix(): b'foreign changed input'}


@pytest.mark.parametrize('damage', ['changed', 'truncated'])
def test_initial_staged_content_is_verified_before_publication(tmp_path, damage):
    model, _, journal = partial_commit(tmp_path)
    before = snapshot(tmp_path)
    native, fired = os.fsync, []
    def corrupt(fd):
        result = native(fd)
        if os.fstat(fd).st_nlink == 0 and not fired:
            fired.append(True)
            if damage == 'truncated':
                os.ftruncate(fd, 17)
            else:
                os.lseek(fd, 0, os.SEEK_SET)
                os.write(fd, b'X')
        return result
    with patch.object(os, 'fsync', side_effect=corrupt):
        with pytest.raises(RecoveryError) as error:
            recover(tmp_path, journal)
    assert fired and error.value.reason == 'recovery_initial_stage_changed'
    assert snapshot(tmp_path) == before
    assert recover(tmp_path, journal).data['rollback_completed']
    assert files(tmp_path) == model.source_files


def test_changed_published_initial_helper_never_replaces_original_journal(tmp_path):
    _, _, journal = partial_commit(tmp_path)
    pending = (tmp_path / journal.path).with_name('journal.rollback')
    before = snapshot(tmp_path)
    native, fired = rollback_impl._prove_rollback_inputs, []
    def change_after_check(*args, **kwargs):
        result = native(*args, **kwargs)
        if pending.exists() and not fired:
            fired.append(True)
            pending.write_bytes(b'changed before journal replacement')
        return result
    with patch.object(rollback_impl, '_prove_rollback_inputs', side_effect=change_after_check):
        with pytest.raises(RecoveryError) as error:
            recover(tmp_path, journal)
    assert fired and error.value.exit_code == 6
    assert snapshot(tmp_path) == {**before, pending.relative_to(tmp_path).as_posix():
                                 b'changed before journal replacement'}


@pytest.mark.parametrize('missing', ['flag', 'filesystem', 'proc_link'])
def test_unavailable_initial_atomic_staging_preserves_project(tmp_path, monkeypatch, missing):
    _, _, journal = partial_commit(tmp_path)
    before = snapshot(tmp_path)
    if missing == 'flag':
        monkeypatch.delattr(os, 'O_TMPFILE')
    elif missing == 'filesystem':
        native = os.open
        def unavailable(name, flags, *args, **kwargs):
            if flags & os.O_TMPFILE == os.O_TMPFILE:
                raise OSError(errno.EOPNOTSUPP, 'no anonymous staging on this filesystem')
            return native(name, flags, *args, **kwargs)
        monkeypatch.setattr(os, 'open', unavailable)
    else:
        monkeypatch.setattr(os, 'link', lambda *a, **kw: (_ for _ in ()).throw(
            OSError(errno.ENOENT, 'no usable proc descriptor link')))
    with pytest.raises(RecoveryError) as error:
        recover(tmp_path, journal)
    assert error.value.exit_code == 5 and error.value.normative_writes_by_recovery == 0
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize('phase', ['empty', 'prefix'])
def test_real_initial_process_stop_resumes_with_audited_native_takeover(tmp_path, phase):
    model, _, journal = partial_commit(tmp_path)
    before = snapshot(tmp_path)
    child(tmp_path, '''
from unittest.mock import patch
from specroad.changes import CommittingJournal
from test_transaction_recovery_rollback import recover
journal = CommittingJournal((root / sys.argv[3]).read_bytes())
native_open, native_write = os.open, os.write
selected = []
def opening(name, flags, *args, **kwargs):
    fd = native_open(name, flags, *args, **kwargs)
    if flags & os.O_TMPFILE == os.O_TMPFILE:
        selected.append(fd)
        if sys.argv[4] == 'empty': os._exit(23)
    return fd
def writing(fd, raw):
    if fd in selected:
        assert native_write(fd, raw[:17]) == 17
        os._exit(23)
    return native_write(fd, raw)
with patch.object(os, 'open', side_effect=opening), patch.object(os, 'write', side_effect=writing):
    recover(root, journal)
raise AssertionError('missing process interruption')
''', journal.path, phase, exit_code=23)
    assert snapshot(tmp_path) == before
    lock = LockRecord((tmp_path / '.specroad/locks/project.json').read_bytes())
    with takeover(tmp_path, lock, journal) as held:
        result = rollback_interrupted_transaction(TRANSACTION, held_lock=held,
            authority=RECOVER, expected_journal_sha256=journal.sha256)
        assert result.data['rollback_completed'] and files(tmp_path) == model.source_files
        current = RolledBackJournal((tmp_path / journal.path).read_bytes())
        retry = rollback_interrupted_transaction(TRANSACTION, held_lock=held,
            authority=RECOVER, expected_journal_sha256=current.sha256)
        assert retry.data['normative_writes'] == 0
        cleaned = cleanup_recovered_transaction(TRANSACTION, held_lock=held,
            authority=RECOVER, expected_journal_sha256=current.sha256)
        assert cleaned.data['cleanup_completed']
    with writer(tmp_path):
        pass
    assert files(tmp_path) == model.source_files
