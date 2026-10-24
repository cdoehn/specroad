"""Adversarial native bindings, closure, deterministic bytes and export losses."""
from dataclasses import replace
from hashlib import sha256
import io
import json
import zipfile

import pytest

from specroad.exchange import merge_reqif_source, decode_reqif_structure
from specroad.exchange.exporting import ExportError, prepare_export
from specroad.exchange._export_manifest import ExportLosses
from specroad.graph.scope_descriptors import ScopeDescriptor
from specroad.mappings import CSVProfile
from specroad.model.attachments import AttachmentDescriptor
from specroad.model.canonical import canonical_json_bytes
from specroad.model.errors import ModelError
from specroad.validation import ModelDocument
from support.domain import domain_value, relation
from support.records import record_value, ref
from support.reqif_objects import one, LIMITS
from support.scopes import descriptor, query
from support.targets import model
from test_exchange_export import mapping


def inputs(fmt, *, values=None, extra=(), attachments=(), config=None, profiles=None, binding=None):
    rule = mapping('reqif' if fmt == 'reqifz' else fmt,
        types=[{'external_type': 'type', 'artifact_type': 'requirement'}],
        fields=[{'external_type': 'type', 'external_field': 'field',
                 'target_field': 'statement', 'value_map': None}], relations=[], hierarchies=[])
    value = domain_value('requirement', updated_at='2026-10-01t00:00:00.123456789012345678900Z')
    raw = one()
    value['extensions'] = merge_reqif_source(raw,
        source_context={'source_system': 'supplier', 'source_document': 'requirements', 'external_revision': None},
        expected_source_sha256=sha256(raw).hexdigest(), extensions={},
        expected_extensions_sha256=sha256(b'{}').hexdigest(), limits=LIMITS)
    resources = [ModelDocument('mappings/export.json', rule.source_bytes), *extra]
    options = dict(output_format=fmt, mapping_key=rule.key, expected_mapping_sha256=rule.sha256)
    if fmt == 'csv':
        profile = CSVProfile(canonical_json_bytes({'schema_version': '0.2.0',
            'mapping_format_version': 'csv-profile-v1', 'mapping_id': 'export:csv', 'mapping_version': '1.0.0',
            'mapping': rule.binding(), 'external_type': 'type', 'identity': {'column': 'ID', 'kind': 'native_id'},
            'columns': [{'column': 'Text', 'external_field': 'field', 'codec': {'kind': 'string'},
                         'empty_cell': 'value', 'missing_column': 'error'}], 'error_policy': 'reject', 'extensions': {}}))
        resources.append(ModelDocument('mappings/csv.json', profile.source_bytes))
        options.update(csv_profile_key=profile.key, expected_csv_profile_sha256=profile.sha256)
    if fmt in ('reqif', 'reqifz'):
        options['reqif_limits'] = LIMITS
    if fmt == 'reqifz':
        options['max_archive_bytes'] = 20 * 1024 * 1024
    native = model([value] if values is None else values, resource_files=resources,
                   attachments=attachments, config=config, profiles=profiles, binding=binding)
    return native, options


def run(native, options, scope=None, **overrides):
    return prepare_export(native, ScopeDescriptor(scope or descriptor('project')), **(options | overrides))


@pytest.mark.parametrize('fmt', ['ndjson', 'csv', 'reqif', 'reqifz'])
def test_export_permutation_exact_time_and_owned_manifest(fmt):
    native, options = inputs(fmt)
    values = [dict(native.artifacts[0]), domain_value('goal', updated_at='2035-01-01T00:00:00Z')]
    first_model, options = inputs(fmt, values=values)
    second_model, _ = inputs(fmt, values=list(reversed(values)))
    first, second = run(first_model, options), run(second_model, options)
    assert first == second
    expected = values if fmt == 'ndjson' else values[:1]
    assert first.manifest['included_ids'] == sorted(v['id'] for v in expected)
    assert first.manifest['snapshot_at'] == ('2035-01-01T00:00:00Z' if fmt == 'ndjson'
                                           else '2026-10-01T00:00:00.1234567890123456789Z')
    assert first.manifest['model_root_sha256'] == first_model.manifest(first_model.artifacts, descriptor('project')).sha256
    assert first.manifest['output_sha256'] == sha256(first.output_bytes).hexdigest()
    manifest = first.manifest
    manifest['mapping']['sha256'] = '0' * 64
    manifest['losses'].clear()
    assert first == second and first.manifest != manifest
    if fmt != 'ndjson':
        assert any(r['resource_id'] == values[1]['id'] and r['pointer'] == '' for r in first.manifest['losses'])


