"""Blockwise real input capture, exact Baseline parity and native Work resume."""
from base64 import b64decode
import copy
import json
import os
from pathlib import Path
import pickle
import shutil

import pytest

from specroad.archive.work import (BaselineSnapshotTask, BaselineSnapshotConflict,
    advance_baseline_work, publish_baseline_work)
from specroad.changes import ChangePlan
from specroad.changes._target_materialization import materialize_target
from specroad.model.canonical import canonical_json_bytes
from specroad.model.errors import ModelError
from specroad.model.paths import artifact_path
from specroad.security import ProjectBoundary
from specroad.validation import ModelDocument, ModelGate
from specroad.work._normative_binding import read_plan
from specroad.work.checkpoints import CheckpointStore
from specroad.work.publication import prepare_normative_work
from specroad.work.root import WorkDirectory
from specroad.work.snapshot import SnapshotCaptureError
from support.domain import domain_value
from support.model import put
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import inventory, no_write_attempts
from support.records import ref
from support.relations import aid
from test_baseline_creation import project, preview, ACTOR, TIME, ALLOW
from test_configured_baseline_right import variant_project
from test_work_resume import recorded
from test_work_resume_right import registry


def options(**changes):
    return dict(baseline_id=ref('BASE'), name='Working snapshot', actor=ACTOR,
        planned_at=TIME, change_plan_id='CP-baseline', request_id='baseline-1', **changes)


def large_project(root):
    model = project(root)
    value = domain_value('goal', statement='Owned snapshot bytes. ' * 7000)
    document = ModelDocument(artifact_path('goal', value['id'], 'SR'), canonical_json_bytes(value))
    put(root, document.path, document.content)
    return materialize_target(model, (document,))


def finish(task, window=1000):
    while not task.state['source_binding_verified']: task.advance(window)
    return task.state


def checkpoint(root, initial, directory):
    return CheckpointStore(WorkDirectory(initial, protected_roots=(ProjectBoundary(root),),
        directory=directory), initial)


def assert_same_preparation(left, right):
    # Separate Work allocation has its own identity and checkpoint self-hash;
    # every task/input/plan binding and every retained payload must be equal.
    a, b = left.as_dict(), right.as_dict()
    for key in ('work_id', 'checkpoint_sha256'):
        a.pop(key); b.pop(key)
    assert a == b and dict(left.objects) == dict(right.objects)


@pytest.mark.parametrize('window', [1, 7, 100000])
@pytest.mark.parametrize('configured', [False, True])
def test_split_capture_builds_the_exact_single_run_manifest_objects_and_work(recorded, tmp_path, window, configured):
    root = tmp_path / 'project'; model = variant_project(root) if configured else large_project(root)
    fields = options(**({'configuration_id': aid('configuration', 2)} if configured else {}))
    direct = preview(model, **fields); expected = ChangePlan(canonical_json_bytes(direct['plan']))
    before = inventory(tmp_path)
    with no_write_attempts(), BaselineSnapshotTask(model, block_bytes=4096) as task:
        finish(task, window)
        split = task.prepare_working_plan(**fields)
        initial = task.prepare_work(registry(), **fields)
        ordinary = prepare_normative_work(registry(), expected, model=model)
    assert split == direct
    assert_same_preparation(initial, ordinary)
    assert read_plan(initial.as_dict(), initial.objects).source_bytes == expected.source_bytes
    assert inventory(tmp_path) == before and not (root / 'archive').exists()


def test_large_source_is_read_once_in_bounded_blocks_across_windows(tmp_path, monkeypatch):
    root = tmp_path / 'project'; model = large_project(root); path = root / model.documents[0].path
    raw = path.read_bytes(); observed = []; native = os.read
    def read(fd, size):
        selected = os.readlink('/proc/self/fd/' + str(fd)) == str(path)
        offset = os.lseek(fd, 0, os.SEEK_CUR) if selected else None
        result = native(fd, size)
        if selected: observed.append((offset, size, len(result)))
        return result
    monkeypatch.setattr('specroad.work.snapshot.os.read', read)
    with no_write_attempts(), BaselineSnapshotTask(model, block_bytes=10**9) as task:
        finish(task, 1)
        report = task.state
    assert len(raw) > 131072 and sum(row[2] for row in observed) == len(raw)
    assert [row[0] for row in observed] == [0, 65536, 131072, len(raw)]
    assert max(row[1] for row in observed) <= 65536
    assert report['capture']['captured_bytes'] == sum(len(raw) for raw in model.source_files.values())
    assert not report['capture']['atomic_project_snapshot'] and not report['durable_checkpoint']


