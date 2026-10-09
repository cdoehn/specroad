"""Lazy private work locations and real native lock lifetime, without resume."""

import copy
import errno
import json
import os
import pickle
import stat

import pytest

from specroad.security import ProjectBoundary, SafetyViolation
from specroad.work.root import WorkDirectory
from support.processes import run_cli, run_core
from support.read_only import inventory, no_write_attempts
from test_work_manifest import create


def protected(tmp_path):
    root = tmp_path / 'project'
    root.mkdir()
    (root / '.specroad').mkdir()
    (root / 'specroad.json').write_bytes(b'normative fixture')
    (root / '.specroad/journal').write_bytes(b'operational fixture')
    return (ProjectBoundary(root),)


@pytest.mark.parametrize('explicit', [False, True])
def test_declaring_storage_without_checkpoint_need_creates_nothing(tmp_path, explicit):
    roots = protected(tmp_path)
    manifest = create()
    before = inventory(tmp_path)
    with no_write_attempts():
        location = WorkDirectory(manifest, protected_roots=roots,
            directory=tmp_path / 'work' if explicit else None, temporary_directory=tmp_path)
        assert location.path is None
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('arguments', [['version'], ['command', 'describe', 'version']])
def test_small_completed_cli_command_leaves_no_work_files(tmp_path, monkeypatch, arguments):
    monkeypatch.setenv('TMPDIR', str(tmp_path))
    before = inventory(tmp_path)
    completed = run_cli(arguments, tmp_path, capture=True)
    assert completed.returncode == 0, completed.stderr
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('kind', ['automatic', 'explicit_new', 'explicit_empty'])
def test_first_needed_root_is_private_bound_external_and_reusable(tmp_path, kind):
    roots = protected(tmp_path)
    before = inventory(roots[0].root)
    manifest = create()
    path = tmp_path / 'work'
    if kind == 'explicit_empty':
        path.mkdir(mode=0o700)
    location = WorkDirectory(manifest, protected_roots=roots,
        directory=None if kind == 'automatic' else path, temporary_directory=tmp_path)
    with location.for_checkpoint() as held:
        actual = held.path
        assert actual == location.path
        assert actual.parent == tmp_path
        if kind != 'automatic':
            assert actual == path
        assert held.work_id == manifest.as_dict()['work_id'] and held.check()
        for entry in [actual, *actual.iterdir()]:
            assert stat.S_IMODE(entry.stat().st_mode) & 0o077 == 0
        binding = (actual / 'root.json').read_bytes()
        owner = (actual / 'work-lock.json').read_bytes()
        assert json.loads(binding)['initial_checkpoint_sha256'] == manifest.as_dict()['checkpoint_sha256']
        assert json.loads(owner)['process_id'] == os.getpid()
        assert not (actual / 'work.json').exists()  # This is no published checkpoint.
    assert not (actual / 'work-lock.json').exists()
    with pytest.raises(SafetyViolation):
        held.check()
    with location.for_checkpoint() as again:
        assert again.path == actual and again.check()
        assert (actual / 'root.json').read_bytes() == binding
        assert (actual / 'work-lock.json').read_bytes() != owner
    assert inventory(roots[0].root) == before


def test_explicit_same_manifest_can_reopen_a_released_root(tmp_path):
    roots = protected(tmp_path)
    manifest = create()
    path = tmp_path / 'work'
    with WorkDirectory(manifest, protected_roots=roots, directory=path).for_checkpoint():
        pass
    before = inventory(path)
    with WorkDirectory(manifest, protected_roots=roots, directory=path).for_checkpoint() as held:
        assert held.check()
    assert inventory(path) == before


