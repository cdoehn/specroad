"""15.i.W: actual external files, separate package kinds and recovery gates.

Build metadata is an explicit compatibility fixture. Checkpoints, canonical
archives, native file publication and interrupted transactions are real.
"""
from hashlib import sha256
import os

import pytest

from specroad.bundles import BundleError, decode_bundle, prepare_project_bundle
from specroad.bundles.publication import create_project_bundle
from specroad.changes._lock_files import LockFiles
from specroad.changes.lock_values import ProjectLockError
from specroad.changes.staging_values import StagingError
from specroad.model.errors import ModelError
from specroad.security import SafetyViolation
from specroad.storage.archive import ArchiveError
from specroad.work import package_publication as publication
from specroad.work.checkpoints import CheckpointStorageError
from specroad.work.finalization import finalize_read_only_work
from specroad.work.packages import export_work_package
from specroad.work.resume import WorkResumeError, resume_read_only_work
from support.read_only import inventory, no_write_attempts
from support.work_publication_process import child
from test_project_bundle import project
from test_work_packages import restore, unpack
from test_work_publication_right import restore as restore_native
from test_work_resume import recorded, setup


def destination(tmp_path):
    root = tmp_path / 'external'; root.mkdir()
    return root


def save(store, root, path='saved/work.zip'):
    return publication.publish_work_package(store, output_root=root, output=path)


@pytest.mark.parametrize('generation', [0, 1, 2])
def test_written_work_file_restores_exact_checkpoint_and_handler_result(recorded, tmp_path, generation):
    _, roots, location, store = setup(tmp_path)
    outcome = resume_read_only_work(store).outcome_bytes if generation else None
    if generation == 2:
        finalize_read_only_work(store)
    current = store.read(); expected = export_work_package(store)
    source = inventory(location.path); protected = inventory(roots[0].root)
    output = destination(tmp_path)
    result = save(store, output)
    raw = (output / result['file']['path']).read_bytes()
    assert raw == expected
    assert result == {'format_version': 'work-package-export-v1', 'package_kind': 'work',
        **{key: current.as_dict()[key] for key in ('work_id', 'checkpoint_generation', 'checkpoint_sha256')},
        'file': {'root': str(output), 'path': 'saved/work.zip', 'size': len(raw), 'sha256': sha256(raw).hexdigest()},
        'generated': True, 'normative': False, 'source_bytes_rechecked': True, 'external_backup_confirmed': False}
    assert unpack(raw)[0]['package_kind'] == 'work'
    assert all(not p.stat().st_mode & 0o077 for p in output.rglob('*'))
    assert inventory(location.path) == source and inventory(roots[0].root) == protected
    restored = restore(raw, roots, tmp_path / 'restored')
    assert restored.read().raw == current.raw
    assert dict(restored.read().objects) == dict(current.objects)
    replay = resume_read_only_work(restored)
    assert replay.executed is (generation == 0)
    if outcome is not None:
        assert replay.outcome_bytes == outcome
    assert inventory(location.path) == source and inventory(roots[0].root) == protected


def test_completed_project_backup_and_work_package_remain_distinct(recorded, tmp_path):
    root = tmp_path / 'normal'; project(root)
    _, _, _, store = setup(tmp_path)
    output = destination(tmp_path); before = inventory(root)
    result = create_project_bundle(root, output='project.zip', output_root=str(output))
    assert result.exit_code == 0, result.as_dict()
    raw = (output / 'project.zip').read_bytes()
    assert raw == prepare_project_bundle(root).source_bytes
    assert decode_bundle(raw).manifest['bundle_kind'] == 'project'
    save(store, output)
    with no_write_attempts(), pytest.raises(BundleError):
        decode_bundle((output / 'saved/work.zip').read_bytes())
    assert inventory(root) == before


@pytest.mark.parametrize('cut', ['prepared', 'first_target', 'committed'])
def test_actual_unresolved_transaction_is_not_a_project_backup_or_work_export(recorded, tmp_path, cut):
    packet, stopped = child(tmp_path, cut)
    assert stopped['cut'] == cut and stopped['pid'] != os.getpid()
    _, _, store = restore_native(tmp_path, packet)
    output = destination(tmp_path); before = inventory(tmp_path)
    with no_write_attempts():
        result = create_project_bundle(tmp_path / 'project', output='project.zip', output_root=str(output))
        assert result.exit_code == 5
        with pytest.raises(ArchiveError) as caught:
            save(store, output)
    assert caught.value.reason == 'normative_work_package_requires_native_binding'
    assert caught.value.exit_code == 6
    assert inventory(tmp_path) == before and not list(output.iterdir())


