"""Observed blockers, actual post-failure checkpoints and no empty progress."""

import errno
import json

import pytest

from specroad import _build
from specroad.cli.requests import CommandRequest
from specroad.runtime.consumption import InvocationConsumption, WorkConsumption
from specroad.security import SafetyViolation
from specroad.work.manifest import _tree
from specroad.work.progress import advance_read_only_work_outcome
from specroad.work.resume import WorkResumeError
from support.read_only import inventory, no_write_attempts
from test_work_checkpoints_right import documents, point_record, put
from test_work_manifest import sealed
from test_work_progress import ticking, unknown
from test_work_resume import recorded, setup


def outcome(store, *, sampler=None):
    call = WorkConsumption(sampler=ticking() if sampler is None else sampler).begin({'--step-cpu-ms': 1})
    try:
        value = advance_read_only_work_outcome(store, call)
    finally:
        call.finish()
    return value


def test_complete_unit_or_reused_result_is_separate_from_global_work_completion(recorded, tmp_path, monkeypatch):
    initial, _, location, store = setup(tmp_path)
    first = outcome(store)
    assert first['state'] == 'unit_result_available' and first['exit_code'] == 0
    assert first['blocker'] is None and first['window']['progress_made']
    assert first['global_finalization_required'] and first['window']['step']['work_state'] == 'running'
    before = inventory(location.path)
    def forbidden(*args, **kwargs):
        raise AssertionError('completed unit recomputed')
    monkeypatch.setattr('specroad.work.resume.execute_request', forbidden)
    again = outcome(store, sampler=unknown)
    assert again['state'] == 'unit_result_available' and not again['window']['progress_made']
    assert again['window']['step']['command_outcome'] == first['window']['step']['command_outcome']
    assert again['window']['step']['checkpoint_generation'] == 1 and inventory(location.path) == before


ERRNOS = [errno.ENOSPC, errno.ENOMEM, errno.EMFILE, errno.ENFILE, errno.EACCES,
          errno.EPERM, errno.EROFS, errno.ENOENT, errno.EIO]
if hasattr(errno, 'EDQUOT'):
    ERRNOS.append(errno.EDQUOT)


@pytest.mark.parametrize('number', ERRNOS)
def test_observed_publication_resource_failure_preserves_the_actual_prior_checkpoint(recorded, tmp_path, monkeypatch, number):
    initial, roots, location, store = setup(tmp_path)
    before = inventory(tmp_path);attempts = []
    def refuse(*args, **kwargs):
        attempts.append(True)
        raise OSError(number, 'labelled publication resource failure')
    monkeypatch.setattr('specroad.work.checkpoints._write_new', refuse)
    result = outcome(store);blocker = result['blocker']
    assert result['state'] == 'blocked' and result['exit_code'] == 5 and result['window'] is None
    assert attempts == [True] and blocker['native_errno'] == number
    assert blocker['failure_basis'] == 'observed_exception_from_resume'
    assert not blocker['automatic_retry_performed'] and not blocker['blocker_persisted']
    assert blocker['smallest_unit_attempted'] is None and not blocker['minimum_resources_known']
    assert blocker['required_action'] and blocker['retained']['status'] == 'verified_storage_chain'
    assert blocker['retained']['checkpoint']['checkpoint_generation'] == 0
    assert blocker['retained']['checkpoint']['checkpoint_sha256'] == initial.as_dict()['checkpoint_sha256']
    assert not blocker['project_writes_performed'] and not blocker['critical_data_deleted']
    assert store.read().raw == initial.raw and inventory(tmp_path) == before


def test_observed_memory_refusal_does_not_reexecute_until_a_new_explicit_call(recorded, tmp_path, monkeypatch):
    initial, _, location, store = setup(tmp_path);attempts = []
    def refuse(*args, **kwargs):
        attempts.append(True)
        raise MemoryError('labelled allocation refusal inside resume')
    before = inventory(location.path)
    with monkeypatch.context() as scoped:
        scoped.setattr('specroad.work.resume.execute_request', refuse)
        result = outcome(store)
    assert attempts == [True] and result['blocker']['blocked_reason'] == 'memory_unavailable'
    assert result['blocker']['native_errno'] is None and inventory(location.path) == before
    assert store.read().raw == initial.raw
    after_remedy = outcome(store)
    assert after_remedy['state'] == 'unit_result_available' and after_remedy['window']['progress_made']


