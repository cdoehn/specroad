"""An active, exactly bound marker keeps interrupted terminal cleanup visible."""
from hashlib import sha256
import os

from ..model.canonical import canonical_json_bytes
from ._recovery_evidence import EvidenceRecord, read_evidence
from ._recovery_receipts import recheck_recovery_record
from .recovery_values import RecoveryError


def barrier_path(transaction_id, action):
    return '.specroad/recovery/pending-' + action + '-' + sha256(transaction_id.encode()).hexdigest() + '.json'


def barrier_record(journal, intent, action):
    data = journal.data
    return EvidenceRecord(barrier_path(data['transaction_id'], action), canonical_json_bytes({
        'format_version': 'terminal-recovery-pending-v1', 'action': action,
        'transaction_id': data['transaction_id'], 'project_id': data['project_id'],
        'root_identity': data['root_identity'], 'journal_sha256': journal.sha256,
        'intent': intent.reference}))


def remove_barrier(files, record, token):
    files.require_held()
    recheck_recovery_record(files, record, token)
    parts = tuple(record.path.split('/'))
    with files.directory(parts[:-1]) as directory:
        recheck_recovery_record(files, record, token)
        os.unlink(parts[-1], dir_fd=directory)
        os.fsync(directory)
    if read_evidence(files, record.path) is not None:
        raise RecoveryError('recovery_barrier_changed', path=record.path, exit_code=6)
