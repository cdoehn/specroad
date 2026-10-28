"""Complete native Restore output, actual crash boundaries and saved replay.

Host grants are synthetic; no public CLI registration or product review is
claimed. Native project execution is real, including in the child processes.
"""
from base64 import b64decode
from dataclasses import FrozenInstanceError
from hashlib import sha256
import json
import os
from pathlib import Path
import sys

import pytest

from specroad import _build
from specroad.changes.recovery_values import RecoveryAuthority
from specroad.model.canonical import canonical_json_bytes
from specroad.recovery import RestoreError
from specroad.security import ProjectBoundary
from specroad.work import restore_delivery as delivery
from specroad.work import restore_progress as progress
from specroad.work.checkpoints import CheckpointStore
from specroad.work.manifest import _put, read_work_manifest
from specroad.work.restore import read_restore_work_manifest
from specroad.work.restore_delivery import RestoreWorkCompletion
from specroad.work.restore_progress import resume_restore_work, RestoreWorkProgressError
from specroad.work.root import WorkDirectory
from support.read_only import inventory, no_write_attempts
from support.restore import restore_case, plan_for
from support.processes import run_python
from test_restore_execution import ACTOR, ALLOW, files
from test_restore_execution_right import fixture
from test_work_manifest import sealed
from test_work_restore_binding import registry
from test_work_restore_execution import stored, takeover, RECOVERY_ACTOR
from test_work_restore_progress import advance, consent
from test_work_resume import recorded


pytestmark = pytest.mark.skipif(sys.platform != 'linux', reason='Native Linux Work/Restore leases')


def resume(store, **options):
    return resume_restore_work(store, **{'registry': registry(), 'authority': ALLOW,
                                        'actor': ACTOR, **options})


def payload(current):
    ref = current.as_dict()['result_parts'][0]
    return json.loads(current.objects[ref['sha256']])


@pytest.mark.parametrize('kind', ['project_bundle', 'baseline'])
def test_full_delivery_is_durable_and_completed_replay_never_rechecks_changed_project(recorded, tmp_path, monkeypatch, kind):
    options, _, _ = restore_case(tmp_path, kind)
    plan = plan_for(options); initial, location, store = stored(tmp_path, plan)
    observed = []
    def check(request):
        owner = (location.path / 'work-lock.json').read_bytes()
        observed.append(owner)
        return True
    result = resume(store, authority=RecoveryAuthority('synthetic-delivery', '1', check))
    value = result.as_dict(); current = store.read()
    assert observed and len(set(observed)) == 1
    assert value['work_state'] == 'completed' and value['checkpoint_generation'] == 3
    assert value['progress'] == {'completed_units': 2, 'total_units': 2}
    assert value['work_completion_recorded'] and value['checkpoint_changed']
    assert value['native_execution_checked'] and value['command_exit_code'] == 0
    assert not current.entries('remaining') and not (location.path / 'work-lock.json').exists()
    assert value['restore'] == payload(current)['outcome']
    assert value['restore']['request']['actor'] == initial.as_dict()['actor']
    assert value['restore']['request']['request_id'] == initial.as_dict()['request_id']
    assert current.as_dict()['operations_sha256'] is None
    diagnostics = current.as_dict()['diagnostic_parts'][0]
    assert json.loads(current.objects[diagnostics['sha256']])['diagnostics'] == value['restore']['historical_findings']
    for reference in value['result_files']:
        raw = Path(reference['path']).read_bytes()
        assert len(raw) == reference['size'] and sha256(raw).hexdigest() == reference['sha256']
        assert Path(reference['path']).stat().st_mode & 0o777 == 0o600
    assert json.loads(Path(value['result_files'][0]['path']).read_bytes()) == value['restore']
    assert all((options['project_root'] / p).read_bytes() == raw for p, raw in files(plan, 'target').items())
    (options['source_root'] / options['source_path']).unlink()
    (options['project_root'] / 'specroad.json').write_bytes(b'changed-after-completion')
    def forbidden(*args, **kwargs): raise AssertionError('Completed Work re-executed the project')
    monkeypatch.setattr(progress, '_native_held', forbidden)
    before = inventory(tmp_path)
    with no_write_attempts():
        replay = resume_restore_work(store, registry=registry()).as_dict()
    assert replay['restore'] == value['restore'] and replay['result_files'] == value['result_files']
    assert not replay['native_execution_checked'] and not replay['checkpoint_changed']
    assert store.read().raw == current.raw and inventory(tmp_path) == before
    with pytest.raises(TypeError): RestoreWorkCompletion()
    with pytest.raises(TypeError): bool(result)
    with pytest.raises(FrozenInstanceError): result._raw = b'{}'
    value['restore']['request']['actor']['actor_id'] = 'foreign'
    assert result.as_dict()['restore']['request']['actor'] == ACTOR


