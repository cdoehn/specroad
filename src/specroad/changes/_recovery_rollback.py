"""Deterministic recovery rollback from an interrupted committing journal.

The journal is moved to ``rolling_back`` before any normative target is changed.
Each changed target is then handled in reverse journal order.  Before images stay
intact; restoration uses a private rollback copy and an atomic target replace.
Newly-created target bytes are atomically moved into the transaction rollback
area instead of being destroyed.  A durable journal decrement follows each
observed/restored basis member.
"""
import os

from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..security import SafetyViolation
from ..security import paths as guards
from .committing_values import CommittingJournal
from .execution_values import ChangeExecutionError
from .locking import HeldProjectLock
from ._recovery_binding import check_run_lock as _rollback_lock
from ._recovery_binding import check_directory_binding, check_journal_binding
from .publication_check import _rights
from .recovery_values import (RecoveryAuthority, RecoveryError,
    RecoveryObservation, RolledBackJournal, RollingBackJournal)
from ._journal_codec import _hash, _transaction
from ._journal_io import _read
from ._recovery_inputs import _parse, _read_journal
from ._recovery_inventory import verified_membership
from ._recovery_bytes import fingerprint_recovery_file as _fingerprint
from ._staging_files import _image
from ._publication_io import replace_bound_image
from ._recovery_evidence import EvidenceRecord, rollback_evidence, sync_evidence
from ._recovery_receipts import existing_recovery_record
from ._recovery_initial import write_initial_successor
from ._recovery_files import ensure_exact_recovery_file, write_recovery_file
from ._writer_pending import writer_next


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
    with verified_membership(files, journal, phase='base'):
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


def _prove_rollback_inputs(files, journal):
    """Reject an unrestorable inventory before altering any recovery state."""
    with verified_membership(files, journal, phase='intermediate'):
        changed = {entry['path']: entry for entry in journal.data['files']}
        tokens = {}
        for item in journal.data['target_inventory']:
            entry = changed.get(item['path'])
            if entry is not None:
                _, tokens[item['path']] = _state(files, entry)
                continue
            token = _fingerprint(files, item['path'])
            if token is None or (token['size'], token['sha256']) != (item['size'], item['sha256']):
                raise RecoveryError('recovery_basis_unchanged_resource_mismatch', path=item['path'], exit_code=6)
            tokens[item['path']] = token
        return tokens


def _rollback_guard(files, journal, directory_identity, held_lock):
    observed = _prove_rollback_inputs(files, journal)
    pending = writer_next(files, journal)
    def check():
        _rollback_lock(held_lock, journal)
        if _read_journal(files, journal.data['transaction_id']) != (journal.source_bytes, directory_identity):
            raise RecoveryError('recovery_journal_changed', exit_code=6)
        if _prove_rollback_inputs(files, journal) != observed:
            raise RecoveryError('recovery_basis_changed', exit_code=6)
        if writer_next(files, journal) != pending:
            raise RecoveryError('recovery_writer_successor_changed', exit_code=6)
    return check


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


def _replace_journal(files, journal, successor, directory_identity, *, before_publish):
    prefix = tuple(journal.path.split('/')[:-1])
    with files.directory(prefix) as directory:
        check_journal_binding(directory, journal, directory_identity)
        def unchanged():
            before_publish()
            with files.directory(prefix) as current:
                check_journal_binding(current, journal, directory_identity)

        def create(parent, name, raw):
            if type(journal) is CommittingJournal:
                return write_initial_successor(parent, name, raw, before_publish=unchanged)
            return write_recovery_file(parent, name, raw, before_publish=unchanged,
                                       conflict_reason='recovery_journal_successor_conflict')

        identity = ensure_exact_recovery_file(
            directory, 'journal.rollback', successor.source_bytes,
            reason='recovery_journal_successor_conflict', write_new=create)
        unchanged()
        _image(directory, 'journal.rollback', len(successor.source_bytes),
               successor.sha256, identity=identity)
        os.replace('journal.rollback', 'journal.json', src_dir_fd=directory, dst_dir_fd=directory)
        os.fsync(directory)


