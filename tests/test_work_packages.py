"""Real Work bytes survive external transport and fresh private storage.

Build metadata and generic declared task evidence are labelled fixtures. Real
bootstrap handlers, sealed captures, checkpoints and isolated child processes
provide behavior evidence without asserting a general production Work CLI.
"""

import errno
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil

import pytest

from specroad import _build
from specroad.cli.commands import builtin_registry
from specroad.cli.requests import CommandRequest
from specroad.model.canonical import canonical_json_bytes
from specroad.security import ProjectBoundary, SafetyViolation
from specroad.work._archive import ArchiveError, decode_archive, encode_archive
from specroad.work.checkpoints import CheckpointStore, CheckpointStorageError
from specroad.work.control import cancel_read_only_work
from specroad.work.finalization import finalize_read_only_work
from specroad.work.manifest import create_work_manifest, partition_work_manifest
from specroad.work.packages import export_work_package, restore_work_package
from specroad.work.result_files import publish_read_only_result_files
from specroad.work.resume import WorkResumeError, prepare_read_only_work, resume_read_only_work
from specroad.work.root import WorkDirectory
from specroad.work.snapshot import InputSnapshotTask
from support.processes import run_core
from support.read_only import inventory, no_write_attempts
from test_work_publication import setup as native_setup, ready, publish
from test_work_resume import recorded, setup, REQUESTS
from test_work_root import protected


def restore(raw, roots, directory):
    return restore_work_package(raw, expected_sha256=sha256(raw).hexdigest(),
        registry=builtin_registry(), protected_roots=roots, directory=directory)


def unpack(raw):
    return decode_archive(raw, manifest_name='work-package.json', expected_sha256=sha256(raw).hexdigest())


@pytest.mark.parametrize('generation', [0, 1, 2])
@pytest.mark.parametrize('command_request', REQUESTS, ids=lambda item: item.command_id)
def test_every_closed_handler_resumes_or_replays_after_root_loss(recorded, tmp_path, generation, command_request):
    initial, roots, location, store = setup(tmp_path, command_request)
    saved_outcome = None
    if generation:
        saved_outcome = resume_read_only_work(store).outcome_bytes
    if generation == 2:
        finalize_read_only_work(store)
    current = store.read(); old_pointer = (location.path / 'work.json').read_bytes()
    before = inventory(tmp_path)
    with no_write_attempts():
        raw = export_work_package(store)
        assert export_work_package(store) == raw
    assert inventory(tmp_path) == before
    metadata, payloads = unpack(raw)
    assert metadata['package_kind'] == 'work' and metadata['checkpoint_generation'] == generation
    assert not any('root.json' in name or 'work-lock' in name for name in payloads)
    # Only externally retained package bytes survive removal of the old Work root.
    shutil.rmtree(location.path)
    project = inventory(roots[0].root)
    restored = restore(raw, roots, tmp_path / 'restored')
    actual = restored.read()
    assert actual.raw == current.raw and dict(actual.objects) == dict(current.objects)
    assert restored._initial.raw == initial.raw and dict(restored._initial.objects) == dict(initial.objects)
    assert (restored._location.path / 'work.json').read_bytes() == old_pointer
    binding = json.loads((restored._location.path / 'root.json').read_bytes())
    observed_root = restored._location.path.stat()
    assert binding['device'] == str(observed_root.st_dev) and binding['inode'] == str(observed_root.st_ino)
    assert binding['work_id'] == current.as_dict()['work_id']
    assert not (restored._location.path / 'work-lock.json').exists()
    assert all(not p.stat().st_mode & 0o077 for p in restored._location.path.rglob('*'))
    step = resume_read_only_work(restored)
    assert step.executed is (generation == 0)
    if saved_outcome is not None:
        assert step.outcome_bytes == saved_outcome
    finalize_read_only_work(restored)
    delivery = publish_read_only_result_files(restored).as_dict()
    assert json.loads(Path(delivery['command_outcome']['result_ref']['path']).read_bytes()) == json.loads(step.outcome_bytes)['result']
    assert inventory(roots[0].root) == project


