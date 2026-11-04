"""Real Work checkpoints, portable bytes, fresh native checks and one writer."""
from hashlib import sha256
import errno
import shutil

import pytest

from specroad import _build
from specroad.model.errors import ModelError
from specroad.model.canonical import canonical_json_bytes as jcs
from specroad.security import ProjectBoundary
from specroad.work.manifest import partition_work_manifest, complete_work_manifest
from specroad.work.checkpoints import CheckpointStorageError
from specroad.work.packages import export_work_package, restore_work_package
from specroad.work.migration import (resume_migration_work, migration_work_result,
                                    apply_migration_work)
from specroad.changes.schema_transition_values import SchemaTransitionError
from support.migration_verification import case, verify
from support.migration_transaction import normative, apply
from support.migration_work import create, registry, finish, publication
from support.read_only import inventory, no_write_attempts


@pytest.fixture
def recorded(monkeypatch):
    monkeypatch.setattr(_build, 'BUILD_METADATA', {'format_version': 1,
        'hash_algorithm': 'specroad-dev-payload-v1', 'build_sha256': '4' * 64})


@pytest.mark.parametrize('mode', ['plan','verify'])
def test_real_phases_equal_direct_native_results_and_preserve_source(recorded, tmp_path, mode):
    data = case(tmp_path); before = inventory(data[0]); store = create(data, tmp_path/'work', mode=mode)
    initial = store.read(); original = initial.as_dict()
    for index in range(3):
        current = resume_migration_work(store)
        assert current.as_dict()['progress'] == {'completed_units': index + 1, 'total_units': 3}
        assert current.as_dict()['work_id'] == original['work_id']
        assert current.as_dict()['input_manifest_sha256'] == original['input_manifest_sha256']
        assert current.as_dict()['state'] == 'running'
        assert inventory(data[0]) == before
    current = resume_migration_work(store)
    assert current.as_dict()['state'] == 'completed'
    with no_write_attempts():
        result = migration_work_result(store)
    assert result['planning'] == data[5].data
    assert result['verification'] == verify(data).data
    assert result['target_observation'] == ('planned_target' if mode == 'plan' else 'provided_target_bytes')
    assert not result['project_writes_performed'] and not result['write_authorized']
    assert resume_migration_work(store).raw == current.raw
    assert inventory(data[0]) == before


@pytest.mark.parametrize('mode', ['plan','verify'])
@pytest.mark.parametrize('generation', range(5))
def test_every_phase_survives_external_package_and_sandbox_loss(recorded, tmp_path, mode, generation):
    data = case(tmp_path); store = create(data, tmp_path/'first', mode=mode)
    for _ in range(generation): resume_migration_work(store)
    old = store.read(); raw = export_work_package(store)
    shutil.rmtree(tmp_path/'first')
    restored = restore_work_package(raw, expected_sha256=sha256(raw).hexdigest(),
        registry=registry(), protected_roots=(ProjectBoundary(data[0]),), directory=tmp_path/'fresh')
    assert restored.read().raw == old.raw
    finish(restored)
    result = migration_work_result(restored)
    assert result['planning'] == data[5].data and result['verification'] == verify(data).data
    assert normative(data[0]) == data[1]


def test_complete_work_then_exactly_one_real_transaction_and_historical_replay(recorded, tmp_path):
    data = case(tmp_path); store = create(data, tmp_path/'work'); finish(store)
    before = store.read().raw
    result = apply_migration_work(store, data[0], **publication(data))
    assert result['write_state'] == 'committed' and normative(data[0]) == data[6]
    project = inventory(data[0])
    replay = apply_migration_work(store, data[0], **publication(data))
    assert replay['write_state'] == 'committed'
    assert inventory(data[0]) == project and store.read().raw == before


@pytest.mark.parametrize('progress', range(4))
def test_incomplete_work_cannot_publish_or_claim_final_verification(recorded, tmp_path, progress):
    data = case(tmp_path); store = create(data, tmp_path/'work')
    for _ in range(progress): resume_migration_work(store)
    before = inventory(data[0])
    with no_write_attempts(), pytest.raises(ModelError, match='migration_work_incomplete'):
        apply_migration_work(store, data[0], **publication(data))
    assert inventory(data[0]) == before


