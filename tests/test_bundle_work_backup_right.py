"""15.i.R: actual retained bytes bound restoration after loss and path changes.

The build label is an explicit compatibility fixture. File publication, fresh
processes, complete checkpoint chains and injected filesystem changes are real.
No export report, prompt or hash is treated as replacement payload data.
"""
from hashlib import sha256
import json
import os
import shutil

import pytest

from specroad.cli.commands import builtin_registry
from specroad.cli.requests import CommandRequest
from specroad.model.canonical import canonical_json_bytes
from specroad.security import SafetyViolation
from specroad.storage.archive import ArchiveError, encode_archive
from specroad.work import packages
from specroad.work.checkpoints import CheckpointStore
from specroad.work.finalization import finalize_read_only_work
from specroad.work.manifest import create_work_manifest, partition_work_manifest
from specroad.work.package_restoration import restore_work_package_file
from specroad.work.prompt import read_only_work_prompt
from specroad.work.resume import WorkResumeError, _runtime_build, resume_read_only_work
from support.processes import run_core
from support.read_only import inventory, no_write_attempts
from test_bundle_work_backup import destination, save
from test_project_bundle import project
from specroad.bundles import prepare_project_bundle
from test_work_packages import unpack
from test_work_resume import recorded, setup
from test_work_root import protected


def retained(store, tmp_path):
    output = destination(tmp_path)
    report = save(store, output, 'work.zip')
    return output / 'work.zip', report['file']['sha256']


def restore(path, digest, roots, target):
    return restore_work_package_file(path, expected_sha256=digest,
        registry=builtin_registry(), protected_roots=roots, directory=target)


@pytest.mark.parametrize('generation', [0, 1, 2])
@pytest.mark.parametrize('empty_target', [False, True])
def test_moved_external_file_survives_total_sandbox_loss_in_a_new_process(
        recorded, tmp_path, generation, empty_target):
    old = tmp_path / 'old-sandbox'; old.mkdir()
    _, _, _, store = setup(old)
    outcome = resume_read_only_work(store).outcome_bytes if generation else None
    if generation == 2:
        finalize_read_only_work(store)
    current = store.read()
    path, digest = retained(store, tmp_path)
    moved = tmp_path / 'moved-backup'; path.parent.rename(moved); path = moved / path.name
    shutil.rmtree(old)
    fresh = tmp_path / 'fresh-sandbox'; fresh.mkdir()
    roots = protected(fresh); before = inventory(roots[0].root)
    target = fresh / 'restored'
    if empty_target:
        target.mkdir(mode=0o700)
    inode = target.stat().st_ino if empty_target else None
    body = (
        'import json, os\nfrom specroad import _build\n'
        'from specroad.cli.commands import builtin_registry\n'
        'from specroad.security import ProjectBoundary\n'
        'from specroad.work.package_restoration import restore_work_package_file\n'
        'from specroad.work.resume import resume_read_only_work\n'
        "_build.BUILD_METADATA={'format_version':1,'hash_algorithm':'specroad-dev-payload-v1','build_sha256':'4'*64}\n"
        f'store=restore_work_package_file({str(path)!r},expected_sha256={digest!r},'
        f'registry=builtin_registry(),protected_roots=(ProjectBoundary({str(roots[0].root)!r}),),'
        f'directory={str(target)!r})\n'
        'saved=store.read()\nstep=resume_read_only_work(store)\n'
        "print(json.dumps({'pid':os.getpid(),'manifest':saved.raw.hex(),"
        "'objects':{k:v.hex() for k,v in saved.objects.items()},"
        "'executed':step.executed,'outcome':step.outcome_bytes.hex()}))\n")
    process = run_core(body, fresh, capture=True)
    assert process.returncode == 0, process.stderr
    value = json.loads(process.stdout)
    assert value['pid'] != os.getpid()
    assert bytes.fromhex(value['manifest']) == current.raw
    assert {k: bytes.fromhex(v) for k, v in value['objects'].items()} == dict(current.objects)
    assert value['executed'] is (generation == 0)
    if outcome is not None:
        assert bytes.fromhex(value['outcome']) == outcome
    if empty_target:
        assert target.stat().st_ino == inode
    assert not old.exists() and inventory(roots[0].root) == before
    assert sha256(path.read_bytes()).hexdigest() == digest


def test_last_retained_generation_is_the_boundary_despite_a_newer_saved_prompt(recorded, tmp_path):
    initial, roots, location, store = setup(tmp_path)
    path, digest = retained(store, tmp_path)
    resume_read_only_work(store)
    prompt = read_only_work_prompt(store)
    assert prompt['continuation']['checkpoint_generation'] == 1
    (path.parent / 'later-prompt.json').write_bytes(canonical_json_bytes(prompt))
    original_path = path
    moved = tmp_path / 'elsewhere'; path.parent.rename(moved); path = moved / path.name
    shutil.rmtree(location.path)
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(FileNotFoundError):
        restore(original_path, digest, roots, tmp_path / 'not-discovered')
    assert inventory(tmp_path) == before
    restored = restore(path, digest, roots, tmp_path / 'restored')
    assert restored.read().raw == initial.raw
    assert restored.read().as_dict()['checkpoint_generation'] == 0
    assert resume_read_only_work(restored).executed


