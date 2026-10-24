"""Actual scoped format bytes, native hashes, losses and exact snapshot time."""
from copy import deepcopy
from hashlib import sha256
import json

import pytest

from specroad.exchange.exporting import ExportError, prepare_export
from specroad.exchange._export_manifest import snapshot_time
from specroad.graph.scope_descriptors import ScopeDescriptor
from specroad.mappings import ExchangeMapping, CSVProfile
from specroad.model.canonical import canonical_json_bytes
from specroad.model.errors import ModelError
from specroad.validation import ModelDocument
from support.domain import domain_value
from support.exchange_mappings import mapping_value
from support.scopes import descriptor, query
from support.targets import model


def mapping(fmt='ndjson', **overrides):
    return ExchangeMapping(canonical_json_bytes(mapping_value(source_format=fmt, **overrides)))


def export(values, *, fmt='ndjson', scope=None, rule=None, extra=(), **options):
    rule = rule or mapping(fmt)
    native = model(values, resource_files=(ModelDocument('mappings/export.json', rule.source_bytes), *extra))
    return native, prepare_export(native, ScopeDescriptor(scope or descriptor('project')),
        output_format=fmt, mapping_key=rule.key, expected_mapping_sha256=rule.sha256, **options)


@pytest.mark.parametrize(('times', 'expected'), [
    ([], '1970-01-01T00:00:00Z'),
    (['2026-10-01t00:00:00.000Z'], '2026-10-01T00:00:00Z'),
    (['2026-10-01T00:00:00.10Z', '2026-10-01t00:00:00.1000Z'], '2026-10-01T00:00:00.1Z'),
    (['2026-10-01T00:00:00.123456789012345678900Z', '2026-10-01T00:00:00.123456789012345678901Z'],
     '2026-10-01T00:00:00.123456789012345678901Z'),
    (['2026-10-01T00:00:00.9Z', '2026-10-01T00:00:01Z'], '2026-10-01T00:00:01Z'),
    (['2026-06-30T23:59:60.100Z', '2026-06-30T23:59:59.999Z'], '2026-06-30T23:59:60.1Z'),
])
def test_export_exact_time(times, expected):
    assert snapshot_time([{'updated_at': t} for t in times]) == expected
    assert snapshot_time([{'updated_at': t} for t in reversed(times)]) == expected


@pytest.mark.parametrize('value', [None, '', '2026-02-30T00:00:00Z', '2026-10-01T00:00:00+00:00'])
def test_export_missing_invalid_time_is_not_empty(value):
    with pytest.raises(ModelError):
        snapshot_time([{'updated_at': value}])


def test_export_ndjson_full_native_payload_hash_and_closed_manifest():
    artifact = domain_value('requirement')
    native, prepared = export([artifact])
    assert [json.loads(line)['object'] for line in prepared.output_bytes.splitlines()] == [artifact]
    manifest = prepared.manifest
    assert set(manifest) == {'manifest_version', 'format', 'format_version', 'mapping', 'format_profile',
        'scope_descriptor', 'boundary_references', 'model_root_sha256', 'snapshot_at', 'tool_version',
        'options', 'included_ids', 'excluded_contents', 'losses', 'attachments', 'output_sha256'}
    assert manifest['model_root_sha256'] == native.manifest(native.artifacts, descriptor('project')).sha256
    assert manifest['output_sha256'] == sha256(prepared.output_bytes).hexdigest()
    assert prepared.manifest_bytes == canonical_json_bytes(manifest)
    assert manifest['included_ids'] == [artifact['id']]
    assert manifest['snapshot_at'] == artifact['updated_at']
    assert manifest['options'] == {'include_attachments': False, 'fail_on_loss': False}
    assert manifest['format_profile'] is None


