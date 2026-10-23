"""Bound field lookup and pure XHTML updates for existing ReqIF source records.

The facade supplies bounded decoding and deterministic serialization. Unchanged
fields preserve the imported tree; all candidates are checked by the same
native prose contract before bytes are returned, without writing a project.
"""
from dataclasses import replace

from ..mappings import select_mapping
from ._reqif_values import REQIF_NAMESPACE, ReqIFError, _Node, _SEP, _replace_node
from ._reqif_xhtml import from_markdown, parse_markdown, project_xhtml


def require_structure(document):
    if not document._structure:
        raise ReqIFError('reqif_structure_profile_required', exit_code=2)


def records(document):
    return document.objects + document.specifications + document.relations


def field(document, identifier, definition_id):
    require_structure(document)
    obj = next((o for o in records(document) if o.identifier == identifier), None)
    if obj is None:
        raise ReqIFError('reqif_object_missing', object_id=identifier)
    definition = next((d for t in document.types if t.identifier == obj.type_id
                       for d in t.definitions if d.identifier == definition_id), None)
    if definition is None or definition.family != 'XHTML':
        raise ReqIFError('reqif_xhtml_definition_required', object_id=identifier, definition_id=definition_id)
    value = next((v for v in obj.values if v.definition_id == definition_id), definition.default)
    return obj, definition, value


def export_xhtml(document, identifier, definition_id, markdown, *, expected_source_sha256, attachments, decode, serialize):
    if expected_source_sha256 != document.source_sha256:
        raise ReqIFError('reqif_source_changed', exit_code=6)
    obj, definition, old = field(document, identifier, definition_id)
    if document.unsupported:
        raise ReqIFError('reqif_uninterpreted_export', pointer=document.unsupported[0][0])
    try:
        _, native = parse_markdown(markdown, pointer=definition.element.pointer)
        # Preserve the complete imported tree, absence/default origin and flags.
        if old is not None and project_xhtml(old.lexical, attachments=attachments)['content'] == native:
            raw = document.source_bytes
        else:
            root = from_markdown(markdown, attachments=attachments)
            def node(tag, children=()):
                return _Node(REQIF_NAMESPACE + _SEP + tag, (), tuple(children))
            value = node('ATTRIBUTE-VALUE-XHTML', (
                node('DEFINITION', (node('ATTRIBUTE-DEFINITION-XHTML-REF', (definition_id,)),)),
                node('THE-VALUE', (root,))))
            if old is not None:
                value = replace(old.element, content=tuple(
                    node('THE-VALUE', (root,)) if c.tag == 'THE-VALUE' else c for c in old.element.children))
            values = tuple(value if v.definition_id == definition_id else v.element for v in obj.values)
            if all(v.definition_id != definition_id for v in obj.values):
                values += (value,)
            old_values = next((c for c in obj.element.children if c.tag == 'VALUES'), None)
            new_values = node('VALUES', values)
            updated = (replace(obj.element, content=(new_values,) + obj.element.content) if old_values is None
                       else _replace_node(obj.element, old_values, new_values))
            raw = serialize(_replace_node(document._root, obj.element, updated))
        checked = decode(raw, limits=document._limits)
        actual = checked.project_xhtml(identifier, definition_id, attachments=attachments)
        if actual['content'] != native:
            raise ReqIFError('reqif_xhtml_inverse_roundtrip_loss', exit_code=6)
    except ReqIFError as error:
        if error.exit_code == 3: error.exit_code = 6
        raise
    return {'xml_bytes': raw, 'source_sha256': document.source_sha256,
            'external_id': identifier, 'definition_id': definition_id,
            'export_complete': False, 'write_authorized': False, 'execution_ready': False}


def bound_mapping(document, *, mappings, key, expected_mapping_sha256, expected_source_sha256):
    require_structure(document)
    if expected_source_sha256 != document.source_sha256:
        raise ReqIFError('reqif_source_changed', exit_code=6)
    selected = select_mapping(mappings, key=key, expected_sha256=expected_mapping_sha256)
    if selected.resource.data['source_format'] != 'reqif':
        raise ReqIFError('reqif_mapping_format_required', exit_code=2)
    return selected
