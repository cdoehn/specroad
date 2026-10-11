"""Read-only status and repair data over a byte-bound supplied project model.

This is an owned report API, not disk discovery or a registered CLI command.
History is supplied evidence; neither its authenticity nor approval is granted.
"""
from dataclasses import replace

from ..changes.target_model import TargetModel
from ..changes.target_values import TargetError
from ..diagnostics import assess_diagnostics
from ..graph.relations import SourceRelations
from ..graph.review_context_values import EndpointReviewContext, relation_content_sha256
from ..graph.review_status import RelationReviewStatuses, _time_key


def _endpoint(source):
    if source is None:
        return None
    value = EndpointReviewContext(source)
    return {'id': value.artifact_id, 'revision': value.revision,
        'artifact_sha256': value.artifact_sha256, 'context_sha256': value.context_sha256}


def _review(record):
    if record is None:
        return None
    keys = ('id', 'decision', 'source_id', 'target_id', 'source_revision',
        'target_revision', 'source_artifact_sha256', 'target_artifact_sha256',
        'relation_content_sha256', 'source_context_sha256', 'target_context_sha256')
    return {**{key: record.get(key) for key in keys},
        'reviewed_at': record.get('reviewed_at', record['created_at'])}


def _row(value, source, relation, target, reviews, profile):
    source_context, target_context = _endpoint(source), _endpoint(target)
    relation_hash = relation_content_sha256(relation)
    history = [reviews[identity] for identity in value.historical_review_ids]
    latest = max(history, key=_time_key) if history else None
    current_hashes = {'relation_content_sha256': relation_hash,
        'source_context_sha256': source_context['context_sha256'],
        'target_context_sha256': None if target_context is None else target_context['context_sha256']}
    changes = [] if latest is None else sorted(key for key, current in current_hashes.items()
        if latest[key] != current)
    repairs = {'current': [], 'unreviewed': ['record_human_review'],
        'suspect': ['review_changed_context'],
        'invalid': (['resolve_rejection_and_record_new_human_review']
            if value.reason == 'current_review_rejected'
            else ['repair_relation_structure', 'record_human_review'])}
    maturity = source.data['maturity']
    return {**value.as_fields(), 'relation_type': relation.type, 'source_maturity': maturity,
        'severity': profile.relation_review_severity(relation.type, maturity, value.status),
        'current_source': source_context, 'current_target': target_context,
        'relation_content_sha256': relation_hash,
        'selected_review': _review(reviews.get(value.selected_review_id)),
        'latest_review': _review(latest), 'changes_since_latest_review': changes,
        'required_repair': repairs[value.status]}


def relation_status_report(model, artifact_id=None, *, fail_on='error', strict=False):
    """Stable outgoing/incoming observations for an optional existing artifact.

    All supplied inputs are validated before filtering. Revision differences
    are shown as evidence; only Appendix J hashes determine currentness.
    """
    if type(model) is not TargetModel:
        raise TargetError('target_model_required')
    owned = model.snapshot()
    sources = tuple(SourceRelations(document.content, path=document.path)
        for document in owned.documents)
    statuses = RelationReviewStatuses(sources)
    index = {source.identity.id: source for source in sources}
    if artifact_id is not None:
        if type(artifact_id) is not str:
            raise TargetError('review_artifact_identity_required')
        if artifact_id not in index:
            raise TargetError('review_artifact_missing')
    reviews = {identity: source.data for identity, source in index.items()
        if source.identity.artifact_type == 'relation_review'}
    edges = {(source.identity.id, relation.identity.id): relation
        for source in sources for relation in source.relations}
    selected = [value for value in statuses.statuses
        if artifact_id is None or artifact_id in (value.source_id, value.target_id)]
    rows = [_row(value, index[value.source_id], edges[(value.source_id, value.relation_id)],
        index.get(value.target_id), reviews, owned.profile) for value in selected]
    by_relation = {row['relation_id']: row for row in rows}
    findings = []
    for finding in statuses.diagnostics:
        # Every status finding carries exactly one stored relation identity.
        row = next((by_relation[key] for key in finding.related_ids if key in by_relation), None)
        if row is not None:
            findings.append(replace(finding, severity=row['severity']))
    assessment = assess_diagnostics(findings,
        checked_ids=tuple(sorted({value.source_id for value in selected})),
        complete=True, fail_on=fail_on, strict=strict)
    return {**assessment.as_dict(), 'report_version': 'relation-status-v1',
        'validation_scope': 'supplied_relation_status_policy_only', 'approval_granted': False,
        'artifact_filter': artifact_id, 'profile': owned.profile.binding(), 'relations': rows}
