"""15.a.W: the exact product manifest and canonical payload byte contract."""
from copy import deepcopy
from hashlib import sha256
from io import BytesIO
import json
from unittest.mock import patch
from zipfile import ZipFile, ZIP_STORED

import pytest

from specroad import __version__
from specroad.bundles import BundleError, decode_bundle, encode_bundle
from specroad.model.canonical import canonical_json_bytes
from support.bundles import bundle_inputs
from support.read_only import inventory, no_write_attempts
from test_work_archive import foreign_zip

NAME = 'bundle-manifest.json'


def independent(metadata, files, *, manifest_change=None, manifest_raw=None, **options):
    # Independent inventory oracle: no production bundle projection is called.
    manifest = {**deepcopy(metadata), 'entries': [
        {'path': name, 'size': len(raw), 'sha256': sha256(raw).hexdigest(),
         'media_type': 'application/json' if name.endswith('.json') else 'application/octet-stream'}
        for name, raw in sorted(files.items(), key=lambda pair: pair[0].encode('utf-8'))]}
    if manifest_change is not None:
        manifest_change(manifest)
    members = {**files, NAME: canonical_json_bytes(manifest) if manifest_raw is None else manifest_raw}
    return foreign_zip(sorted(members.items(), key=lambda pair: pair[0].encode('utf-8')), **options)


@pytest.mark.parametrize('kind', ['project', 'document', 'release'])
def test_exact_manifest_roundtrip_binds_native_scopes_and_actual_payloads(kind, tmp_path):
    metadata, files = bundle_inputs(kind)
    # Opaque bytes, empty payload and coarse transport MIME never rewrite native bytes.
    files.update({'attachments/ä.png': b'\x89PNG\r\n\x1a\n', 'empty': b'', 'upper.JSON': b'not JSON',
                  'archive/objects/opaque': b'\0\xffhistorical'})
    before = inventory(tmp_path)
    with no_write_attempts():
        raw = encode_bundle(metadata, files)
        assert raw == independent(metadata, files)
        assert raw == encode_bundle(dict(reversed(list(metadata.items()))), dict(reversed(list(files.items()))))
        value = decode_bundle(raw, expected_sha256=sha256(raw).hexdigest())
        assert value.source_bytes == raw and value.sha256 == sha256(raw).hexdigest()
        assert value.files == files and len(value.manifest) == 15
        assert {k: v for k, v in value.manifest.items() if k != 'entries'} == metadata
        assert value.manifest_bytes == canonical_json_bytes(value.manifest)
        assert encode_bundle(metadata, value.files) == raw
        assert value.validation_scope == 'container_manifest_and_payload_only'
        assert not value.project_verified and not value.write_authorized
    assert inventory(tmp_path) == before
    with ZipFile(BytesIO(raw)) as archive:
        assert archive.namelist() == sorted([NAME, *files], key=lambda p: p.encode('utf-8'))
        for info in archive.infolist():
            assert info.date_time == (1980, 1, 1, 0, 0, 0) and info.compress_type == ZIP_STORED
            assert info.create_system == 3 and info.create_version == info.extract_version == 20
            assert info.external_attr == 0o100644 << 16 and info.internal_attr == 0
            assert info.flag_bits == (0 if info.filename.isascii() else 0x800)
            assert not info.extra and not info.comment
        assert not archive.comment
        assert archive.read(NAME) == value.manifest_bytes
    assert NAME not in [e['path'] for e in value.manifest['entries']]
    assert not {'sha256', 'size', 'archive_sha256'} & value.manifest.keys()