def test_export_query_page_preserves_native_fields_and_ignores_outside_changes():
    one = domain_value('requirement')
    other = domain_value('goal', updated_at='2030-01-01T00:00:00Z')
    scope = descriptor('query', {'query': query(filters={'type': ['requirement']}, select=['/id'], limit=1)})
    _, first = export([other, one], scope=scope)
    other['statement'] = 'Unrelated changed statement.'
    _, second = export([one, other], scope=scope)
    assert first == second
    assert json.loads(first.output_bytes)['object'] == one
    assert first.manifest['included_ids'] == [one['id']]
    assert first.manifest['snapshot_at'] == one['updated_at']
    assert all(r['resource_id'] != other['id'] for r in first.manifest['excluded_contents'])


def test_export_empty_page_uses_epoch_and_emits_no_ndjson_manifest_row():
    _, prepared = export([domain_value()], scope=descriptor('query', {'query': query(offset=10)}))
    assert prepared.output_bytes == b''
    assert prepared.manifest['included_ids'] == []
    assert prepared.manifest['snapshot_at'] == '1970-01-01T00:00:00Z'


@pytest.mark.parametrize('kind', ['document', 'release'])
def test_export_scopes_use_native_seeds_and_strong_closure(kind):
    from support.records import record_value
    from support.domain import relation
    requirement = domain_value('requirement')
    outside = domain_value('goal', updated_at='2030-01-01T00:00:00Z')
    if kind == 'document':
        seed = record_value('document')
        block = record_value('content_block', block_kind='artifact_ref', payload={'render_mode': 'full'},
                             relations=[relation('references', requirement['id'])])
        section = record_value('section')
        edge = relation('contains', section['id'])
        edge.update(relation_id='REL-' + '1' * 26, position=0)
        seed['relations'] = [edge]
        edge = relation('contains', block['id'])
        edge.update(relation_id='REL-' + '2' * 26, position=0)
        section['relations'] = [edge]
        extra = [section, block]
    else:
        seed = domain_value('release')
        requirement['relations'] = [relation('scheduled_for', seed['id'])]
        extra = []
    scope = descriptor(kind, {kind + '_id': seed['id']})
    _, prepared = export([requirement, outside, seed, *extra], scope=scope)
    expected = {seed['id'], requirement['id'], *(v['id'] for v in extra)}
    assert prepared.manifest['included_ids'] == sorted(expected)
    assert prepared.manifest['snapshot_at'] != outside['updated_at']
    assert {json.loads(line)['object']['id'] for line in prepared.output_bytes.splitlines()} == expected


@pytest.mark.parametrize('include', [False, True])
def test_export_attachment_inventory_and_unchanged_native_root(include):
    from specroad.model.attachments import AttachmentDescriptor
    from support.records import record_value
    payload = b'actual attachment\x00\xff'
    attachment = AttachmentDescriptor('attachments/result.bin', 'application/octet-stream', len(payload), sha256(payload).hexdigest())
    requirement = domain_value('requirement')
    evidence = record_value('evidence', attachments=[attachment.data])
    rule = mapping()
    native = model([evidence, requirement], resource_files=(ModelDocument('mappings/export.json', rule.source_bytes),
        ModelDocument(attachment.path, payload)), attachments=(attachment,))
    options = dict(output_format='ndjson', mapping_key=rule.key, expected_mapping_sha256=rule.sha256)
    prepared = prepare_export(native, ScopeDescriptor(descriptor('project')), include_attachments=include, **options)
    assert prepared.manifest['attachments'] == [{**attachment.data, 'included': include}]
    assert prepared.attachment_files == ((attachment.path, payload),) if include else prepared.attachment_files == ()
    assert prepared.manifest['model_root_sha256'] == native.manifest(native.artifacts, descriptor('project')).sha256
    losses = [r for r in prepared.manifest['losses'] if r['resource_id'] == attachment.path]
    assert losses == ([] if include else [{'resource_id': attachment.path, 'pointer': '',
                                          'reason': 'attachments_disabled', 'format_details': {}}])
    with pytest.raises(ExportError, match='export_information_loss') as rejected:
        prepare_export(native, ScopeDescriptor(descriptor('project')), include_attachments=include, fail_on_loss=True, **options)
    assert json.loads(rejected.value.manifest)['options']['fail_on_loss'] is True


