"""Stored Work observations and real cancellation without semantic success.

Fixtures use explicit host registrations and labelled build compatibility. All
native locks, checkpoints, transactions and child-process cuts are real.
"""

import errno
from hashlib import sha256
import json
import os
from pathlib import Path

import pytest

from specroad import _build
from specroad.changes import ProjectLockError
from specroad.changes._lock_files import LockFiles
from specroad.model.canonical import canonical_json_bytes
from specroad.work import control
from specroad.work._cancellation import cancellation_candidate
from specroad.work.checkpoints import CheckpointStore
from specroad.work.control import (inspect_work_status, cancel_read_only_work,
                                  cancel_normative_preparation)
from specroad.work.finalization import finalize_read_only_work
from specroad.work.manifest import WorkManifestError, read_work_successor
from specroad.work.resume import WorkResumeError, resume_read_only_work
from specroad.work.root import WorkDirectory
from support.automatic_recovery import current_model
from support.project_locks import attempt
from support.read_only import inventory, no_write_attempts
from support.work_publication_process import child
from test_work_manifest import sealed
from test_work_publication import setup as normative_setup, prepare, ready, publish, arguments
from test_work_publication_right import restore
from test_work_resume import recorded, setup, REQUESTS


def forbidden(*args, **kwargs):
    raise AssertionError('Control must not execute semantic work')


def cancel_native(store, reg, model, plan, reason='Explicit owned cancellation'):
    return cancel_normative_preparation(store, reason=reason, **arguments(reg, model, plan))


@pytest.mark.parametrize('generation', [0, 1, 2])
def test_status_observes_exact_stored_state_without_handler_or_project_access(recorded, tmp_path, monkeypatch, generation):
    _, _, location, store = setup(tmp_path)
    if generation:
        resume_read_only_work(store)
    if generation == 2:
        finalize_read_only_work(store)
    current = store.read(); expected = current.as_dict(); before = inventory(tmp_path)
    monkeypatch.setattr('specroad.work.resume.execute_request', forbidden)
    monkeypatch.setattr(control, '_source', forbidden)
    with no_write_attempts():
        value = inspect_work_status(store)
    for key in ('work_id', 'checkpoint_sha256', 'checkpoint_generation', 'command_id',
                'command_class', 'state', 'tool_build', 'source_bindings', 'progress',
                'remaining_manifest_sha256', 'next_action', 'blocked_reason'):
        assert value[key] == expected[key]
    assert value['work_dir'] == str(location.path)
    assert value['remaining_manifest'] == expected['manifests']['remaining']
    assert value['verification_scope'] == 'persisted_work_chain'
    assert value['cancellation'] is None and not value['native_transaction_checked']
    assert not value['action_is_executable_command'] and not value['command_execution_performed']
    assert not value['project_writes_performed'] and inventory(tmp_path) == before
    value['progress']['completed_units'] = 900
    assert inspect_work_status(store)['progress'] == expected['progress']


@pytest.mark.parametrize('command_request', REQUESTS, ids=lambda value: value.command_id)
def test_cancel_preserves_entire_pending_work_and_prevents_handler_execution(recorded, tmp_path, monkeypatch, command_request):
    initial, roots, location, store = setup(tmp_path, command_request)
    prior = initial.as_dict(); old = inventory(location.path); project = inventory(roots[0].root)
    monkeypatch.setattr('specroad.work.resume.execute_request', forbidden)
    value = cancel_read_only_work(store, reason='Requested stop')
    current = store.read(); saved = current.as_dict()
    assert value['state'] == saved['state'] == 'cancelled' and value['next_action'] is None
    assert saved['checkpoint_generation'] == 1 and saved['progress'] == prior['progress']
    assert saved['manifests'] == prior['manifests']
    assert all(current.objects[k] == v for k, v in initial.objects.items())
    for path, mode, raw, target in old:
        if raw is not None and path != 'work.json':
            assert (location.path / path).read_bytes() == raw
    receipt = value['cancellation']
    assert receipt['reason'] == 'Requested stop'
    assert receipt['source_checkpoint_generation'] == 0
    assert receipt['source_checkpoint_sha256'] == prior['checkpoint_sha256']
    assert receipt['remaining_manifest_sha256'] == prior['remaining_manifest_sha256']
    assert 'outcome' not in receipt and 'exit_code' not in receipt
    assert inventory(roots[0].root) == project
    fresh = CheckpointStore(WorkDirectory(initial, protected_roots=roots, directory=location.path), initial)
    before = inventory(tmp_path)
    with no_write_attempts():
        assert inspect_work_status(fresh) == value
        assert cancel_read_only_work(fresh, reason='Requested stop') == value
        with pytest.raises(WorkResumeError) as caught:
            resume_read_only_work(fresh)
        assert caught.value.reason == 'work_cannot_resume'
        with pytest.raises(WorkResumeError) as caught:
            finalize_read_only_work(fresh)
        assert caught.value.reason == 'work_cannot_complete'
    assert inventory(tmp_path) == before


