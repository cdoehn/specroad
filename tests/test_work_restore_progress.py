"""Native Restore and Work progress across actual independent process exits.

Synthetic host grants do not represent human product reviews or public CLI
readiness. Result delivery and completed Work remain explicitly pending.
"""
from base64 import b64encode, b64decode
from dataclasses import FrozenInstanceError
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
import tempfile

import pytest

from specroad import _build
from specroad.changes.recovery_values import RecoveryAuthority
from specroad.model.canonical import canonical_json_bytes
from specroad.recovery import RestoreError
from specroad.recovery._execution_store import RestoreStore
from specroad.security import ProjectBoundary
from specroad.work import restore_progress as implementation
from specroad.work.checkpoints import CheckpointStore
from specroad.work.manifest import partition_work_manifest
from specroad.work.restore import read_restore_work_manifest
from specroad.work.restore_progress import (advance_restore_work, RestoreWorkProgress,
                                          RestoreWorkProgressError)
from specroad.work.root import WorkDirectory
from support.processes import run_python
from support.read_only import inventory, no_write_attempts
from support.restore import restore_case, plan_for
from test_restore_execution import ACTOR, ALLOW, execute, files
from test_restore_execution_right import fixture
from test_work_restore_binding import registry
from test_work_restore_execution import stored, takeover, RECOVERY_ACTOR
from test_work_restore_owner import orphan
from test_work_resume import recorded, setup as read_only_store


pytestmark = pytest.mark.skipif(sys.platform != 'linux', reason='Native Linux Work/Restore leases')


def advance(store, **options):
    return advance_restore_work(store, **{'registry': registry(), 'authority': ALLOW,
                                          'actor': ACTOR, **options})


def consent(location):
    return {'expected_work_lock_sha256': sha256((location.path / 'work-lock.json').read_bytes()).hexdigest(),
            'work_recovery_reason': 'Explicit current synthetic outer recovery'}


def proof(current):
    row = current.entries('completed')[0]['evidence']
    return json.loads(current.objects[row['sha256']])


@pytest.mark.parametrize('kind', ['project_bundle', 'baseline'])
def test_success_retains_native_completion_and_pending_delivery_under_one_live_owner(recorded, tmp_path, kind):
    options, _, _ = restore_case(tmp_path, kind)
    plan = plan_for(options)
    initial, location, store = stored(tmp_path, plan)
    observed = []
    def check(request):
        import fcntl
        raw = (location.path / 'work-lock.json').read_bytes()
        owner = json.loads(raw)
        assert owner['process_id'] == os.getpid() and owner['work_id'] == initial.as_dict()['work_id']
        observed.append(raw)
        fd = os.open(location.path, os.O_RDONLY | os.O_DIRECTORY)
        try:
            with pytest.raises(BlockingIOError): fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        finally:
            os.close(fd)
        return True
    result = advance(store, authority=RecoveryAuthority('synthetic-progress-host', '1', check))
    value = result.as_dict(); current = store.read(); evidence = proof(current)
    assert observed and len(set(observed)) == 1 and not (location.path / 'work-lock.json').exists()
    assert result.manifest.raw == current.raw and value['checkpoint_changed'] is True
    assert value['progress'] == {'completed_units': 1, 'total_units': 2}
    assert value['work_state'] == 'running' and value['checkpoint_generation'] == 1
    assert value['work_completion_recorded'] is False and value['owner_handoff'] is None
    assert current.entries('remaining')[0]['key'] == 'restore_result'
    assert current.as_dict()['result_parts'] == current.as_dict()['diagnostic_parts'] == []
    assert evidence['initial_checkpoint_sha256'] == initial.as_dict()['checkpoint_sha256']
    assert evidence['completion'] == json.loads((options['project_root'] / value['restore']['audit_path']).read_bytes())
    assert all((options['project_root'] / p).read_bytes() == raw for p, raw in files(plan, 'target').items())
    before = inventory(tmp_path)
    again = advance(store, actor=RECOVERY_ACTOR).as_dict()
    assert again['restore']['replayed'] and not again['checkpoint_changed']
    assert again['restore']['request']['actor'] == ACTOR
    assert store.read().raw == current.raw and inventory(tmp_path) == before
    with pytest.raises(TypeError): RestoreWorkProgress()
    with pytest.raises(TypeError): bool(result)
    with pytest.raises(FrozenInstanceError): result._raw = b'{}'
    value['progress']['completed_units'] = 999
    assert result.as_dict()['progress']['completed_units'] == 1


