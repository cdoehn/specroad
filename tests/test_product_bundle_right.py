"""15.a.R: frozen independent ZIP bytes and strict manifest error boundaries."""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import base64
import json
import stat
import struct
from unittest.mock import patch
from zipfile import ZipFile

import pytest

from specroad import __version__
from specroad.bundles import BundleError, decode_bundle, encode_bundle
from support.bundles import bundle_inputs
from support.read_only import inventory, no_write_attempts
from support.relations import aid
from test_product_bundle import independent, NAME
from test_work_archive import foreign_zip
from test_reqifz_right import offsets

CORPUS = json.loads((Path(__file__).parent/'fixtures/product_bundle_container_v1.json').read_text())


def refuse(raw, exit_code, code, *, pre_read=False):
    with no_write_attempts(), pytest.raises(BundleError) as caught:
        if pre_read:
            with patch.object(ZipFile, 'read', side_effect=AssertionError('premature payload read')):
                decode_bundle(raw)
        else:
            decode_bundle(raw)
    assert (caught.value.exit_code, caught.value.code) == (exit_code, code)


@pytest.mark.parametrize('case', CORPUS['cases'], ids=[c['id'] for c in CORPUS['cases']])
def test_versioned_foreign_zip_vectors_fail_without_materializing_files(case, tmp_path):
    raw = base64.b64decode(case['zip_base64'], validate=True)
    assert sha256(raw).hexdigest() == case['sha256']
    before = inventory(tmp_path)
    refuse(raw, case['exit_code'], case['code'], pre_read=case['pre_payload_read'])
    assert inventory(tmp_path) == before


def test_frozen_foreign_positive_preserves_bytes_without_issuing_project_authority():
    vector = CORPUS['positive']; raw = base64.b64decode(vector['zip_base64'], validate=True)
    files = {n: base64.b64decode(b, validate=True) for n, b in vector['payloads_base64'].items()}
    with no_write_attempts():
        value = decode_bundle(raw, expected_sha256=vector['sha256'])
        assert value.files == files
        assert {k: v for k, v in value.manifest.items() if k != 'entries'} == vector['metadata']
        assert value.validation_scope == 'container_manifest_and_payload_only'
        assert not value.project_verified and not value.write_authorized
        current = {**vector['metadata'], 'tool_version': __version__}
        assert encode_bundle(current, files) == independent(current, files)


@pytest.mark.parametrize('kind,change', [
    ('project', 'read-only'), ('project', 'partial-policy'), ('project', 'configuration'),
    ('project', 'document-scope'), ('document', 'writable'), ('release', 'writable'),
    ('document', 'closed-policy'), ('release', 'closed-policy'),
    ('document', 'portable'), ('release', 'portable'), ('document', 'project-kind'),
    ('release', 'project-kind'), ('document', 'kind-alias'), ('release', 'kind-alias'),
])
def test_type_matrix_does_not_infer_or_repair_scope_authority(kind, change):
    metadata, files = bundle_inputs(kind)
    if change == 'read-only': metadata['read_only'] = True
    elif change == 'writable': metadata['read_only'] = False
    elif change == 'partial-policy': metadata['scope_descriptor']['boundary_policy'] = 'partial'
    elif change == 'closed-policy': metadata['scope_descriptor']['boundary_policy'] = 'closed'
    elif change == 'configuration': metadata['scope_descriptor']['configuration_id'] = aid('configuration')
    elif change == 'document-scope': metadata['scope_descriptor'] = bundle_inputs('document')[0]['scope_descriptor']
    elif change == 'portable': metadata['idempotency_scope'] = 'portable'
    elif change == 'project-kind': metadata['bundle_kind'] = 'project'
    else: metadata['bundle_kind'] = kind
    with no_write_attempts():
        for call in (lambda: encode_bundle(metadata, files), lambda: decode_bundle(independent(metadata, files))):
            with pytest.raises(BundleError) as caught: call()
            assert (caught.value.exit_code, caught.value.code) == (3, 'SRV002')


@pytest.mark.parametrize('field', ['scope_version', 'scope_kind', 'selector', 'configuration_id',
                                  'closure_profile', 'boundary_policy'])
def test_descriptor_bindings_cannot_be_omitted(field):
    metadata, files = bundle_inputs('document'); del metadata['scope_descriptor'][field]
    with no_write_attempts(), pytest.raises(BundleError) as caught: encode_bundle(metadata, files)
    assert (caught.value.exit_code, caught.value.code) == (3, 'SRV002')
    refuse(independent(metadata, files), 3, 'SRV002')


