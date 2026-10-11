"""Pure Appendix J selection over supplied endpoints and matching history.

Input inventory checks and diagnostic projection live outside this module.
"""
from dataclasses import dataclass

from ..model.audit_values import UtcTimestamp
from ..model.errors import ModelError
from .review_context_values import RelationReviewContext


@dataclass(frozen=True)
class RelationReviewStatus:
    source_id: str
    relation_id: str
    target_id: str
    status: str
    reason: str | None
    selected_review_id: str | None
    matching_review_ids: tuple
    historical_review_ids: tuple

    def as_fields(self):
        return {'source_id': self.source_id, 'relation_id': self.relation_id,
            'target_id': self.target_id, 'status': self.status, 'reason': self.reason,
            'selected_review_id': self.selected_review_id,
            'matching_review_ids': list(self.matching_review_ids),
            'historical_review_ids': list(self.historical_review_ids)}


def _time_key(record):
    # Older passive records retain only creation time. Trailing zeroes denote
    # the same instant; arbitrary fractional precision must not be rounded.
    stamp = record.get('reviewed_at', record['created_at'])
    UtcTimestamp(stamp)
    fraction = stamp[20:-1].rstrip('0') if stamp[19:20] == '.' else ''
    return stamp[:19].upper(), fraction, record['id']


def _status(source, relation, index, history):
    historical = tuple(sorted(record['id'] for record in history))

    def result(status, reason=None, selected=None, matching=()):
        return RelationReviewStatus(source.identity.id, relation.identity.id,
            relation.target, status, reason, selected, matching, historical)

    target = index.get(relation.target)
    if target is None:
        return result('invalid', 'missing_relation_target')
    try:
        context = RelationReviewContext(relation, source, target)
    except ModelError as error:
        if error.reason not in ('self_relation_forbidden', 'relation_type_pair_forbidden',
                                'noncanonical_symmetric_relation'):
            raise
        return result('invalid', error.reason)
    matching = [record for record in history
        if record['relation_content_sha256'] == context.relation_sha256
        and record['source_context_sha256'] == context.source.context_sha256
        and record['target_context_sha256'] == context.target.context_sha256]
    if not matching:
        return result('suspect' if history else 'unreviewed')
    selected = max(matching, key=_time_key)
    rejected = selected['decision'] == 'rejected'
    return result('invalid' if rejected else 'current',
        'current_review_rejected' if rejected else None, selected['id'],
        tuple(sorted(record['id'] for record in matching)))