def test_error_after_pointer_replacement_reports_new_actual_generation_without_rollback(recorded, tmp_path, monkeypatch):
    _, _, location, store = setup(tmp_path)
    from specroad.work import checkpoints
    native = checkpoints.replace_bound_image;attempts = []
    def committed_then_failed(*args, **kwargs):
        native(*args, **kwargs)
        attempts.append(True)
        raise OSError(errno.EIO, 'labelled failure after actual atomic publication')
    with monkeypatch.context() as scoped:
        scoped.setattr(checkpoints, 'replace_bound_image', committed_then_failed)
        result = outcome(store)
    assert result['state'] == 'blocked' and attempts == [True]
    saved = store.read();retained = result['blocker']['retained']
    assert retained['status'] == 'verified_storage_chain'
    assert retained['checkpoint']['checkpoint_generation'] == saved.as_dict()['checkpoint_generation'] == 1
    assert retained['checkpoint']['checkpoint_sha256'] == saved.as_dict()['checkpoint_sha256']
    before = inventory(location.path)
    def forbidden(*args, **kwargs):
        raise AssertionError('durably saved output was recomputed after late error')
    monkeypatch.setattr('specroad.work.resume.execute_request', forbidden)
    again = outcome(store)
    assert again['state'] == 'unit_result_available' and not again['window']['progress_made']
    assert store.read().raw == saved.raw and inventory(location.path) == before


def test_missing_actual_work_root_reports_unavailable_storage_without_allocating(recorded, tmp_path):
    _, _, _, store = setup(tmp_path, publish=False)
    before = inventory(tmp_path)
    with no_write_attempts():
        result = outcome(store)
    assert result['state'] == 'blocked' and result['blocker']['native_errno'] == errno.ENOENT
    assert result['blocker']['retained']['status'] == 'unavailable'
    assert result['blocker']['retained']['checkpoint'] is None and inventory(tmp_path) == before


def test_failed_readback_is_not_reported_as_a_verified_old_checkpoint(recorded, tmp_path, monkeypatch):
    initial, _, _, store = setup(tmp_path)
    native = store.read;reads = []
    def reading():
        reads.append(True)
        if len(reads) > 1:
            raise OSError(errno.EIO, 'labelled inspection unavailable')
        return native()
    def refuse(*args, **kwargs):
        raise OSError(errno.ENOSPC, 'labelled write unavailable')
    with monkeypatch.context() as scoped:
        scoped.setattr(store, 'read', reading)
        scoped.setattr('specroad.work.checkpoints._write_new', refuse)
        result = outcome(store)
    assert reads == [True, True] and result['blocker']['native_errno'] == errno.ENOSPC
    retained = result['blocker']['retained']
    assert retained['status'] == 'unavailable' and retained['checkpoint'] is None
    assert retained['error']['native_errno'] == errno.EIO
    assert store.read().raw == initial.raw


@pytest.mark.parametrize('failure', [OSError(errno.EINVAL, 'not a classified resource failure'),
                                    RuntimeError('labelled implementation failure'), KeyboardInterrupt()])
def test_unclassified_or_interrupted_execution_keeps_its_original_exception(recorded, tmp_path, monkeypatch, failure):
    initial, _, location, store = setup(tmp_path);before = inventory(location.path)
    def refuse(*args, **kwargs):
        raise failure
    monkeypatch.setattr('specroad.work.resume.execute_request', refuse)
    with pytest.raises(type(failure)) as caught:
        outcome(store)
    assert caught.value is failure and store.read().raw == initial.raw
    assert inventory(location.path) == before


@pytest.mark.parametrize('edge', ['start', 'end'])
def test_measurement_failure_does_not_masquerade_as_a_resume_resource_blocker(recorded, tmp_path, monkeypatch, edge):
    initial, _, _, store = setup(tmp_path);native = InvocationConsumption.control
    failure = OSError(errno.ENOSPC, 'labelled observation failure')
    def failing(self, point):
        if point.phase == 'work_unit' and point.edge == edge:
            raise failure
        return native(self, point)
    monkeypatch.setattr(InvocationConsumption, 'control', failing)
    with pytest.raises(OSError) as caught:
        outcome(store)
    assert caught.value is failure
    assert store.read().as_dict()['checkpoint_generation'] == (0 if edge == 'start' else 1)


