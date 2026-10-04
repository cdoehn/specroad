"""Exact receipt detection and repair for full-target recovery."""
import os
from ..security import paths as guards
from ._journal_io import _read
from .execution_values import ChangeExecutionError
from .recovery_values import RecoveryError


def existing_recovery_record(files, record):
    """Return an exact durable record token, or None when it is absent."""
    parts, name = tuple(record.path.split('/')[:-1]), record.path.rsplit('/', 1)[-1]
    with files.directory(parts) as directory:
        if directory is None:
            return None
        try:
            info = os.stat(name, dir_fd=directory, follow_symlinks=False)
        except FileNotFoundError:
            return None
        guards._regular(info)
        identity = guards._identity(info)
        try:
            raw = _read(directory, name, expected_identity=identity)
        except ChangeExecutionError as error:
            raise RecoveryError('recovery_receipt_conflict', path=record.path, exit_code=6) from error
        if raw != record.source_bytes:
            raise RecoveryError('recovery_receipt_conflict', path=record.path, exit_code=6)
        return raw, identity


def recheck_recovery_record(files, record, token):
    if existing_recovery_record(files, record) != token:
        raise RecoveryError('recovery_receipt_changed', path=record.path, exit_code=6)


def ensure_recovery_record(files, record, *, write_new, before_create=None,
                           before_publish=None):
    """Reuse exact evidence; announce possible writes before creating its parents."""
    token = existing_recovery_record(files, record)
    if token is not None:
        return token, False
    parts, name = tuple(record.path.split('/')[:-1]), record.path.rsplit('/', 1)[-1]
    if before_create is not None:
        before_create()
    with files.directory(parts, create=True) as directory:
        if before_publish is None:
            identity = write_new(directory, name, record.source_bytes)
        else:
            parent_identity = guards._identity(os.fstat(directory))
            def check():
                before_publish()
                with files.directory(parts) as current:
                    if current is None or guards._identity(os.fstat(current)) != parent_identity:
                        raise RecoveryError('recovery_receipt_changed', path=record.path, exit_code=6)
            identity = write_new(directory, name, record.source_bytes, before_publish=check)
    token = existing_recovery_record(files, record)
    if token is None or token[1] != identity:
        raise RecoveryError('recovery_receipt_changed', path=record.path, exit_code=6)
    return token, True
