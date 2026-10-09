"""Changed work boundaries and orphan ownership fail without stealing storage."""

import os
import stat

import pytest

from specroad.security import ProjectBoundary, SafetyViolation
from specroad.work.root import WorkDirectory
from support.processes import run_core
from support.read_only import inventory, no_write_attempts
from test_work_manifest import create
from test_work_root import protected


def allocated(tmp_path):
    roots = protected(tmp_path)
    manifest = create()
    location = WorkDirectory(manifest, protected_roots=roots, directory=tmp_path / 'work')
    with location.for_checkpoint():
        pass
    return roots, manifest, location


@pytest.mark.parametrize('replacement', ['missing', 'empty', 'copied_binding'])
def test_allocated_location_never_silently_restarts_in_a_replaced_root(tmp_path, replacement):
    roots, _, location = allocated(tmp_path)
    original = location.path
    kept = tmp_path / 'retained'
    original.rename(kept)
    if replacement != 'missing':
        original.mkdir(mode=0o700)
    if replacement == 'copied_binding':
        (original / 'root.json').write_bytes((kept / 'root.json').read_bytes())
        (original / 'root.json').chmod(0o600)
        for name in ('checkpoints', 'objects', 'results'):
            (original / name).mkdir(mode=0o700)
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises((SafetyViolation, FileNotFoundError)):
        with location.for_checkpoint():
            pytest.fail('lost root silently restarted')
    assert inventory(tmp_path) == before and location.path == original
    assert roots[0].root.is_dir()


@pytest.mark.parametrize('area', ['checkpoints', 'objects', 'results'])
@pytest.mark.parametrize('kind', ['symlink', 'hardlink', 'fifo', 'public_file', 'public_directory'])
def test_unsafe_retained_entries_block_reacquisition_without_changing_any_bytes(tmp_path, area, kind):
    roots, _, location = allocated(tmp_path)
    parent = location.path / area
    nested = parent / 'nested'
    nested.mkdir(mode=0o700)
    target = nested / 'payload'
    if kind == 'symlink':
        target.symlink_to(roots[0].root / 'specroad.json')
    elif kind == 'hardlink':
        source = tmp_path / 'private-source'
        source.write_bytes(b'linked payload'); source.chmod(0o600)
        os.link(source, target)
    elif kind == 'fifo':
        os.mkfifo(target, 0o600)
    elif kind == 'public_file':
        target.write_bytes(b'public bytes'); target.chmod(0o644)
    else:
        target.mkdir(mode=0o755)
    before = inventory(tmp_path)
    with pytest.raises(SafetyViolation):
        with location.for_checkpoint():
            pytest.fail('unsafe retained payload accepted')
    assert inventory(tmp_path) == before


def test_private_nested_data_is_inspected_as_bytes_not_executed(tmp_path):
    _, _, location = allocated(tmp_path)
    folder = location.path / 'objects'
    for number in range(80):
        folder = folder / str(number)
        folder.mkdir(mode=0o700)
    script = folder / 'payload.py'
    raw = b'raise AssertionError("must remain inert")\n'
    script.write_bytes(raw); script.chmod(0o600)
    before = inventory(location.path)
    with location.for_checkpoint() as held:
        assert held.check() and script.read_bytes() == raw
    assert inventory(location.path) == before


def test_socket_in_retained_storage_is_rejected_without_connecting(tmp_path):
    _, _, location = allocated(tmp_path)
    target = location.path / 'objects/socket'
    # Native socket-type inode; no bound/listening endpoint or network operation.
    os.mknod(target, stat.S_IFSOCK | 0o600)
    assert stat.S_ISSOCK(target.lstat().st_mode)
    before = inventory(location.path)
    with pytest.raises(SafetyViolation):
        with location.for_checkpoint():
            pytest.fail('socket accepted')
    assert inventory(location.path) == before


def test_rejected_payload_walk_releases_native_descriptors_and_mutex(tmp_path):
    _, _, location = allocated(tmp_path)
    nested = location.path / 'objects/nested'; nested.mkdir(mode=0o700)
    target = nested / 'pipe'; os.mkfifo(target, 0o600)
    before = inventory(location.path)
    descriptors = len(os.listdir('/proc/self/fd'))
    for _ in range(20):
        with pytest.raises(SafetyViolation):
            with location.for_checkpoint():
                pytest.fail('unsafe payload accepted')
    assert len(os.listdir('/proc/self/fd')) == descriptors
    assert inventory(location.path) == before
    target.unlink()  # Remove only this test-owned hostile fixture.
    with location.for_checkpoint() as held:
        assert held.check()