def test_document_scope_keeps_actual_weak_boundary_and_separate_origin_root():
    metadata, files = bundle_inputs('document')
    value = decode_bundle(encode_bundle(metadata, files))
    assert value.manifest['origin_model_root_sha256'] != value.manifest['bundle_model_root_sha256']
    assert len(value.manifest['boundary_references']) == 1
    target = value.manifest['boundary_references'][0]['target_id']
    origin_metadata, origin_files = bundle_inputs()
    path = next(p for p in origin_files if target in p)
    assert path not in value.files
    assert value.manifest['boundary_references'][0]['origin_target_sha256'] == sha256(origin_files[path]).hexdigest()
    assert value.manifest['origin_model_root_sha256'] == origin_metadata['bundle_model_root_sha256']
    assert {'path': path, 'reason': 'outside_scope'} in value.manifest['excluded_contents']


def test_owned_input_and_output_mutation_cannot_change_verified_bytes():
    metadata, files = bundle_inputs()
    raw = encode_bundle(metadata, files); value = decode_bundle(raw)
    before = value.manifest_bytes
    metadata['scope_descriptor']['selector']['extra'] = True
    files.clear(); value.files.clear(); value.manifest['entries'].clear()
    assert value.manifest_bytes == before and value.files and value.source_bytes == raw
    with pytest.raises(AttributeError): value.source_bytes = b'changed'


def test_payload_json_whitespace_is_hashed_without_semantic_reformatting():
    metadata, files = bundle_inputs()
    first = encode_bundle(metadata, files)
    files['specroad.json'] = json.dumps(json.loads(files['specroad.json']), indent=3).encode()
    second = encode_bundle(metadata, files)
    assert first != second and decode_bundle(second).files == files
    assert decode_bundle(first).manifest['bundle_model_root_sha256'] == decode_bundle(second).manifest['bundle_model_root_sha256']


def test_receipt_transport_and_explicit_exclusion_do_not_change_model_hash():
    metadata, files = bundle_inputs()
    receipt = '.specroad/requests/owned.json'
    with_receipt = {**files, receipt: b'{"fixture":"completed-byte-payload"}'}
    portable = decode_bundle(encode_bundle(metadata, with_receipt))
    excluded = deepcopy(metadata); excluded['idempotency_scope'] = 'local_only'
    excluded['excluded_contents'] = [{'path': receipt, 'reason': 'operational_receipts_excluded'}]
    local = decode_bundle(encode_bundle(excluded, files))
    assert portable.manifest['bundle_model_root_sha256'] == local.manifest['bundle_model_root_sha256']
    assert portable.files[receipt] == with_receipt[receipt] and receipt not in local.files
    assert not portable.project_verified and not local.project_verified


@pytest.mark.parametrize('field', ['bundle_format_version', 'bundle_kind', 'read_only', 'project_id',
    'tool_version', 'schema_version', 'scope_descriptor', 'origin_model_root_sha256',
    'bundle_model_root_sha256', 'profile_sha256', 'configuration_sha256', 'boundary_references',
    'excluded_contents', 'idempotency_scope'])
def test_missing_metadata_is_not_replaced_with_a_default(field):
    metadata, files = bundle_inputs(); del metadata[field]
    with no_write_attempts():
        for call in (lambda: encode_bundle(metadata, files), lambda: decode_bundle(independent(metadata, files))):
            with pytest.raises(BundleError) as error: call()
            assert (error.value.exit_code, error.value.code) == (3, 'SRV002')


@pytest.mark.parametrize('field,value,code', [
    ('extra', True, 'SRV002'), ('bundle_format_version', '2.0.0', 'SRV003'),
    ('schema_version', '9.0.0', 'SRV003'), ('schema_version', 2, 'SRV002'),
    ('read_only', 0, 'SRV002'), ('read_only', True, 'SRV002'),
    ('bundle_kind', 'document', 'SRV002'), ('idempotency_scope', 'unknown', 'SRV002'),
    ('project_id', '', 'SRV002'), ('profile_sha256', 'a'*63, 'SRV002'),
    ('configuration_sha256', 'F'*64, 'SRV002'), ('bundle_model_root_sha256', 'a'*64, 'SRV002'),
    ('tool_version', '', 'SRV002'), ('boundary_references', {}, 'SRV002'),
    ('excluded_contents', None, 'SRV002'),
])
def test_invalid_field_types_versions_or_combinations_are_rejected(field, value, code):
    metadata, files = bundle_inputs(); metadata[field] = value
    with no_write_attempts():
        for call in (lambda: encode_bundle(metadata, files), lambda: decode_bundle(independent(metadata, files))):
            with pytest.raises(BundleError) as error: call()
            assert error.value.as_dict()['code'] == code and error.value.exit_code == 3