def test_live_native_lock_blocks_another_process_and_releases_at_step_end(tmp_path):
    roots = protected(tmp_path)
    before = inventory(roots[0].root)
    location = WorkDirectory(create(), protected_roots=roots, temporary_directory=tmp_path)
    with location.for_checkpoint() as held:
        body = ('import fcntl, os\nfd=os.open(' + repr(str(held.path)) + ', os.O_RDONLY|os.O_DIRECTORY)\n'
                'try:\n fcntl.flock(fd, fcntl.LOCK_EX|fcntl.LOCK_NB)\n'
                'except BlockingIOError:\n raise SystemExit(23)\n'
                'finally:\n os.close(fd)\n')
        assert run_core(body, tmp_path).returncode == 23
        project_probe = ('import fcntl, os\nfd=os.open(' + repr(str(roots[0].root))
            + ', os.O_RDONLY|os.O_DIRECTORY)\n'
            'fcntl.flock(fd, fcntl.LOCK_EX|fcntl.LOCK_NB); os.close(fd)\n')
        assert run_core(project_probe, tmp_path).returncode == 0
        assert held.check()
    assert run_core(body, tmp_path).returncode == 0
    assert inventory(roots[0].root) == before


def test_exception_releases_owner_but_retains_work_payloads(tmp_path):
    roots = protected(tmp_path)
    before = inventory(roots[0].root)
    location = WorkDirectory(create(), protected_roots=roots, temporary_directory=tmp_path)
    with pytest.raises(RuntimeError):
        with location.for_checkpoint() as held:
            (held.path / 'objects/fixture').write_bytes(b'retained work bytes')
            raise RuntimeError('labelled caller failure')
    assert (location.path / 'objects/fixture').read_bytes() == b'retained work bytes'
    assert not (location.path / 'work-lock.json').exists()
    assert inventory(roots[0].root) == before


@pytest.mark.parametrize('relative', ['', '/work', '/.specroad/work'])
def test_protected_root_and_descendants_are_rejected_before_writes(tmp_path, relative):
    roots = protected(tmp_path)
    location = WorkDirectory(create(), protected_roots=roots,
                             directory=str(roots[0].root) + relative)
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(SafetyViolation):
        with location.for_checkpoint():
            pytest.fail('protected work root accepted')
    assert inventory(tmp_path) == before


def test_work_ancestor_of_input_is_rejected_before_writes(tmp_path):
    roots = protected(tmp_path)
    location = WorkDirectory(create(), protected_roots=roots, directory=tmp_path)
    with no_write_attempts(), pytest.raises(SafetyViolation):
        with location.for_checkpoint():
            pytest.fail('overlapping work root accepted')


@pytest.mark.parametrize('path', ['relative', '/tmp/../work', '/tmp/./work', '/tmp//work', '//tmp/work', '/tmp/a\\b'])
def test_unsafe_path_syntax_is_rejected_without_normalizing_it(tmp_path, path):
    roots = protected(tmp_path)
    manifest = create()
    with no_write_attempts(), pytest.raises(SafetyViolation):
        WorkDirectory(manifest, protected_roots=roots, directory=path)


@pytest.mark.parametrize('kind', ['symlink', 'file', 'foreign', 'public_empty'])
def test_preexisting_unsafe_or_foreign_target_is_preserved(tmp_path, kind):
    roots = protected(tmp_path)
    target = tmp_path / 'work'
    if kind == 'symlink':
        target.symlink_to(roots[0].root, target_is_directory=True)
    elif kind == 'file':
        target.write_bytes(b'original')
    else:
        target.mkdir(mode=0o700 if kind == 'foreign' else 0o755)
        if kind == 'foreign':
            (target / 'keep').write_bytes(b'foreign data')
    before = inventory(tmp_path)
    with pytest.raises((SafetyViolation, OSError)):
        with WorkDirectory(create(), protected_roots=roots, directory=target).for_checkpoint():
            pytest.fail('unsafe target accepted')
    assert inventory(tmp_path) == before


def test_symlinked_ancestor_does_not_create_a_root_in_project(tmp_path):
    roots = protected(tmp_path)
    alias = tmp_path / 'alias'
    alias.symlink_to(roots[0].root, target_is_directory=True)
    before = inventory(tmp_path)
    with pytest.raises(SafetyViolation):
        with WorkDirectory(create(), protected_roots=roots, directory=alias / 'work').for_checkpoint():
            pytest.fail('symlinked ancestor accepted')
    assert inventory(tmp_path) == before


