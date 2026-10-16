"""Late archive changes and hostile/failed native restoration boundaries."""
from base64 import b64decode
import os
import shutil

import pytest

from specroad.archive import show_baseline_snapshot
from specroad.authoring._bootstrap_io import BootstrapError
from specroad.changes import _staging_files
from specroad.changes._lock_files import LockFiles
from specroad.model.canonical import canonical_json_bytes
from specroad.model.errors import ModelError
from specroad.security import ProjectBoundary, SafetyViolation
from support.model import put
from support.read_only import inventory, no_write_attempts
from support.records import ref
from test_baseline_materialization import restore, show
from test_baseline_verification import stored_snapshot, row_for


@pytest.mark.parametrize('role', ['artifact', 'profile', 'rule', 'mapping', 'attachment',
                                  'semantic_configuration', 'effective_profile', 'model_manifest'])
def test_late_missing_archive_bytes_cannot_be_replaced_by_current_project_files(tmp_path, monkeypatch, role):
    root = tmp_path / 'archive'; record, _ = stored_snapshot(root)
    row = row_for(record, role); source = root / row['object_path']
    if 'source_path' in row: put(root, row['source_path'], source.read_bytes())
    original = _staging_files._write_new; changed = False
    def remove_after_write(parent, name, raw):
        nonlocal changed
        result = original(parent, name, raw)
        if not changed:
            changed = True; source.unlink()
        return result
    monkeypatch.setattr(_staging_files, '_write_new', remove_after_write)
    target = tmp_path / 'restored'
    with pytest.raises(ModelError) as error: restore(root, record, target)
    assert error.value.reason == 'snapshot_referenced_object_missing'
    assert error.value.path == row['object_path']
    assert target.is_dir() and not (target / 'specroad.json').exists()
    if 'source_path' in row: assert (root / row['source_path']).is_file()


@pytest.mark.parametrize('change', ['missing', 'corrupt'])
def test_archive_is_rechecked_after_output_configuration_and_root_readback(tmp_path, monkeypatch, change):
    root = tmp_path / 'archive'; record, _ = stored_snapshot(root)
    source = root / row_for(record, 'attachment')['object_path']
    original = _staging_files._write_new
    def alter_after_configuration(parent, name, raw):
        result = original(parent, name, raw)
        if name == 'specroad.json':
            if change == 'missing': source.unlink()
            else: source.write_bytes(b'corrupted original')
        return result
    monkeypatch.setattr(_staging_files, '_write_new', alter_after_configuration)
    target = tmp_path / 'restored'
    with pytest.raises(ModelError) as error: restore(root, record, target)
    assert error.value.reason in ('snapshot_referenced_object_missing', 'snapshot_object_size_mismatch')
    assert (target / 'specroad.json').exists()
    assert (target / 'attachments/manual.bin').read_bytes() == b'\x00\xff\r\n'


@pytest.mark.parametrize('change', ['removed', 'replaced'])
def test_lost_output_directory_never_becomes_a_write_in_the_process_cwd(tmp_path, monkeypatch, change):
    root = tmp_path / 'archive'; record, _ = stored_snapshot(root)
    target = tmp_path / 'restored'; host = tmp_path / 'host'; host.mkdir()
    monkeypatch.chdir(host)
    original = _staging_files._write_new; changed = False
    def change_empty_directory(parent, name, raw):
        nonlocal changed
        result = original(parent, name, raw)
        if not changed:
            changed = True
            path = target / 'mappings'; fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
            try:
                path.rmdir()
                if change == 'replaced': path.mkdir(mode=0o700)
            finally: os.close(fd)
        return result
    monkeypatch.setattr(_staging_files, '_write_new', change_empty_directory)
    with pytest.raises(SafetyViolation): restore(root, record, target)
    assert list(host.iterdir()) == []
    assert not (target / 'mappings/exchange.json').exists()
    assert not (target / 'specroad.json').exists()