def test_handoff_keeps_exact_replacement_owner_through_native_execution_and_checkpoint(recorded, tmp_path):
    options, plan, selection, _, _ = fixture(tmp_path)
    initial, location, store = stored(tmp_path, plan, selection)
    old = orphan(store); observed = []
    def check(request):
        raw = (location.path / 'work-lock.json').read_bytes(); observed.append(raw)
        assert json.loads(raw)['format_version'] == 'restore-work-lock-v1'
        directory = location.path / 'checkpoints/restore-owner-handoffs'
        intents = [p for p in directory.iterdir() if not p.name.endswith('.complete.json')]
        assert len(intents) == 1
        intent = json.loads(intents[0].read_bytes())
        assert b64decode(intent['new_owner']['bytes']['base64']) == raw
        assert (directory / (intents[0].stem + '.complete.json')).is_file()
        return True
    result = advance(store, **consent(location),
                     authority=RecoveryAuthority('synthetic-separated-host', '1', check)).as_dict()
    assert observed and len(set(observed)) == 1 and observed[0] != old
    assert result['owner_handoff']['old_owner_sha256'] == sha256(old).hexdigest()
    assert result['owner_handoff']['checkpoint_generation'] == 0
    assert result['checkpoint_generation'] == 1 and not (location.path / 'work-lock.json').exists()
    assert proof(store.read())['completion']['request']['actor'] == initial.as_dict()['actor']


@pytest.mark.parametrize('options', [
    {'expected_work_lock_sha256': 'a' * 64}, {'work_recovery_reason': 'current'},
    {'expected_work_lock_sha256': 'A' * 64, 'work_recovery_reason': 'current'},
    {'expected_work_lock_sha256': 'a' * 64, 'work_recovery_reason': '  '},
])
def test_outer_pair_is_explicit_current_input_before_any_write(recorded, tmp_path, options):
    setup, _, _ = restore_case(tmp_path); plan = plan_for(setup)
    _, _, store = stored(tmp_path, plan)
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(RestoreWorkProgressError) as caught:
        advance(store, **options)
    assert caught.value.exit_code == 2 and inventory(tmp_path) == before
    assert not caught.value.work_mutation_possible and not caught.value.mutation_possible


@pytest.mark.parametrize('override', [{}, {'force': True, 'expected_lock_sha256': 'a' * 64,
                                          'reason': 'project force is not outer consent'}])
def test_retained_outer_owner_blocks_without_its_own_pair(recorded, tmp_path, override):
    setup, _, _ = restore_case(tmp_path); plan = plan_for(setup)
    initial, location, store = stored(tmp_path, plan)
    orphan(store); before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(RestoreWorkProgressError) as caught:
        advance(store, **override)
    assert caught.value.exit_code == 5 and not caught.value.work_mutation_possible
    assert not caught.value.mutation_possible and inventory(tmp_path) == before
    assert store.read().raw == initial.raw


def test_read_only_work_is_not_granted_recovery_by_this_adapter(recorded, tmp_path):
    _, _, _, store = read_only_store(tmp_path)
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(RestoreWorkProgressError) as caught:
        advance(store)
    assert caught.value.exit_code == 2 and inventory(tmp_path) == before