def test_export_csv_profile_identity_values_and_single_field_losses():
    rule = mapping('csv', fields=[{'external_type': 'Requirement', 'external_field': 'Statement',
                                  'target_field': 'statement', 'value_map': None}])
    profile = CSVProfile(canonical_json_bytes({
        'schema_version': '0.2.0', 'mapping_format_version': 'csv-profile-v1',
        'mapping_id': 'export:csv', 'mapping_version': '1.0.0', 'mapping': rule.binding(),
        'external_type': 'Requirement', 'identity': {'column': 'ID', 'kind': 'native_id'},
        'columns': [{'column': 'Text', 'external_field': 'Statement', 'codec': {'kind': 'string'},
                     'empty_cell': 'value', 'missing_column': 'error'}], 'error_policy': 'reject', 'extensions': {}}))
    value = domain_value('requirement', statement='A comma, a quote " and\na newline')
    _, prepared = export([value, domain_value('goal')], fmt='csv', rule=rule,
        extra=(ModelDocument('mappings/csv.json', profile.source_bytes),),
        csv_profile_key=profile.key, expected_csv_profile_sha256=profile.sha256)
    assert prepared.output_bytes == ('ID,Text\r\n' + value['id'] + ',"A comma, a quote "" and\na newline"\r\n').encode()
    assert prepared.manifest['included_ids'] == [value['id']]
    assert prepared.manifest['format_profile'] == profile.binding()
    assert any(r['pointer'] == '/updated_at' for r in prepared.manifest['losses'])
    assert any(r['reason'] == 'csv_artifact_type_unmapped' and r['pointer'] == '' for r in prepared.manifest['losses'])


@pytest.mark.parametrize('fmt', ['reqif', 'reqifz'])
def test_export_reqif_uses_bound_definitions_and_same_header_timestamp(fmt):
    from support.reqif_objects import one, LIMITS
    from specroad.exchange.reqif_preservation import merge_reqif_source
    from specroad.exchange.reqif import decode_reqif_structure
    from specroad.exchange.reqifz import decode_reqifz
    rule = mapping('reqif', types=[{'external_type': 'type', 'artifact_type': 'requirement'}],
        fields=[{'external_type': 'type', 'external_field': 'field', 'target_field': 'statement', 'value_map': None}])
    raw = one()
    context = {'source_system': 'supplier', 'source_document': 'requirements', 'external_revision': None}
    value = domain_value('requirement', statement='New native text', updated_at='2026-10-24t01:02:03.123456789000Z')
    value['extensions'] = merge_reqif_source(raw, source_context=context, expected_source_sha256=sha256(raw).hexdigest(),
        extensions={}, expected_extensions_sha256=sha256(b'{}').hexdigest(), limits=LIMITS)
    _, prepared = export([value], fmt=fmt, rule=rule, reqif_limits=LIMITS, max_archive_bytes=20*1024*1024)
    xml = prepared.output_bytes
    if fmt == 'reqifz':
        container = decode_reqifz(xml, expected_sha256=sha256(xml).hexdigest(), document_paths=('exchange.reqif',),
                                 limits=LIMITS, max_uncompressed_bytes=20*1024*1024)
        xml = dict(container.files)['exchange.reqif']
    parsed = decode_reqif_structure(xml, limits=LIMITS)
    assert parsed.project_record(parsed.objects[0].identifier)['fields']['field'] == value['statement']
    assert b'<CREATION-TIME>2026-10-24T01:02:03.123456789Z</CREATION-TIME>' in xml
    assert prepared.manifest['snapshot_at'] == '2026-10-24T01:02:03.123456789Z'
    assert prepared.manifest['included_ids'] == [value['id']]
    assert prepared.manifest['losses']
    assert any('loss_id' in r['format_details'] for r in prepared.manifest['losses'])