def test_foreign_work_identity_cannot_reuse_existing_storage(tmp_path):
    roots = protected(tmp_path)
    path = tmp_path / 'work'
    with WorkDirectory(create(), protected_roots=roots, directory=path).for_checkpoint():
        pass
    before = inventory(tmp_path)
    with pytest.raises(SafetyViolation):
        with WorkDirectory(create(), protected_roots=roots, directory=path).for_checkpoint():
            pytest.fail('different work reused root')
    assert inventory(tmp_path) == before


def test_unknown_owner_identity_cannot_gain_a_live_work_lease(tmp_path, monkeypatch):
    from specroad.changes.lock_values import OwnerIdentity
    roots = protected(tmp_path)
    location = WorkDirectory(create(), protected_roots=roots, temporary_directory=tmp_path)
    monkeypatch.setattr('specroad.work.root.LinuxOwnerProbe.current',
                        lambda self: OwnerIdentity(None, os.getpid(), None))
    before = inventory(roots[0].root)
    with pytest.raises(SafetyViolation):
        with location.for_checkpoint():
            pytest.fail('unknown owner accepted')
    assert location.path is None
    assert inventory(roots[0].root) == before
    assert not list(tmp_path.rglob('work-lock.json'))


def test_real_child_exit_leaves_orphan_record_that_is_never_stolen(tmp_path):
    roots = protected(tmp_path)
    manifest = create()
    path = tmp_path / 'work'
    body = ('import os\nfrom specroad.security import ProjectBoundary\n'
            'from specroad.work.root import WorkDirectory\n'
            'from specroad.work.manifest import read_work_manifest\n'
            'from specroad.cli.commands import builtin_registry\n'
            'm=read_work_manifest(' + repr(manifest.raw) + ',' + repr(dict(manifest.objects))
            + ', registry=builtin_registry(), expected_tool_build=' + repr(manifest.as_dict()['tool_build']) + ')\n'
            'location=WorkDirectory(m, protected_roots=(ProjectBoundary(' + repr(str(roots[0].root))
            + '),), directory=' + repr(str(path)) + ')\n'
            'context=location.for_checkpoint(); held=context.__enter__(); os._exit(42)\n')
    result = run_core(body, tmp_path, capture=True)
    assert result.returncode == 42, result.stderr
    before = inventory(path)
    with pytest.raises(SafetyViolation):
        with WorkDirectory(manifest, protected_roots=roots, directory=path).for_checkpoint():
            pytest.fail('orphan work lock stolen')
    assert inventory(path) == before and (path / 'work-lock.json').exists()


def test_native_write_failure_preserves_partial_root_and_propagates(tmp_path, monkeypatch):
    roots = protected(tmp_path)
    target = tmp_path / 'work'
    location = WorkDirectory(create(), protected_roots=roots, directory=target)
    attempts = []
    def fail(fd, raw):
        attempts.append(len(raw))
        raise OSError(errno.ENOSPC, 'labelled native write failure')
    monkeypatch.setattr('specroad.work.root.os.write', fail)
    with pytest.raises(OSError) as error:
        with location.for_checkpoint():
            pytest.fail('failed publication accepted')
    assert error.value.errno == errno.ENOSPC and len(attempts) == 1
    assert (target / 'root.json').read_bytes() == b''
    assert not (target / 'work.json').exists()


@pytest.mark.parametrize('operation', [copy.copy, copy.deepcopy, pickle.dumps])
def test_live_work_handle_cannot_be_copied_or_serialized(tmp_path, operation):
    roots = protected(tmp_path)
    location = WorkDirectory(create(), protected_roots=roots, temporary_directory=tmp_path)
    with location.for_checkpoint() as held:
        with pytest.raises(TypeError):
            operation(held)
        assert held.check()
