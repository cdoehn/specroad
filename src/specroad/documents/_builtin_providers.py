"""Native calculated fields and shared admission for Built-in view consumers.

The synchronous projection and resumed Work use these same providers. Renderer
adapters consume their data without making a second readiness decision. Callers
retain admission order and snapshot ownership; no provider performs file I/O.
Public error classes remain in builtin_views and are imported only when used.
"""
from ._builtin_projection import _computed_reports


def require_view_name(view_name):
    from .builtin_views import BuiltinViewError
    if type(view_name) is not str or view_name not in (
            'specification', 'traceability', 'verification', 'roadmap'):
        raise BuiltinViewError('builtin_view_not_supported', pointer='/view_name', exit_code=2)


def readiness_model(readiness):
    from ..planning import ReleaseReadinessContext
    from .builtin_views import BuiltinViewError
    if type(readiness) is not ReleaseReadinessContext:
        raise BuiltinViewError('typed_release_readiness_context_required', pointer='/readiness')
    return readiness._model


def require_readiness_binding(model, owned):
    from .builtin_views import BuiltinViewError
    if owned._sources_sha256 != model._sources_sha256 or owned.binding != model.binding:
        raise BuiltinViewError('builtin_readiness_binding_mismatch', pointer='/readiness', exit_code=6)


def roadmap_fields(model, readiness, readiness_gates, blocker_reviews, blocker_verifier):
    from ..planning import project_roadmap, assess_release_readiness
    roadmap = project_roadmap(model)
    report = None
    if readiness is not None:
        owned = readiness_model(readiness).snapshot()
        require_readiness_binding(model, owned)
        report = assess_release_readiness(readiness, gates=readiness_gates,
            blocker_reviews=blocker_reviews, blocker_verifier=blocker_verifier)
    return dict(mode='evaluated_roadmap', roadmap=roadmap.data, roadmap_sha256=roadmap.sha256,
        rows=roadmap.data['items'], row_count=len(roadmap.data['items']),
        computed_reports=_computed_reports(roadmap=roadmap.data),
        readiness=None if report is None else report.data,
        readiness_sha256=None if report is None else report.sha256,
        release_readiness_evaluated=report is not None,
        validation_scope=roadmap.data['validation_scope'])


def verification_fields(model, verification, currentness):
    from ..verification.coverage import assess_verification_coverage
    coverage = assess_verification_coverage(model, verification, currentness=currentness)
    coverage_data = coverage.data
    return dict(mode='evaluated_requirement_coverage',
        selection_scope_descriptor=verification.data['scope_descriptor'],
        summary=verification.summary, coverage=coverage_data, coverage_sha256=coverage.sha256,
        rows=coverage_data['requirements'], row_count=coverage_data['totals']['requirements'],
        verification_evaluated=True, computed_reports=_computed_reports(verification=coverage_data),
        validation_scope=coverage_data['validation_scope'])


def traceability_verification_fields(model, verification, observed, rows):
    """Attach native results to the caller's freshly projected trace rows."""
    from ..verification.coverage import assess_verification_coverage
    from ..verification._read_evaluation import computed_results
    coverage_data = (observed['observation']['coverage'] if observed is not None else
                     assess_verification_coverage(model, verification).data)
    subjects = computed_results(coverage_data)
    for row in rows:
        row['verification_result'] = subjects.get(row['requirement_id'])
    fields = dict(mode='evaluated_traceability', verification_evaluated=True,
        computed_reports=_computed_reports(verification=coverage_data))
    if verification is not None:
        fields.update(summary=verification.summary,
            selection_scope_descriptor=verification.data['scope_descriptor'])
    return fields
