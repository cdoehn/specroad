"""Read-only relation-status query over an owned caller-supplied TargetModel."""
from dataclasses import replace

from ..changes.target_model import TargetModel
from ..changes.target_values import TargetError
from ..diagnostics import assess_diagnostics
from ..graph.relations import SourceRelations
from ..graph.review_status import RelationReviewStatuses


def relation_review_status(model, source_id, relation_id):
    if type(model) is not TargetModel:
        raise TargetError('target_model_required')
    owned = model.snapshot()
    statuses = RelationReviewStatuses(tuple(SourceRelations(document.content,
        path=document.path) for document in owned.documents))
    return {**statuses.for_relation(source_id, relation_id).as_fields(),
        'validation_scope': statuses.validation_scope,
        'approval_granted': statuses.approval_granted}


def relation_review_diagnostics(model, *, fail_on='error', strict=False):
    """Assess the supplied snapshot only; never waive a rejected-review error."""
    if type(model) is not TargetModel:
        raise TargetError('target_model_required')
    owned = model.snapshot()
    sources = tuple(SourceRelations(document.content,
        path=document.path) for document in owned.documents)
    statuses = RelationReviewStatuses(sources)
    by_relation = {value.relation_id: value for value in statuses.statuses}
    selectors = {relation.identity.id: (relation.type, source.data['maturity'])
        for source in sources for relation in source.relations}
    findings = []
    for finding in statuses.diagnostics:
        value = next(by_relation[key] for key in finding.related_ids if key in by_relation)
        severity = owned.profile.relation_review_severity(*selectors[value.relation_id], value.status)
        findings.append(replace(finding, severity=severity))
    assessment = assess_diagnostics(findings,
        checked_ids=tuple(sorted({value.source_id for value in statuses.statuses})),
        complete=True, fail_on=fail_on, strict=strict)
    return {**assessment.as_dict(), 'validation_scope': statuses.validation_scope,
        'relation_statuses': statuses.data['relations']}