def test_existing_execution_unit_completes_without_overwriting_its_original_proof(recorded, tmp_path):
    options, plan, selection, _, _ = fixture(tmp_path)
    initial, location, store = stored(tmp_path, plan, selection)
    first = advance(store).manifest
    (options['source_root'] / options['source_path']).unlink()
    result = resume(store, actor=RECOVERY_ACTOR).as_dict(); final = store.read()
    assert result['restore']['replayed']
    assert result['restore']['source_observation']['status'] == 'unavailable_or_changed'
    assert final.entries('completed')[0] == first.entries('completed')[0]
    assert all(final.objects[k] == v for k, v in first.objects.items())
    assert result['restore']['request']['actor'] == ACTOR
    assert result['work_state'] == 'completed'


def test_partial_native_target_rolls_back_without_delivery_or_completed_work(recorded, tmp_path):
    from test_work_restore_progress import interrupt as interrupt_progress
    options, plan, selection, changed, _ = fixture(tmp_path)
    initial, location, store = stored(tmp_path, plan, selection)
    originals = {p: (options['project_root'] / p).read_bytes() for p in changed}
    interrupt_progress(store, plan, 'partial')
    (options['source_root'] / options['source_path']).unlink()
    value = resume(store, **consent(location), **takeover(plan), actor=RECOVERY_ACTOR).as_dict()
    assert value['restore']['result'] == 'rolled_back' and value['restore']['recovery_required']
    assert not value['work_completion_recorded'] and store.read().raw == initial.raw
    assert not list((location.path / 'results').iterdir())
    assert {p: (options['project_root'] / p).read_bytes() for p in changed} == originals


def child(packet_path, stage):
    _build.BUILD_METADATA = {'format_version': 1, 'hash_algorithm': 'specroad-dev-payload-v1',
                             'build_sha256': '4' * 64}
    packet = json.loads(Path(packet_path).read_bytes())
    raw = b64decode(packet['raw']); value = json.loads(raw)
    initial = read_restore_work_manifest(raw, {k: b64decode(v) for k, v in packet['objects'].items()},
        registry=registry(), expected_tool_build=value['tool_build'])
    location = WorkDirectory(initial, protected_roots=(ProjectBoundary(packet['project']),),
                             directory=Path(packet['directory']))
    store = CheckpointStore(location, initial)
    if stage in ('payload', 'file_manifest'):
        original = delivery._publish_file; count = 0
        def publish(*args, **kwargs):
            nonlocal count
            original(*args, **kwargs); count += 1
            if count == (1 if stage == 'payload' else 2): os._exit(86)
        delivery._publish_file = publish
    else:
        original = CheckpointStore._publish_held
        def publish(self, held, candidate, pointer):
            result = original(self, held, candidate, pointer)
            if result.as_dict()['checkpoint_generation'] == (2 if stage == 'delivery' else 3): os._exit(86)
            return result
        CheckpointStore._publish_held = publish
    resume(store)
    raise AssertionError('Actual delivery crash was not reached')