@pytest.mark.parametrize('confirm_first', [False, True])
def test_fresh_authority_denial_never_confirms_or_republishes_native_work(recorded, tmp_path, confirm_first):
    setup, _, _ = restore_case(tmp_path); plan = plan_for(setup)
    _, location, store = stored(tmp_path, plan)
    if confirm_first: advance(store)
    current = store.read(); before = inventory(tmp_path); calls = []
    def deny(request): calls.append(request); return False
    with pytest.raises(RestoreWorkProgressError) as caught:
        advance(store, authority=RecoveryAuthority('synthetic-denied', '1', deny))
    assert caught.value.exit_code == 7 and calls and not caught.value.mutation_possible
    assert store.read().raw == current.raw and inventory(tmp_path) == before
    assert not (location.path / 'work-lock.json').exists()
    assert not caught.value.owner_recovery_required


@pytest.mark.parametrize('fault', ['unknown', 'delivery_first', 'foreign_attribution'])
def test_saved_work_progress_is_not_native_execution_truth(recorded, tmp_path, fault):
    setup, _, _ = restore_case(tmp_path); plan = plan_for(setup)
    initial, location, store = stored(tmp_path, plan)
    if fault == 'foreign_attribution':
        native = execute(plan).data
        core = {key: native[key] for key in implementation._COMPLETION}
        core['authority_id'] = 'forged'
        evidence = implementation._evidence(initial, initial.entries('tasks')[0]['unit_id'], core)
    else: evidence = b'{"pretended":true}'
    unit = initial.entries('tasks')[1 if fault == 'delivery_first' else 0]['unit_id']
    saved = partition_work_manifest(initial, {unit: evidence}); store.publish(saved)
    before = inventory(tmp_path)
    with pytest.raises(RestoreWorkProgressError) as caught:
        advance(store)
    assert caught.value.exit_code == (3 if fault == 'unknown' else 6)
    assert not caught.value.mutation_possible and store.read().raw == saved.raw
    assert inventory(tmp_path) == before


def test_missing_native_completion_cannot_turn_confirmed_progress_into_a_new_restore(recorded, tmp_path):
    options, _, _ = restore_case(tmp_path); plan = plan_for(options)
    initial, _, store = stored(tmp_path, plan)
    result = advance(store).as_dict(); root = options['project_root']
    # Remove only test-created completed native history. The target was already
    # equal to the original plan, so an unguarded executor could start anew.
    import shutil
    shutil.rmtree(root / '.specroad/recovery/archive')
    shutil.rmtree(root / '.specroad/recovery/transaction-audit')
    before = inventory(tmp_path); current = store.read()
    with pytest.raises(RestoreWorkProgressError) as caught: advance(store)
    assert caught.value.exit_code == 6 and not caught.value.mutation_possible
    assert store.read().raw == current.raw and inventory(tmp_path) == before


def child(packet_path, stage):
    _build.BUILD_METADATA = {'format_version': 1, 'hash_algorithm': 'specroad-dev-payload-v1',
                             'build_sha256': '4' * 64}
    packet = json.loads(Path(packet_path).read_bytes())
    raw = b64decode(packet['raw']); data = json.loads(raw)
    initial = read_restore_work_manifest(raw, {k: b64decode(v) for k, v in packet['objects'].items()},
        registry=registry(), expected_tool_build=data['tool_build'])
    location = WorkDirectory(initial, protected_roots=(ProjectBoundary(packet['project']),),
                             directory=Path(packet['directory']))
    store = CheckpointStore(location, initial)
    if stage in ('partial', 'full'):
        original = RestoreStore.publish; count = 0
        def publish(self, *args):
            nonlocal count
            result = original(self, *args); count += 1
            if count == (1 if stage == 'partial' else 2): os._exit(86)
            return result
        RestoreStore.publish = publish
    elif stage == 'native_returned':
        original = implementation._native_held
        def execute_held(*args, **kwargs):
            original(*args, **kwargs); os._exit(86)
        implementation._native_held = execute_held
    elif stage == 'pointer':
        original = CheckpointStore._publish_held
        def publish(self, *args):
            original(self, *args); os._exit(86)
        CheckpointStore._publish_held = publish
    else:
        from specroad.work import checkpoints
        original = checkpoints._ensure_file
        def ensure(*args, **kwargs):
            original(*args, **kwargs)
            if args[1] == ('objects' if stage == 'objects' else 'checkpoints'): os._exit(86)
        checkpoints._ensure_file = ensure
    advance(store)
    raise AssertionError('Real crash boundary was not reached')