@pytest.mark.parametrize('missing', [None, 'input', 'manifest', 'inventory_segment', 'ancestor', 'result'])
def test_actual_sealed_inputs_and_complete_ancestry_are_required_after_loss(recorded, tmp_path, missing):
    source = tmp_path / 'source'; source.write_bytes(b'actual retained input\0\xff')
    initial = create_work_manifest(builtin_registry(), CommandRequest('version'),
        tool_build=_runtime_build(),
        source_bindings={'project_id': None, 'scope': ['retained-loss-fixture'], 'model_root_sha256': None},
        inputs=[{'root_id': 'input', 'path': 'source', 'raw': source.read_bytes()}],
        units=[{'key': str(n), 'phase': 'data-fixture', 'range': {'n': n}} for n in range(70)])
    _, roots, location, store = setup(tmp_path, initial=initial)
    evidence = b'{"declared_fixture_data":true}'
    current = partition_work_manifest(initial, {initial.entries('tasks')[0]['unit_id']: evidence})
    store.publish(current)
    path, digest = retained(store, tmp_path)
    if missing is not None:
        metadata, payloads = unpack(path.read_bytes())
        pointer = json.loads(payloads['work.json'])
        record = json.loads(payloads['checkpoints/' + pointer['checkpoint']['sha256'] + '.json'])
        if missing == 'input': absent = 'objects/' + initial.entries('inputs')[0]['sha256']
        elif missing == 'manifest': absent = 'objects/' + metadata['initial_manifest']['sha256']
        elif missing == 'ancestor': absent = 'checkpoints/' + record['parent']['sha256'] + '.json'
        elif missing == 'result': absent = 'objects/' + sha256(evidence).hexdigest()
        else:
            absent = next(name for name, data in payloads.items()
                if name.startswith('objects/') and b'"kind":"checkpoint-objects"' in data)
        del payloads[absent]
        raw = encode_archive('work-package.json', metadata, payloads)
        path.write_bytes(raw); digest = sha256(raw).hexdigest()
    source.unlink(); shutil.rmtree(location.path)
    before = inventory(tmp_path); target = tmp_path / 'restored'
    if missing is not None:
        with no_write_attempts(), pytest.raises(ArchiveError) as caught:
            restore(path, digest, roots, target)
        assert caught.value.reason == 'work_package_bytes_missing'
        assert not target.exists() and inventory(tmp_path) == before
    else:
        restored = restore(path, digest, roots, target)
        assert restored.read().raw == current.raw
        assert dict(restored.read().objects) == dict(current.objects)
        assert restored.read().entries('remaining') == current.entries('remaining')
        assert restored.read().objects[initial.entries('inputs')[0]['sha256']] == b'actual retained input\0\xff'
        before = inventory(tmp_path)
        with no_write_attempts(), pytest.raises(WorkResumeError):
            resume_read_only_work(restored)
        assert inventory(tmp_path) == before


@pytest.mark.parametrize('substitute', ['export_report', 'prompt_record', 'prompt_only', 'project_package'])
def test_descriptions_and_other_package_kinds_cannot_substitute_for_work_bytes(recorded, tmp_path, substitute):
    _, roots, location, store = setup(tmp_path)
    output = destination(tmp_path); report = save(store, output, 'work.zip')
    path = output / 'work.zip'; prompt = read_only_work_prompt(store)
    if substitute == 'export_report': raw = canonical_json_bytes(report)
    elif substitute == 'prompt_record': raw = canonical_json_bytes(prompt)
    elif substitute == 'prompt_only': raw = prompt['prompt'].encode('utf-8')
    else:
        root = tmp_path / 'normal'; project(root); raw = prepare_project_bundle(root).source_bytes
    path.write_bytes(raw); shutil.rmtree(location.path)
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(ArchiveError):
        restore(path, sha256(raw).hexdigest(), roots, tmp_path / 'rejected')
    assert inventory(tmp_path) == before and not (tmp_path / 'rejected').exists()


@pytest.mark.parametrize('digest', [None, '', '0' * 63, 'A' * 64])
@pytest.mark.parametrize('entrypoint', ['bytes', 'file'])
def test_external_hash_is_required_and_cannot_enable_optional_codec_hash_mode(recorded, tmp_path, digest, entrypoint):
    _, roots, _, store = setup(tmp_path); path, _ = retained(store, tmp_path)
    raw = path.read_bytes(); before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(ArchiveError) as caught:
        if entrypoint == 'file': restore(path, digest, roots, tmp_path / 'rejected')
        else:
            packages.restore_work_package(raw, expected_sha256=digest, registry=builtin_registry(),
                protected_roots=roots, directory=tmp_path / 'rejected')
    assert caught.value.reason == 'invalid_archive_hash' and caught.value.exit_code == 3
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('change', ['missing', 'truncated', 'other_valid_package'])
def test_missing_or_changed_external_file_never_allocates_target(recorded, tmp_path, change):
    _, roots, location, store = setup(tmp_path); path, digest = retained(store, tmp_path)
    if change == 'missing': path.unlink()
    elif change == 'truncated': path.write_bytes(path.read_bytes()[:100])
    else:
        resume_read_only_work(store); path.write_bytes(packages.export_work_package(store))
    shutil.rmtree(location.path)
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(FileNotFoundError if change == 'missing' else ArchiveError):
        restore(path, digest, roots, tmp_path / 'rejected')
    assert inventory(tmp_path) == before and not (tmp_path / 'rejected').exists()


