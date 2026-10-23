"""Bound ReqIF structure/prose adapters; callers own native metadata and bytes."""
from dataclasses import replace

from ..documents import assess_document_structure
from ..documents.prose import ProseError, _parse_markdown
from ..mappings import select_mapping
from ..model.errors import ModelError
from ..storage.json_syntax import parse_json_object
from ._reqif_mapping import _source_identity
from ._reqif_values import REQIF_NAMESPACE, ReqIFError, _Node, _SEP, _replace_node
from ._reqif_xhtml import from_markdown, project_xhtml


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
        _, native = _parse_markdown(markdown)
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
    except (ReqIFError, ProseError) as error:
        if isinstance(error, ReqIFError):
            if error.exit_code == 3: error.exit_code = 6
            raise
        raise ReqIFError('reqif_xhtml_inverse_not_representable', exit_code=6) from error
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


def map_structure(document, *, object_bindings, occurrence_bindings, relation_bindings,
                  native_model, source_system, source_document, external_revision=None, **mapping_binding):
    """Check explicit edge proposals against supplied native M11 source bytes.

    This never constructs/retypes an artifact or discovers its metadata. The
    separate field adapters own field mapping; this check covers structure only.
    """
    mapping = bound_mapping(document, **mapping_binding)
    for supplied in (object_bindings, occurrence_bindings, relation_bindings):
        if type(supplied) is not dict or any(type(k) is not str or type(v) is not str or not v.strip()
                                          for k, v in supplied.items()):
            raise ReqIFError('reqif_native_bindings_required', exit_code=2)
    if len(set(relation_bindings.values())) != len(relation_bindings):
        raise ReqIFError('reqif_relation_binding_ambiguous', exit_code=6)
    assessment = assess_document_structure(native_model)
    if not assessment.structure_valid:
        raise ReqIFError('reqif_native_structure_invalid', pointer=assessment.data['diagnostics'][0].get('pointer', ''))
    supplied = {v['id']: v for v in (parse_json_object(d.content) for d in native_model.documents)}

    def binding(values, key):
        if key not in values:
            raise ReqIFError('reqif_native_binding_missing', exit_code=6, object_id=key)
        return values[key]

    def native(values, key, kinds=None):
        target = binding(values, key)
        if target not in supplied or kinds is not None and supplied[target]['artifact_type'] not in kinds:
            raise ReqIFError('reqif_native_binding_type', exit_code=6, object_id=key)
        return target

    def identity(identifier, kind):
        return {'object_class': kind, **_source_identity(identifier, source_system, source_document, external_revision)}

    def check_edge(edge, identifier, position=None):
        rel_id = binding(relation_bindings, identifier)
        matches = [r for r in supplied[edge['source']]['relations'] if r['relation_id'] == rel_id]
        if (len(matches) != 1 or matches[0]['type'] != edge['relation_type'] or matches[0]['target'] != edge['target']
                or position is not None and matches[0].get('position') != position):
            raise ReqIFError('reqif_native_relation_binding_mismatch', exit_code=6, object_id=identifier)
        return {**edge, 'relation_id': rel_id}

    specifications, hierarchies, relations = [], [], []
    for spec in document.specifications:
        native_id = native(occurrence_bindings, spec.identifier, {'document'})
        projected = document.project_record(spec.identifier)
        if not projected['representable']:
            raise ReqIFError('reqif_specification_fields_not_representable', object_id=spec.identifier)
        fields = mapping.artifact(spec.type_id, projected['fields'])
        if fields['artifact']['artifact_type'] != 'document':
            raise ReqIFError('reqif_specification_native_type', exit_code=6, object_id=spec.identifier)
        specifications.append({'external_id': spec.identifier, 'native_id': native_id, 'children': list(spec.children),
                               'field_projection': fields, 'external_identity': _source_identity(
                                   spec.identifier, source_system, source_document, external_revision)})
    by_id = {v.identifier: v for v in document.specifications + document.hierarchies}
    by_object = {v.identifier: v for v in document.objects}
    for item in document.hierarchies:
        parent = native(occurrence_bindings, item.owner_id, {'document', 'section'})
        child = native(occurrence_bindings, item.identifier, {'section', 'content_block'})
        obj = native(object_bindings, item.object_id)
        if obj != child and not any(r['type'] == 'references' and r['target'] == obj for r in supplied[child]['relations']):
            raise ReqIFError('reqif_occurrence_object_binding_mismatch', exit_code=6, object_id=item.identifier)
        edge = mapping.hierarchy(by_object[item.object_id].type_id, parent, child)
        position = by_id[item.owner_id].children.index(item.identifier)
        edge = check_edge(edge, item.identifier, position if edge['relation_type'] == 'contains' else None)
        hierarchies.append({**edge, 'external_identity': identity(item.identifier, 'hierarchy'),
            'object_id': item.object_id, 'owner_id': item.owner_id, 'children': list(item.children), 'position': position})
    for item in document.relations:
        edge = mapping.relation(item.type_id, native(object_bindings, item.source), native(object_bindings, item.target))
        relations.append({**check_edge(edge, item.identifier), 'external_identity': identity(item.identifier, 'relation'),
                          'external_source': item.source, 'external_target': item.target})
    return {'mapping': mapping.resource.binding(), 'source_sha256': document.source_sha256,
            'specifications': specifications, 'hierarchies': hierarchies, 'relations': relations,
            'native_structure': assessment.data, 'native_structure_sha256': assessment.sha256,
            'uninterpreted': document.observation()['uninterpreted'],
            'validation_scope': 'explicit_reqif_native_structure_bindings',
            'import_complete': False, 'write_authorized': False, 'execution_ready': False}