@pytest.mark.parametrize('kind', ['file', 'directory', 'symlink', 'fifo', 'case'])
def test_existing_output_is_preserved_without_any_write_attempt(recorded, tmp_path, kind):
    _, _, _, store = setup(tmp_path); output = destination(tmp_path)
    target = output / ('WORK.ZIP' if kind == 'case' else 'work.zip')
    if kind == 'directory': target.mkdir()
    elif kind == 'symlink': target.symlink_to(tmp_path / 'absent')
    elif kind == 'fifo': os.mkfifo(target)
    else: target.write_bytes(b'owned existing bytes')
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises((ArchiveError, SafetyViolation)):
        save(store, output, 'work.zip')
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('kind', ['work', 'work_child', 'project', 'ancestor', 'foreign_project',
                                  'symlink_root', 'symlink_parent', 'nested_project', 'missing_root'])
def test_unsafe_or_overlapping_destinations_do_not_mutate_any_root(recorded, tmp_path, kind):
    _, roots, location, store = setup(tmp_path); output = destination(tmp_path); path = 'work.zip'
    if kind == 'work': output = location.path
    elif kind == 'work_child': output = location.path / 'objects'
    elif kind == 'project': output = roots[0].root
    elif kind == 'ancestor': output = tmp_path
    elif kind == 'foreign_project': (output / 'specroad.json').write_bytes(b'foreign project')
    elif kind == 'symlink_root':
        alias = tmp_path / 'alias'; alias.symlink_to(output, target_is_directory=True); output = alias
    elif kind == 'symlink_parent':
        (output / 'nested').symlink_to(location.path, target_is_directory=True); path = 'nested/work.zip'
    elif kind == 'nested_project':
        (output / 'nested').mkdir(); (output / 'nested/specroad.json').write_bytes(b'foreign'); path = 'nested/work.zip'
    else: output = tmp_path / 'missing'
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises((SafetyViolation, ProjectLockError, OSError)):
        save(store, output, path)
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('path', ['../escape.zip', '/absolute.zip', '.specroad/work.zip', 'specroad.json'])
def test_invalid_relative_output_is_write_free(recorded, tmp_path, path):
    _, _, _, store = setup(tmp_path); output = destination(tmp_path); before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises((ModelError, SafetyViolation)):
        save(store, output, path)
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('change', ['pointer', 'object', 'image', 'target'])
def test_changes_at_publication_preserve_actual_state_and_never_overwrite(recorded, tmp_path, monkeypatch, change):
    _, roots, location, store = setup(tmp_path); output = destination(tmp_path)
    protected = inventory(roots[0].root); original = publication._write_new
    def changed(parent, name, raw):
        identity = original(parent, name, raw)
        if change == 'pointer': (location.path / 'work.json').write_bytes(b'changed pointer')
        elif change == 'object':
            next((location.path / 'objects').iterdir()).write_bytes(b'changed object')
        elif change == 'image':
            fd = os.open(name, os.O_WRONLY | os.O_TRUNC, dir_fd=parent)
            try: os.write(fd, b'changed pending image')
            finally: os.close(fd)
        else: (output / 'work.zip').write_bytes(b'raced owned target')
        return identity
    monkeypatch.setattr(publication, '_write_new', changed)
    with pytest.raises((ArchiveError, CheckpointStorageError, StagingError, WorkResumeError)) as caught:
        save(store, output, 'work.zip')
    if change == 'pointer':
        assert caught.value.as_dict() == {'reason': 'checkpoint_pointer_changed', 'exit_code': 6}
        assert (location.path / 'work.json').read_bytes() == b'changed pointer'
    assert inventory(roots[0].root) == protected
    assert list(output.glob('.specroad-work-export-*.tmp'))
    if change == 'target': assert (output / 'work.zip').read_bytes() == b'raced owned target'
    else: assert not (output / 'work.zip').exists()


def test_output_mutex_contention_is_write_free(recorded, tmp_path):
    _, _, _, store = setup(tmp_path); output = destination(tmp_path); before = inventory(tmp_path)
    with LockFiles(output) as held:
        held.acquire()
        with no_write_attempts(), pytest.raises(ProjectLockError) as caught:
            save(store, output)
    assert caught.value.reason == 'project_lock_busy'
    assert inventory(tmp_path) == before


def test_failure_after_publication_preserves_the_complete_file(recorded, tmp_path, monkeypatch):
    _, _, _, store = setup(tmp_path); output = destination(tmp_path)
    expected = export_work_package(store); original = publication.replace_bound_image
    def fail_after(*args, **kwargs):
        original(*args, **kwargs)
        raise OSError('injected post-publication IO failure')
    monkeypatch.setattr(publication, 'replace_bound_image', fail_after)
    with pytest.raises(OSError): save(store, output, 'work.zip')
    assert (output / 'work.zip').read_bytes() == expected
    assert not list(output.glob('.specroad-work-export-*.tmp'))