def test_cancel_after_handler_retains_its_evidence_without_relabeling_it_success(recorded, tmp_path, monkeypatch):
    _, _, _, store = setup(tmp_path)
    previous = resume_read_only_work(store).manifest
    monkeypatch.setattr('specroad.work.resume.execute_request', forbidden)
    value = cancel_read_only_work(store, reason='Do not finalize')
    current = store.read()
    assert value['state'] == 'cancelled' and value['checkpoint_generation'] == 2
    assert value['progress'] == {'completed_units': 1, 'total_units': 1}
    assert all(current.objects[k] == v for k, v in previous.objects.items())
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(WorkResumeError):
        resume_read_only_work(store)
    with no_write_attempts(), pytest.raises(WorkResumeError):
        finalize_read_only_work(store)
    with no_write_attempts(), pytest.raises(WorkResumeError) as caught:
        cancel_read_only_work(store, reason='Different reason')
    assert caught.value.reason == 'cancellation_reason_changed' and inventory(tmp_path) == before


def test_completed_work_cannot_be_cancelled(recorded, tmp_path):
    _, _, _, store = setup(tmp_path)
    resume_read_only_work(store); finalize_read_only_work(store)
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(WorkResumeError) as caught:
        cancel_read_only_work(store, reason='Too late')
    assert caught.value.reason == 'work_cannot_cancel' and inventory(tmp_path) == before


@pytest.mark.parametrize('generation', [0, 1, 2])
def test_native_preparation_cancellation_preserves_project_and_original_request(recorded, tmp_path, generation):
    model, plan, _, reg, initial, _, store = normative_setup(tmp_path, multi=True)
    for _ in range(generation):
        prepare(store, reg, model, plan)
    previous = store.read(); project = Path(model.binding.source_root); before = inventory(project)
    value = cancel_native(store, reg, model, plan); current = store.read()
    assert value['state'] == 'cancelled' and value['checkpoint_generation'] == generation + 1
    assert value['progress'] == previous.as_dict()['progress']
    assert current.as_dict()['manifests'] == previous.as_dict()['manifests']
    for field in ('actor', 'request_id', 'operations_sha256', 'plan_binding'):
        assert value['cancellation']['binding'][field] == initial.as_dict()[field]
    assert all(current.objects[k] == v for k, v in previous.objects.items())
    assert inventory(project) == before and not (project / '.specroad').exists()
    all_before = inventory(tmp_path)
    with no_write_attempts():
        assert cancel_native(store, reg, model, plan) == value
        with pytest.raises(WorkResumeError):
            prepare(store, reg, model, plan)
        with pytest.raises(WorkResumeError):
            publish(store, reg, model, plan)
    assert inventory(tmp_path) == all_before


def test_native_commit_is_not_undone_or_relabelled_by_cancel(recorded, tmp_path):
    model, plan, _, reg, _, _, store = normative_setup(tmp_path, multi=True)
    ready(store, reg, model, plan); publish(store, reg, model, plan)
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(WorkResumeError) as caught:
        cancel_native(store, reg, model, plan)
    assert caught.value.reason == 'normative_request_already_committed'
    assert inventory(tmp_path) == before and store.read().as_dict()['state'] == 'running'


@pytest.mark.parametrize('cut', ['prepared', 'first_target', 'committed'])
def test_real_interrupted_transaction_cannot_be_unlocked_by_work_cancellation(recorded, tmp_path, cut):
    packet, stopped = child(tmp_path, cut)
    assert stopped['pid'] != os.getpid()
    reg, plan, store = restore(tmp_path, packet)
    model = current_model(tmp_path / 'project'); before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(WorkResumeError) as caught:
        cancel_native(store, reg, model, plan)
    assert caught.value.reason == 'normative_transaction_requires_recovery'
    assert caught.value.exit_code == 5
    assert inventory(tmp_path) == before and store.read().raw == bytes.fromhex(packet['checkpoint'])


def test_project_mutex_is_retained_through_real_cancellation_checkpoint(recorded, tmp_path, monkeypatch):
    model, plan, _, reg, _, _, store = normative_setup(tmp_path)
    ready(store, reg, model, plan)
    project = Path(model.binding.source_root); before = inventory(project)
    native = store._publish_held; attempts = []
    def observe(*args):
        attempts.append(attempt(project))
        result = native(*args)
        attempts.append(attempt(project))
        return result
    monkeypatch.setattr(store, '_publish_held', observe)
    value = cancel_native(store, reg, model, plan)
    assert attempts == [{'acquired': False, 'reason': 'project_lock_busy'}] * 2
    assert value['state'] == 'cancelled' and inventory(project) == before
    with no_write_attempts(), LockFiles(project) as held:
        held.acquire(); held.require_held()
    assert inventory(project) == before