@pytest.mark.parametrize('units', [0, 1, 3])
def test_incomplete_capture_cannot_make_a_plan_or_work_manifest(recorded, tmp_path, units):
    model = large_project(tmp_path / 'project'); before = inventory(tmp_path)
    with no_write_attempts(), BaselineSnapshotTask(model, block_bytes=2) as task:
        if units: task.advance(units)
        for call in (lambda: task.prepare_working_plan(**options()),
                     lambda: task.prepare_work(registry(), **options())):
            with pytest.raises(ModelError) as error: call()
            assert error.value.reason == 'baseline_snapshot_incomplete'
        assert not task.state['source_binding_verified']
        assert not task.state['capture']['complete']
    assert inventory(tmp_path) == before


def test_actual_captured_bytes_must_match_the_owned_model(tmp_path):
    root = tmp_path / 'project'; model = project(root); path = model.documents[0].path
    (root / path).write_bytes(model.documents[0].content + b' '); before = inventory(tmp_path)
    with no_write_attempts(), BaselineSnapshotTask(model) as task:
        with pytest.raises(BaselineSnapshotConflict) as error: finish(task)
        assert error.value.exit_code == 6 and error.value.reason == 'baseline_snapshot_source_changed'
        assert error.value.path == path and not task.state['source_binding_verified']
        with pytest.raises(BaselineSnapshotConflict): task.prepare_working_plan(**options())
    assert inventory(tmp_path) == before


def test_missing_input_is_reported_without_publishing_any_baseline(tmp_path):
    root = tmp_path / 'project'; model = project(root); path = model.documents[0].path
    (root / path).unlink(); before = inventory(tmp_path)
    with no_write_attempts(), BaselineSnapshotTask(model) as task:
        with pytest.raises(SnapshotCaptureError) as error: finish(task)
        assert error.value.reason == 'source_missing' and error.value.path == path
        assert not task.state['source_binding_verified']
    assert inventory(tmp_path) == before


def test_replaced_source_root_is_not_accepted_as_the_original_model(tmp_path):
    root = tmp_path / 'project'; model = project(root)
    root.rename(tmp_path / 'original'); root.mkdir()
    with no_write_attempts(), pytest.raises(BaselineSnapshotConflict) as error: BaselineSnapshotTask(model)
    assert error.value.reason == 'baseline_snapshot_root_changed' and error.value.exit_code == 6


def test_closed_partial_capture_cannot_be_promoted_by_detached_progress(tmp_path):
    model = project(tmp_path / 'project'); task = BaselineSnapshotTask(model, block_bytes=1)
    task.advance(1); state = task.state; state['source_binding_verified'] = True
    state['capture']['complete'] = True; task.close()
    assert not task.state['source_binding_verified'] and task.state['capture']['closed']
    with no_write_attempts(), pytest.raises(ModelError) as error: task.prepare_working_plan(**options())
    assert error.value.reason == 'baseline_snapshot_incomplete'
    with pytest.raises(SnapshotCaptureError): task.advance(1)


def test_sealed_owned_inputs_prepare_work_without_rereading_a_later_tree(recorded, tmp_path):
    root = tmp_path / 'project'; model = project(root)
    with BaselineSnapshotTask(model) as task:
        finish(task); original = task.prepare_work(registry(), **options())
    shutil.rmtree(root)
    with no_write_attempts(): later = task.prepare_work(registry(), **options())
    assert_same_preparation(later, original)
    assert not root.exists() and not task.state['write_authorized']


@pytest.mark.parametrize('copying', [copy.copy, copy.deepcopy, pickle.dumps])
def test_live_capture_is_not_a_serialized_durable_checkpoint(tmp_path, copying):
    model = project(tmp_path / 'project')
    with BaselineSnapshotTask(model) as task, pytest.raises(TypeError): copying(task)


