"""Section moves may publish changed relation owners, never referenced content."""
from ..changes.request_ids import AuthoringError
from ..model.canonical import canonical_json_sha256
from ..storage.json_syntax import parse_json_object


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
            if value['artifact_type'] not in ('document', 'section'):
                raise AuthoringError('document_composition_owner_required', exit_code=3)
            current = parse_json_object(proposed[path])
            # Only the ownership edit and the native lifecycle/metadata fold
            # may change an owner. Its other content is not a move payload.
            mutable = {'relations', 'revision', 'updated_at', 'updated_by', 'maturity'}
            before = {key: item for key, item in value.items() if key not in mutable}
            after = {key: item for key, item in current.items() if key not in mutable}
            maturity = 'proposed' if value['maturity'] == 'approved' else value['maturity']
            if (canonical_json_sha256(before) != canonical_json_sha256(after)
                    or current['maturity'] != maturity):
                raise AuthoringError('document_composition_owner_content_changed', exit_code=3)
            removal, addition = operations
            relations = [edge for edge in value['relations'] if not (
                value['id'] == removal['source'] and edge['relation_id'] == removal['relation_id'])]
            if value['id'] == addition['source']:
                relations.append(addition['relation'])
            if canonical_json_sha256(current['relations']) != canonical_json_sha256(relations):
                raise AuthoringError('document_composition_relations_changed', exit_code=3)
        elif proposed[path] != raw:
            raise AuthoringError('document_composition_content_changed', exit_code=3)
