"""Bound, whole-input loss assessment and a pure ReqIF export return boundary.

Original-source transport, mapped XML records, and one native JSON record are
distinct scopes. Unknown XML is never matched heuristically to modified XML.
Record comparisons use the existing explicit mapping and prose projection;
all remaining source information is inventoried, including metadata and edges.
This does not construct a native model, publish files, or authorize an import.
"""
from copy import deepcopy
from hashlib import sha256

from ..mappings import select_mapping
from ..model.attachments import AttachmentDescriptor
from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..storage.json_syntax import parse_json_object
from .reqif import ReqIFError, ReqIFLimits, decode_reqif_structure
from .reqif_preservation import (_KEY, _bound, _carrier, _context,
                                _json_at, _key, _target_sources)
from ._reqif_attachments import _attachments, relative_reference
from ._reqif_fields import records
from ._reqif_loss_inventory import (_attribute, _location, _native_inventory,
                                   _nodes, _pointer, _xml_inventory)
from ._reqif_loss_report import _assessed_items
from ._reqif_values import _SEP
from ._reqif_xhtml import _binding as _xhtml_attachment, parse_markdown
from ._reqif_xhtml_profile import _tag

_URI_ATTRIBUTES = {'href', 'src', 'data', 'action', 'formaction', 'codebase', 'archive', 'poster'}


class ReqIFLossError(ReqIFError):
    """Code 3 with an owned machine report, never export bytes or source text."""

    def __init__(self, report):
        super().__init__('reqif_export_loss' if report['assessment_complete'] else 'reqif_assessment_incomplete')
        self._report = deepcopy(report)

    @property
    def report(self):
        return deepcopy(self._report)


def _json(raw):
    try:
        return parse_json_object(raw)
    except ModelError as error:
        raise ReqIFError(error.reason, pointer=error.pointer) from error


def _mapping(mappings, key, expected):
    if key is None and expected is None:
        if mappings:
            raise ReqIFError('reqif_mapping_binding_required', exit_code=2)
        return None
    result = select_mapping(mappings, key=key, expected_sha256=expected)
    if result.resource.data['source_format'] != 'reqif':
        raise ReqIFError('reqif_mapping_format_required', exit_code=2)
    return result


def _target(raw, expected, kind, pointer, limits, source, context):
    if raw is None:
        if any(v is not None for v in (expected, kind, pointer)):
            raise ReqIFError('reqif_target_bytes_required', exit_code=2)
        return None, None, None
    _bound(raw, expected, name='target')
    if kind == 'xml':
        if pointer is not None:
            raise ReqIFError('reqif_target_kind_invalid', exit_code=2)
        document = decode_reqif_structure(raw, limits=limits)
        proof = ({'target_sha256': expected, 'location': _location(()), 'source_key': None}
                 if raw == source else None)
        return None, document, proof
    if kind != 'json':
        raise ReqIFError('reqif_target_kind_invalid', exit_code=2)
    value = _json(raw)
    proof = None
    if pointer is not None:
        entries = _target_sources(raw, expected, pointer, limits)
        key = [context[k] for k in ('source_system', 'source_document', 'external_revision')] + [sha256(source).hexdigest()]
        for i, (entry, original) in enumerate(entries):
            if _key(entry) == key:
                if original != source:
                    raise ReqIFError('reqif_preservation_source_changed', exit_code=6)
                proof = {'target_sha256': expected,
                         'location': {'kind': 'json', 'pointer': pointer + '/' + _KEY + '/sources/' + str(i)},
                         'source_key': key}
    return value, None, proof


def _xml_references(document, bindings):
    """Resolve every URI attribute, including originals and opaque subtrees.

    Only supplied immutable bindings are consulted. Keys remain the original
    XML reference; this does not perform a second decode or any I/O.
    """
    result = []
    for node, path in _nodes(document):
        for name, reference in node.attributes:
            if name.rpartition(_SEP)[2].lower() not in _URI_ATTRIBUTES:
                continue
            relative_reference(reference)
            if reference not in bindings:
                raise ReqIFError('reqif_attachment_unresolved', pointer=node.pointer)
            result.append((_location(path, _attribute(name)), bindings[reference]))
        if _tag(node) in ('a', 'object'):
            required = {'href'} if _tag(node) == 'a' else {'data', 'type'}
            if not required <= node.attrs.keys():
                raise ReqIFError('reqif_xhtml_reference_attribute_required', pointer=node.pointer)
            _xhtml_attachment(node, bindings)
    return result


