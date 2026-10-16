"""Native source/edge/target checks, independent of presentation and ownership."""
from ..graph.references import RelationReferences
from ..graph.relations import SourceRelations
from ..model.domain_schemas import DOMAIN_TYPES
from ..model.errors import ModelError
from ..storage.domain_artifact import DomainArtifact
from ..storage.record_artifact import RecordArtifact
from .blocks import ContentBlock


def _resolve_reference_sources(model, block_id, error_type):
    from ..changes.target_model import TargetModel
    if type(model) is not TargetModel:
        raise ModelError('document_target_model_required')
    if type(block_id) is not str:
        raise error_type('content_block_id_required', pointer='/block_id')
    model = model.snapshot()
    records = tuple(SourceRelations(d.content, path=d.path) for d in model.documents)
    index = {record.identity.id: record for record in records}
    source = index.get(block_id)
    if source is None:
        raise error_type('content_block_not_found', pointer='/block_id')
    if source.identity.artifact_type != 'content_block':
        raise error_type('artifact_reference_block_required', path=source.path, pointer='/block_id')
    block = ContentBlock(source.source_bytes, path=source.path)
    if block.block_kind != 'artifact_ref':
        raise error_type('artifact_reference_block_required', path=source.path, pointer='/block_kind')
    RelationReferences(records)
    position, relation = next((position, relation) for position, relation in enumerate(source.relations)
                              if relation.type == 'references')
    target = index[relation.target]
    reader = DomainArtifact if target.identity.artifact_type in DOMAIN_TYPES else RecordArtifact
    target_record = reader(target.source_bytes, path=target.path)
    value = target_record.data
    return model, source, block, position, relation, target, value
