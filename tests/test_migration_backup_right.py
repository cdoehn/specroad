"""Independent malformed inputs, complete closure, freshness and actual I/O failures."""
import errno
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile, ZipInfo, ZIP_STORED
import pytest

from specroad.bundles import BundleError
from specroad.migration import backup as api
from specroad.security import SafetyViolation
from specroad.changes.lock_values import ProjectLockError
from specroad.documents.exports import ViewExportError
from support.reference01 import minimal, full_project, encoded
from support.migration_backups import file_hash, write_project, disk_files


def repack(backup, *, mutate_manifest=None, mutate_files=None, rebuild_entries=False):
    with ZipFile(BytesIO(backup.source_bytes)) as archive:
        files = {p: archive.read(p) for p in archive.namelist()}
    manifest = json.loads(files.pop('migration-source-manifest.json'))
    if mutate_files: mutate_files(files)
    if rebuild_entries:
        manifest['entries'] = [{'path': p, 'size': len(b),
            'media_type': 'application/json' if p.endswith('.json') else 'application/octet-stream',
            'sha256': sha256(b).hexdigest()} for p, b in sorted(files.items(), key=lambda x: x[0].encode())]
        manifest['source_files_sha256'] = file_hash({p[7:]: b for p, b in files.items() if p.startswith('source/')})
    if mutate_manifest: mutate_manifest(manifest)
    files['migration-source-manifest.json'] = encoded(manifest)
    output = BytesIO()
    with ZipFile(output, 'w') as archive:
        for p, raw in sorted(files.items(), key=lambda x: x[0].encode()):
            entry = ZipInfo(p, date_time=(1980,1,1,0,0,0)); entry.create_system = 3
            entry.create_version = entry.extract_version = 20
            entry.external_attr = 0o100644 << 16; entry.compress_type = ZIP_STORED
            archive.writestr(entry, raw)
    return output.getvalue(), manifest['source_files_sha256']


def verify(raw, source_hash):
    return api.verify_source_backup(raw, expected_sha256=sha256(raw).hexdigest(),
                                    expected_source_files_sha256=source_hash)


@pytest.mark.parametrize('field,value', [
    ('backup_format_version','unknown'), ('bundle_kind','project'), ('read_only',1),
    ('read_only',False), ('project_id','foreign-project'), ('source_contract',{}),
    ('scope_descriptor',{}), ('source_model_root_sha256','0'*64),
    ('source_files_sha256','0'*64), ('tool_version',''), ('unknown',True)])
def test_closed_manifest_and_source_domains_cannot_be_relabelled(field, value):
    backup = api.prepare_source_backup(minimal())
    raw, _ = repack(backup, mutate_manifest=lambda m: m.update({field:value}))
    with pytest.raises(BundleError): verify(raw, backup.manifest['source_files_sha256'])


@pytest.mark.parametrize('change', ['missing', 'extra', 'altered', 'inventory', 'manifestless', 'trailing'])
def test_transport_corruption_is_rejected_even_with_its_recomputed_zip_hash(change):
    backup = api.prepare_source_backup(minimal())
    def tamper(files):
        if change == 'missing': files.pop('source/specroad.json')
        if change == 'extra': files['source/hidden'] = b'new'
        if change == 'altered': files['source/specroad.json'] += b'\n'
    raw, h = repack(backup, mutate_files=tamper,
        mutate_manifest=(lambda m: m['entries'].clear()) if change == 'inventory' else None)
    if change == 'manifestless': raw = b'not a ZIP'
    if change == 'trailing': raw += b'trailing'
    with pytest.raises(BundleError): verify(raw, h)


def test_self_consistent_omission_of_nonmodel_original_requires_external_full_file_binding():
    files = minimal(); files['extra-original'] = b'not in semantic root'
    backup = api.prepare_source_backup(files)
    raw, replacement = repack(backup, mutate_files=lambda f: f.pop('source/extra-original'), rebuild_entries=True)
    assert replacement != file_hash(files)
    with pytest.raises(BundleError, match='migration_backup_source_changed'):
        verify(raw, file_hash(files))


@pytest.mark.parametrize('change', ['missing_archive', 'corrupt_archive', 'missing_profile', 'missing_primary'])
def test_self_consistent_container_cannot_conceal_incomplete_native_source_closure(change):
    files = full_project(); backup = api.prepare_source_backup(files)
    if change.endswith('archive'): path = next(p for p in files if p.startswith('archive/objects/'))
    elif change == 'missing_profile': path = 'profiles/core-reference01.json'
    else: path = next(p for p,b in files.items() if p.startswith('spec/documents/') and
                      json.loads(b).get('document_role') == 'primary_specification')
    def tamper(f):
        if change == 'corrupt_archive': f['source/'+path] += b'corrupt'
        else: f.pop('source/'+path)
    raw, current = repack(backup, mutate_files=tamper, rebuild_entries=True)
    with pytest.raises(BundleError): verify(raw, current)


