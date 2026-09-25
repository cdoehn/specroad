"""Formal Requirement checks and explicit human-review gating, with no writes."""
from __future__ import annotations

import math

from ..diagnostics import Diagnostic, diagnostic_key
from ..model.errors import ModelError
from ..model.domain_schemas import DOMAIN_TYPES, validate_domain_fields
from ..model.record_schemas import RECORD_TYPES, validate_record_fields
from ..model.canonical import canonical_json_bytes
from ..profiles.composition import check_composed_fields
from ..storage.json_syntax import parse_json_object
from ..graph.relations import SourceRelations
from ..graph.references import RelationReferences
from ..graph.hierarchies import validate_hierarchies
from ..graph.symmetry import require_canonical_relations
from ..graph.relation_obligations import RelationObligations
from ..srx.pointers import parse_pointer, resolve_tokens
from ..srx.errors import SrxError
from ..srx.types import MISSING
from .approval_values import (APPROVAL_VERSION, PREREQUISITES, HUMAN_CRITERIA,
    ApprovalContext, ApprovalPrerequisite, HumanRequirementReview, ReviewVerification,
    ReviewVerifier, ApprovalAssessment)


def _finding(context, reason, *, pointer='', code='SRV030', path=None, origin='core_rule'):
    return {'reason':reason, 'diagnostic':Diagnostic(code,'error','approval',
        'Requirement approval prerequisite not satisfied.', artifact_id=context.requirement_id,
        path=path, location={'pointer':pointer}, rationale=reason, origin=origin).as_dict()}


def _read(value, pointer):
    try:
        return resolve_tokens(value, parse_pointer(pointer, rule_id='approval-fields'), rule_id='approval-fields')
    except SrxError as error:
        raise ModelError('approval_pointer_invalid',pointer=pointer) from error


def _nonempty(value):
    return type(value) is str and bool(value.strip())


def _numeric(value):
    return type(value) in (int,float) and (type(value) is int or math.isfinite(value))