@pytest.mark.parametrize('configured', [False, True])
def test_fresh_work_controllers_publish_exact_saved_baseline_once(recorded, tmp_path, configured):
    root = tmp_path / 'project'; model = variant_project(root) if configured else project(root)
    fields = options(**({'configuration_id': aid('configuration', 2)} if configured else {}))
    with BaselineSnapshotTask(model, block_bytes=31) as task:
        finish(task, 7); initial = task.prepare_work(registry(), **fields)
    plan = read_plan(initial.as_dict(), initial.objects); before = inventory(root)
    directory = tmp_path / 'work'; store = checkpoint(root, initial, directory); store.publish(initial)
    arguments = dict(registry=registry(), model=model, actor=ACTOR, request_id=fields['request_id'])
    previous = initial
    for generation in (1, 2):
        fresh = checkpoint(root, initial, directory)
        current = advance_baseline_work(fresh, **arguments)
        assert current.as_dict()['checkpoint_generation'] == generation
        assert len(current.entries('remaining')) == 2 - generation
        assert all(current.objects[k] == v for k, v in previous.objects.items())
        assert inventory(root) == before
        previous = current
    result = publish_baseline_work(checkpoint(root, initial, directory), **arguments,
        transaction_id='txn-baseline-work', authority=ALLOW).as_dict()
    assert result['publication_performed'] and result['transaction']['commit_completed']
    operation = plan.data['operations'][0]; record = operation['record']
    assert (root / artifact_path('baseline', record['id'], 'SR')).read_bytes() == canonical_json_bytes(record)
    for item in operation['objects']: assert (root / item['path']).read_bytes() == b64decode(item['bytes_base64'])
    after = inventory(root)
    with no_write_attempts():
        repeated = publish_baseline_work(checkpoint(root, initial, directory), **arguments,
            transaction_id='different-requested-transaction', authority=ALLOW).as_dict()
    assert not repeated['publication_performed'] and inventory(root) == after
    assert repeated['transaction']['transaction_id'] == 'txn-baseline-work'


def test_invalid_target_cannot_become_a_ready_work_preparation(recorded, tmp_path):
    root = tmp_path / 'project'; model = project(root, broken=True); before = inventory(tmp_path)
    with no_write_attempts(), BaselineSnapshotTask(model) as task:
        finish(task)
        for call in (lambda: task.prepare_working_plan(**options()),
                     lambda: task.prepare_work(registry(), **options())):
            with pytest.raises(ModelError) as error: call()
            assert error.value.reason == 'missing_field'
            assert error.value.pointer == '/artifacts/0/statement'
    assert inventory(tmp_path) == before


def test_actual_target_gate_refusal_cannot_create_a_work_manifest(recorded, tmp_path):
    root = tmp_path / 'project'; model = project(root); before = inventory(tmp_path)
    gate = ModelGate('lifecycle', 'deny-baseline',
        lambda c: c.dependency_result({key: list(c.all_ids) for key in c.subjects}),
        lambda c: c.result([{'reason': 'baseline_withheld', 'severity': 'error'}]))
    with no_write_attempts(), BaselineSnapshotTask(model) as task:
        finish(task)
        assert not task.prepare_working_plan(**options(gates=(gate,)))['target_validated']
        with pytest.raises(ModelError) as error: task.prepare_work(registry(), **options(gates=(gate,)))
    assert error.value.reason == 'baseline_snapshot_target_validation_required'
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('mode', ['core', 'pyz'])
def test_capture_and_native_plan_parity_run_in_isolated_core_and_pyz(tmp_path, mode):
    root = tmp_path / 'project'; model = project(root)
    code = '''from pathlib import Path
from specroad.archive.work import BaselineSnapshotTask
from specroad.archive.creation import prepare_working_baseline
from specroad.changes import TargetModel
from specroad.model.canonical import canonical_json_bytes
from specroad.model.model_manifest import ProjectReadBinding
from specroad.model.language_registry import LanguageRegistry
from specroad.profiles import ProfileResource,compose_profiles
from specroad.validation import ModelDocument
'''
    code += 'configuration=' + repr(model.configuration.data) + '\n'
    code += 'documents=' + repr([(d.path, d.content) for d in model.documents]) + '\n'
    code += 'resources=' + repr([(d.path, d.content) for d in model.resource_files]) + '\n'
    code += 'root=Path(' + repr(str(root)) + ')\noptions=' + repr(options()) + '\n'
    code += '''mapping=dict(resources);data=configuration['language_registry']
registry=LanguageRegistry(mapping[data['path']],expected_sha256=data['sha256'],expected_version=data['registry_version'])
profile=ProfileResource(mapping['profiles/core.json']);info=root.stat()
model=TargetModel(canonical_json_bytes(configuration),ProjectReadBinding(configuration['project_id'],str(root),(info.st_dev,info.st_ino)),
    [ModelDocument(p,b) for p,b in documents],profile=compose_profiles([profile],core_key=profile.key,language_registry=registry),
    resource_files=[ModelDocument(p,b) for p,b in resources])
with BaselineSnapshotTask(model,block_bytes=17) as task:
    while not task.state['source_binding_verified']: task.advance(2)
    assert task.prepare_working_plan(**options)==prepare_working_baseline(model,**options)
    assert not task.state['baseline_created'] and not task.state['write_authorized']
'''
    if mode == 'core': result = run_core(code, tmp_path, capture=True)
    else:
        _, package = build_distribution(tmp_path / 'distribution')
        result = run_python(['-I', '-S', '-B', '-c', 'import sys;sys.path.insert(0,' + repr(str(package)) + ')\n' + code], tmp_path, capture=True)
    assert result.returncode == 0, result.stderr
