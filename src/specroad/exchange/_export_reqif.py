"""Build ReqIF with explicitly retained type definitions, never guessed types.

Native first-export identities use the existing stable identifier algorithm.
Imported type/definition metadata comes only from verified source carriers in
the selected native scope. Missing bindings are reported as actual losses.
"""
from dataclasses import replace
from hashlib import sha256

from .. import __version__
from ..model.canonical import canonical_json_bytes
from ._export_manifest import snapshot_time
from ._reqif_mapping import _native_value, reqif_object_identifier
from ._reqif_values import _Node, _SEP, REQIF_NAMESPACE, ReqIFError, ReqIFLimits
from ._reqif_xml import _serialize
from .reqif import decode_reqif_structure
from .reqif_preservation import _carrier


def node(tag, children=(), **attrs):
    return _Node(REQIF_NAMESPACE + _SEP + tag, tuple(sorted(attrs.items())), tuple(children))


def _inverse(rule, artifact):
    name = rule['target_field']
    if name not in artifact:
        raise ReqIFError('mapping_source_field_missing', pointer='/' + name)
    value = artifact[name]
    if rule['value_map'] is not None:
        matches = [r['external_value'] for r in rule['value_map']
                   if canonical_json_bytes(r['target_value']) == canonical_json_bytes(value)]
        if len(matches) != 1:
            raise ReqIFError('reqif_inverse_mapping_ambiguous', exit_code=6)
        value = matches[0]
    return value