def _formal(context):
    issues, records, index = [], [], {}
    candidate = None
    for document in context.documents:
        try:
            data = parse_json_object(document.content, path=document.path)
            if data.get('id') == context.requirement_id:
                if candidate is not None or data.get('artifact_type') != 'requirement':
                    raise ModelError('approval_requirement_missing_or_ambiguous')
                candidate = data
                required_state = 'in_review' if context.data['mode'] == 'transition' else 'approved'
                if data.get('maturity') != required_state:
                    issues.append(_finding(context,'approval_source_maturity_invalid',pointer='/maturity',path=document.path))
                # A detached hypothetical state exercises the approved field rules.
                data = dict(data, maturity='approved')
            kind = data.get('artifact_type')
            if kind in DOMAIN_TYPES: validate_domain_fields(data)
            elif kind in RECORD_TYPES: validate_record_fields(data)
            else: raise ModelError('approval_artifact_type_invalid',pointer='/artifact_type')
            record = SourceRelations(canonical_json_bytes(data),path=document.path)
            if record.identity.id in index: raise ModelError('duplicate_artifact_id',pointer='/id')
            records.append(record);index[record.identity.id]=record
        except ModelError as error:
            issues.append(_finding(context,error.reason,code='SRV002',pointer=error.pointer or '',path=document.path))
    if candidate is None:
        issues.append(_finding(context,'approval_requirement_missing_or_ambiguous'))
        return issues
    if issues:
        return issues  # No successful graph projection over a damaged source set.
    try:
        references=RelationReferences(records)
        require_canonical_relations(references)
        validate_hierarchies(references)
        # Core always requires origin and verified_by; a permissive profile or a
        # verification-plan waiver cannot remove these structural obligations.
        obligations=RelationObligations(records, profile_rules=() if context.profile is None else context.profile.minimum_relation_rules())
        for check in obligations.checks:
            if check.artifact_id==context.requirement_id and not check.satisfied and check.severity=='error':
                code=('SRV031' if check.rule_id=='core:requirement-origin' else 'SRV032'
                      if check.rule_id=='core:requirement-verification' else 'SRV030')
                issues.append(_finding(context,check.rule_id,code=code,pointer='/relations'))
    except ModelError as error:
        issues.append(_finding(context,error.reason,code='SRV021',pointer=error.pointer or '',path=error.path))
    projected=index[context.requirement_id].data
    if context.profile is None:
        issues.append(_finding(context,'approval_profile_unavailable',code='APPROVAL_UNAVAILABLE'))
    else:
        for item in check_composed_fields(context.profile,projected)['diagnostics']:
            issues.append(_finding(context,item['reason'],code='SRV002',pointer=item.get('pointer','')))
    kind=candidate['requirement_kind']
    if kind=='quality':
        rows=context.data['quality_fields']
        if not rows: issues.append(_finding(context,'approval_quality_projection_missing',pointer='/thresholds'))
        for row in rows:
            values=[_read(candidate,p) for p in row]
            target=values[3]
            valid_target = _numeric(target) or _nonempty(target) or type(target) is bool or (type(target) is dict and set(target)=={'value','unit'}
                            and _numeric(target['value']) and _nonempty(target['unit']))
            conditions=(_nonempty(values[0]), _nonempty(values[1]),
                type(values[2]) is str and values[2] in ('eq','ne','lt','lte','gt','gte','=','!=','<','<=','>','>='),valid_target)
            for i, valid in enumerate(conditions):
                if not valid: issues.append(_finding(context,('approval_quality_property_missing',
                    'approval_quality_method_missing','approval_quality_comparison_invalid',
                    'approval_quality_target_invalid')[i],pointer=row[i]))
    if kind=='interface':
        fields=context.data['interface_fields']
        if not fields: issues.append(_finding(context,'approval_interface_boundary_missing',pointer='/scope'))
        values=[_read(candidate,p) for p in fields]
        targets=[]
        for p,value in zip(fields,values):
            allowed=('component',) if len(fields)==2 else ('component','interface')
            record=index.get(value) if type(value) is str else None
            if record is None or record.identity.artifact_type not in allowed:
                issues.append(_finding(context,'approval_interface_reference_invalid',code='SRV020',pointer=p))
            else:
                targets.append(record.identity.id)
                if record.identity.artifact_type=='interface':
                    for key in ('source_component','target_component'):
                        target=index.get(record.data[key])
                        if target is None or target.identity.artifact_type!='component':
                            issues.append(_finding(context,'approval_interface_endpoint_missing',code='SRV020',pointer=p))
    return issues


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
    issues=_formal(context)
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
    human_status='missing'; authenticated=False; current=False
    if review is None:
        issues.append(_finding(context,'approval_human_review_missing'))
    else:
        data=review.data
        try:
            bound=(data['input_sha256']==context.input_sha256 and data['requirement_id']==context.requirement_id
                and data['requirement_sha256']==context.requirement_sha256
                and data['force_statement_sha256']==context.force_statement_sha256)
        except ModelError:
            bound=False
        human_status='unverified'
        if not bound:
            human_status='stale';issues.append(_finding(context,'approval_review_binding_mismatch'))
        elif data['reviewer']['actor_type']!='human':
            human_status='nonhuman';issues.append(_finding(context,'approval_nonhuman_review',code='SRV030'))
        elif verifier is None:
            issues.append(_finding(context,'approval_review_verifier_unavailable',code='APPROVAL_UNAVAILABLE'))
        else:
            try:
                evidence=verifier.check(context,review)
                if (type(evidence) is not ReviewVerification or evidence.input_sha256!=context.input_sha256
                        or evidence.review_sha256!=review.sha256):
                    raise ModelError('approval_review_verifier_unbound')
                authenticated=evidence.authenticated_human;current=evidence.current
                if not authenticated or not current:
                    issues.append(_finding(context,'approval_review_not_authenticated_or_current'))
                elif data['compound']:
                    human_status='compound'
                    issues.append(_finding(context,'approval_human_confirmed_compound',code='SRV162',origin='core_rule'))
                elif data['decision']!='confirmed':
                    human_status='rejected';issues.append(_finding(context,'approval_human_review_rejected'))
                elif any(data['criteria'].get(name) is not True for name in HUMAN_CRITERIA):
                    human_status='incomplete';issues.append(_finding(context,'approval_human_criteria_unconfirmed'))
                else: human_status='confirmed'
            except Exception:
                human_status='verification_failed'
                issues.append(_finding(context,'approval_review_verification_failed',code='APPROVAL_UNAVAILABLE'))
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