@pytest.mark.parametrize('name', ['../escape', '/absolute', 'source/../escape',
                                 'source/.aws/key', 'source/nested/.codex/token',
                                 'source/../specroad.json'])
def test_unsafe_or_protected_payload_names_are_never_admitted(name):
    backup = api.prepare_source_backup(minimal())
    raw, h = repack(backup, mutate_files=lambda f: f.update({name:b'unsafe'}), rebuild_entries=True)
    with pytest.raises(BundleError): verify(raw, h)


@pytest.mark.parametrize('name', ['.specroad/locks/project.json', '.specroad/transactions/active/journal.json',
                                 '.specroad/recovery/pending', '.specroad/unknown/value', '.specroad/tmp/a'])
def test_active_or_unknown_operational_source_is_not_a_successful_full_backup(name):
    files = minimal(); files[name] = b'unknown'
    with pytest.raises(BundleError, match='migration_backup_operational_state'):
        api.prepare_source_backup(files)


@pytest.mark.parametrize('which', ['zip', 'source'])
def test_both_external_bindings_are_required_and_exact(which):
    files = minimal(); backup = api.prepare_source_backup(files)
    values = {'expected_sha256':backup.sha256, 'expected_source_files_sha256':file_hash(files)}
    values['expected_sha256' if which == 'zip' else 'expected_source_files_sha256'] = '0'*64
    with pytest.raises(BundleError): api.verify_source_backup(backup.source_bytes, **values)
    values['expected_sha256' if which == 'zip' else 'expected_source_files_sha256'] = None
    with pytest.raises(BundleError): api.verify_source_backup(backup.source_bytes, **values)


def setup_project(tmp_path):
    files = minimal(); root = write_project(tmp_path/'project', files)
    out = tmp_path/'backups'; out.mkdir()
    options = {'output_root':str(out), 'output':'source.zip', 'expected_source_files_sha256':file_hash(files)}
    return files, root, out, options


def test_existing_backup_is_reopened_against_actual_source_without_trusting_a_report(tmp_path):
    files, root, out, options = setup_project(tmp_path)
    report = api.create_source_backup(root, **options)
    assert api.verify_source_backup_file(root, expected_sha256=report['file']['sha256'], **options) == report
    (root/'new-original').write_bytes(b'after original backup')
    with pytest.raises(BundleError, match='migration_backup_source_changed'):
        api.verify_source_backup_file(root, expected_sha256=report['file']['sha256'], **options)
    assert (root/'specroad.json').read_bytes() == files['specroad.json']


def test_corrupted_published_backup_cannot_be_promoted_by_an_old_success_report(tmp_path):
    files, root, out, options = setup_project(tmp_path)
    report = api.create_source_backup(root, **options)
    (out/'source.zip').write_bytes(b'corrupt')
    with pytest.raises(BundleError, match='migration_backup_hash_mismatch'):
        api.verify_source_backup_file(root, expected_sha256=report['file']['sha256'], **options)
    assert disk_files(root) == files


def test_missing_backup_bytes_is_an_io_failure_without_schema_mutation(tmp_path):
    files, root, out, options = setup_project(tmp_path)
    with pytest.raises(BundleError) as failure:
        api.verify_source_backup_file(root, expected_sha256='0'*64, **options)
    assert failure.value.exit_code == 5 and disk_files(root) == files


def test_real_no_space_error_does_not_publish_or_modify_source(tmp_path, monkeypatch):
    import specroad.bundles.publication as publication
    files, root, out, options = setup_project(tmp_path)
    def no_space(*args, **kwargs): raise OSError(errno.ENOSPC, 'synthetic no space')
    monkeypatch.setattr(publication, '_write_new', no_space)
    with pytest.raises(BundleError) as failure: api.create_source_backup(root, **options)
    assert failure.value.exit_code == 5 and failure.value.reason == 'migration_backup_host_io'
    assert not (out/'source.zip').exists() and disk_files(root) == files


@pytest.mark.parametrize('change', ['bytes', 'addition', 'deletion', 'operational'])
def test_source_changes_at_publication_boundary_prevent_success(tmp_path, monkeypatch, change):
    files, root, out, options = setup_project(tmp_path); original = api._publish
    def altered(*args, **kwargs):
        if change == 'bytes': (root/'specroad.json').write_bytes(files['specroad.json']+b'\n')
        elif change == 'addition': (root/'unreported').write_bytes(b'added')
        elif change == 'deletion': (root/'profiles/core-reference01.json').unlink()
        else:
            (root/'.specroad/locks').mkdir(parents=True); (root/'.specroad/locks/project.json').write_bytes(b'active')
        return original(*args, **kwargs)
    monkeypatch.setattr(api, '_publish', altered)
    with pytest.raises(BundleError): api.create_source_backup(root, **options)
    assert not (out/'source.zip').exists()
    assert json.loads((root/'specroad.json').read_bytes())['schema_version'] == '0.1.0'


