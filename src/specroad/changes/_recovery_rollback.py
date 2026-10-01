"""Deterministic recovery rollback from an interrupted committing journal.

The journal is moved to ``rolling_back`` before any normative target is changed.
Each changed target is then handled in reverse journal order.  Before images stay
intact; restoration uses a private rollback copy and an atomic target replace.
Newly-created target bytes are atomically moved into the transaction rollback
area instead of being destroyed.  A durable journal decrement follows each
observed/restored basis member.
"""
from hashlib import sha256
import os

from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..security import SafetyViolation
from ..security import paths as guards
from ..storage.byte_binding import fingerprint_reader
from .committing_values import CommittingJournal
from .execution_values import ChangeExecutionError
from .locking import HeldProjectLock
from .publication_check import _rights
from .recovery_values import (RecoveryAuthority, RecoveryError,
    RecoveryObservation, RolledBackJournal, RollingBackJournal)
from ._journal_codec import _hash, _transaction
from ._journal_io import _read
from ._recovery_inputs import _parse, _read_journal
from ._recovery_target import prove_complete_target
from ._staging_files import _image, _write_new

_BLOCK = 65536


def _rollback_lock(held, journal):
    if type(held) is not HeldProjectLock:
        raise RecoveryError('native_recovery_lock_required', exit_code=7)
    held.check()
    lock, data = held.record.data, journal.data
    if (lock['kind'] != 'recovery' or lock['command'] != 'recover run'
            or lock['transaction_id'] != data['transaction_id']
            or lock['project_id'] != data['project_id']
            or lock['request_id'] != data['request_id']):
        raise RecoveryError('recovery_lock_binding_mismatch', exit_code=6)


def _authorize(authority, journal):
    request = {
        'action': 'rollback',
        'transaction_id': journal.data['transaction_id'],
        'project_id': journal.data['project_id'],
        'request_id': journal.data['request_id'],
        'journal_sha256': journal.sha256,
        'base_model_root_sha256': journal.data['base_model_root_sha256'],
        'target_model_root_sha256': journal.data['target_model_root_sha256'],
    }
    raw = canonical_json_bytes(request)
    try:
        allowed = authority.check(request)
    except Exception as error:
        raise RecoveryError('recovery_authority_failed', exit_code=7) from error
    if canonical_json_bytes(request) != raw or type(allowed) is not bool or not allowed:
        raise RecoveryError('recovery_not_authorized', exit_code=7)


def _fingerprint(files, logical_path):
    parts = tuple(logical_path.split('/'))
    try:
        with files.directory(parts[:-1]) as directory:
            if directory is None:
                return None
            try:
                before = os.stat(parts[-1], dir_fd=directory, follow_symlinks=False)
            except FileNotFoundError:
                return None
            guards._regular(before)
            if before.st_nlink != 1:
                raise RecoveryError('recovery_linked_target_refused', path=logical_path, exit_code=7)
            fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW |
                         getattr(os, 'O_NONBLOCK', 0) | getattr(os, 'O_CLOEXEC', 0),
                         dir_fd=directory)
            try:
                first = os.fstat(fd)
                guards._regular(first)
                if first.st_nlink != 1 or guards._signature(first) != guards._signature(before):
                    raise RecoveryError('recovery_target_changed', path=logical_path, exit_code=6)
                observed = fingerprint_reader(lambda n: os.read(fd, n), first.st_size)
                after = os.stat(parts[-1], dir_fd=directory, follow_symlinks=False)
                if (guards._signature(first) != guards._signature(after)
                        or guards._signature(first) != guards._signature(os.fstat(fd))):
                    raise RecoveryError('recovery_target_changed', path=logical_path, exit_code=6)
                return {'identity': guards._identity(first), 'size': observed.size,
                        'sha256': observed.sha256, 'mode': first.st_mode & 0o7777}
            finally:
                os.close(fd)
    except RecoveryError:
        raise
    except SafetyViolation as error:
        raise RecoveryError('unsafe_recovery_target', path=logical_path, exit_code=7) from error


def _state(files, entry):
    token = _fingerprint(files, entry['path'])
    if token is None:
        if entry['existed_before']:
            raise RecoveryError('recovery_target_missing', path=entry['path'], exit_code=6)
        return 'base', None
    after = (entry['after_size'], entry['after_sha256'])
    observed = (token['size'], token['sha256'])
    if observed == after:
        return 'target', token
    if entry['existed_before'] and observed == (entry['before_size'], entry['before_sha256']):
        return 'base', token
    raise RecoveryError('recovery_target_mismatch', path=entry['path'], exit_code=6)


def _prove_basis(files, journal):
    changed = {entry['path']: entry for entry in journal.data['files']}
    for item in journal.data['target_inventory']:
        entry = changed.get(item['path'])
        if entry is not None:
            state, _ = _state(files, entry)
            if state != 'base':
                raise RecoveryError('recovery_basis_not_restored', path=item['path'], exit_code=6)
            continue
        token = _fingerprint(files, item['path'])
        if token is None or (token['size'], token['sha256']) != (item['size'], item['sha256']):
            raise RecoveryError('recovery_basis_unchanged_resource_mismatch', path=item['path'], exit_code=6)
    return journal.data['base_model_root_sha256']