@pytest.mark.parametrize('name', ['root.json', 'work-lock.json'])
@pytest.mark.parametrize('change', ['bytes', 'inode', 'symlink', 'hardlink', 'permissions'])
def test_changed_live_control_record_is_not_removed_on_exit(tmp_path, name, change):
    roots = protected(tmp_path)
    before_project = inventory(roots[0].root)
    location = WorkDirectory(create(), protected_roots=roots, directory=tmp_path / 'work')
    context = location.for_checkpoint()
    held = context.__enter__()
    target = held.path / name
    raw = target.read_bytes()
    if change == 'bytes':
        target.write_bytes(b'foreign record')
    elif change == 'permissions':
        target.chmod(0o644)
    else:
        saved = tmp_path / 'retained-control'
        target.rename(saved)
        if change == 'inode':
            target.write_bytes(raw); target.chmod(0o600)
        elif change == 'symlink':
            target.symlink_to(saved)
        else:
            os.link(saved, target)
    before = inventory(tmp_path)
    with pytest.raises(SafetyViolation):
        held.check()
    with pytest.raises(SafetyViolation):
        context.__exit__(None, None, None)
    assert inventory(tmp_path) == before
    assert inventory(roots[0].root) == before_project
    assert (held.path / 'work-lock.json').exists()


@pytest.mark.parametrize('change', ['root', 'ancestor', 'protected_project', 'container'])
def test_directory_replacement_during_lease_prevents_owner_cleanup(tmp_path, change):
    roots = protected(tmp_path)
    parent = tmp_path / 'outside'; parent.mkdir(mode=0o700)
    location = WorkDirectory(create(), protected_roots=roots, directory=parent / 'work')
    context = location.for_checkpoint(); held = context.__enter__()
    target = {'root': held.path, 'ancestor': parent, 'protected_project': roots[0].root,
              'container': held.path / 'objects'}[change]
    target.rename(tmp_path / 'retained-directory')
    target.mkdir(mode=0o700)
    before = inventory(tmp_path)
    with pytest.raises((SafetyViolation, FileNotFoundError)):
        context.__exit__(None, None, None)
    assert inventory(tmp_path) == before


def test_reentrant_lease_does_not_unlock_or_remove_first_owner(tmp_path):
    roots = protected(tmp_path)
    location = WorkDirectory(create(), protected_roots=roots, directory=tmp_path / 'work')
    with location.for_checkpoint() as held:
        raw = (held.path / 'work-lock.json').read_bytes()
        with pytest.raises(BlockingIOError):
            with location.for_checkpoint():
                pytest.fail('second owner entered')
        assert held.check() and (held.path / 'work-lock.json').read_bytes() == raw
    assert not (held.path / 'work-lock.json').exists()


@pytest.mark.parametrize('temp_preference', ['explicit', 'environment'])
def test_automatic_root_rejects_project_temp_location_without_probe_writes(tmp_path, monkeypatch, temp_preference):
    roots = protected(tmp_path)
    monkeypatch.setenv('TMPDIR', str(roots[0].root))
    location = WorkDirectory(create(), protected_roots=roots,
        temporary_directory=roots[0].root if temp_preference == 'explicit' else None)
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(SafetyViolation):
        with location.for_checkpoint():
            pytest.fail('project temporary root accepted')
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('area', ['input', 'output'])
def test_additional_input_and_output_boundaries_are_protected(tmp_path, area):
    roots = protected(tmp_path)
    extra = tmp_path / area; extra.mkdir()
    roots = roots + (ProjectBoundary(extra),)
    location = WorkDirectory(create(), protected_roots=roots, directory=extra / 'work')
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(SafetyViolation):
        with location.for_checkpoint():
            pytest.fail('additional boundary ignored')
    assert inventory(tmp_path) == before


def test_forked_child_cannot_check_or_release_its_parents_work_lock(tmp_path):
    roots = protected(tmp_path)
    manifest = create()
    body = ('import os, json\nfrom specroad.security import ProjectBoundary, SafetyViolation\n'
            'from specroad.work.root import WorkDirectory\n'
            'from specroad.work.manifest import read_work_manifest\n'
            'from specroad.cli.commands import builtin_registry\n'
            'm=read_work_manifest(' + repr(manifest.raw) + ',' + repr(dict(manifest.objects))
            + ', registry=builtin_registry(), expected_tool_build=' + repr(manifest.as_dict()['tool_build']) + ')\n'
            'location=WorkDirectory(m, protected_roots=(ProjectBoundary(' + repr(str(roots[0].root))
            + '),), directory=' + repr(str(tmp_path / 'work')) + ')\n'
            'context=location.for_checkpoint(); held=context.__enter__()\n'
            'raw=(held.path / "work-lock.json").read_bytes()\n'
            'pid=os.fork()\n'
            'if pid==0:\n'
            ' try:\n  held.check()\n except SafetyViolation:\n  context.__exit__(None,None,None); os._exit(0)\n'
            ' os._exit(41)\n'
            '_,status=os.waitpid(pid,0); assert os.waitstatus_to_exitcode(status)==0\n'
            'assert held.check() and (held.path / "work-lock.json").read_bytes()==raw\n'
            'import fcntl\nfd=os.open(held.path, os.O_RDONLY|os.O_DIRECTORY)\n'
            'try:\n fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB); raise AssertionError("parent lock lost")\n'
            'except BlockingIOError:\n pass\nfinally:\n os.close(fd)\n'
            'context.__exit__(None,None,None)\n')
    before = inventory(roots[0].root)
    completed = run_core(body, tmp_path, capture=True)
    assert completed.returncode == 0, completed.stderr
    assert inventory(roots[0].root) == before
    assert not (tmp_path / 'work/work-lock.json').exists()