def test_supported_reader_accepts_other_tool_provenance_but_writer_binds_its_actual_version():
    metadata, files = bundle_inputs(); metadata['tool_version'] = 'other-build-9'
    assert metadata['tool_version'] != __version__
    with no_write_attempts():
        assert decode_bundle(independent(metadata, files)).manifest['tool_version'] == 'other-build-9'
        with pytest.raises(BundleError) as error: encode_bundle(metadata, files)
        assert error.value.code == 'SRV002'


@pytest.mark.parametrize('change', ['missing', 'extra', 'size', 'hash', 'media_type', 'self', 'order'])
def test_inventory_is_an_exact_bijection_to_actual_bytes(change):
    metadata, files = bundle_inputs()
    def alter(manifest):
        rows = manifest['entries']
        if change == 'missing': rows.pop()
        elif change == 'extra': rows.append({'path': 'extra', 'size': 0, 'media_type': 'application/octet-stream', 'sha256': sha256(b'').hexdigest()})
        elif change == 'size': rows[0]['size'] += 1
        elif change == 'hash': rows[0]['sha256'] = 'a'*64
        elif change == 'media_type': rows[0]['media_type'] = 'application/other'
        elif change == 'self': rows[0]['path'] = NAME
        else: rows.reverse()
    raw = independent(metadata, files, manifest_change=alter)
    with no_write_attempts(), pytest.raises(BundleError) as error: decode_bundle(raw)
    assert (error.value.exit_code, error.value.code) == (3, 'SRV060')


@pytest.mark.parametrize('change', ['unknown', 'missing', 'boolean_size'])
def test_inventory_entry_shape_is_closed(change):
    metadata, files = bundle_inputs()
    def alter(manifest):
        if change == 'unknown': manifest['entries'][0]['extra'] = True
        elif change == 'missing': del manifest['entries'][0]['path']
        else: manifest['entries'][0]['size'] = True
    with no_write_attempts(), pytest.raises(BundleError) as error:
        decode_bundle(independent(metadata, files, manifest_change=alter))
    assert (error.value.exit_code, error.value.code) == (3, 'SRV002')


@pytest.mark.parametrize('change', ['manifest_payload', 'config_id', 'config_schema', 'missing_config'])
def test_manifest_recursion_and_direct_native_identity_mismatch_are_rejected(change):
    metadata, files = bundle_inputs()
    if change == 'manifest_payload': files[NAME] = b'{}'
    elif change == 'missing_config': del files['specroad.json']
    else:
        data = json.loads(files['specroad.json']); data['project_id' if change == 'config_id' else 'schema_version'] = 'wrong'
        files['specroad.json'] = canonical_json_bytes(data)
    with no_write_attempts(), pytest.raises(BundleError) as error: encode_bundle(metadata, files)
    assert (error.value.exit_code, error.value.code) == (3, 'SRV060')
    if change != 'manifest_payload':
        with pytest.raises(BundleError) as error: decode_bundle(independent(metadata, files))
        assert error.value.code == 'SRV060'