def interrupt(store, plan, stage):
    from base64 import b64encode
    import tempfile
    root = Path(__file__).resolve().parents[1]; initial = store._initial
    packet = {'raw': b64encode(initial.raw).decode(),
        'objects': {k: b64encode(v).decode() for k, v in initial.objects.items()},
        'project': plan.data['project_root'], 'directory': str(store._location.path)}
    with tempfile.NamedTemporaryFile(mode='w', dir=store._location.path.parent,
                                     prefix='.delivery-test-', suffix='.json') as stream:
        json.dump(packet, stream); stream.flush()
        code = ('import sys;sys.path[:0]=' + repr([str(root / 'src'), str(root / 'tests')])
                + '\nfrom test_work_restore_delivery import child\nchild('
                + repr(stream.name) + ',' + repr(stage) + ')')
        result = run_python(['-I', '-B', '-c', code], root, capture=True)
    assert result.returncode == 86, result.stderr.decode()


@pytest.mark.parametrize('stage,generation', [('payload', 1), ('file_manifest', 1), ('delivery', 2), ('completed', 3)])
def test_actual_crashes_keep_last_complete_generation_and_resume_without_second_restore(recorded, tmp_path, stage, generation):
    options, plan, selection, _, _ = fixture(tmp_path)
    initial, location, store = stored(tmp_path, plan, selection)
    interrupt(store, plan, stage)
    current = store.read(); assert current.as_dict()['checkpoint_generation'] == generation
    saved = None if generation < 2 else json.loads(current.objects[current.entries('completed')[1]['evidence']['sha256']])['outcome']
    project = inventory(options['project_root'])
    (options['source_root'] / options['source_path']).unlink()
    owner = (location.path / 'work-lock.json').read_bytes()
    with pytest.raises(RestoreWorkProgressError) as caught: resume(store)
    assert caught.value.exit_code == 5 and (location.path / 'work-lock.json').read_bytes() == owner
    result = resume(store, **consent(location), **takeover(plan), actor=RECOVERY_ACTOR).as_dict()
    assert result['owner_handoff']['old_owner_sha256'] == sha256(owner).hexdigest()
    assert result['checkpoint_generation'] == 3 and result['work_completion_recorded']
    assert inventory(options['project_root']) == project
    assert not (location.path / 'work-lock.json').exists()
    if saved is not None:
        assert result['restore'] == saved
    else:
        assert result['restore']['source_observation']['status'] == 'unavailable_or_changed'
    assert result['native_execution_checked'] == (generation != 3)
    before = inventory(tmp_path)
    with no_write_attempts(): again = resume_restore_work(store, registry=registry()).as_dict()
    assert again['restore'] == result['restore'] and inventory(tmp_path) == before


@pytest.mark.parametrize('after', [False, True])
def test_terminal_io_error_retains_actual_generation_and_needs_no_second_publication(recorded, tmp_path, monkeypatch, after):
    options, _, _ = restore_case(tmp_path); plan = plan_for(options)
    initial, location, store = stored(tmp_path, plan)
    original = CheckpointStore._publish_held
    def publish(self, held, candidate, pointer):
        if candidate.as_dict()['state'] != 'completed': return original(self, held, candidate, pointer)
        if after: original(self, held, candidate, pointer)
        raise OSError('synthetic terminal durability failure')
    with monkeypatch.context() as patch:
        patch.setattr(CheckpointStore, '_publish_held', publish)
        with pytest.raises(RestoreWorkProgressError) as caught: resume(store)
    assert caught.value.exit_code == 5 and caught.value.work_mutation_possible
    assert caught.value.mutation_possible and not caught.value.owner_recovery_required
    current = store.read(); assert current.as_dict()['checkpoint_generation'] == (3 if after else 2)
    before = inventory(tmp_path)
    deny = RecoveryAuthority('synthetic-denied-delivery', '1', lambda request: False)
    if not after:
        with pytest.raises(RestoreWorkProgressError) as denied: resume(store, authority=deny)
        assert denied.value.exit_code == 7 and inventory(tmp_path) == before
        assert store.read().raw == current.raw
    result = resume(store, authority=deny if after else ALLOW).as_dict()
    assert result['work_completion_recorded'] and store.read().as_dict()['checkpoint_generation'] == 3
    assert result['native_execution_checked'] == (not after)


