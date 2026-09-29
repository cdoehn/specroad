"""Exclusive descriptor-relative building journal creation; no model writes."""
import os
from ..security import SafetyViolation
from ..security import paths as guards
from ._lock_files import LockFiles
from .lock_values import ProjectLockError
from .journal_values import JournalError


def _read(parent, name, *, expected_identity=None):
    before=os.stat(name,dir_fd=parent,follow_symlinks=False)
    guards._regular(before)
    if expected_identity is not None and guards._identity(before)!=expected_identity:
        raise JournalError('journal_file_replaced',exit_code=6)
    if before.st_nlink != 1:
        raise JournalError('journal_hardlink_refused',exit_code=7)
    fd=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|getattr(os,'O_NONBLOCK',0)|getattr(os,'O_CLOEXEC',0),dir_fd=parent)
    try:
        first=os.fstat(fd); guards._regular(first)
        if first.st_nlink != 1 or guards._signature(first) != guards._signature(before):
            raise JournalError('journal_changed_during_read',exit_code=6)
        out=bytearray()
        while len(out) <= first.st_size:
            b=os.read(fd,min(65536,first.st_size+1-len(out)))
            if not b:break
            out.extend(b)
        after=os.stat(name,dir_fd=parent,follow_symlinks=False)
        if (len(out)!=first.st_size or guards._signature(after)!=guards._signature(first)
                or guards._signature(os.fstat(fd))!=guards._signature(first)):
            raise JournalError('journal_changed_during_read',exit_code=6)
        return bytes(out)
    finally:os.close(fd)


def read_record(source,path):
    try:
        with LockFiles(source.boundary.root) as files:
            if files.boundary._root_identity!=source.boundary._root_identity:
                raise JournalError('journal_root_changed',exit_code=6,path=path)
            with files.directory(tuple(path.split('/')[:-1])) as parent:
                if parent is None:raise JournalError('journal_missing',exit_code=5,path=path)
                return _read(parent,'journal.json')
    except JournalError:raise
    except ProjectLockError as e:
        raise JournalError(e.reason,exit_code=e.exit_code,path=path) from e
    except SafetyViolation as e:
        raise JournalError('unsafe_journal_path',exit_code=7,path=path) from e
    except OSError as e:
        raise JournalError('journal_read_failed',exit_code=5,path=path) from e


def persist_building_record(journal,held):
    path=journal.path; txn=journal.data['transaction_id']; possible=False
    try:
        held.check()
        files=held._files
        if files.journal_entries():
            raise JournalError('journal_recovery_required',exit_code=5,path=path)
        # Starting namespace creation can leave recovery-relevant information.
        possible=True
        with files.directory(('.specroad','transactions'),create=True) as parent:
            held.check()
            if files.journal_entries():
                raise JournalError('journal_recovery_required',exit_code=5,path=path)
            os.mkdir(txn,mode=0o700,dir_fd=parent)  # Never reuse an existing namespace.
            created=os.stat(txn,dir_fd=parent,follow_symlinks=False)
            guards._regular(created,directory=True)
            os.fsync(parent)
            with files.directory(('.specroad','transactions',txn)) as directory:
                held.check()
                if guards._identity(os.fstat(directory))!=guards._identity(created):
                    raise JournalError('journal_directory_replaced',exit_code=6,path=path)
                if files.journal_entries()!=('.specroad/transactions/'+txn,):
                    raise JournalError('journal_recovery_set_changed',exit_code=6,path=path)
                if os.listdir(directory):
                    raise JournalError('journal_namespace_not_empty',exit_code=6,path=path)
                fd=os.open('journal.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|
                           getattr(os,'O_CLOEXEC',0),0o600,dir_fd=directory)
                try:
                    identity=guards._identity(os.fstat(fd))
                    raw=journal.source_bytes; offset=0
                    while offset<len(raw):
                        n=os.write(fd,raw[offset:])
                        if n<=0:raise JournalError('journal_short_write',exit_code=5,path=path)
                        offset+=n
                    os.fsync(fd)
                    if os.fstat(fd).st_size!=len(raw):
                        raise JournalError('journal_write_incomplete',exit_code=5,path=path)
                finally:os.close(fd)
                os.fsync(directory)
                if _read(directory,'journal.json',expected_identity=identity)!=raw:
                    raise JournalError('journal_readback_mismatch',exit_code=6,path=path)
                held.check()
                if files.journal_entries()!=('.specroad/transactions/'+txn,):
                    raise JournalError('journal_recovery_set_changed',exit_code=6,path=path)
                if sorted(os.listdir(directory))!=['journal.json']:
                    raise JournalError('journal_namespace_changed',exit_code=6,path=path)
        held.check()
    except JournalError as e:
        e.mutation_possible |= possible
        raise
    except ProjectLockError as e:
        raise JournalError(e.reason,exit_code=e.exit_code,path=path,mutation_possible=possible) from e
    except SafetyViolation as e:
        raise JournalError('unsafe_journal_path',exit_code=7,path=path,mutation_possible=possible) from e
    except OSError as e:
        raise JournalError('journal_io_failure',exit_code=5,path=path,mutation_possible=possible) from e