@pytest.mark.parametrize('phase', range(3))
def test_rehashed_fabricated_completed_phase_is_not_execution_proof(recorded, tmp_path, phase):
    data = case(tmp_path); store = create(data, tmp_path/'work')
    for _ in range(phase): resume_migration_work(store)
    current = store.read(); task = current.entries('remaining')[0]
    candidate = partition_work_manifest(current, {task['unit_id']: jcs({
        'format_version': 'migration-work-phase-v1', 'phase': task['key'], 'result': {'passed': True}})})
    store.publish(candidate)
    with pytest.raises(ModelError, match='migration_work_phase_evidence_changed'):
        resume_migration_work(store)
    assert store.read().raw == candidate.raw and normative(data[0]) == data[1]


def test_forged_complete_result_is_not_a_write_capability(recorded, tmp_path):
    data = case(tmp_path); store = create(data, tmp_path/'work')
    for _ in range(3): resume_migration_work(store)
    current = store.read()
    forged = {'format_version':'migration-work-result-v1', 'command_id':'migrate.plan',
        'target_observation':'planned_target', 'planning':{'ready':True}, 'verification':{'verified':True},
        'project_writes_performed':False,'write_authorized':False,'approval_granted':False}
    store.publish(complete_work_manifest(current, forged, exit_code=0))
    before = inventory(data[0])
    with no_write_attempts(), pytest.raises(ModelError, match='migration_work_result_changed'):
        apply_migration_work(store, data[0], **publication(data))
    assert inventory(data[0]) == before


@pytest.mark.parametrize('changed', ['source','backup','authority','verify_mode'])
def test_final_publication_still_requires_fresh_native_live_bindings(recorded, tmp_path, changed):
    data = case(tmp_path); store = create(data, tmp_path/'work', mode='verify' if changed == 'verify_mode' else 'plan')
    finish(store); options = publication(data)
    if changed == 'source': (data[0]/'specroad.json').write_bytes(data[1]['specroad.json'] + b' ')
    elif changed == 'backup':
        from pathlib import Path
        Path(options['backup_path']).write_bytes(b'not a source ZIP')
    elif changed == 'authority':
        from specroad.changes.publication_values import PublicationAuthority
        options['authority'] = PublicationAuthority('synthetic-denial', '1', lambda request: False)
    before = normative(data[0])
    with pytest.raises((ModelError, SchemaTransitionError)):
        apply_migration_work(store, data[0], **options)
    assert normative(data[0]) == before


@pytest.mark.parametrize('generation', range(4))
def test_checkpoint_write_failure_retains_a_reusable_confirmed_prefix(recorded, tmp_path, monkeypatch, generation):
    data = case(tmp_path); store = create(data, tmp_path/'work')
    for _ in range(generation): resume_migration_work(store)
    old = store.read()
    from specroad.work import checkpoints
    def fail_before_publish(self, held, candidate, pointer):
        raise OSError(errno.ENOSPC, 'Synthetic full Work storage')
    with monkeypatch.context() as patch:
        patch.setattr(checkpoints.CheckpointStore, '_publish_held', fail_before_publish)
        with pytest.raises(OSError): resume_migration_work(store)
    assert store.read().raw == old.raw
    finish(store)
    assert migration_work_result(store)['planning'] == data[5].data
    assert normative(data[0]) == data[1]


def test_changed_runtime_cannot_resume_or_publish(recorded, tmp_path, monkeypatch):
    data = case(tmp_path); store = create(data, tmp_path/'work'); finish(store)
    monkeypatch.setattr(_build, 'BUILD_METADATA', {'format_version':1,
        'hash_algorithm':'specroad-dev-payload-v1','build_sha256':'5'*64})
    from specroad.work.resume import WorkResumeError
    with pytest.raises((WorkResumeError, CheckpointStorageError)):
        apply_migration_work(store, data[0], **publication(data))
    assert normative(data[0]) == data[1]


