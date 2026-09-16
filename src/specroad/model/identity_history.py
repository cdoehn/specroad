"""Pure identity classification, independent of storage and future merge policy."""

from .errors import ModelError
from .history_values import HistoryOrigin, HistoryObservation, HistoryComparison


def compare_histories(left, right):
    """Classify identity, not field conflicts or an import/merge resolution."""
    if not isinstance(left, HistoryObservation) or not isinstance(right, HistoryObservation):
        raise ModelError("history_observation_required")
    if left.identity.id != right.identity.id:
        return HistoryComparison.DIFFERENT_IDENTITY
    if left.identity != right.identity:
        return HistoryComparison.IDENTITY_CONFLICT
    if left.origin is None or right.origin is None:
        return HistoryComparison.UNRESOLVED
    if left.origin != right.origin:
        return HistoryComparison.IDENTITY_CONFLICT
    if left.content_sha256 == right.content_sha256 and left.source == right.source:
        return HistoryComparison.IDENTICAL_COPY
    return HistoryComparison.SAME_HISTORY


def require_same_history(left, right):
    """Necessary identity precondition only; never authorizes combining content."""
    result = compare_histories(left, right)
    if result == HistoryComparison.IDENTITY_CONFLICT:
        raise ModelError("identity_conflict")
    if result == HistoryComparison.UNRESOLVED:
        raise ModelError("identity_history_unresolved")
    if result == HistoryComparison.DIFFERENT_IDENTITY:
        raise ModelError("different_identity")
    return result