def interrupt(store, plan, stage):
    root = Path(__file__).resolve().parents[1]
    initial = store._initial
    packet = {'raw': b64encode(initial.raw).decode(),
        'objects': {k: b64encode(v).decode() for k, v in initial.objects.items()},
        'project': plan.data['project_root'], 'directory': str(store._location.path)}
    with tempfile.NamedTemporaryFile(mode='w', dir=store._location.path.parent,
                                     prefix='.progress-test-', suffix='.json') as stream:
        json.dump(packet, stream); stream.flush()
        code = ('import sys;sys.path[:0]=' + repr([str(root / 'src'), str(root / 'tests')]) +
                '\nfrom test_work_restore_progress import child\nchild(' + repr(stream.name) + ',' + repr(stage) + ')')
        result = run_python(['-I', '-B', '-c', code], root, capture=True)
    assert result.returncode == 86, result.stderr.decode()


@pytest.mark.parametrize('stage', ['partial', 'full', 'native_returned', 'objects', 'checkpoint', 'pointer'])
def test_real_exit_recovers_native_truth_before_work_progress_even_after_source_loss(recorded, tmp_path, stage):
    options, plan, selection, changed, old = fixture(tmp_path)
    initial, location, store = stored(tmp_path, plan, selection)
    root = options['project_root']; originals = {p: (root / p).read_bytes() for p in changed}
    interrupt(store, plan, stage)
    prior = store.read()
    assert prior.as_dict()['checkpoint_generation'] == (1 if stage == 'pointer' else 0)
    (options['source_root'] / options['source_path']).unlink()
    old_owner = (location.path / 'work-lock.json').read_bytes()
    current_consent = consent(location)
    with pytest.raises(RestoreWorkProgressError) as caught: advance(store, **takeover(plan))
    assert caught.value.exit_code == 5 and not caught.value.mutation_possible
    assert (location.path / 'work-lock.json').read_bytes() == old_owner
    result = advance(store, actor=RECOVERY_ACTOR, **current_consent, **takeover(plan)).as_dict()
    assert result['owner_handoff']['old_owner_sha256'] == sha256(old_owner).hexdigest()
    assert result['restore']['request']['actor'] == ACTOR
    assert result['restore']['source_observation']['status'] == 'unavailable_or_changed'
    if stage == 'partial':
        assert result['restore']['result'] == 'rolled_back' and result['restore']['recovery_required']
        assert not result['checkpoint_changed'] and store.read().raw == initial.raw
        assert {p: (root / p).read_bytes() for p in changed} == originals
        assert (root / old / 'journal.json').read_bytes() == b'{damaged'
    else:
        assert result['restore']['result'] == 'restored' and not result['restore']['recovery_required']
        assert store.read().as_dict()['checkpoint_generation'] == 1
        assert result['checkpoint_changed'] == (stage != 'pointer')
        assert all((root / p).read_bytes() == raw for p, raw in files(plan, 'target').items())
    assert not result['work_completion_recorded'] and not (location.path / 'work-lock.json').exists()