@pytest.mark.parametrize('event', ['journal:prepared:0','committed','receipts','archived'])
def test_writer_interruption_requires_native_recovery_not_work_replay(recorded, tmp_path, monkeypatch, event):
    data = case(tmp_path); store = create(data, tmp_path/'work'); finish(store)
    from specroad.changes import schema_transition
    from test_migration_transaction_right import recover
    total = len(data[2].data['operations'][0]['changes'])
    checkpoint = 'journal:committed:' + str(total) if event == 'committed' else event
    observed = []
    def stop(point):
        if point == checkpoint:
            observed.append(point)
            raise OSError('Synthetic migration publication interruption')
    with monkeypatch.context() as patch:
        patch.setattr(schema_transition, '_checkpoint', stop)
        with pytest.raises(SchemaTransitionError) as caught:
            apply_migration_work(store, data[0], **publication(data))
    assert observed == [checkpoint] and caught.value.write_state == 'unknown'
    if event != 'archived':
        with pytest.raises(SchemaTransitionError):
            apply_migration_work(store, data[0], **publication(data))
        recover(data[0], data[3])
    if event == 'journal:prepared:0':
        assert normative(data[0]) == data[1]
        # Retained recovery audit is real state: no automatic restart or replan.
        with pytest.raises(SchemaTransitionError):
            apply_migration_work(store, data[0], **publication(data))
    else:
        result = apply_migration_work(store, data[0], **publication(data))
        assert result['write_state'] == 'committed' and normative(data[0]) == data[6]


def test_actual_partial_work_object_write_keeps_confirmed_prefix(recorded, tmp_path, monkeypatch):
    import os
    data = case(tmp_path); store = create(data, tmp_path/'work'); old = store.read()
    native_write = os.write; observed = []
    def partial(fd, raw):
        if not observed and b'migration-work-phase-v1' in bytes(raw):
            observed.append(native_write(fd, raw[:17]))
            raise OSError(errno.ENOSPC, 'Synthetic interrupted Work object write')
        return native_write(fd, raw)
    with monkeypatch.context() as patch:
        patch.setattr(os, 'write', partial)
        with pytest.raises(OSError): resume_migration_work(store)
    assert observed == [17] and store.read().raw == old.raw
    assert normative(data[0]) == data[1]
    # The durable old prefix remains readable; an incomplete object may require
    # explicit storage repair. The adapter may never claim its phase completed.
    try:
        resumed = resume_migration_work(store)
    except (CheckpointStorageError, OSError) as error:
        assert str(error) and store.read().raw == old.raw
    else:
        assert resumed.as_dict()['progress']['completed_units'] == 1


def test_new_process_needs_only_bound_package_runtime_and_explicit_host(recorded, tmp_path):
    from pathlib import Path
    import json
    from support.processes import run_core
    data = case(tmp_path); store = create(data, tmp_path/'lost')
    resume_migration_work(store); resume_migration_work(store)
    raw = export_work_package(store); package = tmp_path/'saved.zip'; package.write_bytes(raw)
    old_id = store.read().as_dict()['work_id']; shutil.rmtree(tmp_path/'lost')
    tests_root = str(Path(__file__).resolve().parent)
    script = ('import json\nfrom pathlib import Path\nfrom specroad import _build\n'
        'sys.path.insert(0, ' + repr(tests_root) + ')\n'
        'from support.migration_work import registry, finish\n'
        'from specroad.security import ProjectBoundary\n'
        'from specroad.work.packages import restore_work_package\n'
        'from specroad.work.migration import migration_work_result\n'
        "_build.BUILD_METADATA={'format_version':1,'hash_algorithm':'specroad-dev-payload-v1','build_sha256':'4'*64}\n"
        'store=restore_work_package(Path(' + repr(str(package)) + ').read_bytes(), expected_sha256='
        + repr(sha256(raw).hexdigest()) + ', registry=registry(), protected_roots=(ProjectBoundary('
        + repr(str(data[0])) + '),), directory=' + repr(str(tmp_path/'new')) + ')\n'
        "finish(store)\nprint(json.dumps({'work_id':store.read().as_dict()['work_id'],'result':migration_work_result(store)}))\n")
    completed = run_core(script, tmp_path, capture=True)
    assert completed.returncode == 0, completed.stderr
    value = json.loads(completed.stdout)
    assert value['work_id'] == old_id and value['result']['planning'] == data[5].data
    assert value['result']['verification'] == verify(data).data
    assert normative(data[0]) == data[1]