@pytest.mark.parametrize('change', ['missing', 'bytes', 'symlink', 'parent_identity'])
def test_source_changes_after_validation_prevent_allocation(recorded, tmp_path, monkeypatch, change):
    _, roots, _, store = setup(tmp_path); path, digest = retained(store, tmp_path)
    protected_before = inventory(roots[0].root); original = packages._checked_package
    def checked(*args, **kwargs):
        result = original(*args, **kwargs)
        if change == 'missing': path.unlink()
        elif change == 'bytes': path.write_bytes(b'changed input')
        elif change == 'symlink':
            other = tmp_path / 'same-bytes'; other.write_bytes(path.read_bytes())
            path.unlink(); path.symlink_to(other)
        else:
            old = tmp_path / 'old-backup'; path.parent.rename(old)
            path.parent.mkdir(); path.write_bytes((old / path.name).read_bytes())
        return result
    monkeypatch.setattr(packages, '_checked_package', checked)
    with pytest.raises((ArchiveError, SafetyViolation, OSError)) as caught:
        restore(path, digest, roots, tmp_path / 'rejected')
    if change == 'bytes':
        assert caught.value.reason == 'work_package_input_changed' and caught.value.exit_code == 6
    assert not (tmp_path / 'rejected').exists() and inventory(roots[0].root) == protected_before


@pytest.mark.parametrize('generation', [0, 2])
@pytest.mark.parametrize('change', ['missing', 'bytes'])
def test_source_loss_during_restore_preserves_the_real_published_prefix(recorded, tmp_path, monkeypatch, generation, change):
    _, roots, _, store = setup(tmp_path); resume_read_only_work(store); finalize_read_only_work(store)
    path, digest = retained(store, tmp_path)
    protected_before = inventory(roots[0].root); original = CheckpointStore._publish_held
    def publish(self, held, manifest, pointer):
        result = original(self, held, manifest, pointer)
        if manifest.as_dict()['checkpoint_generation'] == generation:
            if change == 'missing': path.unlink()
            else: path.write_bytes(b'changed retained source')
        return result
    monkeypatch.setattr(CheckpointStore, '_publish_held', publish)
    target = tmp_path / 'interrupted'
    with pytest.raises(FileNotFoundError if change == 'missing' else ArchiveError):
        restore(path, digest, roots, target)
    pointer = json.loads((target / 'work.json').read_bytes())
    assert pointer['checkpoint_generation'] == generation
    assert len(list((target / 'checkpoints').iterdir())) == generation + 1
    assert not (target / 'work-lock.json').exists()
    assert inventory(roots[0].root) == protected_before


@pytest.mark.parametrize('kind', ['symlink', 'parent_symlink', 'fifo', 'relative', 'traversal'])
def test_source_paths_are_explicit_canonical_regular_files(recorded, tmp_path, kind):
    _, roots, _, store = setup(tmp_path); path, digest = retained(store, tmp_path)
    if kind == 'symlink':
        alias = path.parent / 'alias.zip'; alias.symlink_to(path); path = alias
    elif kind == 'parent_symlink':
        alias = tmp_path / 'alias'; alias.symlink_to(path.parent, target_is_directory=True); path = alias / path.name
    elif kind == 'fifo': path.unlink(); os.mkfifo(path)
    elif kind == 'relative': path = 'external/work.zip'
    else: path = str(path.parent / '..' / path.parent.name / path.name)
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises((SafetyViolation, OSError)):
        restore(path, digest, roots, tmp_path / 'rejected')
    assert inventory(tmp_path) == before and not (tmp_path / 'rejected').exists()


@pytest.mark.parametrize('kind', ['input_child', 'input_parent', 'project', 'occupied'])
def test_restore_never_overwrites_retained_input_or_protected_targets(recorded, tmp_path, kind):
    _, roots, _, store = setup(tmp_path); path, digest = retained(store, tmp_path)
    if kind == 'input_child': target = path.parent / 'restored'
    elif kind == 'input_parent': target = path.parent
    elif kind == 'project': target = roots[0].root
    else:
        target = tmp_path / 'occupied'; target.mkdir(mode=0o700)
        (target / 'owned').write_bytes(b'preserve these actual bytes')
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(SafetyViolation):
        restore(path, digest, roots, target)
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('roots', [(), (None,)])
def test_adding_input_boundary_never_replaces_required_explicit_protected_roots(recorded, tmp_path, roots):
    _, _, _, store = setup(tmp_path); path, digest = retained(store, tmp_path)
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(ValueError):
        restore(path, digest, roots, tmp_path / 'rejected')
    assert inventory(tmp_path) == before
