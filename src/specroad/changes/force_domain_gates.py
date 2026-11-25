"""Translate real native negative findings to the shared Force ledger."""
from ..model.errors import ModelError


def classification(reason):
    """Classification only: this function neither skips nor executes a check."""
    words = set(reason.replace('-', '_').split('_'))
    for gate, names in (
        ('actor', {'actor', 'human'}), ('approval', {'approval', 'approved'}),
        ('review', {'review', 'reviews'}), ('readiness', {'readiness', 'evidence'}),
        ('lifecycle', {'lifecycle', 'maturity', 'retired', 'successor'}),
        ('immutable', {'immutable', 'original', 'archive'}),
        ('partial', {'partial'}), ('stale', {'stale', 'revision', 'base'}),
        ('hash', {'hash', 'sha256', 'digest', 'binding'}),
        ('merge_conflict', {'merge'}), ('import_conflict', {'import'}),
        ('work_marker', {'work'}), ('write_marker', {'marker', 'journal', 'recovery'}),
        ('lock', {'lock', 'owner'}), ('path', {'path', 'symlink'}),
        ('resource_limit', {'limit', 'size', 'budget'}),
        ('analyzer_policy', {'analyzer'}), ('language', {'language'}),
        ('profiles', {'profile'}), ('cycles', {'cycle', 'cyclic'}),
        ('references', {'reference', 'relation'}), ('task', {'task'}),
        ('format', {'format', 'version'}), ('safety', {'security', 'unsafe'}),
        ('structure', {'parse', 'parsing', 'syntax'}),
    ):
        if words & names:
            return gate
    return 'schema'


def record_denial(decisions, error, *, operation, subject, requested):
    from ..bundles.errors import BundleError
    if not isinstance(error, (ModelError, BundleError)):
        raise TypeError('Native model finding required')
    diagnostic = error.diagnostic() if hasattr(error, 'diagnostic') else {'reason': error.reason}
    decisions.decide(False, gate_id=classification(error.reason) + ':' + error.reason,
        diagnostic_code=diagnostic.get('code') or 'CORE_MODEL', subject=subject,
        operation=operation, observed_binding=diagnostic, requested_binding=requested,
        effect='execute_explicit_target_preserving_native_denial')
