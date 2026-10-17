"""Section moves may publish changed relation owners, never referenced content."""
from ..changes.request_ids import AuthoringError
from ..storage.json_syntax import parse_json_object
from ._composition_ownership import _preserve_owner_content


def _preserve_composition_sources(model, documents, operations):
    owners = {operation['source'] for operation in operations}
    originals = {document.path: document.content for document in model.documents}
    proposed = {document.path: document.content for document in documents}
    if (len(originals) != len(model.documents) or len(proposed) != len(documents)
            or set(originals) != set(proposed)):
        raise AuthoringError('document_composition_inventory_changed', exit_code=3)
    for path, raw in originals.items():
        value = parse_json_object(raw)
        if value['id'] in owners:
            _preserve_owner_content(value, proposed[path], operations)
        elif proposed[path] != raw:
            raise AuthoringError('document_composition_content_changed', exit_code=3)