@pytest.mark.parametrize('fmt', ['ndjson', 'csv', 'reqif', 'reqifz'])
def test_export_empty_query_no_self_manifest_or_container_metadata(fmt):
    native, options = inputs(fmt)
    output = run(native, options, descriptor('query', {'query': query(offset=100)}))
    assert output.manifest['included_ids'] == []
    assert output.manifest['snapshot_at'] == '1970-01-01T00:00:00Z'
    assert output.manifest['losses'] == []
    assert run(native, options, descriptor('query', {'query': query(offset=100)}), fail_on_loss=True).output_bytes == output.output_bytes
    if fmt == 'ndjson':
        assert output.output_bytes == b''
    elif fmt == 'csv':
        assert output.output_bytes == b'ID,Text\r\n'
    else:
        raw = output.output_bytes
        if fmt == 'reqifz':
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                assert archive.namelist() == ['exchange.reqif']
                assert not archive.comment
                raw = archive.read('exchange.reqif')
        parsed = decode_reqif_structure(raw, limits=LIMITS)
        assert not parsed.objects
        assert b'<CREATION-TIME>1970-01-01T00:00:00Z</CREATION-TIME>' in raw
    assert b'exchange-export-v1' not in output.output_bytes


@pytest.mark.parametrize('kind', ['prose', 'admonition'])
@pytest.mark.parametrize('scope_kind', ['query', 'document'])
@pytest.mark.parametrize('include', [False, True])
def test_export_native_prose_attachment_dependency_is_part_of_scope(kind, scope_kind, include):
    raw = b'owned binary bytes'
    attachment = AttachmentDescriptor('attachments/report.bin', 'application/octet-stream', len(raw), sha256(raw).hexdigest())
    payload = {'markdown': '[report](attachments/report.bin)'}
    if kind == 'admonition':
        payload['level'] = 'note'
    block = record_value('content_block', block_kind=kind, payload=payload)
    document = record_value('document', relations=[{**relation('contains', ref('SEC')), 'position': 0}])
    section = record_value('section', relations=[{**relation('contains', block['id']), 'position': 0,
                                                'relation_id': 'REL-' + '1' * 26}])
    native, options = inputs('ndjson', values=[document, section, block],
        extra=[ModelDocument(attachment.path, raw)], attachments=[attachment])
    scope = (descriptor('query', {'query': query(filters={'type': ['content_block']})}) if scope_kind == 'query'
             else descriptor('document', {'document_id': document['id']}))
    result = run(native, options, scope, include_attachments=include)
    assert result.manifest['attachments'] == [{**attachment.data, 'included': include}]
    assert result.attachment_files == (((attachment.path, raw),) if include else ())
    losses = [r for r in result.manifest['losses'] if r['resource_id'] == attachment.path]
    assert [r['reason'] for r in losses] == ([] if include else ['attachments_disabled'])
    other = run(native, options, scope, include_attachments=not include)
    assert other.manifest['model_root_sha256'] == result.manifest['model_root_sha256']
    assert other.output_bytes == result.output_bytes


@pytest.mark.parametrize('include', [False, True])
def test_export_missing_native_prose_attachment_is_error_not_format_loss(include):
    block = record_value('content_block', payload={'markdown': '[missing](attachments/missing.bin)'})
    native, options = inputs('ndjson', values=[block])
    with pytest.raises(ModelError):
        run(native, options, include_attachments=include, fail_on_loss=False)


def test_export_nonreferential_statement_is_not_parsed_as_markdown():
    value = domain_value('requirement', statement='Document the text [example](attachments/not-a-reference.bin).')
    native, options = inputs('ndjson', values=[value])
    result = run(native, options)
    assert json.loads(result.output_bytes)['object'] == value
    assert result.manifest['attachments'] == []


@pytest.mark.parametrize('fmt', ['ndjson', 'csv', 'reqif', 'reqifz'])
@pytest.mark.parametrize('policy', ['closed', 'partial'])
def test_export_missing_strong_target_is_never_a_loss_or_boundary(fmt, policy):
    value = domain_value('requirement', relations=[relation('depends_on', ref('REQ', '1'))])
    native, options = inputs(fmt, values=[value])
    with pytest.raises(ModelError):
        run(native, options, descriptor('project', boundary_policy=policy), fail_on_loss=False)