def test_export_reqif_document_uses_registered_occurrences_and_native_order():
    from support.reqif_objects import document, TIME, LIMITS
    from support.records import record_value, ref
    from support.domain import relation
    from support.exchange_mappings import registry_value
    from specroad.exchange import merge_reqif_source, decode_reqif_structure
    from specroad.mappings import ExternalIdentityRegistry
    types = ''.join('<' + tag + ' IDENTIFIER="' + identity + '" LAST-CHANGE="' + TIME
        + '"><SPEC-ATTRIBUTES/></' + tag + '>' for tag, identity in (
            ('SPECIFICATION-TYPE', 'doc_type'), ('SPEC-OBJECT-TYPE', 'sec_type'),
            ('SPEC-OBJECT-TYPE', 'block_type')))
    raw = document().replace(b'</SPEC-TYPES>', types.encode() + b'</SPEC-TYPES>')
    context = {'source_system': 'supplier', 'source_document': 'native-doc', 'external_revision': None}
    rule = mapping('reqif', types=[{'external_type': external, 'artifact_type': native} for external, native in
        [('doc_type', 'document'), ('sec_type', 'section'), ('block_type', 'content_block')]],
        fields=[], relations=[], hierarchies=[{'external_type': external, 'relation_type': 'contains',
            'direction': 'parent_to_child'} for external in ('sec_type', 'block_type')])
    entries = []
    def edge(target, token, external_id, position=0):
        identity = {'source_system': context['source_system'], 'source_document': context['source_document'],
                    'external_id': external_id}
        entries.append({'object_class': 'hierarchy', **identity, 'external_revision': None, 'data': {}, 'extensions': {}})
        return {**relation('contains', target), 'relation_id': 'REL-' + token*26, 'position': position,
                'external_identities': [identity]}
    doc = record_value('document', relations=[edge(ref('SEC'), '0', 'section_occurrence')])
    doc['extensions'] = merge_reqif_source(raw, source_context=context, expected_source_sha256=sha256(raw).hexdigest(),
        extensions={}, expected_extensions_sha256=sha256(b'{}').hexdigest(), limits=LIMITS)
    section = record_value('section', relations=[edge(ref('BLOCK', '1'), '1', 'block_second', 2),
                                               edge(ref('BLOCK'), '2', 'block_first', 1)])
    blocks = [record_value('content_block'), record_value('content_block', id=ref('BLOCK', '1'))]
    registry = ExternalIdentityRegistry(canonical_json_bytes(registry_value(rule, entries=entries)))
    _, prepared = export([doc, section, *blocks], fmt='reqif', scope=descriptor('document', {'document_id': doc['id']}),
        rule=rule, extra=[ModelDocument('mappings/registry.json', registry.source_bytes)], reqif_limits=LIMITS)
    parsed = decode_reqif_structure(prepared.output_bytes, limits=LIMITS)
    assert len(parsed.specifications) == 1 and len(parsed.objects) == 3
    assert [row.identifier for row in parsed.hierarchies] == ['section_occurrence', 'block_first', 'block_second']
    assert prepared.manifest['included_ids'] == sorted([doc['id'], section['id'], *(b['id'] for b in blocks)])
    assert not any(row['reason'] == 'reqif_hierarchy_binding_missing' for row in prepared.manifest['losses'])
    assert any(row['resource_id'] == registry.key for row in prepared.manifest['losses'])


