"""Section moves may publish changed relation owners, never referenced content."""
from ..changes.request_ids import AuthoringError
from ..storage.json_syntax import parse_json_object


def _preserve_composition_sources(model, documents, operations):
    owners = {operation['source'] for operation in operations}
    originals = {document.path: document.content for document in model.documents}
    proposed = {document.path: document.content for document in documents}
    if set(originals) != set(proposed):
        raise AuthoringError('document_composition_inventory_changed', exit_code=3)
    for path, raw in originals.items():
        value = parse_json_object(raw)
        if value['id'] in owners:
            if value['artifact_type'] not in ('document', 'section'):
                raise AuthoringError('document_composition_owner_required', exit_code=3)
        elif proposed[path] != raw:
            raise AuthoringError('document_composition_content_changed', exit_code=3)