@pytest.mark.parametrize('fmt', ['ndjson', 'csv', 'reqif', 'reqifz'])
def test_export_mapping_hash_and_format_cannot_be_overridden(fmt):
    native, options = inputs(fmt)
    for change in ({'expected_mapping_sha256': '0' * 64}, {'mapping_key': 'missing:mapping@1.0.0'}):
        with pytest.raises(ModelError):
            run(native, options, **change)
    with pytest.raises(ExportError) as failure:
        run(native, options, output_format='csv' if fmt == 'ndjson' else 'ndjson')
    assert failure.value.exit_code == 2


@pytest.mark.parametrize('wrong', ['hash', 'key', 'missing'])
def test_export_csv_profile_must_be_actually_bound(wrong):
    native, options = inputs('csv')
    if wrong == 'hash':
        options['expected_csv_profile_sha256'] = '0' * 64
    elif wrong == 'key':
        options['csv_profile_key'] = 'missing:csv@1.0.0'
    else:
        options.pop('csv_profile_key')
    with pytest.raises(ModelError):
        run(native, options)


@pytest.mark.parametrize(('fmt', 'change'), [
    ('ndjson', {'reqif_limits': LIMITS}), ('csv', {'reqif_limits': LIMITS}),
    ('ndjson', {'max_archive_bytes': 1}), ('csv', {'max_archive_bytes': 1}),
    ('reqif', {'max_archive_bytes': 1}), ('reqifz', {'max_archive_bytes': True}),
    ('reqifz', {'max_archive_bytes': 0}), ('reqif', {'reqif_limits': {}}),
    ('ndjson', {'csv_profile_key': 'export:csv@1.0.0'}),
    ('ndjson', {'include_attachments': 1}), ('csv', {'fail_on_loss': 'false'}),
])
def test_export_rejects_invalid_or_inapplicable_options(fmt, change):
    native, options = inputs(fmt)
    with pytest.raises(ExportError) as failure:
        run(native, options, **change)
    assert failure.value.exit_code == 2


@pytest.mark.parametrize('fmt', ['reqif', 'reqifz'])
def test_export_actual_xml_limit_cannot_be_bypassed(fmt):
    native, options = inputs(fmt)
    with pytest.raises(ModelError):
        run(native, options, reqif_limits=replace(LIMITS, max_depth=1))


def test_export_reqifz_actual_byte_limit_cannot_be_bypassed():
    native, options = inputs('reqifz')
    with pytest.raises(ModelError):
        run(native, options, max_archive_bytes=1)


def test_export_conflicting_loss_details_are_a_conflict_and_do_not_overwrite():
    losses = ExportLosses()
    losses.add('record', '/extensions/a~1b', 'native_loss', {'source': 'a'})
    before = losses.rows
    losses.add('record', '/extensions/a~1b', 'native_loss', {'source': 'a'})
    with pytest.raises(ModelError) as failure:
        losses.add('record', '/extensions/a~1b', 'native_loss', {'source': 'b'})
    assert failure.value.exit_code == 6
    assert losses.rows == before


def test_export_loss_identity_order_and_detached_details():
    rows = [('é', '/x~0', 'some_loss'), ('a', '', 'whole_loss'), ('a', '/x~1', 'field_loss')]
    first, second = ExportLosses(), ExportLosses()
    detail = {'nested': {'value': 'owned'}}
    for row in rows:
        first.add(*row, detail)
    for row in reversed(rows):
        second.add(*row, detail)
    detail['nested']['value'] = 'changed'
    assert first.rows == second.rows
    assert [(r['resource_id'], r['pointer'], r['reason']) for r in first.rows] == sorted(rows)
    detached = first.rows
    detached[0]['format_details']['nested']['value'] = 'changed'
    assert first.rows != detached


@pytest.mark.parametrize('bad', ['', 'not/a/pointer', '/bad~2escape'])
def test_export_loss_rejects_invalid_identities(bad):
    with pytest.raises(ModelError):
        ExportLosses().add('' if bad == '' else 'record', bad, 'field_loss')