@pytest.mark.parametrize('include', [False, True])
def test_export_reqifz_xhtml_image_is_bound_or_explicitly_lost(include):
    from support.reqif_structure import xdocument, attachment
    from support.reqif_objects import LIMITS
    from support.records import record_value
    from specroad.exchange import merge_reqif_source, decode_reqif_structure, decode_reqifz
    image = attachment(reference='attachments/a.png')
    value = domain_value('requirement', statement='![image](attachments/a.png)')
    raw = xdocument('<p>Original source</p>')
    context = {'source_system': 'supplier', 'source_document': 'images', 'external_revision': None}
    value['extensions'] = merge_reqif_source(raw, source_context=context, expected_source_sha256=sha256(raw).hexdigest(),
        extensions={}, expected_extensions_sha256=sha256(b'{}').hexdigest(), limits=LIMITS)
    rule = mapping('reqif', types=[{'external_type': 'type', 'artifact_type': 'requirement'}],
        fields=[{'external_type': 'type', 'external_field': 'field', 'target_field': 'statement', 'value_map': None}])
    native = model([value, record_value('evidence', attachments=[image.descriptor.data])],
        resource_files=[ModelDocument('mappings/export.json', rule.source_bytes),
                        ModelDocument(image.descriptor.path, image.content)], attachments=[image.descriptor])
    prepared = prepare_export(native, ScopeDescriptor(descriptor('project')), output_format='reqifz',
        mapping_key=rule.key, expected_mapping_sha256=rule.sha256, include_attachments=include,
        reqif_limits=LIMITS, max_archive_bytes=20*1024*1024)
    container = decode_reqifz(prepared.output_bytes, expected_sha256=sha256(prepared.output_bytes).hexdigest(),
        document_paths=('exchange.reqif',), limits=LIMITS, max_uncompressed_bytes=20*1024*1024)
    parsed = decode_reqif_structure(dict(container.files)['exchange.reqif'], limits=LIMITS)
    if include:
        fields = parsed.project_record(parsed.objects[0].identifier, xhtml=True, attachments=[image])['fields']
        assert fields['field'] == value['statement']
        assert dict(container.files)[image.descriptor.path] == image.content
    else:
        assert not parsed.objects and value['id'] not in prepared.manifest['included_ids']
        assert any(row['pointer'] == '' and row['resource_id'] == value['id'] and row['reason'] == 'reqif_attachment_transport_omitted'
                   for row in prepared.manifest['losses'])


@pytest.mark.parametrize('policy', ['closed', 'partial'])
def test_export_query_keeps_actual_weak_boundary_policy(policy):
    from support.records import ref
    from support.domain import relation
    first = domain_value('requirement', owner='selected')
    second = domain_value('requirement', id=ref('REQ', '1'), owner='outside', updated_at='2030-01-01T00:00:00Z')
    first['relations'] = [relation('duplicates', second['id'])]
    scope = descriptor('query', {'query': query(filters={'owner': ['selected']})}, boundary_policy=policy)
    _, prepared = export([first, second], scope=scope)
    if policy == 'closed':
        assert prepared.manifest['included_ids'] == sorted([first['id'], second['id']])
        assert prepared.manifest['boundary_references'] == []
        assert prepared.manifest['snapshot_at'] == second['updated_at']
    else:
        assert prepared.manifest['included_ids'] == [first['id']]
        boundary = prepared.manifest['boundary_references']
        assert len(boundary) == 1 and boundary[0]['source_id'] == first['id'] and boundary[0]['target_id'] == second['id']
        assert prepared.manifest['snapshot_at'] == first['updated_at']


def test_export_applies_bound_configuration_before_query_selection():
    from test_configuration_scope import configuration, condition
    from support.records import ref
    selected = configuration()
    first = domain_value('requirement', applicability=condition('linux'))
    second = domain_value('requirement', id=ref('REQ', '1'), applicability=condition('windows'))
    scope = descriptor('query', {'query': query(filters={'type': ['requirement']})}, configuration_id=selected['id'])
    _, prepared = export([selected, first, second], scope=scope)
    assert prepared.manifest['included_ids'] == [first['id']]
    assert prepared.manifest['scope_descriptor']['configuration_id'] == selected['id']
    assert json.loads(prepared.output_bytes)['object'] == first
