"""Exact contains-edge ownership, separate from unchanged referenced sources."""
from ..changes.request_ids import AuthoringError
from ..model.canonical import canonical_json_sha256
from ..storage.json_syntax import parse_json_object


def _require_section_ownership(artifacts, operations):
    removal, addition = operations
    matches = [edge for value in artifacts if value['id'] == removal['source']
               for edge in value['relations'] if edge['relation_id'] == removal['relation_id']]
    index = {value['id']: value for value in artifacts}
    if (len(matches) != 1 or matches[0]['type'] != 'contains'
            or matches[0]['target'] != addition['relation']['target']
            or index.get(matches[0]['target'], {}).get('artifact_type') != 'section'):
        raise AuthoringError('document_original_section_relation_required', exit_code=3)


def _preserve_owner_content(value, proposed_bytes, operations):
    if value['artifact_type'] not in ('document', 'section'):
        raise AuthoringError('document_composition_owner_required', exit_code=3)
    current = parse_json_object(proposed_bytes)
    # Only the ownership edit and the native lifecycle/metadata fold may change
    # an owner. Reference edges and all other content stay outside that edit.
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