def _journal_successor(journal, *, initial=False, terminal=False):
    data = journal.data
    if initial:
        rollback = {'started_from_sha256': journal.sha256,
                    'started_from_published_count': data['published_count']}
        data['state'] = 'rolling_back'
        data['rollback'] = rollback
        data['published_count'] = len(data['files'])
        for entry in data['files']:
            entry['published'] = True
        return RollingBackJournal(canonical_json_bytes(data))
    if terminal:
        if data['published_count'] != 0:
            raise RecoveryError('rollback_not_complete', exit_code=6)
        data['state'] = 'rolled_back'
        return RolledBackJournal(canonical_json_bytes(data))
    count = data['published_count']
    if count <= 0:
        raise RecoveryError('rollback_cursor_invalid', exit_code=6)
    data['files'][count - 1]['published'] = False
    data['published_count'] = count - 1
    return RollingBackJournal(canonical_json_bytes(data))


def _ensure_exact_file(directory, name, raw, *, reason):
    """Create once or resume an exact durable operational file after interruption."""
    digest = sha256(raw).hexdigest()
    try:
        info = os.stat(name, dir_fd=directory, follow_symlinks=False)
    except FileNotFoundError:
        identity = _write_new(directory, name, raw)
    else:
        try:
            guards._regular(info)
            if info.st_nlink != 1:
                raise RecoveryError(reason, exit_code=7)
            identity = guards._identity(info)
            if _read(directory, name, expected_identity=identity) != raw:
                raise RecoveryError(reason, exit_code=6)
        except (SafetyViolation, ChangeExecutionError) as error:
            if isinstance(error, RecoveryError):
                raise
            raise RecoveryError(reason, exit_code=6) from error
    _image(directory, name, len(raw), digest, identity=identity)
    return identity


def _replace_journal(files, journal, successor, directory_identity):
    prefix = tuple(journal.path.split('/')[:-1])
    with files.directory(prefix) as directory:
        if directory is None or guards._identity(os.fstat(directory)) != directory_identity:
            raise RecoveryError('recovery_work_changed', exit_code=6)
        if _read(directory, 'journal.json') != journal.source_bytes:
            raise RecoveryError('recovery_journal_changed', exit_code=6)
        _ensure_exact_file(directory, 'journal.rollback', successor.source_bytes,
                           reason='recovery_journal_successor_conflict')
        os.replace('journal.rollback', 'journal.json', src_dir_fd=directory, dst_dir_fd=directory)
        os.fsync(directory)


def _copy_before(files, journal, entry, index, target_token):
    prefix = tuple(journal.path.split('/')[:-1])
    before_name = entry['before_image_path'].rsplit('/', 1)[-1]
    with files.directory((*prefix, 'before')) as before:
        if before is None:
            raise RecoveryError('recovery_before_image_missing', path=entry['path'], exit_code=6)
        _image(before, before_name, entry['before_size'], entry['before_sha256'])
        raw = _read(before, before_name)
    with files.directory((*prefix, 'rollback'), create=True) as rollback:
        name = str(index) + '.bin'
        identity = _ensure_exact_file(rollback, name, raw,
                                      reason='recovery_restore_stage_conflict')
        parts = tuple(entry['path'].split('/'))
        with files.directory(parts[:-1]) as target:
            if target is None:
                raise RecoveryError('recovery_target_parent_missing', path=entry['path'], exit_code=6)
            if os.fstat(target).st_dev != os.fstat(rollback).st_dev:
                raise RecoveryError('recovery_cross_device', path=entry['path'], exit_code=7)
            _rights(target, entry['path'])
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, 'O_CLOEXEC', 0), dir_fd=rollback)
            try:
                if guards._identity(os.fstat(fd)) != identity:
                    raise RecoveryError('recovery_image_changed', path=entry['path'], exit_code=6)
                if target_token['mode'] & 0o7000:
                    raise RecoveryError('unsafe_recovery_mode', path=entry['path'], exit_code=7)
                os.fchmod(fd, target_token['mode'])
                os.fsync(fd)
            finally:
                os.close(fd)
            os.replace(name, parts[-1], src_dir_fd=rollback, dst_dir_fd=target)
            os.fsync(target); os.fsync(rollback)
            _image(target, parts[-1], entry['before_size'], entry['before_sha256'])