def _json_references(value, bindings):
    entries = value.get('attachments', [])
    if type(entries) is not list:
        raise ReqIFError('reqif_native_attachments_invalid')
    by_path, seen, result = {}, set(), []
    for attachment in bindings.values():
        by_path.setdefault(attachment.descriptor.path, []).append(attachment)
    for i, data in enumerate(entries):
        try:
            descriptor = AttachmentDescriptor.from_data(data)
        except ModelError as error:
            raise ReqIFError(error.reason) from error
        if descriptor.path in seen:
            raise ReqIFError('reqif_attachment_binding_ambiguous', exit_code=6)
        seen.add(descriptor.path)
        matches = by_path.get(descriptor.path, [])
        if not matches:
            raise ReqIFError('reqif_attachment_unresolved')
        if len(matches) != 1 or matches[0].descriptor != descriptor:
            raise ReqIFError('reqif_attachment_binding_ambiguous', exit_code=6)
        result.append(({'kind': 'json', 'pointer': '/attachments/' + str(i)}, matches[0]))
    return result


def _transport(references, target_bindings):
    transfers, losses = [], []
    for location, source in references:
        target = target_bindings.get(source.reference)
        # Paths, media and bytes are all part of the supplied transport unit.
        # A same-hash claim without actual bytes never reaches this comparison.
        if target is not None and (target.content != source.content or target.descriptor != source.descriptor):
            raise ReqIFError('reqif_attachment_transport_changed', exit_code=6)
        if target is None:
            losses.append((location, 'reqif_attachment_not_transported', None))
        else:
            transfers.append({'source_location': location, 'reference': source.reference,
                              'descriptor': source.descriptor.data,
                              'target_sha256': sha256(target.content).hexdigest(), 'transport': 'bound_file_bytes'})
    return transfers, losses


def _projections(document, attachments):
    return {record.identifier: document.project_record(record.identifier, xhtml=True, attachments=attachments)
            for record in records(document)}


def _import_comparisons(document, projections, mapping, target, bindings):
    if type(bindings) is not dict or any(type(k) is not str or type(v) is not str for k, v in bindings.items()):
        raise ReqIFError('reqif_record_bindings_required', exit_code=2)
    if len(set(bindings.values())) != len(bindings):
        raise ReqIFError('reqif_native_identity_binding_ambiguous', exit_code=6)
    known = {record.identifier for record in records(document)}
    if set(bindings) - known:
        raise ReqIFError('reqif_object_missing', exit_code=6)
    consumed, comparisons, unassessed = set(), [], set()
    rows = mapping.resource.data['fields']
    for record in records(document):
        projected = projections[record.identifier]
        if record.identifier not in bindings or target is None:
            unassessed.add('native_record_target_missing')
            continue
        at = bindings[record.identifier]
        actual = _json_at(target, at)
        if type(actual) is not dict:
            raise ReqIFError('reqif_native_record_required', exit_code=6)
        if not projected['representable']:
            unassessed.add('native_record_projection_incomplete')
            continue
        mapped = mapping.artifact(record.type_id, projected['fields'])
        expected = mapped['artifact']
        type_matches = actual.get('artifact_type') == expected['artifact_type']
        fields = []
        for row in rows:
            if row['external_type'] != record.type_id:
                continue
            name = row['target_field']
            matches = type_matches and name in actual and canonical_json_bytes(actual[name]) == canonical_json_bytes(expected[name])
            if matches:
                consumed.add((record.identifier, row['external_field']))
            fields.append({'external_field': row['external_field'], 'target_pointer': _pointer(at, name), 'matches': matches})
        comparisons.append({'external_id': record.identifier, 'target_pointer': at,
                            'type_matches': type_matches, 'fields': fields})
    return consumed, comparisons, unassessed


