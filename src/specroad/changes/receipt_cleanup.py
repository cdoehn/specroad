"""Public cleanup orchestration; immutable completion proof is never discarded."""
from ..model.errors import ModelError
from ..security import SafetyViolation
from .publication_values import PublicationPreflight, PublicationAuthority
from .locking import HeldProjectLock
from .execution_values import ChangeExecutionError
from .receipt_values import ReceiptError, TransactionCompletion
from .receipt_read import _CompletionProof
from ._receipt_work import _CleanupSession


def cleanup_completed_transaction(preflight, transaction_id, *, held_lock, authority):
    """Discard only verified work after durable completion, preserving all receipts.

    Only cleanup can be resumed here; no plan is executed or target republished.
    A late cleanup error preserves a verified historical committed result with
    cleanup_completed=false. If durable proof is damaged, even that is refused.
    """
    if (type(preflight) is not PublicationPreflight or type(held_lock) is not HeldProjectLock
            or type(authority) is not PublicationAuthority):
        raise ReceiptError('explicit_cleanup_inputs_required', exit_code=2)
    session = None
    try:
        session = _CleanupSession(preflight, transaction_id, held_lock, authority)
        session.archive()
        session.discard()
        session.guard()
        return TransactionCompletion._create(session.journal, live=True, cleanup=True)
    except (OSError, ModelError, SafetyViolation, ChangeExecutionError) as error:
        # No claim of atomic rollback. If proof survives, a cleanup failure does
        # not undo the already durable transaction or call its writer again.
        if session is not None:
            try:
                proof = _CompletionProof(session.files, session.source, transaction_id)
                if proof.journal.source_bytes == session.journal.source_bytes:
                    return TransactionCompletion._create(proof.journal, cleanup=False,
                        warnings=(getattr(error, 'reason', 'cleanup_io_failed'),))
            except (OSError, ModelError, SafetyViolation, ChangeExecutionError):
                pass
        if isinstance(error, ReceiptError): raise
        raise ReceiptError(getattr(error, 'reason', 'cleanup_failed'),
                           exit_code=getattr(error, 'exit_code', 5),
                           mutation_possible=session is not None, committed_possible=True) from error