def test_live_native_mutex_refuses_cancel_before_work_writes(recorded, tmp_path):
    model, plan, _, reg, _, _, store = normative_setup(tmp_path)
    project = Path(model.binding.source_root); before = inventory(tmp_path)
    with LockFiles(project) as held:
        held.acquire()
        with no_write_attempts(), pytest.raises(ProjectLockError) as caught:
            cancel_native(store, reg, model, plan)
        assert caught.value.reason == 'project_lock_busy'
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('late', [False, True])
def test_checkpoint_failure_preserves_real_cancel_state_for_inspection(recorded, tmp_path, monkeypatch, late):
    _, roots, _, store = setup(tmp_path); initial = store.read()
    before = inventory(roots[0].root); native = os.replace
    with monkeypatch.context() as patcher:
        def fail(src, dst, **kwargs):
            if dst == 'work.json':
                if late:
                    native(src, dst, **kwargs)
                raise OSError(errno.EIO, 'Owned checkpoint publication failure')
            return native(src, dst, **kwargs)
        patcher.setattr(os, 'replace', fail)
        with pytest.raises(OSError) as caught:
            cancel_read_only_work(store, reason='Explicit stop')
    assert caught.value.errno == errno.EIO and inventory(roots[0].root) == before
    status = inspect_work_status(store)
    assert status['state'] == ('cancelled' if late else 'running')
    assert status['checkpoint_generation'] == (1 if late else 0)
    if not late:
        assert store.read().raw == initial.raw
    assert cancel_read_only_work(store, reason='Explicit stop')['state'] == 'cancelled'


def test_cancel_between_resume_inspection_and_lease_prevents_handler(recorded, tmp_path, monkeypatch):
    _, _, _, store = setup(tmp_path); native = store._update
    def changed(transform):
        cancel_read_only_work(store, reason='Concurrent explicit cancellation')
        return native(transform)
    monkeypatch.setattr(store, '_update', changed)
    monkeypatch.setattr('specroad.work.resume.execute_request', forbidden)
    with pytest.raises(WorkResumeError) as caught:
        resume_read_only_work(store)
    assert caught.value.reason == 'work_cannot_resume'
    assert inspect_work_status(store)['state'] == 'cancelled'


@pytest.mark.parametrize('field', ['reason', 'binding', 'source_checkpoint_sha256', 'outcome'])
def test_cancellation_control_cannot_change_identity_source_or_claim_success(recorded, tmp_path, field):
    initial, _, _, _ = setup(tmp_path)
    candidate = cancellation_candidate(initial, 'Explicit reason')
    value = candidate.as_dict(); objects = dict(candidate.objects)
    record = json.loads(objects[value['result_parts'][0]['sha256']])
    if field == 'reason':
        record[field] = ' '
    elif field == 'binding':
        record[field]['work_id'] = 'WORK-' + '0' * 26
    elif field == 'source_checkpoint_sha256':
        record[field] = '0' * 64
    else:
        record[field] = {'status': 'success', 'exit_code': 0}
    raw = canonical_json_bytes(record); digest = sha256(raw).hexdigest(); objects[digest] = raw
    value['result_parts'] = [{'sha256': digest, 'size': len(raw)}]
    with pytest.raises(WorkManifestError):
        read_work_successor(sealed(value), objects, previous=initial,
            registry=initial._registry, expected_tool_build=initial.as_dict()['tool_build'])


@pytest.mark.parametrize('reason', [None, '', ' ', '\0'])
def test_cancel_requires_an_explicit_nonempty_reason_before_writes(recorded, tmp_path, reason):
    _, _, _, store = setup(tmp_path); before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(WorkResumeError) as caught:
        cancel_read_only_work(store, reason=reason)
    assert caught.value.exit_code == 2 and inventory(tmp_path) == before


def test_changed_runtime_cannot_inspect_or_cancel_old_work(recorded, tmp_path, monkeypatch):
    _, _, _, store = setup(tmp_path); before = inventory(tmp_path)
    monkeypatch.setattr(_build, 'BUILD_METADATA', {**_build.BUILD_METADATA, 'build_sha256': '9' * 64})
    with no_write_attempts(), pytest.raises(WorkResumeError):
        inspect_work_status(store)
    with no_write_attempts(), pytest.raises(WorkResumeError):
        cancel_read_only_work(store, reason='Explicit stop')
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('cancel', [False, True])
def test_missing_work_is_not_allocated_by_status_or_cancel(recorded, tmp_path, cancel):
    _, _, location, store = setup(tmp_path, publish=False); before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(FileNotFoundError):
        if cancel:
            cancel_read_only_work(store, reason='Explicit stop')
        else:
            inspect_work_status(store)
    assert inventory(tmp_path) == before and location.path is None
    assert not (tmp_path / 'work').exists()