@pytest.mark.parametrize('fmt', ['ndjson', 'csv', 'reqif', 'reqifz'])
def test_export_partial_weak_boundary_uses_native_target_but_not_its_payload(fmt):
    native, options = inputs(fmt)
    requirement = dict(native.artifacts[0])
    outside = domain_value('requirement', id=ref('REQ', '1'), owner='outside', updated_at='2035-01-01T00:00:00Z')
    requirement['owner'] = 'selected'
    requirement['relations'] = [relation('duplicates', outside['id'])]
    native, options = inputs(fmt, values=[outside, requirement])
    scope = descriptor('query', {'query': query(filters={'owner': ['selected']})}, boundary_policy='partial')
    result = run(native, options, scope)
    assert result.manifest['included_ids'] == [requirement['id']]
    assert result.manifest['snapshot_at'] == '2026-10-01T00:00:00.1234567890123456789Z'
    assert len(result.manifest['boundary_references']) == 1
    assert all(r['resource_id'] != outside['id'] for r in result.manifest['losses'])


@pytest.mark.parametrize('fmt', ['ndjson', 'csv', 'reqif', 'reqifz'])
def test_export_native_source_mutation_cannot_be_hidden_by_old_model_hash(fmt):
    native, options = inputs(fmt)
    # Tampering with an owned model's source invalidates its original digest;
    # a cached composed profile or model root must not authorize it.
    documents = list(native.documents)
    documents[0] = ModelDocument(documents[0].path, documents[0].content + b' ')
    object.__setattr__(native, 'documents', tuple(documents))
    with pytest.raises(ModelError):
        run(native, options, fail_on_loss=False)


@pytest.mark.parametrize('bound', ['project', 'profile'])
def test_export_reqif_hard_depth_is_not_raised_by_caller(bound):
    from support.model import configuration_value
    from support.profiles import profile_data
    config = configuration_value()
    profile = profile_data(profile_id='core')
    if bound == 'project':
        config['resource_limits'] = {'xml_depth': 1}
    else:
        profile['hard_limits'] = {'xml_depth': 1}
    native, options = inputs('reqif', config=config, profiles=[profile])
    with pytest.raises(ModelError):
        run(native, options)


@pytest.mark.parametrize('bound', ['project', 'profile'])
def test_export_reqifz_hard_size_is_not_raised_by_caller(bound):
    from support.model import configuration_value
    from support.profiles import profile_data
    config = configuration_value()
    profile = profile_data(profile_id='core')
    if bound == 'project':
        config['resource_limits'] = {'archive_uncompressed_bytes': 1}
    else:
        profile['hard_limits'] = {'archive_uncompressed_bytes': 1}
    native, options = inputs('reqifz', config=config, profiles=[profile])
    with pytest.raises(ModelError):
        run(native, options)


@pytest.mark.parametrize('fmt', ['ndjson', 'csv', 'reqif', 'reqifz'])
def test_export_host_identity_is_not_export_metadata(fmt):
    from specroad.model.model_manifest import ProjectReadBinding
    from support.read_only import no_write_attempts
    first, options = inputs(fmt, binding=ProjectReadBinding('sample', '/private/one', (1, 2)))
    second, _ = inputs(fmt, binding=ProjectReadBinding('sample', '/private/two', (3, 4)))
    with no_write_attempts():
        result = run(first, options)
        assert result == run(second, options)
    assert b'/private/' not in result.manifest_bytes and b'/private/' not in result.output_bytes


@pytest.mark.parametrize('fmt', ['ndjson', 'csv', 'reqif', 'reqifz'])
@pytest.mark.parametrize('policy', ['closed', 'partial'])
def test_export_configuration_excluded_strong_dependency_stays_an_error(fmt, policy):
    from test_configuration_scope import configuration, condition
    selected = configuration()
    first = domain_value('requirement', applicability=condition('linux'),
                         relations=[relation('depends_on', ref('REQ', '1'))])
    excluded = domain_value('requirement', id=ref('REQ', '1'), applicability=condition('windows'))
    native, options = inputs(fmt, values=[selected, first, excluded])
    scope = descriptor('query', {'query': query(filters={'type': ['requirement']})},
                       configuration_id=selected['id'], boundary_policy=policy)
    with pytest.raises(ModelError):
        run(native, options, scope, fail_on_loss=False)


@pytest.mark.parametrize('fmt', ['ndjson', 'csv', 'reqif', 'reqifz'])
def test_export_missing_mapping_resource_dependency_is_not_a_loss(fmt):
    value = domain_value('requirement', external_identities=[{'source_system': 'supplier',
        'source_document': 'document', 'external_id': 'record', 'external_revision': None,
        'mapping_id': 'absent:mapping@1.0.0'}])
    native, options = inputs(fmt, values=[value])
    with pytest.raises(ModelError):
        run(native, options, fail_on_loss=False)
