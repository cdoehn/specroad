"""Read-only transaction diagnosis and explicit unpublished preparation discard.

The caller supplies an independently checked, owned base preflight. No ordinary
model loading, new planning, target writes, receipt reuse or automatic lock
recovery occurs. A native recovery lock and fresh full-byte base checks remain
mandatory for mutation; diagnostics are never reusable authorizations.
"""
from datetime import datetime, timezone
from hashlib import sha256
import os
from uuid import uuid4
from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..security import SafetyViolation
from ..security import paths as guards
from ..storage.json_syntax import parse_json_object
from .authoring import normalize_authoring_actor
from .execution_values import ChangeExecutionError
from .journal_values import BuildingJournal
from .staging_values import PreparedJournal
from .committing_values import CommittingJournal
from .receipt_values import CommittedJournal
from .publication_values import PublicationPreflight
from .locking import HeldProjectLock
from ._lock_files import LockFiles
from ._journal_codec import _hash, _text, _transaction, journal_path
from ._journal_io import _read
from ._journal_inventory import prepare_building_journal
from ._publication_observation import _root, observe_publication_files
from ._staging_files import _write_new, _image
from .recovery_values import (AUDIT_ROOT, RecoveryAuthority, RecoveryError,
                              RecoveryObservation, DiscardedJournal)

_KNOWN = {'building': BuildingJournal, 'prepared': PreparedJournal,
          'committing': CommittingJournal, 'committed': CommittedJournal,
          'rolled_back': DiscardedJournal}


def _read_journal(files, transaction_id):
    path = journal_path(transaction_id)
    with files.directory(tuple(path.split('/')[:-1])) as directory:
        if directory is None:
            raise RecoveryError('recovery_journal_missing', path=path, exit_code=5)
        ident = guards._identity(os.fstat(directory))
        raw = _read(directory, 'journal.json')
    return raw, ident


def _parse(raw, transaction_id, files, expected_project_id=None):
    value = parse_json_object(raw)
    cls = _KNOWN.get(value.get('state'))
    if cls is None:
        raise RecoveryError('recovery_journal_state_unsupported')
    journal = cls(raw)
    data = journal.data
    if (data['transaction_id'] != transaction_id
            or data['root_identity'] != list(files.boundary._root_identity)
            or (expected_project_id is not None and data['project_id'] != expected_project_id)):
        raise RecoveryError('recovery_journal_binding_mismatch', exit_code=6)
    return journal


def _unchanged_base(preflight, journal, files):
    """Independent inventory plus every live source byte, never journal hashes alone."""
    if type(preflight) is not PublicationPreflight:
        raise RecoveryError('recovery_base_preflight_required', exit_code=2)
    data = journal.data
    if data['state'] not in ('building', 'prepared'):
        raise RecoveryError('discard_state_forbidden', exit_code=6)
    expected = prepare_building_journal(preflight, transaction_id=data['transaction_id']).data
    expected['state'] = data['state']
    if data != expected:
        raise RecoveryError('recovery_inventory_unproven', exit_code=6)
    model = preflight._model.snapshot()
    source = _root(model)
    if source.boundary._root_identity != files.boundary._root_identity:
        raise RecoveryError('recovery_base_root_mismatch', exit_code=6)
    return observe_publication_files(source, model, preflight.request,
                                    preflight._package_files, check_rights=lambda fd, path: None)