def test_identical_bytes_cannot_hide_replacement_of_a_created_file(tmp_path, monkeypatch):
    root = tmp_path / 'archive'; record, _ = stored_snapshot(root)
    original = _staging_files._write_new; changed = False
    def replace_file(parent, name, raw):
        nonlocal changed
        result = original(parent, name, raw)
        if not changed:
            changed = True; old = os.open(name, os.O_RDONLY, dir_fd=parent)
            try:
                os.unlink(name, dir_fd=parent)
                new = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=parent)
                try: os.write(new, raw)
                finally: os.close(new)
            finally: os.close(old)
        return result
    monkeypatch.setattr(_staging_files, '_write_new', replace_file)
    target = tmp_path / 'restored'
    with pytest.raises(SafetyViolation): restore(root, record, target)
    assert (target / 'attachments/manual.bin').read_bytes() == b'\x00\xff\r\n'
    assert not (target / 'specroad.json').exists()


def test_foreign_entries_in_a_just_created_root_prevent_all_payload_writes(tmp_path, monkeypatch):
    root = tmp_path / 'archive'; record, _ = stored_snapshot(root)
    target = tmp_path / 'restored'; original = LockFiles.__enter__
    def enter(held):
        result = original(held)
        if held.boundary.root == target: (target / 'foreign').write_bytes(b'keep')
        return result
    monkeypatch.setattr(LockFiles, '__enter__', enter)
    with pytest.raises(BootstrapError): restore(root, record, target)
    assert [p.name for p in target.iterdir()] == ['foreign']
    assert (target / 'foreign').read_bytes() == b'keep'


def test_concurrent_empty_directory_is_not_reused_as_owned_output(tmp_path, monkeypatch):
    root = tmp_path / 'archive'; record, _ = stored_snapshot(root)
    original = os.mkdir; changed = False
    def mkdir(path, mode=0o777, *, dir_fd=None):
        nonlocal changed
        if path == 'attachments' and dir_fd is not None and not changed:
            changed = True; original(path, 0o700, dir_fd=dir_fd)
        return original(path, mode, dir_fd=dir_fd)
    monkeypatch.setattr(os, 'mkdir', mkdir)
    target = tmp_path / 'restored'
    with pytest.raises(FileExistsError): restore(root, record, target)
    assert (target / 'attachments').is_dir() and list((target / 'attachments').iterdir()) == []
    assert not (target / 'specroad.json').exists()


@pytest.mark.parametrize('destination', [None, 42, b'/tmp/unused'])
def test_nonpath_destination_has_a_machine_readable_failure_before_writes(tmp_path, destination):
    root = tmp_path / 'archive'; record, _ = stored_snapshot(root)
    with no_write_attempts(), pytest.raises(ModelError) as error:
        restore(root, record, destination)
    assert error.value.reason == 'baseline_materialization_destination_required'


@pytest.mark.parametrize('kind', ['symlink', 'hardlink'])
def test_show_preserves_security_failures_instead_of_showing_verified_integrity(tmp_path, kind):
    root = tmp_path / 'archive'; record, _ = stored_snapshot(root)
    path = root / row_for(record, 'attachment')['object_path']
    outside = tmp_path / 'outside'; outside.write_bytes(path.read_bytes()); path.unlink()
    if kind == 'symlink': path.symlink_to(outside)
    else: os.link(outside, path)
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(SafetyViolation): show(root, record)
    assert inventory(tmp_path) == before


def test_symlinked_external_parent_cannot_redirect_materialization(tmp_path):
    root = tmp_path / 'archive'; record, _ = stored_snapshot(root)
    real = tmp_path / 'real'; real.mkdir(mode=0o700)
    alias = tmp_path / 'alias'; alias.symlink_to(real, target_is_directory=True)
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(SafetyViolation):
        restore(root, record, alias / 'restored')
    assert inventory(tmp_path) == before


