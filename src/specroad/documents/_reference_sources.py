"""Native source/edge/target checks, independent of presentation and ownership."""
from ._read_model import require_read_model, read_scope, read_root, partial_observation, local_references

from ..graph.references import RelationReferences
from ..graph.relations import SourceRelations
from ..model.domain_schemas import DOMAIN_TYPES
from ..model.errors import ModelError
from ..storage.domain_artifact import DomainArtifact
from ..storage.record_artifact import RecordArtifact
from .blocks import ContentBlock


def _resolve_reference_sources(model, block_id, error_type):
    from ..changes.target_model import TargetModel
    require_read_model(model)
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
    local_references(model, records)
    position, relation = next((position, relation) for position, relation in enumerate(source.relations)
                              if relation.type == 'references')
    target = index.get(relation.target)
    if target is None:
        raise error_type('artifact_reference_target_not_loaded', path=source.path, pointer='/relations')
    reader = DomainArtifact if target.identity.artifact_type in DOMAIN_TYPES else RecordArtifact
    target_record = reader(target.source_bytes, path=target.path)
    value = target_record.data
    return model, source, block, position, relation, target, value
