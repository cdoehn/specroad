"""Actual adapter process loss, native recovery, and bound completion reports."""

import os
from pathlib import Path

import pytest

from specroad.changes import ChangePlan, read_transaction_completion, transaction_preflight
from specroad.cli.contracts import CommandClass
from specroad.security import ProjectBoundary
from specroad.storage.project import ProjectSource
from specroad.work import publication
from specroad.work.checkpoints import CheckpointStore
from specroad.work.manifest import read_work_manifest
from specroad.work.resume import WorkResumeError, _runtime_build
from specroad.work.root import WorkDirectory
from support.automatic_recovery import current_model
from support.publication import TRANSACTION, files
from support.read_only import inventory, no_write_attempts
from support.targets import SCOPE
from support.work_publication_process import CUTS, child
from support.writer_boundaries import child as recovery_child
from test_work_publication import setup, prepare, ready, publish
from test_work_resume import recorded
from test_work_resume_right import registry


def restore(root, packet):
    # The independently emitted initial binding predates native publication.
    # Never invent a new initial plan from the current Work pointer or targets.
    reg = registry()
    initial = read_work_manifest(bytes.fromhex(packet['initial']),
        {p: bytes.fromhex(b) for p, b in packet['initial_objects'].items()},
        registry=reg, expected_tool_build=_runtime_build())
    project = root / 'project'
    store = CheckpointStore(WorkDirectory(initial, protected_roots=(ProjectBoundary(project),),
                                         directory=root / 'work'), initial)
    return reg, ChangePlan(bytes.fromhex(packet['plan'])), store


@pytest.mark.parametrize('cut', ['pause_one', 'pause_two'])
def test_preparation_pause_releases_project_and_work_for_a_fresh_process(recorded, tmp_path, cut):
    packet, = child(tmp_path, cut)
    assert packet['pid'] != os.getpid()
    project = tmp_path / 'project'; before = inventory(project)
    reg, plan, store = restore(tmp_path, packet)
    with no_write_attempts():
        gate = transaction_preflight(project, command_class=CommandClass.READ_ONLY).data
        model = current_model(project)
        checkpoint = store.read()
    assert gate['exit_code'] == 0 and not gate['recovery_required']
    assert model.manifest(model.artifacts, SCOPE).sha256 == packet['base_root']
    assert checkpoint.raw == bytes.fromhex(packet['checkpoint'])
    assert checkpoint.as_dict()['checkpoint_generation'] == (1 if cut == 'pause_one' else 2)
    assert not (project / '.specroad').exists()
    assert not (tmp_path / 'work/work-lock.json').exists()
    final_preparation = prepare(store, reg, model, plan)
    assert final_preparation.as_dict()['checkpoint_generation'] == 2
    assert inventory(project) == before
    result = publish(store, reg, model, plan).as_dict()
    assert result['publication_performed'] and result['transaction']['commit_completed']
    assert files(project) == {p: bytes.fromhex(b) for p, b in packet['after'].items()}
    assert store.read().raw == final_preparation.raw