def _native_comparisons(value, document, mapping, identifier, attachments):
    if type(identifier) is not str or not identifier:
        raise ReqIFError('reqif_object_identifier_required', exit_code=2)
    if document is None or mapping is None:
        return set(), [], {'native_mapping_and_target_required'}
    record = next((r for r in records(document) if r.identifier == identifier), None)
    if record is None:
        raise ReqIFError('reqif_object_missing', exit_code=6, object_id=identifier)
    projected = document.project_record(identifier, xhtml=True, attachments=attachments)
    if not projected['representable']:
        return set(), [{'external_id': identifier, 'unrepresentable': projected['unrepresentable']}], {'native_record_projection_incomplete'}
    mapped = mapping.artifact(record.type_id, projected['fields'])['artifact']
    consumed, comparisons = set(), []
    missing = {'native_source_fields_missing'} if any(name not in value for name in mapped) else set()
    type_matches = value.get('artifact_type') == mapped['artifact_type']
    if type_matches:
        consumed.add('artifact_type')
    for name, expected in mapped.items():
        if name == 'artifact_type':
            continue
        matches = type_matches and name in value and canonical_json_bytes(value[name]) == canonical_json_bytes(expected)
        if matches:
            consumed.add(name)
        comparisons.append({'source_pointer': _pointer('', name), 'external_id': identifier, 'matches': matches})
    return consumed, comparisons, missing


def _native_prose_references(value, document, mapping, identifier, references):
    if document is None or mapping is None:
        return
    record = next((r for r in records(document) if r.identifier == identifier), None)
    if record is None:
        return
    definitions = next(t.definitions for t in document.types if t.identifier == record.type_id)
    xhtml = {d.identifier for d in definitions if d.family == 'XHTML'}
    paths = {a.descriptor.path for _, a in references}
    for row in mapping.resource.data['fields']:
        if row['external_type'] != record.type_id or row['external_field'] not in xhtml:
            continue
        name = row['target_field']
        if name not in value:
            continue
        _, content = parse_markdown(value[name], pointer=_pointer('', name))
        pending = [content]
        while pending:
            node = pending.pop()
            if node.get('attachment_path') is not None and node['attachment_path'] not in paths:
                raise ReqIFError('reqif_attachment_unresolved', pointer=_pointer('', name))
            pending.extend(node.get('children', []))