@pytest.mark.parametrize('field', ['source_id', 'relation_id', 'relation_type', 'target_id',
                                  'target_type', 'reason', 'origin_target_sha256'])
def test_boundary_bindings_cannot_be_omitted(field):
    metadata, files = bundle_inputs('document'); del metadata['boundary_references'][0][field]
    with no_write_attempts(), pytest.raises(BundleError) as caught: encode_bundle(metadata, files)
    assert caught.value.code == 'SRV002' and caught.value.exit_code == 3
    refuse(independent(metadata, files), 3, 'SRV002')


@pytest.mark.parametrize('change', ['extra', 'duplicate', 'order', 'strong', 'hash', 'target-type'])
def test_boundaries_keep_native_closed_ordered_weak_edge_contract(change):
    metadata, files = bundle_inputs('document'); row = metadata['boundary_references'][0]
    if change == 'extra': row['approved'] = True
    elif change == 'duplicate': metadata['boundary_references'].append(deepcopy(row))
    elif change == 'order':
        other = {**row, 'target_id': aid(number=3)}
        metadata['boundary_references'] = [other, row]
    elif change == 'strong': row['relation_type'] = 'depends_on'
    elif change == 'hash': row['origin_target_sha256'] = 'F'*64
    else: row['target_type'] = 'document'
    with no_write_attempts(), pytest.raises(BundleError) as caught: encode_bundle(metadata, files)
    assert caught.value.code == 'SRV002' and caught.value.exit_code == 3
    refuse(independent(metadata, files), 3, 'SRV002')


@pytest.mark.parametrize('field,value', [('path', None), ('path', 2), ('path', []), ('path', {}),
    ('size', True), ('size', -1), ('size', 0.5), ('size', '2'), ('size', 9007199254740993),
    ('media_type', False), ('media_type', None), ('sha256', True), ('sha256', 'F'*64)])
def test_entry_types_are_format_errors_not_path_or_integrity_guesses(field, value):
    metadata, files = bundle_inputs()
    def change(manifest): manifest['entries'][0][field] = value
    if field == 'size' and value == 9007199254740993:
        # Literal input with precision loss, not encoded by the product JCS helper.
        raw_manifest = json.dumps({**metadata, 'entries': [{'path': 'missing', 'size': value,
            'media_type': 'application/octet-stream', 'sha256': '0'*64}]}).encode()
        raw = independent(metadata, files, manifest_raw=raw_manifest)
    else: raw = independent(metadata, files, manifest_change=change)
    refuse(raw, 3, 'SRV002')


@pytest.mark.parametrize('change', ['duplicate', 'order', 'payload-overlap', 'missing-path', 'missing-reason',
    'extra', 'nonstring', 'unknown-reason', 'manifest'])
def test_exclusions_are_complete_unique_ordered_declarations(change):
    metadata, files = bundle_inputs()
    rows = [{'path': 'archive/a', 'reason': 'unreferenced_archive_object'},
            {'path': 'archive/z', 'reason': 'unreferenced_archive_object'}]
    metadata['excluded_contents'] = rows
    if change == 'duplicate': rows.append(deepcopy(rows[0]))
    elif change == 'order': rows.reverse()
    elif change == 'payload-overlap': rows[1]['path'] = 'specroad.json'
    elif change == 'missing-path': del rows[0]['path']
    elif change == 'missing-reason': del rows[0]['reason']
    elif change == 'extra': rows[0]['unknown'] = False
    elif change == 'nonstring': rows[0]['path'] = []
    elif change == 'unknown-reason': rows[0]['reason'] = 'not-found'
    else: rows[1]['path'] = NAME
    with no_write_attempts(), pytest.raises(BundleError) as caught: encode_bundle(metadata, files)
    assert (caught.value.exit_code, caught.value.code) == (3, 'SRV002')
    refuse(independent(metadata, files), 3, 'SRV002')


@pytest.mark.parametrize('paths', [['../escape'], ['Archive/a', 'archive/b'], ['x', 'x/y'], ['SPECROAD.json']])
def test_even_excluded_paths_cannot_alias_portable_payload_targets(paths):
    metadata, files = bundle_inputs()
    metadata['excluded_contents'] = [{'path': p, 'reason': 'unreferenced_archive_object'} for p in paths]
    metadata['excluded_contents'].sort(key=lambda r: r['path'].encode())
    with no_write_attempts(), pytest.raises(BundleError) as caught: encode_bundle(metadata, files)
    assert (caught.value.exit_code, caught.value.code) == (7, 'SRV083')
    refuse(independent(metadata, files), 7, 'SRV083')


