"""Actual block semantics and bound lifecycle folds for document mutations."""
from ..changes.lifecycle import prepare_change_lifecycle
from ..changes._metadata_policy import bind_policy
from ..documents.blocks import ContentBlock
from ..documents.prose import parse_prose
from ..documents.references import resolve_artifact_reference
from ..documents.tables import resolve_table_block
from ..model.canonical import canonical_json_sha256
from ..storage.json_syntax import parse_json_object
from ..validation import ModelGate


def _block_semantics(model):
    for document in model.documents:
        if parse_json_object(document.content)['artifact_type'] != 'content_block':
            continue
        block = ContentBlock(document.content, path=document.path)
        if block.block_kind in ('prose', 'admonition'):
            parse_prose(block)
        elif block.block_kind == 'artifact_ref':
            resolve_artifact_reference(model, block.data['id'])
        elif block.block_kind in ('table', 'query'):
            resolve_table_block(model, block.data['id'])
        # page_break is completely field-defined; include edges and cycles are
        # checked by the mandatory whole-target document/include graph gate.


def _mutation_lifecycle(model, operations, *, actor, planned_at):
    owned = model.snapshot()
    metadata = bind_policy('change-metadata-v1', actor, planned_at)
    resources = canonical_json_sha256({'model_sources_sha256': owned._sources_sha256,
        'operations': operations, 'metadata': metadata})

    def dependencies(context):
        return context.dependency_result({key: list(context.all_ids) for key in context.subjects})

    def check(context):
        folded = prepare_change_lifecycle(owned.artifacts, operations, **metadata,
            source_files=owned.source_files, **owned.reservations)
        expected = {value['id']: value for value in folded.artifacts}
        base = {value['id']: value for value in owned.artifacts}
        supported = {op['target'] for op in operations if op['op'] == 'retire'}
        supported.update(identity for identity, value in expected.items()
            if identity in base and base[identity]['maturity'] == 'approved'
            and value['maturity'] == 'proposed')
        if any(identity not in supported for identity in context.subjects):
            return context.result([{'reason': 'document_mutation_lifecycle_service_required', 'severity': 'error'}])
        actual = {key: context.artifact(key) for key in context.all_ids}
        if canonical_json_sha256(expected) != canonical_json_sha256(actual):
            return context.result([{'reason': 'document_mutation_lifecycle_target_mismatch', 'severity': 'error'}])
        return context.result()

    return ModelGate('lifecycle', 'bound-document-mutation-v1', dependencies, check, resources)
