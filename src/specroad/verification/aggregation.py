"""Prioritized per-subject results over explicitly supplied, bound observations.

No product code, files or clocks are consulted. Results describe the supplied
model and inputs, not a complete live inventory, authenticated test execution
or release readiness. Nothing is stored in a Subject or historical Evidence.
"""
from dataclasses import dataclass
from hashlib import sha256

from ..configurations import resolve_configuration
from ..graph.relations import SourceRelations
from ..graph.scope_descriptors import ScopeDescriptor
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.errors import ModelError
from ..model.waiver_fields import waiver_time
from ..storage.domain_artifact import DomainArtifact
from ..storage.json_syntax import parse_json_object
from .evaluation import assess_evaluation_binding
from .run_replacements import assess_run_replacements
from ._aggregation_results import aggregate_checks, subject_result
from .waivers import (HumanWaiverReview, WaiverContext, WaiverReviewVerifier,
                      assess_verification_waiver)


@dataclass(frozen=True, init=False)
class VerificationResultAggregation:
    """Owned computed results; never a truthy approval or a write capability."""
    _encoded: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError('Use aggregate_verification_results')

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def sha256(self):
        return sha256(self._encoded).hexdigest()

    def __bool__(self):
        raise TypeError('Verification results are not release readiness or approval')


def aggregate_verification_results(model, evaluation, *, configuration_id, inputs,
        input_roles, evaluated_at, scope_descriptor=None, scope_bindings=None,
        waiver_reviews=None, waiver_verifier=None):
    """Apply section 10.5 priorities after the native input and selection gates.

    Inputs and their logical roles are explicit, independent caller declarations.
    Waiver reviews are keyed by Subject ID; only an explicit trusted host verifier
    can confirm their human origin. A time is mandatory, never read from a clock.
    """
    from ..changes.target_model import TargetModel
    if type(model) is not TargetModel:
        raise ModelError('verification_target_model_required')
    model = model.snapshot()
    waiver_time(evaluated_at)
    if waiver_reviews is not None and type(waiver_reviews) is not dict:
        raise ModelError('verification_waiver_reviews_required')
    reviews = {}
    for subject_id, review in ({} if waiver_reviews is None else waiver_reviews).items():
        if type(subject_id) is not str or type(review) is not HumanWaiverReview:
            raise ModelError('typed_waiver_review_required')
        reviews[subject_id] = HumanWaiverReview(review.data)
    if waiver_verifier is not None and type(waiver_verifier) is not WaiverReviewVerifier:
        raise ModelError('typed_waiver_verifier_required')
    binding = assess_evaluation_binding(evaluation, inputs=inputs, input_roles=input_roles)
    replacements = assess_run_replacements(model, evaluation, configuration_id=configuration_id,
        scope_descriptor=scope_descriptor, scope_bindings=scope_bindings)
    bound, replaced = binding.data, replacements.data
    assessed = replaced['assessment']
    coverage = assessed['selection']['coverage']
    required = coverage['required_set']
    subjects = {row['artifact_id'] for row in required['subjects']}
    if set(reviews) - subjects:
        raise ModelError('verification_waiver_review_outside_scope')
    documents = {parse_json_object(d.content)['id']: d for d in model.documents}
    configuration = (None if configuration_id is None else resolve_configuration(
        [SourceRelations(d.content, path=d.path) for d in model.documents], configuration_id))
    scope = ScopeDescriptor(required['scope_descriptor'])
    checks = aggregate_checks(assessed, replaced)
    results, diagnostics = [], []
    for applicability in required['subjects']:
        subject_id = applicability['artifact_id']
        document = documents[subject_id]
        subject = DomainArtifact(document.content, path=document.path)
        value = subject.data
        selected = [check for check in checks if check['subject_artifact_id'] == subject_id]
        runs = [run for check in selected for run in check['active_runs']]
        broken = [row for row in replaced['diagnostics']
                  if row.get('subject_artifact_id') == subject_id and
                  row['reason'] == 'replacement_binding_changed']
        waiver = None
        # Excluded Subjects have the highest priority and need no host callback.
        if applicability['status'] != 'excluded' and value['verification_plan_status'] == 'waived':
            waiver = assess_verification_waiver(WaiverContext(subject, scope,
                evaluated_at=evaluated_at, configuration=configuration),
                review=reviews.get(subject_id), verifier=waiver_verifier).data
        result, reasons = subject_result(applicability=applicability, waiver=waiver,
            plan_status=value['verification_plan_status'], bound=bound, coverage=coverage,
            broken=broken, selected=selected, runs=runs)
        results.append({'subject_artifact_id': subject_id,
            'source_sha256': sha256(subject.source_bytes).hexdigest(),
            'artifact_sha256': canonical_json_sha256(value),
            'verification_plan_status': value['verification_plan_status'],
            'applicability': applicability, 'waiver_assessment': waiver, 'checks': selected,
            'verification_result': result, 'reasons': reasons})
        if result == 'incomplete':
            diagnostics.extend({'code': 'SRV176', 'severity': 'warning',
                'subject_artifact_id': subject_id, 'reason': reason} for reason in reasons)
    report = {'format_version': 'verification-result-aggregation-v1',
        'validation_scope': 'supplied_model_verification_results',
        'project_id': replaced['project_id'], 'input_sha256': replaced['input_sha256'],
        'evaluation_sha256': replaced['evaluation_sha256'], 'evaluated_at': evaluated_at,
        'input_binding': bound, 'input_binding_sha256': binding.sha256,
        'replacement_assessment': replaced, 'replacement_assessment_sha256': replacements.sha256,
        'subjects': results, 'diagnostics': diagnostics,
        'input_bytes_verified': bound['input_bytes_verified'],
        'input_roles_checked': bound['input_roles_checked'], 'input_roles_authenticated': False,
        'evaluation_identity_history_checked': False,
        'project_files_verified': False, 'project_required_checks_complete': False,
        'result_aggregation_evaluated': True, 'full_verification_evaluated': False,
        'external_run_verified': False, 'release_readiness_evaluated': False,
        'test_code_executed': False, 'write_authorized': False, 'approval_granted': False}
    result = object.__new__(VerificationResultAggregation)
    object.__setattr__(result, '_encoded', canonical_json_bytes(report))
    return result