def _remove_created(files, journal, entry, index, target_token):
    prefix = tuple(journal.path.split('/')[:-1])
    parts = tuple(entry['path'].split('/'))
    with files.directory((*prefix, 'rollback'), create=True) as rollback:
        with files.directory(parts[:-1]) as target:
            if target is None:
                raise RecoveryError('recovery_target_parent_missing', path=entry['path'], exit_code=6)
            if os.fstat(target).st_dev != os.fstat(rollback).st_dev:
                raise RecoveryError('recovery_cross_device', path=entry['path'], exit_code=7)
            _rights(target, entry['path'])
            _image(target, parts[-1], entry['after_size'], entry['after_sha256'],
                   identity=target_token['identity'])
            name = str(index) + '.removed'
            try:
                os.stat(name, dir_fd=rollback, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                raise RecoveryError('recovery_rollback_stash_collision', path=entry['path'], exit_code=6)
            os.replace(parts[-1], name, src_dir_fd=target, dst_dir_fd=rollback)
            os.fsync(target); os.fsync(rollback)
            _image(rollback, name, entry['after_size'], entry['after_sha256'],
                   identity=target_token['identity'])


def rollback_interrupted_transaction(transaction_id, *, held_lock, authority,
                                     expected_journal_sha256):
    """Restore an interrupted commit to its journal-bound complete basis."""
    _transaction(transaction_id)
    if not _hash(expected_journal_sha256):
        raise RecoveryError('expected_recovery_journal_sha256_required', exit_code=2)
    if type(authority) is not RecoveryAuthority:
        raise RecoveryError('recovery_authority_required', exit_code=2)
    if type(held_lock) is not HeldProjectLock:
        raise RecoveryError('native_recovery_lock_required', exit_code=7)
    writes = 0
    mutated = False
    try:
        files = held_lock._files
        raw, directory_identity = _read_journal(files, transaction_id)
        journal = _parse(raw, transaction_id, files)
        if journal.sha256 != expected_journal_sha256:
            raise RecoveryError('recovery_journal_changed', exit_code=6)
        if type(journal) is RolledBackJournal:
            _rollback_lock(held_lock, journal)
            _authorize(authority, journal)
            root = _prove_basis(files, journal)
            return RecoveryObservation._create({'format_version': 'recovery-rollback-v1',
                'state': 'rolled_back', 'transaction_id': transaction_id,
                'journal_sha256': journal.sha256, 'base_model_root_sha256': root,
                'rollback_completed': True, 'normative_writes': 0,
                'model_loaded': False, 'write_authorized': False, 'atomic_snapshot': False})
        if type(journal) is CommittingJournal:
            _rollback_lock(held_lock, journal)
            try:
                prove_complete_target(files, journal)
            except RecoveryError:
                pass
            else:
                raise RecoveryError('recovery_full_target_requires_completion', exit_code=6)
            # Refuse unknown bytes before changing the journal.
            for entry in journal.data['files']:
                _state(files, entry)
            _authorize(authority, journal)
            _rollback_lock(held_lock, journal)
            successor = _journal_successor(journal, initial=True)
            mutated = True
            _replace_journal(files, journal, successor, directory_identity)
            raw, directory_identity = _read_journal(files, transaction_id)
            journal = _parse(raw, transaction_id, files)
        if type(journal) is not RollingBackJournal:
            raise RecoveryError('recovery_rollback_state_required', exit_code=6)
        _rollback_lock(held_lock, journal)
        _authorize(authority, journal)
        while journal.data['published_count']:
            _rollback_lock(held_lock, journal)
            index = journal.data['published_count'] - 1
            entry = journal.data['files'][index]
            state, token = _state(files, entry)
            if state == 'target':
                mutated = True
                if entry['existed_before']:
                    _copy_before(files, journal, entry, index, token)
                else:
                    _remove_created(files, journal, entry, index, token)
                writes += 1
                if _state(files, entry)[0] != 'base':
                    raise RecoveryError('recovery_basis_write_unverified', path=entry['path'], exit_code=6)
            successor = _journal_successor(journal)
            mutated = True
            _replace_journal(files, journal, successor, directory_identity)
            raw, directory_identity = _read_journal(files, transaction_id)
            journal = _parse(raw, transaction_id, files)
        root = _prove_basis(files, journal)
        terminal = _journal_successor(journal, terminal=True)
        mutated = True
        _replace_journal(files, journal, terminal, directory_identity)
        raw, _ = _read_journal(files, transaction_id)
        current = _parse(raw, transaction_id, files)
        if type(current) is not RolledBackJournal or current.source_bytes != terminal.source_bytes:
            raise RecoveryError('recovery_rolled_back_marker_changed', exit_code=6)
        if _prove_basis(files, current) != root:
            raise RecoveryError('recovery_basis_changed', exit_code=6)
        return RecoveryObservation._create({'format_version': 'recovery-rollback-v1',
            'state': 'rolled_back', 'transaction_id': transaction_id,
            'journal_sha256': current.sha256, 'base_model_root_sha256': root,
            'rollback_completed': True, 'normative_writes': writes,
            'model_loaded': False, 'write_authorized': False, 'atomic_snapshot': False})
    except RecoveryError as error:
        error.mutation_possible |= mutated
        error.normative_writes_by_recovery = max(
            getattr(error, 'normative_writes_by_recovery', 0), writes)
        raise
    except (OSError, SafetyViolation, ModelError, ChangeExecutionError) as error:
        raise RecoveryError(getattr(error, 'reason', 'recovery_rollback_failed'),
            path=getattr(error, 'path', None), exit_code=getattr(error, 'exit_code', 5),
            mutation_possible=mutated, normative_writes_by_recovery=writes) from error
