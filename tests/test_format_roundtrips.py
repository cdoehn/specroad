"""14.o.W: actual per-format roundtrips, bound resources and review contexts."""
from hashlib import sha256
import json

import pytest

from specroad.exchange import (ExportError, ReqIFAttachment, decode_reqif_structure,
                              decode_reqifz, prepare_export)
from specroad.graph.scope_descriptors import ScopeDescriptor
from specroad.mappings import select_mapping
from specroad.validation import ModelDocument
from support.exchange_oracles import assert_attachment_transport, assert_records_equal, assert_review_status
from support.format_roundtrips import (FORMATS, LANGUAGES, REQIF_FIELDS, corpus,
                                      decode_native_records, export_model)
from support.read_only import no_write_attempts
from support.reqif_objects import LIMITS
from support.targets import SCOPE, model


@pytest.mark.parametrize('fmt', ['ndjson', 'csv'])
@pytest.mark.parametrize('language', LANGUAGES)
@pytest.mark.parametrize('nullable', [False, True])
def test_native_intersection_preserves_full_corpus_and_current_review(fmt, language, nullable):
    records, attachments, files = corpus(language, nullable=nullable)
    expected = {v['id']: v for v in records}
    restored = {}
    # A CSV stream declares exactly one type; no concatenation is passed off
    # as a single CSV file, and no missing field is filled from the original.
    kinds = sorted({v['artifact_type'] for v in records}) if fmt == 'csv' else ['all']
    for kind in kinds:
        native, mapping, profile, options = export_model(records, attachments, files, fmt, kind=kind)
        original = native.source_files
        with no_write_attempts():
            exported = prepare_export(native, ScopeDescriptor(SCOPE), **options)
            recovered = decode_native_records(exported, mapping, profile, fmt)
            assert prepare_export(native, ScopeDescriptor(SCOPE), **options) == exported
        assert native.source_files == original
        ids = {v['id'] for v in records if fmt == 'ndjson' or v['artifact_type'] == kind}
        assert {v['id'] for v in recovered} == ids == set(exported.manifest['included_ids'])
        assert not any(row['resource_id'] in ids for row in exported.manifest['losses'])
        assert_records_equal(recovered, [expected[i] for i in ids])
        for value in recovered:
            assert value['id'] not in restored
            restored[value['id']] = value
        transported = dict(exported.attachment_files)
        assert_attachment_transport(exported, transported, attachments, files)
        assert any(row['reason'] == 'native_resource_not_in_exchange_format' for row in exported.manifest['losses'])
    assert restored == expected
    # Rebuild only from decoded artifacts and actual transported attachment
    # bytes. Project config/profile remain explicit fixture inputs, not export.
    rebuilt = model(list(restored.values()), attachments=attachments,
                    resource_files=[ModelDocument(path, raw) for path, raw in transported.items()])
    before = model(records, attachments=attachments, resource_files=files)
    assert rebuilt.manifest(rebuilt.artifacts, SCOPE).sha256 == before.manifest(before.artifacts, SCOPE).sha256
    assert_review_status(restored.values(), records[0]['id'], records[0]['relations'][0]['relation_id'],
                         'current', selected_review_id=records[-1]['id'])
    assert restored[records[6]['id']]['selection'] == {'platform': 'linux'}
    assert ('parent' in restored[records[6]['id']]) is nullable


@pytest.mark.parametrize('fmt', ['reqif', 'reqifz'])
@pytest.mark.parametrize('language', LANGUAGES)
def test_reqif_intersection_keeps_values_relations_occurrences_and_attachment_bytes(fmt, language):
    records, attachments, files = corpus(language)
    native, mapping, _, options = export_model(records, attachments, files, fmt)
    original = native.source_files
    with no_write_attempts():
        exported = prepare_export(native, ScopeDescriptor(SCOPE), **options)
        xml = exported.output_bytes
        transported = dict(exported.attachment_files)
        if fmt == 'reqifz':
            container = decode_reqifz(xml, expected_sha256=sha256(xml).hexdigest(), document_paths=('exchange.reqif',),
                limits=LIMITS, max_uncompressed_bytes=20 * 1024 * 1024)
            members = dict(container.files)
            xml = members.pop('exchange.reqif')
            transported = members
            assert exported.attachment_files == ()
        decoded = decode_reqif_structure(xml, limits=LIMITS)
        supplied = tuple(ReqIFAttachment(a.path, a, transported[a.path]) for a in attachments)
        selected = select_mapping([mapping], key=mapping.key, expected_sha256=mapping.sha256)
        recovered = {}
        for item in (*decoded.objects, *decoded.specifications):
            projection = decoded.project_record(item.identifier, xhtml=True, attachments=supplied)
            assert projection['representable'] and projection['unrepresentable'] == []
            value = selected.artifact(projection['external_type'], projection['fields'])['artifact']
            recovered[value['id']] = (item.identifier, value)
        assert prepare_export(native, ScopeDescriptor(SCOPE), **options) == exported
    assert native.source_files == original
    expected = [v for v in records if v['artifact_type'] in REQIF_FIELDS]
    assert set(recovered) == {v['id'] for v in expected} == set(exported.manifest['included_ids'])
    assert_records_equal([fields for _, fields in recovered.values()], [
        {'artifact_type': value['artifact_type'],
         **{f: value[f] for f in REQIF_FIELDS[value['artifact_type']]}} for value in expected])
    for value in expected:
        assert recovered[value['id']][0] == value['external_identities'][0]['external_id']
    assert [(h.identifier, h.object_id, h.owner_id, h.children) for h in decoded.hierarchies] == [
        ('section-use', 'record-3', 'record-2', ('first-block', 'second-block')),
        ('first-block', 'record-5', 'section-use', ()),
        ('second-block', 'record-4', 'section-use', ())]
    assert [(r.identifier, r.type_id, r.source, r.target) for r in decoded.relations] == [
        ('addresses-goal', 'addresses', 'record-0', 'record-1')]
    assert_attachment_transport(exported, transported, attachments, files)
    # This declared ReqIF intersection has no native review/config/evidence
    # representation: the whole records must be explicit losses, not current
    # reviews reconstructed from source-only data or asserted by a manifest.
    for value in records:
        if value['artifact_type'] not in REQIF_FIELDS:
            loss = {'resource_id': value['id'], 'pointer': '', 'reason': 'reqif_artifact_type_unmapped'}
            assert loss in exported.manifest['excluded_contents']
            assert {**loss, 'format_details': {}} in exported.manifest['losses']
    assert all(row['reason'] not in ('reqif_hierarchy_binding_missing', 'reqif_relation_binding_missing')
               for row in exported.manifest['losses'])


@pytest.mark.parametrize('fmt', FORMATS)
def test_roundtrip_corpus_cannot_hide_native_resource_or_format_losses(fmt):
    records, attachments, files = corpus()
    native, _, _, options = export_model(records, attachments, files, fmt)
    before = native.source_files
    with no_write_attempts(), pytest.raises(ExportError) as failure:
        prepare_export(native, ScopeDescriptor(SCOPE), fail_on_loss=True, **options)
    assert failure.value.reason == 'export_information_loss' and failure.value.exit_code == 3
    manifest = json.loads(failure.value.manifest)
    assert manifest['losses'] and manifest['options']['fail_on_loss'] is True
    assert native.source_files == before