def assess_reqif_transfer(source_bytes, *, source_kind, source_context, expected_source_sha256,
                          direction, limits, target_bytes=None, expected_target_sha256=None,
                          target_kind=None, extensions_pointer=None, mappings=(), mapping_key=None,
                          expected_mapping_sha256=None, record_bindings=None, record_identifier=None,
                          source_attachments=(), target_attachments=()):
    """Assess the entire bound source unit, never a caller's claimed loss list.

    XML without a mapping assesses original-source transport only. With a
    mapping, record_bindings links actual XML IDs to JSON target pointers and
    every record must be assessed. JSON export covers one entire supplied
    native record candidate against record_identifier in the actual XML target.
    It does not certify the candidate's complete native artifact schema.

    Attachment tuples are actual proposed file payloads, not a cache or an
    assertion that files were written. The export boundary returns those same
    validated bytes; future project/archive integration owns publication.
    """
    context = _context(source_context)
    if direction not in ('import', 'export') or source_kind not in ('xml', 'json'):
        raise ReqIFError('reqif_transfer_scope_invalid', exit_code=2)
    if type(limits) is not ReqIFLimits:
        raise ReqIFError('typed_xml_limits_required', exit_code=2)
    _bound(source_bytes, expected_source_sha256, name='source')
    mapping = _mapping(mappings, mapping_key, expected_mapping_sha256)
    source_files, target_files = _attachments(source_attachments), _attachments(target_attachments)
    target, target_document, proof = _target(target_bytes, expected_target_sha256, target_kind,
        extensions_pointer, limits, source_bytes, context)
    # Every target reference must also resolve, even when unrelated to the
    # compared record. Neither unknown nodes nor an old capsule excuse it.
    if target_document is not None:
        _xml_references(target_document, target_files)
    unassessed = set() if target_bytes is not None else {'target_bytes_missing'}
    comparisons = []
    if source_kind == 'xml':
        if record_identifier is not None:
            raise ReqIFError('reqif_transfer_scope_invalid', exit_code=2)
        document = decode_reqif_structure(source_bytes, limits=limits)
        references = _xml_references(document, source_files)
        projections = _projections(document, source_attachments)
        consumed = set()
        if mapping is None:
            if record_bindings is not None:
                raise ReqIFError('reqif_mapping_binding_required', exit_code=2)
            scope = 'whole_reqif_original_source_transport'
        else:
            if target_bytes is not None and target_kind != 'json':
                raise ReqIFError('reqif_native_json_target_required', exit_code=2)
            scope = 'whole_reqif_mapped_records_and_remainders'
            consumed, comparisons, missing = _import_comparisons(document, projections, mapping, target, record_bindings)
            unassessed.update(missing)
        units = [(loc, reason, proof) for loc, reason in _xml_inventory(document, projections, consumed, mapping)]
    else:
        if direction != 'export' or record_bindings is not None or extensions_pointer is not None:
            raise ReqIFError('reqif_transfer_scope_invalid', exit_code=2)
        if target_bytes is not None and target_kind != 'xml':
            raise ReqIFError('reqif_xml_target_required', exit_code=2)
        scope = 'whole_native_record_candidate_to_reqif'
        value = _json(source_bytes)
        # Explicitly used carriers are checked as sources, not interpreted as
        # proof that current native fields survived in the old XML document.
        extensions = value.get('extensions', {})
        if type(extensions) is dict and _KEY in extensions:
            for _, original in _carrier(extensions[_KEY], limits):
                _xml_references(decode_reqif_structure(original, limits=limits), source_files)
        references = _json_references(value, source_files)
        _native_prose_references(value, target_document, mapping, record_identifier, references)
        consumed, comparisons, missing = _native_comparisons(value, target_document, mapping, record_identifier, target_attachments)
        unassessed.update(missing)
        units = [(loc, reason, None) for loc, reason in _native_inventory(value, consumed)]
    transfers, attachment_losses = _transport(references, target_files)
    units.extend(attachment_losses)
    items = _assessed_items(units, direction=direction,
                            source_sha256=expected_source_sha256, source_context=context)
    complete = not unassessed
    return deepcopy({'validation_scope': scope, 'source_kind': source_kind, 'direction': direction,
        'source_sha256': expected_source_sha256, 'source_context': context,
        'mapping_binding': None if mapping is None else mapping.resource.binding(),
        'target_binding': None if target_bytes is None else {'target_sha256': expected_target_sha256,
            'kind': target_kind, 'extensions_pointer': extensions_pointer},
        'record_bindings': record_bindings, 'record_identifier': record_identifier,
        'assessment_complete': complete, 'loss_free': complete and all(i['disposition'] == 'preserved' for i in items.values()),
        'native_projection_complete': complete and mapping is not None and not items,
        'unassessed': sorted(unassessed), 'items': [items[k] for k in sorted(items)],
        'record_comparisons': comparisons, 'attachment_transfers': transfers,
        'import_complete': False, 'execution_ready': False, 'write_authorized': False})


def prepare_reqif_export(source_bytes, *, fail_on_loss, **binding):
    """Return a checked XML/file candidate, or a report-bearing Code 3 error.

    Always computes the assessment from real bytes; accepts no supplied report.
    No candidate bytes are returned before the loss/completeness gate succeeds.
    Unset fail-on-loss permits completely reported losses, never missing inputs.
    """
    if type(fail_on_loss) is not bool:
        raise ReqIFError('reqif_fail_on_loss_boolean_required', exit_code=2)
    if binding.get('target_bytes') is not None and binding.get('target_kind') != 'xml':
        raise ReqIFError('reqif_xml_target_required', exit_code=2)
    report = assess_reqif_transfer(source_bytes, direction='export', **binding)
    if not report['assessment_complete'] or fail_on_loss and not report['loss_free']:
        raise ReqIFLossError(report)
    return {'xml_bytes': binding['target_bytes'], 'assessment': report,
            'attachments': tuple(_attachments(binding.get('target_attachments', ())).values()),
            'execution_ready': False, 'write_authorized': False}
