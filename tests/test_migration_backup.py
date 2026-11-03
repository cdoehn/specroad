"""Complete source bytes, native closure and durable external backup publication."""
from dataclasses import FrozenInstanceError
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_STORED
import pytest

from specroad.bundles import BundleError, decode_bundle
from specroad.migration.backup import (prepare_source_backup, verify_source_backup,
                                       create_source_backup)
from support.reference01 import minimal, full_project, release_project, seal
from support.migration_backups import file_hash, write_project, disk_files


def test_complete_original_inventory_survives_without_any_model_filter():
    files = full_project(); seal(files, 3)
    files.update({'generated/unreferenced.bin': b'\x00\xff\n', 'notes/Grüße.txt': b'opaque\r\n',
                  'empty.txt': b'', 'archive/objects/unreferenced': b'original unused object',
                  'bundle-manifest.json': b'old transport metadata\n',
                  'migration-source-manifest.json': b'old backup metadata\n',
                  '.specroad/requests/history.json': b'opaque historical receipt, not authority'})
    files['specroad.json'] += b'\n\t'
    before = dict(files)
    backup = prepare_source_backup(files)
    assert backup.files == before == files
    with ZipFile(BytesIO(backup.source_bytes)) as zipped:
        assert set(zipped.namelist()) == {'migration-source-manifest.json', *('source/' + p for p in files)}
        manifest = json.loads(zipped.read('migration-source-manifest.json'))
        rows = [{'path': 'source/' + p, 'size': len(raw),
                 'media_type': 'application/json' if p.endswith('.json') else 'application/octet-stream',
                 'sha256': sha256(raw).hexdigest()} for p, raw in sorted(files.items(), key=lambda r: r[0].encode())]
        assert manifest['entries'] == rows
        assert manifest['source_files_sha256'] == file_hash(files)
        assert manifest['source_contract'] == {'contract_id': 'specroad-reference-0.1',
            'contract_version': '1.0.1', 'schema_version': '0.1.0',
            'contract_sha256': '7c4af8bb230fed758267a9a45c4957b26e015e0f112c8ad5d0f42b9b93fee72e'}
        assert manifest['bundle_kind'] == 'migration_source' and manifest['read_only'] is True
        restored = {p[7:]: zipped.read(p) for p in zipped.namelist() if p.startswith('source/')}
        assert restored == files
        assert json.loads(restored['specroad.json'])['schema_version'] == '0.1.0'
    verified = verify_source_backup(backup.source_bytes, expected_sha256=backup.sha256,
                                    expected_source_files_sha256=file_hash(files))
    assert verified.files == before and verified.write_authorized is False


def test_canonical_zip_profile_and_reordered_inputs_have_identical_bytes():
    files = minimal(); files['extra/ä.txt'] = b'\x00\x81'
    one = prepare_source_backup(files)
    two = prepare_source_backup(dict(reversed(list(files.items()))))
    assert one.source_bytes == two.source_bytes
    with ZipFile(BytesIO(one.source_bytes)) as archive:
        names = archive.namelist()
        assert names == sorted(names, key=lambda p: p.encode('utf-8'))
        assert archive.comment == b''
        for entry in archive.infolist():
            assert entry.date_time == (1980, 1, 1, 0, 0, 0)
            assert entry.compress_type == ZIP_STORED
            assert entry.create_system == 3 and entry.extract_version == 20
            assert entry.extra == entry.comment == b''
            assert entry.external_attr == 0o100644 << 16 and entry.internal_attr == 0
            assert entry.flag_bits == (0 if entry.filename.isascii() else 0x800)


def test_source_model_root_is_not_a_substitute_for_full_original_byte_binding():
    files = minimal(); first = prepare_source_backup(files)
    files['specroad.json'] += b'\n'; files['generated/unused'] = b'kept'
    second = prepare_source_backup(files)
    assert first.manifest['source_model_root_sha256'] == second.manifest['source_model_root_sha256']
    assert first.manifest['source_files_sha256'] != second.manifest['source_files_sha256']
    assert first.sha256 != second.sha256


def test_historical_release_baselines_and_raw_archive_objects_are_retained():
    files = release_project(); original = dict(files)
    backup = prepare_source_backup(files)
    assert backup.files == original
    assert all(backup.files[p] == raw for p, raw in original.items() if p.startswith('archive/'))
    assert all(backup.files[p] == raw for p, raw in original.items() if p.startswith('spec/baselines/'))


