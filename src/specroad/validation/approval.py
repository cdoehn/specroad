"""Combine formal prerequisites and human review without executing a transition."""
from ..diagnostics import Diagnostic, diagnostic_key
from ..model.errors import ModelError
from .approval_values import (APPROVAL_VERSION, PREREQUISITES,
    ApprovalContext, ApprovalPrerequisite, HumanRequirementReview,
    ReviewVerifier, ApprovalAssessment)
from ._approval_findings import _finding
from ._approval_formal import _formal
from ._approval_review import observe_human_review


def assess_requirement_approval(context, *, review=None, verifier=None, prerequisites=()):
    """Check readiness for the human in_review -> approved step, never perform it.

    Mandatory semantic service results come from the trusted caller. Human review
    is separate, byte-/context-bound and must be authenticated/current according
    to an explicitly registered trusted verifier. Neither Core nor a detector
    claims to understand a single testable proposition. There is no implicit
    clock, login, IO, review selection or permissive fallback.
    """
    if type(context) is not ApprovalContext:
        raise ModelError('approval_context_required')
    if type(prerequisites) not in (tuple,list) or any(type(p) is not ApprovalPrerequisite for p in prerequisites):
        raise ModelError('approval_prerequisites_required')
    if len({p.gate_id for p in prerequisites})!=len(prerequisites):
        raise ModelError('approval_duplicate_prerequisite')
    if review is not None and type(review) is not HumanRequirementReview:
        raise ModelError('approval_human_review_required')
    if verifier is not None and type(verifier) is not ReviewVerifier:
        raise ModelError('approval_review_verifier_required')
    try:
        issues=_formal(context)
    except ModelError as error:
        issues=[_finding(context,error.reason,code='SRV002',pointer=error.pointer or '',path=error.path)]
    formal_ok=not issues
    observed={p.gate_id:p for p in prerequisites}
    prerequisite_status=[]
    for gate_id in PREREQUISITES:
        p=observed.get(gate_id)
        state='unavailable' if p is None else p.status if p.input_sha256==context.input_sha256 else 'stale'
        prerequisite_status.append({'gate_id':gate_id,'status':state,
            'evidence_sha256':p.evidence_sha256 if p is not None else None})
        if state!='passed':
            issues.append(_finding(context,'approval_prerequisite_'+state,code='APPROVAL_UNAVAILABLE' if state=='unavailable' else 'SRV030',pointer='/'+gate_id))
    review_issues,human_status,authenticated,current=observe_human_review(context,review,verifier)
    issues.extend(review_issues)
    ready=formal_ok and not issues and human_status=='confirmed'
    # Stable structured findings; no ordering by localized display text.
    issues.sort(key=lambda i:(diagnostic_key(Diagnostic.from_dict(i['diagnostic'])), i['reason']))
    return ApprovalAssessment._create({'format_version':APPROVAL_VERSION,'input_sha256':context.input_sha256,
        'requirement_id':context.requirement_id,'formal_data_valid':formal_ok,'requirements_satisfied':ready,
        'eligible_for_human_approval':ready and context.data['mode']=='transition',
        'human_review_status':human_status,'authenticated_by_supplied_verifier':authenticated,
        'review_current_by_supplied_verifier':current,'review_sha256':None if review is None else review.sha256,
        'verifier':None if verifier is None else {'id':verifier.verifier_id,'version':verifier.version},
        'prerequisites':prerequisite_status,'findings':issues,
        'approval_granted':False,'write_authorized':False,'project_complete':False,'atomic_snapshot':False,
        'validation_scope':'approval_over_supplied_bindings','semantic_detection_performed':False})