def test_completed_file_loss_or_corruption_blocks_return_without_reexecution_or_repair(recorded, tmp_path, monkeypatch):
    options, _, _ = restore_case(tmp_path); plan = plan_for(options)
    _, location, store = stored(tmp_path, plan); result = resume(store); value = result.as_dict()
    def forbidden(*args, **kwargs): raise AssertionError('Output loss invoked native execution')
    monkeypatch.setattr(progress, '_native_held', forbidden)
    for ref in value['result_files']:
        path = Path(ref['path']); original = path.read_bytes()
        for mode in ('missing', 'corrupt'):
            if mode == 'missing': path.unlink()
            else: path.write_bytes(b'corrupt')
            before = inventory(tmp_path)
            with no_write_attempts(), pytest.raises(RestoreError): result.as_dict()
            with no_write_attempts(), pytest.raises(RestoreWorkProgressError): resume(store)
            assert inventory(tmp_path) == before
            path.write_bytes(original); path.chmod(0o600)
    assert result.as_dict()['restore'] == value['restore']


def test_self_hashed_final_payload_cannot_replace_native_result_or_drop_findings(recorded, tmp_path):
    options, plan, selection, _, _ = fixture(tmp_path)
    _, _, store = stored(tmp_path, plan, selection)
    current = resume(store).manifest
    original = payload(current)
    for change in ('actor', 'request', 'target', 'audit', 'result', 'recovery', 'exit', 'findings', 'extra', 'generation'):
        record = json.loads(canonical_json_bytes(original))
        if change == 'actor': record['outcome']['request']['actor']['actor_id'] = 'forged'
        elif change == 'request': record['outcome']['request']['request_id'] = 'forged'
        elif change == 'target': record['outcome']['expected_target_root'] = 'a' * 64
        elif change == 'audit': record['outcome']['audit_path'] = '../elsewhere'
        elif change == 'result': record['outcome']['result'] = 'rolled_back'
        elif change == 'recovery': record['outcome']['recovery_required'] = True
        elif change == 'exit': record['exit_code'] = True
        elif change == 'findings': record['outcome']['historical_findings'] = [{'forged': True}]
        elif change == 'extra': record['outcome']['approved'] = True
        else: record['source_checkpoint_generation'] = 0
        value = current.as_dict(); objects = dict(current.objects)
        value['result_parts'] = [_put(canonical_json_bytes(record), objects)]
        with no_write_attempts(), pytest.raises((RestoreError, ValueError)):
            read_work_manifest(sealed(value), objects, registry=registry(), expected_tool_build=value['tool_build'])


@pytest.mark.parametrize('fault', ['build', 'pointer'])
def test_late_work_change_during_output_publication_never_marks_delivery_complete(recorded, tmp_path, monkeypatch, fault):
    options, _, _ = restore_case(tmp_path); plan = plan_for(options)
    _, location, store = stored(tmp_path, plan)
    original = delivery._publish_file
    def change(held, *args):
        if fault == 'build':
            monkeypatch.setattr(_build, 'BUILD_METADATA', {**_build.BUILD_METADATA, 'build_sha256': '5' * 64})
        else: (location.path / 'work.json').write_bytes(b'foreign')
        return original(held, *args)
    monkeypatch.setattr(delivery, '_publish_file', change)
    with pytest.raises(RestoreWorkProgressError) as caught: resume(store)
    assert caught.value.exit_code == 6 and caught.value.mutation_possible
    assert caught.value.work_mutation_possible and not caught.value.owner_recovery_required
    assert not list((location.path / 'results').glob('result-*.json'))
    if fault == 'build': assert store.read().as_dict()['checkpoint_generation'] == 1

