"""Pure relation-status row projection shared by read-only graph consumers.

Callers supply validated statuses, endpoint sources, history and effective policy.
Model ownership, selection and diagnostic assessment remain with the caller.
"""
from .review_context_values import EndpointReviewContext, relation_content_sha256
from .review_status import _time_key


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