def test_host_read_failure_is_not_converted_to_a_successful_show_result(tmp_path, monkeypatch):
    root = tmp_path / 'archive'; record, _ = stored_snapshot(root)
    leaf = row_for(record, 'attachment')['sha256']; original = os.open
    def open_file(path, flags, *args, **kwargs):
        if path == leaf: raise PermissionError('injected archive denial')
        return original(path, flags, *args, **kwargs)
    monkeypatch.setattr(os, 'open', open_file)
    with no_write_attempts(), pytest.raises(PermissionError): show(root, record)


def test_shared_snapshot_object_becomes_independent_exact_output_files(tmp_path):
    from support.relations import artifact, edge, aid

    raw = canonical_json_bytes(artifact(relations=[edge('depends_on', aid(number=2))]))
    root = tmp_path / 'archive'; record, _ = stored_snapshot(root, attachment=raw)
    target = tmp_path / 'restored'; restore(root, record, target)
    attachment = target / 'attachments/manual.bin'
    artifact_path = target / next(r['source_path'] for r in record['manifest']
        if r['role'] == 'artifact' and r['sha256'] == row_for(record, 'attachment')['sha256'])
    assert attachment.read_bytes() == artifact_path.read_bytes() == raw
    assert attachment.stat().st_ino != artifact_path.stat().st_ino
    assert attachment.stat().st_nlink == artifact_path.stat().st_nlink == 1


def test_explicit_operational_choices_preserve_the_same_historical_model_hash(tmp_path):
    root = tmp_path / 'archive'; record, _ = stored_snapshot(root)
    one = tmp_path / 'one'; two = tmp_path / 'two'
    a = restore(root, record, one, default_locale='de-DE', generated_path='generated')
    b = restore(root, record, two, default_locale='en-GB', generated_path='output')
    assert (one / 'specroad.json').read_bytes() != (two / 'specroad.json').read_bytes()
    assert a['model_root_sha256'] == b['model_root_sha256'] == record['model_root_sha256']
    assert a['configuration_hash'] == b['configuration_hash'] == record['configuration_hash']


def test_older_baseline_registry_and_archive_bytes_survive_without_original_project(tmp_path):
    from test_baseline_creation import project, plan_for, ACTOR, TIME
    from test_baseline_verification_right import document
    from specroad.changes.baselines import object_documents, prepare_baseline_operation
    from specroad.changes._target_materialization import materialize_target
    from specroad.archive import verify_baseline_snapshot

    original = tmp_path / 'original'; model = project(original)
    first = plan_for(model).data['operations'][0]
    prior = materialize_target(model, (document(first['record']), *object_documents(first)))
    second = prepare_baseline_operation(prior, baseline_id=ref('BASE', '1'), name='With history', actor=ACTOR, planned_at=TIME)
    root = tmp_path / 'archive'; root.mkdir()
    for item in second['objects']: put(root, item['path'], b64decode(item['bytes_base64']))
    shutil.rmtree(original)
    target = tmp_path / 'restored'; result = restore(root, second['record'], target)
    for path, raw in prior.source_files.items():
        if path != 'specroad.json': assert (target / path).read_bytes() == raw
    assert result['model_root_sha256'] == second['record']['model_root_sha256']
    with no_write_attempts():
        assert verify_baseline_snapshot(ProjectBoundary(target), canonical_json_bytes(first['record']))['snapshot_integrity_verified']
    assert not original.exists() and not (target / '.git').exists()


def test_final_storage_failure_retains_written_configuration_without_success(tmp_path, monkeypatch):
    root = tmp_path / 'archive'; record, _ = stored_snapshot(root)
    target = tmp_path / 'restored'; original = os.fsync
    def fsync(fd):
        if (target / 'specroad.json').exists(): raise OSError('injected final durability failure')
        return original(fd)
    monkeypatch.setattr(os, 'fsync', fsync)
    with pytest.raises(OSError): restore(root, record, target)
    assert (target / 'specroad.json').exists()
    assert (target / 'attachments/manual.bin').read_bytes() == b'\x00\xff\r\n'