def _copy_before(files, journal, entry, index, target_token, *, before_publish):
    prefix = tuple(journal.path.split('/')[:-1])
    before_name = entry['before_image_path'].rsplit('/', 1)[-1]
    with files.directory((*prefix, 'before')) as before:
        if before is None:
            raise RecoveryError('recovery_before_image_missing', path=entry['path'], exit_code=6)
        source_identity = _image(before, before_name, entry['before_size'], entry['before_sha256'])
        raw = _read(before, before_name)
    with files.directory((*prefix, 'rollback'), create=True) as rollback:
        name = str(index) + '.bin'
        parent_identity = guards._identity(os.fstat(rollback))
        def check():
            before_publish()
            with files.directory((*prefix, 'before')) as source:
                if source is None:
                    raise RecoveryError('recovery_before_image_missing', path=entry['path'], exit_code=6)
                _image(source, before_name, entry['before_size'], entry['before_sha256'],
                       identity=source_identity)
            with files.directory((*prefix, 'rollback')) as current:
                check_directory_binding(current, parent_identity)
        def create(parent, filename, content):
            return write_recovery_file(parent, filename, content, before_publish=check,
                                       conflict_reason='recovery_restore_stage_conflict')
        identity = ensure_exact_recovery_file(
            rollback, name, raw, reason='recovery_restore_stage_conflict', write_new=create)
        check()
        parts = tuple(entry['path'].split('/'))
        with files.directory(parts[:-1]) as target:
            if target is None:
                raise RecoveryError('recovery_target_parent_missing', path=entry['path'], exit_code=6)
            if os.fstat(target).st_dev != os.fstat(rollback).st_dev:
                raise RecoveryError('recovery_cross_device', path=entry['path'], exit_code=7)
            if target_token['mode'] & 0o7000:
                raise RecoveryError('unsafe_recovery_mode', path=entry['path'], exit_code=7)
            replace_bound_image(rollback, name, target, parts[-1],
                size=entry['before_size'], digest=entry['before_sha256'], identity=identity,
                mode=target_token['mode'],
                source_changed=lambda: RecoveryError(
                    'recovery_image_changed', path=entry['path'], exit_code=6),
                before_open=lambda: _rights(target, entry['path']))


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
            replace_bound_image(target, parts[-1], rollback, name,
                size=entry['after_size'], digest=entry['after_sha256'],
                identity=target_token['identity'],
                source_changed=lambda: RecoveryError(
                    'recovery_target_changed', path=entry['path'], exit_code=6))


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
        pending = writer_next(files, journal)
        if type(journal) is RolledBackJournal:
            _rollback_lock(held_lock, journal)
            _authorize(authority, journal)
            if writer_next(files, journal) != pending:
                raise RecoveryError('recovery_writer_successor_changed', exit_code=6)
            root = _prove_basis(files, journal)
            if _read_journal(files, transaction_id) != (raw, directory_identity):
                raise RecoveryError('recovery_journal_changed', exit_code=6)
            marker = EvidenceRecord(journal.path, journal.source_bytes)
            sync_evidence(files, marker, existing_recovery_record(files, marker))
            action, receipt = rollback_evidence(files, journal, authority=authority,
                write_new=write_recovery_file,
                before_publish=_rollback_guard(files, journal, directory_identity, held_lock))
            _rollback_lock(held_lock, journal)
            if (_read_journal(files, transaction_id) != (raw, directory_identity)
                    or _prove_basis(files, journal) != root):
                raise RecoveryError('recovery_basis_changed', exit_code=6)
            return RecoveryObservation._create({'format_version': 'recovery-rollback-v1',
                'state': 'rolled_back', 'transaction_id': transaction_id,
                'journal_sha256': journal.sha256, 'base_model_root_sha256': root,
                'rollback_completed': True, 'normative_writes': 0,
                'receipt': receipt.reference, 'recovery_audit': action.reference,
                'cleanup_completed': False, 'cleanup_required': True,
                'model_loaded': False, 'write_authorized': False, 'atomic_snapshot': False})
        if type(journal) is CommittingJournal:
            _rollback_lock(held_lock, journal)
            observed = _prove_rollback_inputs(files, journal)
            # Only proven base/target bytes can select rollback. A failed
            # target read is NOT proof of partial publication.
            if all(observed[item['path']] is not None
                   and (observed[item['path']]['size'], observed[item['path']]['sha256'])
                   == (item['size'], item['sha256'])
                   for item in journal.data['target_inventory']):
                raise RecoveryError('recovery_full_target_requires_completion', exit_code=6)
            _authorize(authority, journal)
            if writer_next(files, journal) != pending:
                raise RecoveryError('recovery_writer_successor_changed', exit_code=6)
            _rollback_lock(held_lock, journal)
            if _prove_rollback_inputs(files, journal) != observed:
                raise RecoveryError('recovery_basis_changed', exit_code=6)
            successor = _journal_successor(journal, initial=True)
            def initial_guard():
                _rollback_lock(held_lock, journal)
                if _prove_rollback_inputs(files, journal) != observed:
                    raise RecoveryError('recovery_basis_changed', exit_code=6)
                if writer_next(files, journal) != pending:
                    raise RecoveryError('recovery_writer_successor_changed', exit_code=6)
            mutated = True
            _replace_journal(files, journal, successor, directory_identity,
                             before_publish=initial_guard)
            raw, directory_identity = _read_journal(files, transaction_id)
            journal = _parse(raw, transaction_id, files)
        if type(journal) is not RollingBackJournal:
            raise RecoveryError('recovery_rollback_state_required', exit_code=6)
        _rollback_lock(held_lock, journal)
        observed = _prove_rollback_inputs(files, journal)
        _authorize(authority, journal)
        if writer_next(files, journal) != pending:
            raise RecoveryError('recovery_writer_successor_changed', exit_code=6)
        _rollback_lock(held_lock, journal)
        if _prove_rollback_inputs(files, journal) != observed:
            raise RecoveryError('recovery_basis_changed', exit_code=6)
        while journal.data['published_count']:
            _rollback_lock(held_lock, journal)
            _prove_rollback_inputs(files, journal)
            index = journal.data['published_count'] - 1
            entry = journal.data['files'][index]
            state, token = _state(files, entry)
            if state == 'target':
                mutated = True
                if entry['existed_before']:
                    _copy_before(files, journal, entry, index, token,
                        before_publish=_rollback_guard(files, journal, directory_identity, held_lock))
                else:
                    _remove_created(files, journal, entry, index, token)
                writes += 1
                if _state(files, entry)[0] != 'base':
                    raise RecoveryError('recovery_basis_write_unverified', path=entry['path'], exit_code=6)
            successor = _journal_successor(journal)
            mutated = True
            _replace_journal(files, journal, successor, directory_identity,
                before_publish=_rollback_guard(files, journal, directory_identity, held_lock))
            raw, directory_identity = _read_journal(files, transaction_id)
            journal = _parse(raw, transaction_id, files)
        root = _prove_basis(files, journal)
        terminal = _journal_successor(journal, terminal=True)
        mutated = True
        _replace_journal(files, journal, terminal, directory_identity,
            before_publish=_rollback_guard(files, journal, directory_identity, held_lock))
        raw, directory_identity = _read_journal(files, transaction_id)
        current = _parse(raw, transaction_id, files)
        if type(current) is not RolledBackJournal or current.source_bytes != terminal.source_bytes:
            raise RecoveryError('recovery_rolled_back_marker_changed', exit_code=6)
        if _prove_basis(files, current) != root:
            raise RecoveryError('recovery_basis_changed', exit_code=6)
        action, receipt = rollback_evidence(files, current, authority=authority,
            write_new=write_recovery_file,
            before_publish=_rollback_guard(files, current, directory_identity, held_lock))
        _rollback_lock(held_lock, current)
        if (_read_journal(files, transaction_id) != (raw, directory_identity)
                or _prove_basis(files, current) != root):
            raise RecoveryError('recovery_basis_changed', exit_code=6)
        return RecoveryObservation._create({'format_version': 'recovery-rollback-v1',
            'state': 'rolled_back', 'transaction_id': transaction_id,
            'journal_sha256': current.sha256, 'base_model_root_sha256': root,
            'rollback_completed': True, 'normative_writes': writes,
            'receipt': receipt.reference, 'recovery_audit': action.reference,
            'cleanup_completed': False, 'cleanup_required': True,
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