def test_declared_exclusion_never_heals_missing_configuration():
    metadata, files = bundle_inputs('document'); del files['specroad.json']
    metadata['excluded_contents'].append({'path': 'specroad.json', 'reason': 'outside_scope'})
    metadata['excluded_contents'].sort(key=lambda r: r['path'].encode())
    with no_write_attempts(), pytest.raises(BundleError) as caught: encode_bundle(metadata, files)
    assert (caught.value.exit_code, caught.value.code) == (3, 'SRV060')
    refuse(independent(metadata, files), 3, 'SRV060')


@pytest.mark.parametrize('raw', [b'null', b'true', b'[]', b'{"entries":[],"entries":[]}',
    b'{"scope_descriptor":{"scope_kind":"project","scope_kind":"document"}}',
    b'{"entries":Infinity}', b'{"entries":-Infinity}', b'{"entries":NaN}',
    b'{"tool_version":"\\ud800"}'])
def test_duplicate_keys_non_objects_and_unrepresentable_values_are_rejected(raw):
    metadata, files = bundle_inputs()
    refuse(independent(metadata, files, manifest_raw=raw), 3, 'SRV002')


@pytest.mark.parametrize('expected', ['', 'F'*64, '0'*63, True, 1, [], {}])
def test_external_hash_requires_exact_typed_binding(expected):
    raw = base64.b64decode(CORPUS['positive']['zip_base64'])
    with no_write_attempts(), pytest.raises(BundleError) as caught:
        decode_bundle(raw, expected_sha256=expected)
    assert (caught.value.exit_code, caught.value.code) == (3, 'SRV002')


@pytest.mark.parametrize('name', ['a'*65536, 'ä'*32768], ids=['ascii-overflow', 'utf8-overflow'])
def test_writer_reports_unrepresentable_zip_name_without_struct_error(name):
    metadata, files = bundle_inputs(); files[name] = b'x'
    with no_write_attempts(), pytest.raises(BundleError) as caught: encode_bundle(metadata, files)
    assert (caught.value.exit_code, caught.value.code) == (3, 'SRV060')


def test_exact_zip_name_field_boundary_counts_utf8_bytes():
    metadata, files = bundle_inputs(); name = 'ä'*32767 + 'a'; files[name] = b'x'
    with no_write_attempts():
        raw = encode_bundle(metadata, files)
        assert decode_bundle(raw).files[name] == b'x'
        assert raw == independent(metadata, files)


@pytest.mark.parametrize('error_type', [OSError, PermissionError])
def test_writer_real_host_failure_stays_separate_from_invalid_data(error_type):
    metadata, files = bundle_inputs()
    with patch.object(ZipFile, 'writestr', side_effect=error_type('owned failure')), pytest.raises(BundleError) as caught:
        encode_bundle(metadata, files)
    assert caught.value.exit_code == 5 and caught.value.code is None


def test_shared_reqifz_guard_also_checks_later_special_members_before_format_failures():
    from test_reqifz import independent as reqifz, read
    from support.reqif_objects import one
    from specroad.exchange import ReqIFError
    raw = reqifz({'document.reqif': one(), 'z.bin': b'unused'})
    _, central, _ = offsets(raw); broken = bytearray(raw)
    struct.pack_into('<H', broken, central['document.reqif']+12, 1)
    struct.pack_into('<I', broken, central['z.bin']+38, (stat.S_IFLNK|0o777)<<16)
    with no_write_attempts(), patch.object(ZipFile, 'read', side_effect=AssertionError('read')):
        with pytest.raises(ReqIFError) as caught: read(bytes(broken))
    assert caught.value.exit_code == 7


def test_non_security_legacy_archive_error_order_remains_compatible():
    from specroad.work._archive import decode_archive, ArchiveError
    raw = foreign_zip([('a', b'x'), (NAME, b'{}'), ('z', b'y')]); _, central, _ = offsets(raw)
    broken = bytearray(raw)
    struct.pack_into('<H', broken, central['a']+12, 1)
    struct.pack_into('<I', broken, central['z']+38, (stat.S_IFLNK|0o777)<<16)
    # The legacy path retains its format-before-later-type diagnostic order.
    with no_write_attempts(), patch.object(ZipFile, 'read', side_effect=AssertionError('read')), pytest.raises(ArchiveError) as caught:
        decode_archive(bytes(broken), manifest_name=NAME, expected_sha256=sha256(broken).hexdigest())
    assert caught.value.exit_code == 3 and caught.value.reason == 'noncanonical_archive_entry'
