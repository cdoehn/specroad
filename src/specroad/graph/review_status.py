"""Appendix J observations with owned inventory and history preparation.

No status is stored in a relation. These observations neither authenticate the
supplied records nor certify a complete project, grant approval, or allow writes.
"""
from dataclasses import dataclass

from ..diagnostics import diagnostic_key
from ..model.domain_schemas import validate_domain_fields
from ..model.errors import ModelError
from ..model.record_contracts import RECORD_TYPES
from ..model.record_schemas import validate_record_fields
from ._reference_checks import _source_identity_errors, _relation_identity_errors
from ._review_status_selection import RelationReviewStatus, _time_key, _status
from ._review_status_diagnostics import _diagnostic
from .relations import SourceRelations


@dataclass(frozen=True, init=False)
class RelationReviewStatuses:
    """One deterministic observation per stored relation in the supplied input."""
    statuses: tuple
    _source_ids: tuple
    _diagnostics: tuple

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
        by_relation = {(value.source_id, value.relation_id): value for value in observations}
        findings = []
        for source in ordered:
            for position, relation in enumerate(source.relations):
                finding = _diagnostic(by_relation[(source.identity.id, relation.identity.id)],
                    source.path, position)
                if finding is not None:
                    findings.append(finding)
        object.__setattr__(self, '_diagnostics', tuple(sorted(findings, key=diagnostic_key)))

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
    def diagnostics(self):
        return self._diagnostics

    @property
    def data(self):
        return {'validation_scope': self.validation_scope,
            'approval_granted': self.approval_granted,
            'relations': [value.as_fields() for value in self.statuses]}
