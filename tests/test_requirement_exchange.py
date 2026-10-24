"""S.7 content preservation through actual scoped format bytes and live export."""
from dataclasses import asdict
from hashlib import sha256
import json

import pytest

from specroad.exchange import (decode_ndjson, decode_reqif_structure, decode_reqifz,
                               prepare_export, requirement_csv_profile, requirement_mapping,
                               select_csv_profile)
from specroad.graph.scope_descriptors import ScopeDescriptor
from specroad.mappings import ExchangeMapping, select_mapping
from specroad.model.canonical import canonical_json_bytes
from specroad.validation import ModelDocument
from support.domain import domain_value
from support.reqif_objects import LIMITS
from support.scopes import descriptor
from support.targets import model


def resources(fmt):
    mapping = requirement_mapping('reqif' if fmt == 'reqifz' else fmt)
    files = [ModelDocument('mappings/requirements.json', mapping.source_bytes)]
    options = {'output_format': fmt, 'mapping_key': mapping.key, 'expected_mapping_sha256': mapping.sha256}
    if fmt == 'csv':
        profile = requirement_csv_profile()
        files.append(ModelDocument('mappings/requirements-csv.json', profile.source_bytes))
        options.update(csv_profile_key=profile.key, expected_csv_profile_sha256=profile.sha256)
    if fmt in ('reqif', 'reqifz'):
        options['reqif_limits'] = LIMITS
    if fmt == 'reqifz':
        options['max_archive_bytes'] = 16 * 1024 * 1024
    return mapping, files, options


def requirement(language, force):
    text = {'de-DE': 'Bei Ausfall bleibt der vollständige Inhalt erhalten, einschließlich "a < b & c".\r\n'
                     'Ausnahme: Ein ausdrücklich gelöschter Eintrag bleibt gelöscht. Café / Cafe\u0301.',
            'en-IN': 'When offline, the system sends telemetry to an external service.\n'
                     'Except for an explicitly selected local target, "shall" is plain quoted text.'}[language]
    return domain_value('requirement', language=language, normative_force=force, statement=text,
                        **({'deviation_conditions': 'Explicit maintenance window.',
                            'deviation_authority': 'Project review board.'} if force == 'should' else {}))


def read_content(raw, fmt, mapping):
    if fmt == 'ndjson':
        return decode_ndjson(raw).objects[0]['object']
    if fmt == 'csv':
        profile = requirement_csv_profile()
        codec = select_csv_profile([mapping, profile], key=profile.key, expected_sha256=profile.sha256)
        row = codec.decode(raw).records[0]
        assert set(row['fields']) == {'language', 'normative_force', 'statement'}
        return select_mapping([mapping], key=mapping.key, expected_sha256=mapping.sha256).artifact(
            row['external_type'], row['fields'])['artifact']
    if fmt == 'reqifz':
        container = decode_reqifz(raw, expected_sha256=sha256(raw).hexdigest(), document_paths=('exchange.reqif',),
                                 limits=LIMITS, max_uncompressed_bytes=16 * 1024 * 1024)
        raw = dict(container.files)['exchange.reqif']
    document = decode_reqif_structure(raw, limits=LIMITS)
    assert not document.unsupported
    definitions = {d.identifier: d for typ in document.types for d in typ.definitions}
    assert definitions['specroad.language'].family == 'STRING'
    assert definitions['specroad.statement'].family == 'STRING'
    assert definitions['specroad.normative_force'].family == 'ENUMERATION'
    assert definitions['specroad.normative_force'].element.attrs['MULTI-VALUED'] == 'false'
    enum = next(d for d in document.datatypes if d.family == 'ENUMERATION')
    assert set(enum.enum_ids) == {'must', 'must_not', 'should', 'may'}
    return document.map_object(document.objects[0].identifier, mappings=[mapping], key=mapping.key,
        expected_mapping_sha256=mapping.sha256, expected_source_sha256=document.source_sha256,
        source_system='explicit-recipient', source_document='received-requirements')['artifact']