@pytest.mark.parametrize('change', ['extra_field', 'reason', 'overlap', 'portable_exclusion', 'outside_project'])
def test_exclusion_declaration_cannot_hide_a_payload_or_invent_a_reason(change):
    metadata, files = bundle_inputs()
    item = {'path': 'archive/unused', 'reason': 'unreferenced_archive_object'}
    if change == 'extra_field': item['approved'] = True
    elif change == 'reason': item['reason'] = 'missing-but-okay'
    elif change == 'overlap': item['path'] = 'specroad.json'
    elif change == 'portable_exclusion': item['reason'] = 'operational_receipts_excluded'
    else: item['reason'] = 'outside_scope'
    metadata['excluded_contents'] = [item]
    with no_write_attempts():
        for call in (lambda: encode_bundle(metadata, files), lambda: decode_bundle(independent(metadata, files))):
            with pytest.raises(BundleError) as error: call()
            assert (error.value.exit_code, error.value.code) == (3, 'SRV002')


def test_optional_external_hash_distinguishes_self_consistency_from_prior_identity():
    metadata, files = bundle_inputs(); raw = encode_bundle(metadata, files)
    other = encode_bundle(metadata, {**files, 'attachments/additional': b'extra'})
    with no_write_attempts():
        assert decode_bundle(other).files != decode_bundle(raw).files
        with pytest.raises(BundleError) as error: decode_bundle(other, expected_sha256=sha256(raw).hexdigest())
        assert (error.value.exit_code, error.value.code) == (3, 'SRV060')


@pytest.mark.parametrize('files', [{'../escape': b'x'}, {'a': b'x', 'a/b': b'y'},
    {'A/b': b'x', 'a/c': b'y'}, {'A.bin': b'x', 'a.bin': b'y'}, {'.git/config': b'x'}])
def test_unsafe_paths_and_collisions_are_rejected_before_reading_payloads(files):
    metadata, base = bundle_inputs(); files = {**base, **files}; raw = independent(metadata, files)
    with no_write_attempts(), patch.object(ZipFile, 'read', side_effect=AssertionError('payload read')):
        for call in (lambda: encode_bundle(metadata, files), lambda: decode_bundle(raw)):
            with pytest.raises(BundleError) as error: call()
            assert (error.value.exit_code, error.value.code) == (7, 'SRV083')


@pytest.mark.parametrize('raw', [b'[]', b'{}\xff', b'{"entries":[],"entries":[]}', b'{"entries":NaN}'])
def test_manifest_json_is_one_strict_utf8_object(raw):
    metadata, files = bundle_inputs()
    with no_write_attempts(), pytest.raises(BundleError) as error:
        decode_bundle(independent(metadata, files, manifest_raw=raw))
    expected_code = 'SRV060' if raw == b'{}\xff' else 'SRV002'
    assert (error.value.exit_code, error.value.code) == (3, expected_code)


def test_real_host_io_failure_is_not_an_integrity_claim():
    metadata, files = bundle_inputs(); raw = encode_bundle(metadata, files)
    with patch.object(ZipFile, 'read', side_effect=OSError('owned host failure')), pytest.raises(BundleError) as error:
        decode_bundle(raw)
    assert error.value.exit_code == 5 and error.value.code is None


@pytest.mark.parametrize('mode', ['core', 'pyz'])
def test_bundle_codec_runs_without_external_dependencies_in_portable_distributions(mode, tmp_path):
    from support.portable import build_distribution
    from support.processes import run_core, run_python
    metadata, files = bundle_inputs()
    body = ('from specroad.bundles import encode_bundle, decode_bundle\n'
            'from hashlib import sha256\nmetadata=' + repr(metadata) + '\nfiles=' + repr(files) + '\n'
            'raw=encode_bundle(metadata,files)\n'
            'value=decode_bundle(raw,expected_sha256=sha256(raw).hexdigest())\n'
            'assert value.files==files and not value.project_verified and not value.write_authorized\n')
    if mode == 'core': result = run_core(body, tmp_path)
    else:
        _, app = build_distribution(tmp_path/'dist')
        result = run_python(['-I', '-S', '-B', '-c', 'import sys;sys.path.insert(0,'+repr(str(app))+');'+body], tmp_path)
    assert result.returncode == 0, result.stderr
