"""Appendix J status observations over an explicitly supplied review history.

No status is stored in a relation. These observations neither authenticate the
supplied records nor certify a complete project, grant approval, or allow writes.
"""
from dataclasses import dataclass

from ..model.audit_values import UtcTimestamp
from ..model.domain_schemas import validate_domain_fields
from ..model.errors import ModelError
from ..model.record_contracts import RECORD_TYPES
from ..model.record_schemas import validate_record_fields
from ._reference_checks import _source_identity_errors, _relation_identity_errors
from .relations import SourceRelations
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


@dataclass(frozen=True, init=False)
class RelationReviewStatuses:
    """One deterministic observation per stored relation in the supplied input."""
    statuses: tuple
    _source_ids: tuple

    def __init__(self, sources):
        if isinstance(sources, (str, bytes, dict)):
            raise ModelError('source_relations_sequence_required')
        try:
            records = tuple(sources)
        except TypeError as error:
            raise ModelError('source_relations_sequence_required') from error
        index, histories = {}, {}
        prefix = None
        for source in records:
            if type(source) is not SourceRelations:
                raise ModelError('source_relations_required')
            value = source.data
            validator = validate_record_fields if value['artifact_type'] in RECORD_TYPES else validate_domain_fields
            validator(value)
            if prefix is None:
                prefix = source.identity.id_prefix
            for error in _source_identity_errors(source, index, prefix):
                raise error
            index[source.identity.id] = source
            if value['artifact_type'] == 'relation_review':
                histories.setdefault(value['relation_id'], []).append(value)
        seen, external = set(), set()
        ordered = sorted(records, key=lambda source: source.identity.id)
        for source in ordered:
            for relation in source.relations:
                for error in _relation_identity_errors(relation, seen, external):
                    raise error
        observations = tuple(_status(source, relation, index,
                histories.get(relation.identity.id, ()))
            for source in ordered
            for relation in sorted(source.relations, key=lambda edge: edge.identity.id))
        object.__setattr__(self, 'statuses', observations)
        object.__setattr__(self, '_source_ids', tuple(sorted(index)))

    def for_relation(self, source_id, relation_id):
        if type(source_id) is not str or type(relation_id) is not str:
            raise ModelError('review_relation_identity_required')
        if source_id not in self._source_ids:
            raise ModelError('review_source_missing', pointer='/source_id')
        selected = next((value for value in self.statuses
            if value.source_id == source_id and value.relation_id == relation_id), None)
        if selected is None:
            raise ModelError('review_relation_missing', pointer='/relation_id')
        return selected

    @property
    def validation_scope(self):
        return 'supplied_relation_review_status_only'

    @property
    def approval_granted(self):
        return False

    @property
    def data(self):
        return {'validation_scope': self.validation_scope,
            'approval_granted': self.approval_granted,
            'relations': [value.as_fields() for value in self.statuses]}