def test_projection_failure_keeps_confirmed_bytes_and_propagates_instead_of_faking_blocker(recorded, tmp_path, monkeypatch):
    _, _, _, store = setup(tmp_path)
    failure = MemoryError('labelled result projection failure')
    def refuse(*args, **kwargs):
        raise failure
    with monkeypatch.context() as scoped:
        scoped.setattr('specroad.work.progress.canonical_json_bytes', refuse)
        with pytest.raises(MemoryError) as caught:
            outcome(store)
    assert caught.value is failure and store.read().as_dict()['checkpoint_generation'] == 1
    assert not outcome(store)['window']['progress_made']


def test_unsafe_work_data_stays_a_safety_failure_and_is_never_removed(recorded, tmp_path):
    _, roots, location, store = setup(tmp_path)
    (location.path / 'objects/foreign').symlink_to(roots[0].root / 'specroad.json')
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(SafetyViolation):
        outcome(store)
    assert inventory(tmp_path) == before


def test_incompatible_runtime_stays_a_conflict_instead_of_a_resource_blocker(recorded, tmp_path, monkeypatch):
    _, _, _, store = setup(tmp_path);before = inventory(tmp_path)
    monkeypatch.setattr(_build, 'BUILD_METADATA', {'format_version': 1,
        'hash_algorithm': 'specroad-dev-payload-v1', 'build_sha256': 'd' * 64})
    with no_write_attempts(), pytest.raises(WorkResumeError) as caught:
        outcome(store)
    assert caught.value.exit_code == 6 and inventory(tmp_path) == before


@pytest.mark.parametrize('change', ['duplicate_unit', 'empty_generation'])
def test_self_hashed_duplicate_or_empty_progress_cannot_become_a_new_window(recorded, tmp_path, monkeypatch, change):
    _, _, location, store = setup(tmp_path);outcome(store)
    current = store.read();value = current.as_dict();objects = dict(current.objects)
    pointer,record = documents(location.path)
    if change == 'duplicate_unit':
        completed = current.entries('completed') * 2
        reference = _tree('completed', completed, objects)
        value['manifests']['completed'] = reference;value['completed_manifest_sha256'] = reference['sha256']
        value['progress']['completed_units'] = 2
    else:
        value['checkpoint_generation'] = 2
        record['checkpoint_generation'] = 2;record['parent'] = dict(pointer['checkpoint'])
        pointer['checkpoint_generation'] = 2
    raw = sealed(value);semantic = json.loads(raw)['checkpoint_sha256']
    record['manifest'] = put(location.path, 'objects', raw)
    index = {};reference = _tree('checkpoint-objects', [
        {'sha256':digest,'size':len(content)} for digest,content in sorted(objects.items())], index)
    for content in [*objects.values(), *index.values()]:
        put(location.path, 'objects', content)
    record['objects'] = reference;record['checkpoint_sha256'] = semantic
    pointer['checkpoint_sha256'] = semantic;point_record(location.path,pointer,record)
    before = inventory(location.path)
    def forbidden(*args, **kwargs):
        raise AssertionError('invalid progress executed the handler')
    monkeypatch.setattr('specroad.work.resume.execute_request', forbidden)
    with no_write_attempts(), pytest.raises(WorkResumeError) as caught:
        outcome(store)
    assert caught.value.exit_code == 6 and inventory(location.path) == before


def test_incomplete_command_keeps_usage_failure_instead_of_a_resource_blocker(recorded, tmp_path):
    initial, _, location, store = setup(tmp_path,
        CommandRequest('schema.show', arguments={'schema_id':'not-a-schema'}))
    before = inventory(location.path)
    with pytest.raises(WorkResumeError) as caught:
        outcome(store)
    assert caught.value.exit_code == 2 and caught.value.reason == 'command_did_not_complete'
    assert store.read().raw == initial.raw and inventory(location.path) == before