def test_publication_readback_is_reverified_instead_of_believing_generated_object(tmp_path, monkeypatch):
    files, root, out, options = setup_project(tmp_path); original = api._publish
    def damaged(*args, **kwargs):
        result = original(*args, **kwargs); (out/'source.zip').write_bytes(b'corrupted after publication')
        return result
    monkeypatch.setattr(api, '_publish', damaged)
    with pytest.raises(BundleError, match='migration_backup_hash_mismatch'):
        api.create_source_backup(root, **options)
    assert disk_files(root) == files


@pytest.mark.parametrize('destination', ['within', 'ancestor', 'other_project', 'symlink'])
def test_output_cannot_overlap_a_project_or_follow_an_alias(tmp_path, destination):
    files, root, out, options = setup_project(tmp_path)
    if destination == 'within': out = root/'generated'; out.mkdir()
    elif destination == 'ancestor': out = tmp_path
    elif destination == 'other_project': (out/'specroad.json').write_bytes(files['specroad.json'])
    else:
        alias = tmp_path/'alias'; alias.symlink_to(out, target_is_directory=True); out = alias
    options['output_root'] = str(out)
    with pytest.raises((ViewExportError, BundleError)): api.create_source_backup(root, **options)
    assert not (out/'source.zip').exists()
    assert (root/'specroad.json').read_bytes() == files['specroad.json']


@pytest.mark.parametrize('kind', ['symlink', 'fifo', 'nested_project', 'collision'])
def test_unsafe_source_entries_fail_before_publication(tmp_path, kind):
    import os
    files, root, out, options = setup_project(tmp_path)
    if kind == 'symlink': (root/'alias').symlink_to(root/'specroad.json')
    elif kind == 'fifo': os.mkfifo(root/'pipe')
    elif kind == 'nested_project':
        (root/'nested').mkdir(); (root/'nested/specroad.json').write_bytes(files['specroad.json'])
    else:
        (root/'Case').write_bytes(b'A'); (root/'case').write_bytes(b'B')
    with pytest.raises((BundleError, SafetyViolation, ProjectLockError)):
        api.create_source_backup(root, **options)
    assert not (out/'source.zip').exists()


def test_prepared_object_cannot_bypass_verification_of_published_bytes(tmp_path, monkeypatch):
    from types import SimpleNamespace
    files, root, out, options = setup_project(tmp_path)
    files['extra-original'] = b'must remain'; (root/'extra-original').write_bytes(files['extra-original'])
    options['expected_source_files_sha256'] = file_hash(files)
    real = api.prepare_source_backup(files)
    raw, _ = repack(real, mutate_files=lambda f: f.pop('source/extra-original'), rebuild_entries=True)
    forged = SimpleNamespace(source_bytes=raw, sha256=sha256(raw).hexdigest(), manifest=real.manifest)
    monkeypatch.setattr(api, 'prepare_source_backup', lambda ignored: forged)
    with pytest.raises(BundleError, match='migration_backup_source_changed'):
        api.create_source_backup(root, **options)
    assert disk_files(root) == files


def test_reopen_rechecks_target_bytes_after_source_observation(tmp_path, monkeypatch):
    from specroad.security.paths import ProjectBoundary
    files, root, out, options = setup_project(tmp_path)
    report = api.create_source_backup(root, **options)
    original = ProjectBoundary.read_bytes; reads = []
    def changing(self, path):
        raw = original(self, path)
        if self.root == out and path == 'source.zip':
            reads.append(path)
            if len(reads) == 1: (out/path).write_bytes(b'replaced during verification')
        return raw
    monkeypatch.setattr(ProjectBoundary, 'read_bytes', changing)
    with pytest.raises(BundleError, match='migration_backup_published_changed'):
        api.verify_source_backup_file(root, expected_sha256=report['file']['sha256'], **options)
    assert disk_files(root) == files


def test_existing_backup_verification_preserves_source_and_backup_on_io_failure(tmp_path, monkeypatch):
    from specroad.security.paths import ProjectBoundary
    files, root, out, options = setup_project(tmp_path)
    report = api.create_source_backup(root, **options); original = ProjectBoundary.read_bytes
    raw = (out/'source.zip').read_bytes()
    def denied(self, path):
        if self.root == out: raise PermissionError(errno.EACCES, 'synthetic denied')
        return original(self, path)
    monkeypatch.setattr(ProjectBoundary, 'read_bytes', denied)
    with pytest.raises(BundleError) as failure:
        api.verify_source_backup_file(root, expected_sha256=report['file']['sha256'], **options)
    assert failure.value.exit_code == 5
    assert disk_files(root) == files and (out/'source.zip').read_bytes() == raw