@pytest.mark.parametrize('fmt', ['csv', 'ndjson', 'reqif', 'reqifz'])
@pytest.mark.parametrize('language', ['de-DE', 'en-IN'])
@pytest.mark.parametrize('force', ['must', 'must_not', 'should', 'may'])
def test_requirement_exchange_preserves_explicit_content(fmt, language, force):
    value = requirement(language, force)
    mapping, files, options = resources(fmt)
    native = model([value], resource_files=files)
    before = canonical_json_bytes(value)
    exported = prepare_export(native, ScopeDescriptor(descriptor('project')), **options)
    restored = read_content(exported.output_bytes, fmt, mapping)
    for field in ('language', 'normative_force', 'statement'):
        assert restored[field].encode('utf-8') == value[field].encode('utf-8')
    if fmt == 'ndjson':
        assert restored == value
    assert exported.manifest['included_ids'] == [value['id']]
    assert exported.manifest['mapping'] == mapping.binding()
    assert exported.manifest['output_sha256'] == sha256(exported.output_bytes).hexdigest()
    losses = [loss for loss in exported.manifest['losses'] if loss['resource_id'] == value['id']]
    assert not any(loss['pointer'] in ('/language', '/normative_force', '/statement') for loss in losses)
    if fmt != 'ndjson':
        assert any(loss['pointer'] == '/priority' for loss in losses)
        if force == 'should':
            assert any(loss['pointer'] == '/deviation_conditions' for loss in losses)
    assert canonical_json_bytes(value) == before
    assert prepare_export(native, ScopeDescriptor(descriptor('project')), **options) == exported


@pytest.mark.parametrize('fmt', ['csv', 'ndjson', 'reqif', 'reqifz'])
def test_requirement_core_mapping_is_usable_through_live_export(tmp_path, fmt):
    from specroad.cli.application import dispatch_result
    from support.inspection import inspection_project
    from support.model import put
    from support.read_only import inventory
    root = tmp_path / 'project'
    value = requirement('de-DE', 'must_not')
    inspection_project(root, artifacts=[value])
    mapping, files, _ = resources(fmt)
    for file in files:
        put(root, file.path, file.content)
    before = inventory(root)
    arguments = ['export', fmt, '--project', str(root), '--scope', 'project',
                 '--mapping', mapping.key, '--mapping-sha256', mapping.sha256,
                 '--output', 'generated/requirements.' + fmt]
    if fmt == 'csv':
        profile = requirement_csv_profile()
        arguments += ['--csv-profile', profile.key, '--csv-profile-sha256', profile.sha256]
    if fmt in ('reqif', 'reqifz'):
        limits = tmp_path / 'limits.json'
        limits.write_text(json.dumps(asdict(LIMITS)))
        arguments += ['--xml-limits', str(limits)]
    if fmt == 'reqifz':
        arguments += ['--max-archive-bytes', str(16 * 1024 * 1024)]
    result = dispatch_result(arguments)
    assert result.exit_code == 0, result.as_dict()
    actual = read_content((root / ('generated/requirements.' + fmt)).read_bytes(), fmt, mapping)
    assert tuple(actual[k] for k in ('language', 'normative_force', 'statement')) == (
        value['language'], value['normative_force'], value['statement'])
    assert tuple(row for row in inventory(root) if not row[0].startswith('generated')) == before


def test_requirement_core_definitions_are_not_selected_by_name_alone():
    mapping, _, options = resources('reqif')
    changed = mapping.data
    changed['fields'][0]['external_field'] = 'external.language'
    changed = ExchangeMapping(canonical_json_bytes(changed))
    options['expected_mapping_sha256'] = changed.sha256
    exported = prepare_export(model([requirement('de-DE', 'must')], resource_files=[
        ModelDocument('mappings/requirements.json', changed.source_bytes)]),
        ScopeDescriptor(descriptor('project')), **options)
    assert exported.manifest['included_ids'] == []
    assert any(loss['reason'] == 'reqif_type_binding_missing' for loss in exported.manifest['losses'])
    assert not decode_reqif_structure(exported.output_bytes, limits=LIMITS).objects


def test_requirement_core_projection_does_not_claim_full_native_preservation():
    from specroad.exchange import ExportError
    _, files, options = resources('reqif')
    with pytest.raises(ExportError) as failure:
        prepare_export(model([requirement('en-IN', 'should')], resource_files=files),
                       ScopeDescriptor(descriptor('project')), fail_on_loss=True, **options)
    assert failure.value.reason == 'export_information_loss'
    assert failure.value.exit_code == 3
    manifest = json.loads(failure.value.manifest)
    assert any(loss['pointer'] == '/deviation_authority' for loss in manifest['losses'])