@pytest.mark.parametrize('cut', CUTS)
def test_actual_process_loss_uses_native_recovery_before_new_publication(recorded, tmp_path, cut):
    packet, stopped = child(tmp_path, cut)
    assert packet['pid'] == stopped['pid'] != os.getpid() and stopped['cut'] == cut
    project = tmp_path / 'project'
    reg, plan, store = restore(tmp_path, packet)
    checkpoint = store.read(); work_before = inventory(tmp_path / 'work')
    assert checkpoint.raw == bytes.fromhex(packet['checkpoint'])
    assert checkpoint.as_dict()['checkpoint_generation'] == 2
    assert checkpoint.as_dict()['state'] == 'running'
    gate = transaction_preflight(project, command_class=CommandClass.READ_ONLY).data
    # A real process death leaves the native owner record. This remains an
    # explicit Recovery case even after committed receipts or output cleanup.
    assert (project / '.specroad/locks/project.json').exists()
    assert gate['exit_code'] == 5 and gate['recovery_required']
    before = inventory(tmp_path)
    model = current_model(project)  # Raw fixture reconstruction, not a regular read permission.
    with no_write_attempts(), pytest.raises(WorkResumeError) as blocked:
        prepare(store, reg, model, plan)
    assert blocked.value.as_dict() == {'reason': 'normative_transaction_requires_recovery', 'exit_code': 5}
    assert inventory(tmp_path) == before
    if cut in ('committed', 'cleanup'):
        with no_write_attempts():
            replay = publish(store, reg, model, plan).as_dict()
        assert not replay['publication_performed']
        assert replay['result_object']['transaction_id'] == TRANSACTION
        assert replay['transaction']['cleanup_required'] == (cut == 'committed')
    else:
        with no_write_attempts(), pytest.raises(WorkResumeError) as blocked:
            publish(store, reg, model, plan)
        assert blocked.value.exit_code == 5
        assert not (project / '.specroad/requests').exists()
    assert inventory(tmp_path) == before
    if cut == 'first_target':
        actual = {p: b.hex() for p, b in files(project).items()}
        assert actual != packet['before'] and actual != packet['after']

    recovered, = recovery_child(project, 'recover')
    assert recovered['pid'] not in (packet['pid'], os.getpid())
    outcome = 'base' if cut in ('building', 'prepared', 'first_target') else 'target'
    assert recovered['outcome'] == outcome
    assert recovered['files'] == packet['before' if outcome == 'base' else 'after']
    assert recovered['model_root'] == packet['base_root' if outcome == 'base' else 'target_root']
    assert inventory(tmp_path / 'work') == work_before and store.read().raw == checkpoint.raw
    assert transaction_preflight(project, command_class=CommandClass.READ_ONLY).exit_code == 0
    fresh = current_model(project)
    result = publish(store, registry(), fresh, plan, transaction_id='txn-after-recovery').as_dict()
    assert result['publication_performed'] == (outcome == 'base')
    assert result['result_object']['transaction_id'] == ('txn-after-recovery' if outcome == 'base' else TRANSACTION)
    assert result['result_object']['request_id'] == plan.data['request_id']
    assert files(project) == {p: bytes.fromhex(b) for p, b in packet['after'].items()}
    assert store.read().raw == checkpoint.raw and inventory(tmp_path / 'work') == work_before
    before = inventory(tmp_path)
    with no_write_attempts():
        replay = publish(store, registry(), current_model(project), plan).as_dict()
    assert not replay['publication_performed'] and replay['result_object'] == result['result_object']
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('fresh', [False, True])
@pytest.mark.parametrize('other_transaction', ['txn-work-native', 'txn-other'])
def test_individually_valid_but_different_completion_observations_cannot_be_combined(recorded, tmp_path, monkeypatch, fresh, other_transaction):
    model, plan, check, reg, _, _, store = setup(tmp_path / 'original', multi=True)
    checkpoint = ready(store, reg, model, plan)
    other_model, other_plan, _, other_reg, _, _, other_store = setup(tmp_path / 'other', multi=True)
    ready(other_store, other_reg, other_model, other_plan)
    publish(other_store, other_reg, other_model, other_plan, transaction_id=other_transaction)
    # Both observations come from real completed native transactions. Inject a
    # conflicting observation, not forged execution bytes or a fake receipt.
    other_proof = read_transaction_completion(ProjectSource(other_model.binding.source_root), other_transaction)
    if not fresh:
        publish(store, reg, model, plan)
    before_other = inventory(tmp_path / 'other')
    native = publication.cleanup_completed_transaction
    with monkeypatch.context() as patch:
        if fresh:
            def changed_observation(*args, **kwargs):
                native(*args, **kwargs)
                return other_proof
            patch.setattr(publication, 'cleanup_completed_transaction', changed_observation)
            with pytest.raises(WorkResumeError) as caught:
                publish(store, reg, model, plan)
        else:
            before = inventory(tmp_path)
            patch.setattr(publication, 'read_transaction_completion', lambda *a, **k: other_proof)
            with no_write_attempts(), pytest.raises(WorkResumeError) as caught:
                publish(store, reg, model, plan)
            assert inventory(tmp_path) == before
    assert caught.value.as_dict() == {'reason': 'normative_receipt_binding_changed', 'exit_code': 6}
    actual = read_transaction_completion(ProjectSource(model.binding.source_root), 'txn-work-native')
    assert actual.data['receipts']['request'] != other_proof.data['receipts']['request']
    assert files(Path(model.binding.source_root)) == {**model.source_files,
        **{d.path: d.content for d in check.request.documents}}
    assert store.read().raw == checkpoint.raw and inventory(tmp_path / 'other') == before_other
    before = inventory(tmp_path)
    with no_write_attempts():
        replay = publish(store, reg, model, plan).as_dict()
    assert not replay['publication_performed'] and replay['transaction']['commit_completed']
    assert replay['result_object']['transaction_id'] == 'txn-work-native'
    assert inventory(tmp_path) == before