def _work(files, journal, *, raw=None, prefix=None):
    """Closed, hash-bound work inventory. No recursive deletion or path guessing."""
    data = journal.data
    prefix = tuple(journal.path.split('/')[:-1]) if prefix is None else prefix
    with files.directory(prefix) as directory:
        if directory is None:
            raise RecoveryError('recovery_work_missing', exit_code=6)
        names = set(os.listdir(directory))
        required = {'journal.json'} if data['state'] == 'building' else {'journal.json', 'before', 'staging'}
        if names != required:
            raise RecoveryError('recovery_work_inventory_unproven', exit_code=6)
        actual = _read(directory, 'journal.json')
        if actual != (journal.source_bytes if raw is None else raw):
            raise RecoveryError('recovery_journal_changed', exit_code=6)
        result = {'': guards._identity(os.fstat(directory)), 'journal.json': sha256(actual).hexdigest()}
    if data['state'] == 'prepared':
        for folder, path_key, size_key, hash_key in (
                ('staging', 'staging_path', 'after_size', 'after_sha256'),
                ('before', 'before_image_path', 'before_size', 'before_sha256')):
            entries = [e for e in data['files'] if e[path_key] is not None]
            with files.directory((*prefix, folder)) as fd:
                if fd is None or set(os.listdir(fd)) != {e[path_key].rsplit('/', 1)[-1] for e in entries}:
                    raise RecoveryError('recovery_work_inventory_unproven', exit_code=6)
                result[folder] = guards._identity(os.fstat(fd))
                for entry in entries:
                    name = entry[path_key].rsplit('/', 1)[-1]
                    result[folder + '/' + name] = _image(fd, name, entry[size_key], entry[hash_key])
    return result


def inspect_recovery(root, *, transaction_id=None, expected_project_id=None, preflight=None):
    """Observe all active journals without loading the canonical project model.

    Only an independently proven base permits a reported discard candidate;
    the mutating API checks again under the live native lock. Invalid journals
    remain visible with no action permission. No directory or file is created.
    """
    if transaction_id is not None: _transaction(transaction_id)
    if expected_project_id is not None and not _text(expected_project_id):
        raise RecoveryError('recovery_project_id_required', exit_code=2)
    try:
        with LockFiles(root) as files:
            active = files.journal_entries()
            selected = ('.specroad/transactions/' + transaction_id,) if transaction_id is not None else active
            rows, captured = [], {}
            for path in selected:
                row = {'path': path + '/journal.json', 'state': 'unknown',
                       'journal_sha256': None, 'base_model_root_sha256': None,
                       'target_model_root_sha256': None, 'published_count': None,
                       'published_entries': [], 'permitted_actions': [],
                       'base_verified': False, 'diagnostic': None}
                try:
                    if not path.startswith('.specroad/transactions/'):
                        raise RecoveryError('unknown_recovery_entry')
                    txn = _transaction(path.split('/')[-1])
                    raw, ident = _read_journal(files, txn)
                    captured[txn] = (raw, ident)
                    row['journal_sha256'] = sha256(raw).hexdigest()
                    journal = _parse(raw, txn, files, expected_project_id)
                    d = journal.data
                    row.update(state=d['state'], transaction_id=d['transaction_id'], project_id=d['project_id'], base_model_root_sha256=d['base_model_root_sha256'],
                               target_model_root_sha256=d['target_model_root_sha256'],
                               published_count=d['published_count'],
                               published_entries=[e['path'] for e in d['files'] if e['published']])
                    if d['state'] in ('building', 'prepared'):
                        if preflight is None:
                            row['diagnostic'] = 'recovery_base_preflight_required'
                        else:
                            before = _unchanged_base(preflight, journal, files)
                            _work(files, journal)
                            if _unchanged_base(preflight, journal, files) != before:
                                raise RecoveryError('recovery_base_changed', exit_code=6)
                            row.update(base_verified=True, permitted_actions=['discard'] if active == (path,) else [])
                            if active != (path,): row['diagnostic'] = 'recovery_active_set_unproven'
                except (ChangeExecutionError, SafetyViolation, ModelError, OSError, ValueError) as error:
                    row['diagnostic'] = getattr(error, 'reason', 'recovery_input_unreadable')
                rows.append(row)
            for txn, observation in captured.items():
                if _read_journal(files, txn) != observation:
                    raise RecoveryError('recovery_status_changed', exit_code=6)
            if files.journal_entries() != active:
                raise RecoveryError('recovery_status_changed', exit_code=6)
            return RecoveryObservation._create({'format_version': 'recovery-status-v1',
                'transactions': rows, 'active_paths': list(active),
                'recovery_required': bool(active), 'model_loaded': False,
                'observation_only': True, 'write_authorized': False,
                'exclusive_access_proven': False, 'atomic_snapshot': False})
    except RecoveryError: raise
    except (ChangeExecutionError, SafetyViolation, ModelError, OSError) as error:
        raise RecoveryError(getattr(error, 'reason', 'recovery_status_unavailable'),
                            exit_code=getattr(error, 'exit_code', 5)) from error