def test_owned_backup_views_cannot_mutate_verified_bytes_or_grant_authority():
    files = minimal(); backup = prepare_source_backup(files); raw = backup.source_bytes
    backup.files.clear(); backup.manifest['entries'].clear(); files.clear()
    assert backup.source_bytes == raw and backup.files and backup.manifest['entries']
    with pytest.raises(FrozenInstanceError): backup.source_bytes = b'changed'
    with pytest.raises(TypeError): bool(backup)
    assert backup.write_authorized is False


def test_source_backup_is_not_accepted_as_an_ordinary_02_project_bundle():
    backup = prepare_source_backup(minimal())
    with pytest.raises(BundleError): decode_bundle(backup.source_bytes, expected_sha256=backup.sha256)


def test_publication_reconstructs_the_whole_actual_root_and_records_absolute_path(tmp_path):
    files = full_project(); files.update({'generated/unused': b'full original', 'other/tree/file': b'\x00\xff'})
    root = write_project(tmp_path/'project', files); output = tmp_path/'backup'; output.mkdir()
    report = create_source_backup(root, output_root=str(output), output='nested/source.zip',
                                  expected_source_files_sha256=file_hash(files))
    raw = (output/'nested/source.zip').read_bytes()
    assert report == {'format_version': 'migration-source-backup-report-v1',
        'file': {'path': str(output/'nested/source.zip'), 'size': len(raw), 'sha256': sha256(raw).hexdigest()},
        'source_model_root_sha256': prepare_source_backup(files).manifest['source_model_root_sha256'],
        'source_files_sha256': file_hash(files), 'backup_verified': True, 'source_bytes_rechecked': True,
        'atomic_snapshot': False, 'write_authorized': False, 'approval_granted': False}
    assert disk_files(root) == files and not (root/'.specroad').exists()
    assert verify_source_backup(raw, expected_sha256=report['file']['sha256'],
                                expected_source_files_sha256=file_hash(files)).files == files


def test_root_administrative_data_are_never_opened_or_copied(tmp_path, monkeypatch):
    from specroad.security.paths import ProjectBoundary
    files = minimal(); root = write_project(tmp_path/'project', files)
    for name in ('.git', '.codex', '.agents', '.aws', '.ssh', '.patchharbor'):
        (root/name).mkdir(); (root/name/'private.txt').write_bytes(b'private-operator-data')
    output = tmp_path/'backups'; output.mkdir(); original = ProjectBoundary.read_bytes
    def guarded(self, name):
        assert name.split('/')[0] not in ('.git', '.codex', '.agents', '.aws', '.ssh', '.patchharbor')
        return original(self, name)
    monkeypatch.setattr(ProjectBoundary, 'read_bytes', guarded)
    result = create_source_backup(root, output_root=str(output), output='source.zip',
                                  expected_source_files_sha256=file_hash(files))
    assert b'private-operator-data' not in (output/'source.zip').read_bytes()
    assert result['source_files_sha256'] == file_hash(files)


def test_passive_operational_originals_are_copied_without_interpreting_or_activating(tmp_path):
    files = minimal(); files['.specroad/transactions/receipts/old.json'] = b'original receipt\r\n'
    files['.specroad/cache/old.bin'] = b'opaque cache bytes'
    root = write_project(tmp_path/'project', files); output = tmp_path/'backups'; output.mkdir()
    report = create_source_backup(root, output_root=str(output), output='source.zip',
                                  expected_source_files_sha256=file_hash(files))
    assert disk_files(root) == files and report['write_authorized'] is False
    assert prepare_source_backup(files).files == files


def test_existing_target_is_preserved_and_source_schema_remains_unchanged(tmp_path):
    files = minimal(); root = write_project(tmp_path/'project', files)
    output = tmp_path/'backup'; output.mkdir(); (output/'existing.zip').write_bytes(b'existing')
    with pytest.raises(BundleError, match='bundle_output_exists'):
        create_source_backup(root, output_root=str(output), output='existing.zip',
                              expected_source_files_sha256=file_hash(files))
    assert (output/'existing.zip').read_bytes() == b'existing' and disk_files(root) == files


def test_full_actual_file_inventory_must_match_the_external_expected_source(tmp_path):
    files = minimal(); root = write_project(tmp_path/'project', files)
    (root/'unreported').write_bytes(b'cannot silently omit'); output = tmp_path/'backup'; output.mkdir()
    with pytest.raises(BundleError, match='migration_backup_source_changed'):
        create_source_backup(root, output_root=str(output), output='source.zip',
                              expected_source_files_sha256=file_hash(files))
    assert not list(output.iterdir()) and (root/'unreported').read_bytes() == b'cannot silently omit'
