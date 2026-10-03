"""Read-only terminal journal selection and receipt/result proof.

Cleanup and ownership transfer share canonical terminal locations without
importing another mutating recovery entrypoint or searching audit history.
"""
from .receipt_projection import prepare_recovery_receipts
from .receipt_values import CommittedJournal, completion_marker_path
from .recovery_values import RecoveryError, RolledBackJournal
from ._journal_codec import journal_path
from ._recovery_evidence import read_evidence, rollback_evidence
from ._recovery_inputs import _parse
from ._recovery_receipts import existing_recovery_record
from ._recovery_rollback import _prove_basis
from ._recovery_target import prove_complete_target


def terminal_marker_path(transaction_id, journal):
    path = completion_marker_path(transaction_id)
    return path if type(journal) is CommittedJournal else path.replace('/committed.json', '/rolled_back.json')


def read_terminal_journal(files, transaction_id):
    active = read_evidence(files, journal_path(transaction_id))
    committed_path = completion_marker_path(transaction_id)
    markers = [read_evidence(files, committed_path),
               read_evidence(files, committed_path.replace('/committed.json', '/rolled_back.json'))]
    present = [record for record in markers if record is not None]
    if len(present) > 1:
        raise RecoveryError('recovery_terminal_markers_disagree', exit_code=6)
    record = active if active is not None else next(iter(present), None)
    if record is None:
        raise RecoveryError('recovery_terminal_proof_missing', exit_code=6)
    journal = _parse(record.source_bytes, transaction_id, files)
    if type(journal) not in (CommittedJournal, RolledBackJournal):
        raise RecoveryError('recovery_terminal_state_required', exit_code=6)
    if present and (present[0].source_bytes != journal.source_bytes
                    or present[0].path != terminal_marker_path(transaction_id, journal)):
        raise RecoveryError('recovery_terminal_markers_disagree', exit_code=6)
    return journal


def prove_terminal_result(files, journal):
    if type(journal) is CommittedJournal:
        transaction, request, expected = prepare_recovery_receipts(journal.predecessor)
        if expected.source_bytes != journal.source_bytes:
            raise RecoveryError('recovery_committed_binding_mismatch', exit_code=6)
        records = [record for record in (transaction, request) if record is not None]
        live = prove_complete_target(files, journal.predecessor)
    else:
        records = list(rollback_evidence(files, journal))
        live = _prove_basis(files, journal)
    tokens = []
    for record in records:
        token = existing_recovery_record(files, record)
        if token is None:
            raise RecoveryError('recovery_receipt_missing', path=record.path, exit_code=6)
        tokens.append((record, token))
    return live, tokens