def _held(held, journal):
    if type(held) is not HeldProjectLock:
        raise RecoveryError('native_recovery_lock_required', exit_code=7)
    held.check()
    lock, data = held.record.data, journal.data
    if (lock['kind'] != 'recovery' or lock['command'] != 'recover discard'
            or lock['transaction_id'] != data['transaction_id']
            or lock['project_id'] != data['project_id']
            or lock['request_id'] != data['request_id']):
        raise RecoveryError('recovery_lock_binding_mismatch', exit_code=6)


def discard_unpublished_transaction(preflight, transaction_id, *, held_lock,
                                   authority, actor, reason, expected_journal_sha256):
    """Discard ONLY proven unpublished preparations; retain all work in an audit.

    The original journal and an immutable intent are durable before the terminal
    marker. An atomic directory rename moves *all* known work to the audit. No
    normative target, request receipt, before image or prior audit is removed.
    Late failure keeps partial audit/terminal state for explicit diagnosis.
    """
    _transaction(transaction_id)
    if not _hash(expected_journal_sha256) or not _text(reason):
        raise RecoveryError('explicit_recovery_identity_and_reason_required', exit_code=2)
    actor = normalize_authoring_actor(actor)
    if type(authority) is not RecoveryAuthority:
        raise RecoveryError('recovery_authority_required', exit_code=2)
    if type(held_lock) is not HeldProjectLock:
        raise RecoveryError('native_recovery_lock_required', exit_code=7)
    attempted = False
    try:
        files = held_lock._files
        raw, ident = _read_journal(files, transaction_id)
        journal = _parse(raw, transaction_id, files)
        _held(held_lock, journal)
        if journal.sha256 != expected_journal_sha256:
            raise RecoveryError('recovery_journal_changed', exit_code=6)
        base = _unchanged_base(preflight, journal, files)
        active = files.journal_entries()
        if active != ('.specroad/transactions/' + transaction_id,):
            raise RecoveryError('recovery_active_set_unproven', exit_code=6)
        work = _work(files, journal)

        def guard(*, terminal_raw=None, expected_work=work):
            _held(held_lock, journal)
            if files.journal_entries() != active:
                raise RecoveryError('recovery_active_set_changed', exit_code=6)
            if _work(files, journal, raw=terminal_raw) != expected_work:
                raise RecoveryError('recovery_work_changed', exit_code=6)
            if _unchanged_base(preflight, journal, files) != base:
                raise RecoveryError('recovery_base_changed', exit_code=6)

        request = {'action': 'discard', 'transaction_id': transaction_id,
                   'project_id': journal.data['project_id'], 'actor': actor.as_fields(),
                   'reason': reason, 'journal_sha256': journal.sha256,
                   'base_model_root_sha256': journal.data['base_model_root_sha256'],
                   'target_model_root_sha256': journal.data['target_model_root_sha256']}
        request_raw = canonical_json_bytes(request)
        allowed = authority.check(request)
        if canonical_json_bytes(request) != request_raw or type(allowed) is not bool or not allowed:
            raise RecoveryError('recovery_not_authorized', exit_code=7)
        guard()
        event = str(uuid4()); audit_path = AUDIT_ROOT + '/' + event
        intent = canonical_json_bytes({'format_version': 'recovery-audit-v1',
            'event_id': event, 'phase': 'intent', **parse_json_object(request_raw),
            'previous_state': journal.data['state'], 'normative_writes': 0,
            'authority_id': authority.authority_id, 'authority_version': authority.version,
            'created_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')})
        value = journal.data
        value.update(state='rolled_back', discard={'event_id': event,
            'previous_state': journal.data['state'], 'journal_before_sha256': journal.sha256,
            'intent_sha256': sha256(intent).hexdigest(), 'audit_path': audit_path})
        terminal = DiscardedJournal(canonical_json_bytes(value))
        attempted = True
        with files.directory(tuple(AUDIT_ROOT.split('/')), create=True) as audit_root:
            os.mkdir(event, mode=0o700, dir_fd=audit_root)
            os.fsync(audit_root)
        with files.directory(tuple(audit_path.split('/'))) as audit:
            if os.listdir(audit): raise RecoveryError('recovery_audit_collision', exit_code=6)
            _write_new(audit, 'journal.before.json', raw)
            _write_new(audit, 'intent.json', intent)
            guard()
            prefix = tuple(journal.path.split('/')[:-1])
            with files.directory(prefix) as directory:
                if guards._identity(os.fstat(directory)) != ident:
                    raise RecoveryError('recovery_work_changed', exit_code=6)
                _write_new(directory, 'journal.discard', terminal.source_bytes)
                # Recheck all original bytes without trusting the temporary marker.
                _image(directory, 'journal.json', len(raw), journal.sha256)
                _held(held_lock, journal)
                if _unchanged_base(preflight, journal, files) != base:
                    raise RecoveryError('recovery_base_changed', exit_code=6)
                os.replace('journal.discard', 'journal.json', src_dir_fd=directory, dst_dir_fd=directory)
                os.fsync(directory)
            terminal_work = {**work, 'journal.json': terminal.sha256}
            guard(terminal_raw=terminal.source_bytes, expected_work=terminal_work)
            _image(audit, 'journal.before.json', len(raw), journal.sha256)
            _image(audit, 'intent.json', len(intent), sha256(intent).hexdigest())
            with files.directory(('.specroad', 'transactions')) as parent:
                if guards._identity(os.stat(transaction_id, dir_fd=parent, follow_symlinks=False)) != ident:
                    raise RecoveryError('recovery_work_changed', exit_code=6)
                if 'work' in os.listdir(audit): raise RecoveryError('recovery_audit_collision', exit_code=6)
                os.rename(transaction_id, 'work', src_dir_fd=parent, dst_dir_fd=audit)
                os.fsync(parent); os.fsync(audit)
            if _work(files, journal, raw=terminal.source_bytes,
                     prefix=(*tuple(audit_path.split('/')), 'work')) != terminal_work:
                raise RecoveryError('recovery_archive_changed', exit_code=6)
            if _unchanged_base(preflight, journal, files) != base:
                raise RecoveryError('recovery_base_changed', exit_code=6)
            completed = {'format_version': 'recovery-audit-v1', 'event_id': event,
                'phase': 'completed', 'action': 'discard', 'state': 'rolled_back',
                'transaction_id': transaction_id, 'journal_before_sha256': journal.sha256,
                'journal_sha256': terminal.sha256, 'intent_sha256': sha256(intent).hexdigest(),
                'base_model_root_sha256': journal.data['base_model_root_sha256'],
                'archive_path': audit_path + '/work', 'normative_writes': 0}
            _write_new(audit, 'completed.json', canonical_json_bytes(completed))
        _held(held_lock, journal)
        if files.journal_entries() or _unchanged_base(preflight, journal, files) != base:
            raise RecoveryError('recovery_final_observation_changed', exit_code=6)
        return RecoveryObservation._create({**completed, 'discard_completed': True,
            'evidence_preserved': True, 'audit_path': audit_path, 'model_loaded': False,
            'write_authorized': False, 'atomic_snapshot': False})
    except (ChangeExecutionError, SafetyViolation, ModelError, OSError, ValueError) as error:
        raise RecoveryError(getattr(error, 'reason', 'recovery_discard_failed'),
            exit_code=getattr(error, 'exit_code', 5), mutation_possible=attempted) from error