def export_reqif(artifacts, mapping, model, losses, *, attachments, scope_attachments, resource_ids, limits):
    if type(limits) is not ReqIFLimits:
        raise ReqIFError('typed_xml_limits_required', exit_code=2)
    from ._reqif_attachments import ReqIFAttachment
    from .reqif_loss import assess_reqif_transfer
    from ..mappings import ExternalIdentityRegistry, select_registries
    from ..storage.json_syntax import parse_json_object
    from ..documents.structure import assess_document_structure
    structure = assess_document_structure(model)
    for artifact in artifacts:
        if artifact['artifact_type'] == 'document':
            structure.require_document(artifact['id'])
    registry_resources = []
    for document in model.resource_files:
        if document.path.startswith('mappings/'):
            value = parse_json_object(document.content)
            if value.get('mapping_format_version') == 'external-identity-registry-v1':
                resource = ExternalIdentityRegistry(document.content)
                if resource.key in resource_ids and resource.data['mapping'] == mapping.binding():
                    registry_resources.append(resource)
    registries = select_registries(registry_resources,
        bindings=[r.binding() for r in registry_resources], mappings=[mapping])
    descriptions = {a.path: a for a in model.attachment_descriptors}
    supplied = tuple(ReqIFAttachment(path, descriptions[path], raw) for path, raw in attachments)
    source_files = tuple(ReqIFAttachment(a.path, a, model.source_files[a.path])
                         for a in scope_attachments)
    carriers = {}
    for artifact in artifacts:
        carrier = artifact.get('extensions', {}).get('specroad.reqif')
        if carrier is not None:
            for entry, raw in _carrier(carrier, limits):
                context = {k: entry[k] for k in ('source_system', 'source_document', 'external_revision')}
                carriers[(canonical_json_bytes(context), entry['source_sha256'])] = (
                    context, decode_reqif_structure(raw, limits=limits))
    definitions, datatypes, used = {}, {}, set()
    represented, objects, specifications, contexts, ids, native_types = [], [], [], {}, {}, {}
    for artifact in artifacts:
        types = [r['external_type'] for r in mapping.data['types']
                 if r['artifact_type'] == artifact['artifact_type']]
        if len(types) > 1:
            raise ReqIFError('reqif_inverse_type_ambiguous', exit_code=6)
        candidates = []
        expected_tag = 'SPECIFICATION-TYPE' if artifact['artifact_type'] == 'document' else 'SPEC-OBJECT-TYPE'
        for context, document in carriers.values():
            for typ in document.types:
                if typ.identifier in types and typ.element.tag == expected_tag:
                    candidates.append((context, document, typ))
        if not candidates:
            losses.add(artifact['id'], '', 'reqif_type_binding_missing' if types else 'reqif_artifact_type_unmapped')
            continue
        # Semantically equal repeated carriers are harmless; differing source
        # contexts or definitions require an explicit binding, never first-wins.
        signatures = {canonical_json_bytes(context) + _serialize(typ.element)
                      + b''.join(_serialize(d.element) for d in document.datatypes)
                      for context, document, typ in candidates}
        if len(signatures) != 1:
            raise ReqIFError('reqif_type_binding_ambiguous', exit_code=6)
        context, document, typ = candidates[0]
        external_id = reqif_object_identifier(artifact, project_id=model.configuration.project_id,
            source_system=context['source_system'], source_document=context['source_document'], used_ids=used)
        values, omitted = [], False
        for rule in mapping.data['fields']:
            if rule['external_type'] != typ.identifier:
                continue
            definition = next((d for d in typ.definitions if d.identifier == rule['external_field']), None)
            if definition is None:
                raise ReqIFError('reqif_definition_reference', exit_code=6, definition_id=rule['external_field'])
            value = _inverse(rule, artifact)
            if definition.family == 'XHTML':
                from ._reqif_xhtml import from_markdown
                root = from_markdown(value, attachments=source_files)
                pending, references = [root], set()
                while pending:
                    item = pending.pop()
                    references.update(v for k, v in item.attributes if k in ('href', 'data'))
                    pending.extend(child for child in item.content if type(child) is _Node)
                if references - {item.reference for item in supplied}:
                    # Bound source bytes were checked above. Omitting their
                    # transport makes this explicitly mapped record unavailable.
                    # Do not emit a missing mandatory mapping field, unresolved
                    # ReqIFZ URI or invented replacement text.
                    losses.add(artifact['id'], '', 'reqif_attachment_transport_omitted')
                    omitted = True
                    break
                values.append(node('ATTRIBUTE-VALUE-XHTML', (
                    node('DEFINITION', (node('ATTRIBUTE-DEFINITION-XHTML-REF', (definition.identifier,)),)),
                    node('THE-VALUE', (root,)))))
            else:
                values.append(_native_value(definition, value, external_id))
        if omitted:
            continue
        for typ_or_dt, collection in ((typ, definitions), *((d, datatypes) for d in document.datatypes
                                       if d.identifier in {a.datatype_id for a in typ.definitions})):
            existing = collection.get(typ_or_dt.identifier)
            if existing is not None and _serialize(existing) != _serialize(typ_or_dt.element):
                raise ReqIFError('reqif_export_definition_conflict', exit_code=6)
            collection[typ_or_dt.identifier] = typ_or_dt.element
        tag = 'SPECIFICATION' if artifact['artifact_type'] == 'document' else 'SPEC-OBJECT'
        children = (node('VALUES', values), node('TYPE', (node(expected_tag + '-REF', (typ.identifier,)),)))
        value = node(tag, children, **{'IDENTIFIER': external_id, 'LAST-CHANGE': snapshot_time((artifact,))})
        (specifications if tag == 'SPECIFICATION' else objects).append(value)
        used.add(external_id)
        ids[artifact['id']] = external_id
        native_types[artifact['id']] = typ.identifier
        contexts[artifact['id']] = context
        represented.append(artifact)
    # Native document order is stored in contains positions, never file order.
    index = {a['id']: a for a in artifacts}
    by_id = {a['id']: a for a in represented}

    def nonartifact_identity(owner, relation, kind):
        context = contexts[owner]
        matches = [i for i in relation.get('external_identities', [])
                   if i['source_system'] == context['source_system'] and i['source_document'] == context['source_document']]
        if len(matches) > 1:
            raise ReqIFError('reqif_external_identity_ambiguous', exit_code=6)
        if not matches:
            return None
        identity = matches[0]['external_id']
        if registries.lookup(kind, context['source_system'], context['source_document'], identity) is None:
            raise ReqIFError('reqif_registry_binding_missing', exit_code=6)
        if identity in used:
            raise ReqIFError('reqif_export_identifier_conflict', exit_code=6)
        used.add(identity)
        return identity

    def hierarchy(parent, ancestry=()):
        if parent in ancestry:
            raise ReqIFError('reqif_hierarchy_cycle')
        result = []
        for relation in sorted((r for r in index[parent]['relations'] if r['type'] == 'contains'),
                               key=lambda r: (r['position'], r['target'], r['relation_id'])):
            child = relation['target']
            if child not in by_id or by_id[child]['artifact_type'] == 'document':
                continue
            rules = [r for r in mapping.data['hierarchies'] if r['external_type'] == native_types[child]
                     and r['relation_type'] == 'contains' and r['direction'] == 'parent_to_child']
            occurrence = nonartifact_identity(parent, relation, 'hierarchy') if rules else None
            if occurrence is None:
                losses.add(parent, '/relations/' + str(index[parent]['relations'].index(relation)),
                           'reqif_hierarchy_binding_missing')
                continue
            result.append(node('SPEC-HIERARCHY', (
                node('OBJECT', (node('SPEC-OBJECT-REF', (ids[child],)),)),
                node('CHILDREN', hierarchy(child, (*ancestry, parent)))),
                **{'IDENTIFIER': occurrence, 'LAST-CHANGE': snapshot_time((by_id[child],))}))
        return tuple(result)

    specifications = [replace(s, content=s.content + (node('CHILDREN', hierarchy(a['id'])),))
                      for a, s in zip((a for a in represented if a['artifact_type'] == 'document'), specifications)]
    relations = []
    for artifact in represented:
        if artifact['artifact_type'] == 'document':
            continue
        for position, relation in enumerate(artifact['relations']):
            target = relation['target']
            if target not in by_id or by_id[target]['artifact_type'] == 'document':
                continue
            rules = [r for r in mapping.data['relations'] if r['relation_type'] == relation['type']]
            if len(rules) > 1:
                raise ReqIFError('reqif_inverse_relation_ambiguous', exit_code=6)
            if not rules:
                continue
            rule = rules[0]
            candidates = [t for _, d in carriers.values() for t in d.types
                          if t.identifier == rule['external_type'] and t.element.tag == 'SPEC-RELATION-TYPE']
            if len({_serialize(t.element) for t in candidates}) > 1:
                raise ReqIFError('reqif_type_binding_ambiguous', exit_code=6)
            identity = nonartifact_identity(artifact['id'], relation, 'relation') if candidates else None
            if identity is None:
                losses.add(artifact['id'], '/relations/' + str(position), 'reqif_relation_binding_missing')
                continue
            typ = candidates[0]
            # A relation type requiring values needs its existing explicit
            # field projection; an empty-value placeholder is not an export.
            if typ.definitions:
                raise ReqIFError('reqif_relation_value_binding_required', exit_code=6)
            definitions[typ.identifier] = typ.element
            first, second = ids[artifact['id']], ids[target]
            if rule['direction'] == 'reverse':
                first, second = second, first
            relations.append(node('SPEC-RELATION', (node('TYPE', (node('SPEC-RELATION-TYPE-REF', (typ.identifier,)),)),
                node('SOURCE', (node('SPEC-OBJECT-REF', (first,)),)), node('TARGET', (node('SPEC-OBJECT-REF', (second,)),))),
                **{'IDENTIFIER': identity, 'LAST-CHANGE': snapshot_time((artifact,))}))
    timestamp = snapshot_time(represented)
    header_id = '_sr_header_' + sha256(canonical_json_bytes([model.configuration.project_id, sorted(ids)])).hexdigest()
    header = node('REQ-IF-HEADER', (
        node('CREATION-TIME', (timestamp,)), node('REQ-IF-TOOL-ID', ('SpecRoad ' + __version__,)),
        node('REQ-IF-VERSION', ('1.0',)), node('SOURCE-TOOL-ID', ('SpecRoad',)), node('TITLE', ('SpecRoad export',))),
        IDENTIFIER=header_id)
    root = node('REQ-IF', (node('THE-HEADER', (header,)), node('CORE-CONTENT', (node('REQ-IF-CONTENT', (
        node('DATATYPES', [datatypes[k] for k in sorted(datatypes)]),
        node('SPEC-TYPES', [definitions[k] for k in sorted(definitions)]),
        node('SPEC-OBJECTS', objects), node('SPEC-RELATIONS', relations), node('SPECIFICATIONS', specifications))),))))
    output = _serialize(root)
    checked = decode_reqif_structure(output, limits=limits)
    if checked.unsupported:
        raise ReqIFError('reqif_uninterpreted_export')
    # Reuse the existing whole-record loss comparison; preserve its identities
    # in format_details. A new manifest never invents an alternate loss proof.
    for artifact in represented:
        source = canonical_json_bytes(artifact)
        report = assess_reqif_transfer(source, source_kind='json', source_context=contexts[artifact['id']],
            expected_source_sha256=sha256(source).hexdigest(), direction='export', limits=limits,
            target_bytes=output, expected_target_sha256=sha256(output).hexdigest(), target_kind='xml',
            mappings=[mapping], mapping_key=mapping.key, expected_mapping_sha256=mapping.sha256,
            record_identifier=ids[artifact['id']], source_attachments=source_files, target_attachments=supplied)
        if not report['assessment_complete']:
            raise ReqIFError('reqif_export_assessment_incomplete', exit_code=6)
        for item in report['items']:
            if item['disposition'] == 'lost':
                location = item['location']
                losses.add(artifact['id'], location.get('pointer', ''), item['reason'], item)
    return output, tuple(represented)