def test_sealed_input_bytes_and_segmented_history_survive_source_loss(recorded, tmp_path):
    inputs = tmp_path / 'inputs'; inputs.mkdir()
    expected = {f'data-{n:03d}': (str(n).encode() + b'\0\xff') * 9 for n in range(70)}
    for name, raw in expected.items():
        (inputs / name).write_bytes(raw)
    boundary = ProjectBoundary(inputs)
    with InputSnapshotTask({'input': boundary}, [{'root_id': 'input', 'path': name} for name in expected], block_bytes=7) as capture:
        while not capture.state['complete']:
            capture.advance(11)
        captured = capture.work_inputs()
    roots = protected(tmp_path)
    initial = create_work_manifest(builtin_registry(), CommandRequest('version'),
        tool_build=prepare_read_only_work(CommandRequest('version')).as_dict()['tool_build'],
        source_bindings={'project_id': None, 'scope': ['declared-capture-fixture'], 'model_root_sha256': None},
        inputs=captured, units=[{'key': str(n), 'phase': 'data-fixture', 'range': {'n': n}} for n in range(70)])
    location = WorkDirectory(initial, protected_roots=(*roots, boundary), directory=tmp_path / 'work')
    store = CheckpointStore(location, initial);store.publish(initial)
    current = initial
    for task in initial.entries('tasks')[:2]:
        current = partition_work_manifest(current, {task['unit_id']: b'{"fixture_data_retained":true}'})
        store.publish(current)
    with no_write_attempts():
        raw = export_work_package(store)
    shutil.rmtree(inputs);shutil.rmtree(location.path)
    restored = restore(raw, roots, tmp_path / 'restored')
    result = restored.read()
    assert result.raw == current.raw and dict(result.objects) == dict(current.objects)
    assert result.entries('remaining') == current.entries('remaining')
    for row in result.entries('inputs'):
        assert result.objects[row['sha256']] == expected[row['path']]
    # Retained declared data is not a fabricated executable handler plan.
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(WorkResumeError):
        resume_read_only_work(restored)
    assert inventory(tmp_path) == before


def test_a_new_process_restores_only_the_retained_package_and_bound_runtime(recorded, tmp_path):
    _, roots, location, store = setup(tmp_path)
    raw = export_work_package(store); package = tmp_path / 'retained.zip';package.write_bytes(raw)
    identity = store.read().as_dict()['work_id'];shutil.rmtree(location.path)
    body = ('import json\nfrom pathlib import Path\nfrom specroad import _build\n'
        'from specroad.cli.commands import builtin_registry\nfrom specroad.security import ProjectBoundary\n'
        'from specroad.work.packages import restore_work_package\n'
        'from specroad.work.resume import resume_read_only_work\n'
        'from specroad.work.finalization import finalize_read_only_work\n'
        "_build.BUILD_METADATA={'format_version':1,'hash_algorithm':'specroad-dev-payload-v1','build_sha256':'4'*64}\n"
        'store=restore_work_package(Path(' + repr(str(package)) + ').read_bytes(),expected_sha256=' + repr(sha256(raw).hexdigest())
        + ',registry=builtin_registry(),protected_roots=(ProjectBoundary(' + repr(str(roots[0].root)) + '),),directory='
        + repr(str(tmp_path / 'fresh')) + ')\n'
        'step=resume_read_only_work(store)\nfinalize_read_only_work(store)\n'
        "print(json.dumps({'executed':step.executed,'work':store.read().as_dict()}))\n")
    completed = run_core(body, tmp_path, capture=True)
    assert completed.returncode == 0, completed.stderr
    value = json.loads(completed.stdout)
    assert value['executed'] and value['work']['work_id'] == identity
    assert value['work']['state'] == 'completed' and value['work']['checkpoint_generation'] == 2


@pytest.mark.parametrize('kind', ['missing', 'additional', 'object_bytes', 'kind', 'initial', 'pointer', 'build'])
def test_invalid_complete_package_is_rejected_before_destination_writes(recorded, tmp_path, kind):
    _, roots, _, store = setup(tmp_path); resume_read_only_work(store)
    metadata, payloads = unpack(export_work_package(store))
    if kind == 'missing':
        del payloads[next(name for name in payloads if name.startswith('checkpoints/'))]
    elif kind == 'additional':
        payloads['objects/' + sha256(b'owned extra').hexdigest()] = b'owned extra'
    elif kind == 'object_bytes':
        payloads[next(name for name in payloads if name.startswith('objects/'))] = b'altered'
    elif kind == 'kind': metadata['package_kind'] = 'project'
    elif kind == 'initial': metadata['initial_checkpoint_sha256'] = '0' * 64
    elif kind == 'pointer':
        value = json.loads(payloads['work.json']);value['checkpoint_generation'] = True
        payloads['work.json'] = canonical_json_bytes(value)
    else: metadata['tool_build']['build_sha256'] = '0' * 64
    raw = encode_archive('work-package.json', metadata, payloads)
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(ArchiveError):
        restore(raw, roots, tmp_path / 'rejected')
    assert inventory(tmp_path) == before and not (tmp_path / 'rejected').exists()


@pytest.mark.parametrize('kind', ['same_work', 'foreign', 'public_empty', 'symlink', 'project', 'project_child'])
def test_nonempty_unsafe_or_overlapping_restore_target_is_preserved(recorded, tmp_path, kind):
    _, roots, location, store = setup(tmp_path);raw = export_work_package(store)
    target = tmp_path / 'target'
    if kind == 'same_work': target = location.path
    elif kind == 'foreign':
        target.mkdir(mode=0o700);(target / 'retained').write_bytes(b'foreign')
    elif kind == 'public_empty': target.mkdir(mode=0o755)
    elif kind == 'symlink': target.symlink_to(location.path, target_is_directory=True)
    elif kind == 'project': target = roots[0].root
    else: target = roots[0].root / 'nested'
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(SafetyViolation):
        restore(raw, roots, target)
    assert inventory(tmp_path) == before