@pytest.mark.parametrize('after_pointer', [False, True])
def test_work_io_failure_preserves_native_completion_and_actual_checkpoint(recorded, tmp_path, monkeypatch, after_pointer):
    options, plan, selection, _, _ = fixture(tmp_path)
    initial, location, store = stored(tmp_path, plan, selection)
    native = CheckpointStore._publish_held
    def fail(self, *args):
        if after_pointer: native(self, *args)
        raise OSError('synthetic Work publication failure')
    with monkeypatch.context() as patch:
        patch.setattr(CheckpointStore, '_publish_held', fail)
        with pytest.raises(RestoreWorkProgressError) as caught: advance(store)
    assert caught.value.exit_code == 5 and caught.value.mutation_possible
    assert caught.value.work_mutation_possible and caught.value.recovery_required
    assert not caught.value.owner_recovery_required
    assert store.read().as_dict()['checkpoint_generation'] == int(after_pointer)
    assert all((options['project_root'] / p).read_bytes() == raw for p, raw in files(plan, 'target').items())
    result = advance(store).as_dict()
    assert result['restore']['replayed'] and store.read().as_dict()['checkpoint_generation'] == 1
    assert result['checkpoint_changed'] == (not after_pointer)


@pytest.mark.parametrize('fault', ['build', 'pointer', 'owner'])
def test_live_authority_cannot_change_work_binding_before_restore(recorded, tmp_path, monkeypatch, fault):
    options, plan, selection, _, _ = fixture(tmp_path)
    initial, location, store = stored(tmp_path, plan, selection)
    project = inventory(options['project_root'])
    def change(request):
        if fault == 'build':
            monkeypatch.setattr(_build, 'BUILD_METADATA', {**_build.BUILD_METADATA, 'build_sha256': '5' * 64})
        else:
            (location.path / ('work.json' if fault == 'pointer' else 'work-lock.json')).write_bytes(b'foreign')
        return True
    with pytest.raises(RestoreWorkProgressError) as caught:
        advance(store, authority=RecoveryAuthority('synthetic-changing-host', '1', change))
    assert caught.value.exit_code == 6 and not caught.value.mutation_possible
    assert inventory(options['project_root']) == project



@pytest.mark.parametrize('state,code', [('uncompleted', 3), ('corrupt', 6)])
def test_retained_handoff_history_is_mandatory_even_without_an_owner(recorded, tmp_path, state, code):
    from test_work_restore_owner import child as owner_child, recover
    options, _, _ = restore_case(tmp_path); plan = plan_for(options)
    initial, location, store = stored(tmp_path, plan)
    orphan(store)
    if state == 'uncompleted':
        owner_child(store, 'intent')
        # Simulated external loss is confined to this test's owner file.
        (location.path / 'work-lock.json').unlink()
    else:
        recover(store)
        directory = location.path / 'checkpoints/restore-owner-handoffs'
        intent = next(p for p in directory.iterdir() if not p.name.endswith('.complete.json'))
        intent.write_bytes(b'{}')
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(RestoreWorkProgressError) as caught:
        advance(store)
    assert caught.value.exit_code == code and not caught.value.work_mutation_possible
    assert not caught.value.mutation_possible and inventory(tmp_path) == before
    assert store.read().raw == initial.raw


def test_live_handoff_history_change_cannot_authorize_project_writes(recorded, tmp_path):
    from test_work_restore_owner import recover
    options, _, _ = restore_case(tmp_path); plan = plan_for(options)
    initial, location, store = stored(tmp_path, plan)
    orphan(store); recover(store)
    directory = location.path / 'checkpoints/restore-owner-handoffs'
    completion = next(directory.glob('*.complete.json'))
    project = inventory(options['project_root'])
    def change(request):
        completion.write_bytes(b'{}')
        return True
    with pytest.raises(RestoreWorkProgressError) as caught:
        advance(store, authority=RecoveryAuthority('synthetic-changing-history', '1', change))
    assert caught.value.exit_code == 6 and not caught.value.mutation_possible
    assert caught.value.work_mutation_possible and not caught.value.owner_recovery_required
    assert inventory(options['project_root']) == project and completion.read_bytes() == b'{}'
    assert store.read().raw == initial.raw and not (location.path / 'work-lock.json').exists()
