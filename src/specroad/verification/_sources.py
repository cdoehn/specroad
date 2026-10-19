"""Shared native checks over owned source bytes, without discovery or writes."""

from ..graph.references import RelationReferences
from ..graph.relations import SourceRelations
from ..model.errors import ModelError


def contract_sources(model, subject_id, target_id, *, target_field):
    """Keep each public entrypoint's argument names and diagnostic order."""
    from ..changes.target_model import TargetModel
    if type(model) is not TargetModel:
        raise ModelError('verification_target_model_required')
    arguments = (('subject_id', subject_id), (target_field, target_id))
    for field, value in arguments:
        if type(value) is not str:
            raise ModelError('artifact_id_required', pointer='/' + field)
    model = model.snapshot()
    records = tuple(SourceRelations(d.content, path=d.path) for d in model.documents)
    index = {record.identity.id: record for record in records}
    for field, value in arguments:
        if value not in index:
            raise ModelError('verification_artifact_not_found', pointer='/' + field)
    return model, records, index, index[subject_id], index[target_id]


def verified_by_edges(records, source, target_id):
    """Validate subject fields and native references before selecting the edge."""
    from ..model.domain_schemas import DOMAIN_TYPES
    from ..storage.domain_artifact import DomainArtifact
    from ..storage.record_artifact import RecordArtifact
    reader = DomainArtifact if source.identity.artifact_type in DOMAIN_TYPES else RecordArtifact
    reader(source.source_bytes, path=source.path)
    RelationReferences(records)
    edges = [(position, relation) for position, relation in enumerate(source.relations)
             if relation.type == 'verified_by' and relation.target == target_id]
    if not edges:
        raise ModelError('verification_relation_required', path=source.path, pointer='/relations')
    return edges