def test_an_existing_private_empty_target_is_supported(recorded, tmp_path):
    _, roots, _, store = setup(tmp_path);raw = export_work_package(store)
    target = tmp_path / 'empty';target.mkdir(mode=0o700);inode = target.stat().st_ino
    restored = restore(raw, roots, target)
    assert restored.read().raw == store.read().raw and target.stat().st_ino == inode


@pytest.mark.parametrize('committed', [False, True])
def test_native_work_cannot_be_exported_without_native_transaction_binding(recorded, tmp_path, committed):
    model, plan, _, reg, _, _, store = native_setup(tmp_path)
    ready(store, reg, model, plan)
    if committed: publish(store, reg, model, plan)
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(ArchiveError) as caught:
        export_work_package(store)
    assert caught.value.as_dict() == {'reason': 'normative_work_package_requires_native_binding', 'exit_code': 6}
    assert inventory(tmp_path) == before


def test_cancelled_work_retains_its_control_record_after_restore(recorded, tmp_path):
    _, roots, _, store = setup(tmp_path)
    cancel_read_only_work(store, reason='Explicit retained cancellation')
    current = store.read();raw = export_work_package(store)
    restored = restore(raw, roots, tmp_path / 'restored')
    assert restored.read().raw == current.raw and dict(restored.read().objects) == dict(current.objects)
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(WorkResumeError) as caught:
        resume_read_only_work(restored)
    assert caught.value.reason == 'work_cannot_resume' and inventory(tmp_path) == before


def test_an_incomplete_real_handler_is_not_relabelled_success_by_transport(recorded, tmp_path):
    initial, roots, _, store = setup(tmp_path,
        CommandRequest('schema.show', arguments={'schema_id': 'not-a-schema'}))
    with pytest.raises(WorkResumeError) as caught:
        resume_read_only_work(store)
    assert caught.value.as_dict() == {'reason': 'command_did_not_complete', 'exit_code': 2}
    restored = restore(export_work_package(store), roots, tmp_path / 'restored')
    with pytest.raises(WorkResumeError) as caught:
        resume_read_only_work(restored)
    assert caught.value.as_dict() == {'reason': 'command_did_not_complete', 'exit_code': 2}
    assert restored.read().raw == initial.raw and restored.read().entries('completed') == []


@pytest.mark.parametrize('late', [False, True])
def test_restore_io_failure_preserves_the_actual_published_generation(recorded, tmp_path, monkeypatch, late):
    initial, roots, _, store = setup(tmp_path);resume_read_only_work(store)
    raw = export_work_package(store);target = tmp_path / 'partial';replace = os.replace
    calls = []
    with monkeypatch.context() as patcher:
        def failed(src, dst, **options):
            if dst == 'work.json':
                calls.append(dst)
                if len(calls) == 2:
                    if late: replace(src, dst, **options)
                    raise OSError(errno.EIO, 'Owned restore boundary')
            return replace(src, dst, **options)
        patcher.setattr(os, 'replace', failed)
        with pytest.raises(OSError) as caught:
            restore(raw, roots, target)
    assert caught.value.errno == errno.EIO and len(calls) == 2
    preserved = CheckpointStore(WorkDirectory(initial, protected_roots=roots, directory=target), initial)
    assert preserved.read().as_dict()['checkpoint_generation'] == (1 if late else 0)
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(SafetyViolation):
        restore(raw, roots, target)
    assert inventory(tmp_path) == before


def test_corrupt_local_source_and_changed_runtime_cannot_create_a_package(recorded, tmp_path, monkeypatch):
    _, roots, location, store = setup(tmp_path)
    raw = export_work_package(store)
    digest = next(iter(store._initial.objects));(location.path / 'objects' / digest).write_bytes(b'corrupt')
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(CheckpointStorageError):
        export_work_package(store)
    monkeypatch.setattr(_build, 'BUILD_METADATA', {'format_version': 1,
        'hash_algorithm': 'specroad-dev-payload-v1', 'build_sha256': 'b' * 64})
    with no_write_attempts(), pytest.raises(ArchiveError) as caught:
        restore(raw, roots, tmp_path / 'restored')
    assert caught.value.reason == 'incompatible_work_package_build' and inventory(tmp_path) == before


def test_external_hash_and_explicit_target_are_required_before_allocation(recorded, tmp_path):
    _, roots, _, store = setup(tmp_path);raw = export_work_package(store);before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(ArchiveError) as caught:
        restore_work_package(raw, expected_sha256='0' * 64, registry=builtin_registry(),
            protected_roots=roots, directory=tmp_path / 'rejected')
    assert caught.value.reason == 'archive_hash_mismatch'
    with no_write_attempts(), pytest.raises(ArchiveError) as caught:
        restore(raw, roots, None)
    assert caught.value.reason == 'work_package_target_required' and inventory(tmp_path) == before
