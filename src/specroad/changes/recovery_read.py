"""Read-only transaction state diagnosis, separate from mutating recovery."""
from hashlib import sha256
from ..model.errors import ModelError
from ..security import SafetyViolation
from ..storage.json_syntax import parse_json_object
from .execution_values import ChangeExecutionError
from ._lock_files import LockFiles
from ._journal_codec import _hash, _text, _transaction
from .recovery_values import RecoveryError, RecoveryObservation
from ._recovery_inputs import _read_journal, _parse, _unchanged_base, _work


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
                row = {'path': path + '/journal.json', 'state': 'unknown', 'observed_state': None,
                       'journal_schema_validated': False, 'state_actions': [],
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
                    observed = parse_json_object(raw)
                    observed_state = observed.get('state')
                    row['observed_state'] = observed_state if type(observed_state) is str else None
                    # Report state even when a later state's full codec is not
                    # implemented here. No permission follows from these claims.
                    if observed_state in ('building', 'prepared', 'committing', 'committed',
                                          'rolling_back', 'rolled_back', 'corrupt'):
                        row['state'] = observed_state
                        row['state_actions'] = ({'building': ['discard'], 'prepared': ['discard'],
                            'committing': ['recover'], 'rolling_back': ['recover'],
                            'corrupt': ['restore_with_verified_plan']}.get(observed_state, []))
                        for key in ('base_model_root_sha256', 'target_model_root_sha256'):
                            if _hash(observed.get(key)): row[key] = observed[key]
                    entries = observed.get('files')
                    count = observed.get('published_count')
                    if (type(entries) is list and type(count) is int and 0 <= count <= len(entries)
                            and all(type(e) is dict and type(e.get('published')) is bool
                                    and type(e.get('path')) is str for e in entries)
                            and sum(e['published'] for e in entries) == count):
                        row['published_count'] = count
                        row['published_entries'] = [e['path'] for e in entries if e['published']]
                    journal = _parse(raw, txn, files, expected_project_id)
                    row['journal_schema_validated'] = True
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
                            _work(files, journal, preflight=preflight)
                            if _unchanged_base(preflight, journal, files) != before:
                                raise RecoveryError('recovery_base_changed', exit_code=6)
                            row.update(base_verified=True, permitted_actions=['discard'])
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

