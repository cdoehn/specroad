"""Actual native Restore/Recovery from Work bytes, with synthetic host grants.

No test authority is a human review, production CLI registration or release
proof. Durable Work completion and planning-mode Work remain outside this API.
"""
from dataclasses import FrozenInstanceError
from base64 import b64decode, b64encode
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from specroad import _build
from specroad.changes._lock_files import LockFiles
from specroad.changes.recovery_values import RecoveryAuthority
from specroad.cli.requests import CommandRequest
from specroad.model.canonical import canonical_json_bytes
from specroad.recovery import RestoreError
from specroad.recovery._execution_store import RestoreStore
from specroad.security import ProjectBoundary
from specroad.storage.operational_preflight import observe_operational_preflight
from specroad.work.checkpoints import CheckpointStore
from specroad.work.manifest import partition_work_manifest
from specroad.work.restore import create_restore_work_manifest, read_restore_work_manifest
from specroad.work.restore_execution import (RestoreWorkExecution,
    prepare_restore_work, execute_restore_work)
from specroad.work.root import WorkDirectory
from support.model import put
from support.read_only import inventory, no_write_attempts
from support.restore import restore_case, plan_for
from test_restore_execution import ACTOR, ALLOW, execute, selected, files
from test_restore_execution_right import fixture, interrupted
from test_work_restore_binding import registry, with_options
from test_work_resume import recorded


RECOVERY_ACTOR = {'actor_type': 'human', 'actor_id': 'synthetic-current-recovery'}


def request_for(plan, selection=None, **options):
    return CommandRequest('recover.restore', options={
        '--project': plan.data['project_root'], '--plan-root': '/unopened-transport',
        '--plan': 'original.json', '--expected-target-root': plan.data['expected_target_root'],
        '--actor-type': ACTOR['actor_type'], '--actor-id': ACTOR['actor_id'],
        '--request-id': 'restore-test', **({} if selection is None else {
            '--selection-root': '/unopened-selection', '--affected-journals': 'selection.json'}), **options})


def stored(tmp_path, plan, selection=None, *, request=None, initial=None, directory=None):
    request = request_for(plan, selection) if request is None else request
    if initial is None:
        before = inventory(tmp_path)
        with no_write_attempts():
            initial = prepare_restore_work(registry(), request, plan=plan, affected_journals=selection)
        assert inventory(tmp_path) == before
    location = WorkDirectory(initial, protected_roots=(ProjectBoundary(plan.data['project_root']),),
                             directory=tmp_path / 'work' if directory is None else directory)
    store = CheckpointStore(location, initial)
    store.publish(initial)
    return initial, location, store


def run(store, **overrides):
    return execute_restore_work(store, **{'registry': registry(), 'authority': ALLOW,
                                         'actor': ACTOR, **overrides})


def takeover(plan):
    with LockFiles(plan.data['project_root']) as access:
        owner = access.read_record()[0]
    return {} if owner is None else {'force': True, 'expected_lock_sha256': owner.sha256,
        'reason': 'Synthetic current explicit recovery after abrupt process exit'}


@pytest.mark.parametrize('kind', ['project_bundle', 'baseline'])
@pytest.mark.parametrize('journal', [False, True])
def test_bound_work_executes_exact_native_target_without_transport_or_work_completion(recorded, tmp_path, kind, journal):
    options, original, _ = restore_case(tmp_path, kind)
    root = options['project_root']
    damaged = next(p for p in original if p.startswith('spec/goals/'))
    put(root, damaged, b'\xffbroken')
    old = '.specroad/transactions/old'
    if journal:
        put(root, old + '/journal.json', b'{unparseable')
    plan = plan_for(options)
    selection = selected(plan, [old]) if journal else None
    initial, location, store = stored(tmp_path, plan, selection)
    work_before = inventory(location.path)
    calls = []

    def authorize(request):
        calls.append(request)
        assert request['actor'] == initial.as_dict()['actor']
        assert request['plan_bytes_sha256'] == plan.sha256
        # The Work inode mutex remains held through every native authority gate.
        import fcntl
        fd = os.open(location.path, os.O_RDONLY | os.O_DIRECTORY)
        try:
            with pytest.raises(BlockingIOError):
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        finally:
            os.close(fd)
        return True

    result = run(store, authority=RecoveryAuthority('synthetic-current-host', '1', authorize))
    value = result.as_dict(); outcome = value['restore']
    assert calls and outcome['result'] == 'restored' and not outcome['recovery_required']
    assert all((root / p).read_bytes() == raw for p, raw in files(plan, 'target').items())
    assert outcome['request']['actor'] == ACTOR and outcome['request']['request_id'] == 'restore-test'
    assert outcome['request']['affected_journals'] == json.loads(selection or selected(plan, []))
    audit = json.loads((root / outcome['audit_path']).read_bytes())
    assert audit['request'] == outcome['request']
    assert all(((root / outcome['audit_path']).parent / 'objects' / row['sha256']).read_bytes()
               == files(plan, 'backup')[row['path']] for row in plan.data['backup']['entries'])
    if journal:
        assert not (root / old).exists()
        assert ((root / outcome['audit_path']).parent / 'originals/0/journal.json').read_bytes() == b'{unparseable'
    assert store.read().raw == initial.raw and inventory(location.path) == work_before
    assert not value['checkpoint_changed'] and not value['work_completion_recorded']
    assert initial.as_dict()['state'] == 'running' and len(initial.entries('remaining')) == 2
    assert not (location.path / 'work-lock.json').exists()
    # The direct native re-entry returns the same original result bindings.
    direct = execute(plan, affected_journals=selection).data
    for name in ('request', 'result', 'expected_target_root'):
        assert direct[name] == outcome[name]
    assert direct['replayed']
    with pytest.raises(TypeError): bool(result)
    with pytest.raises(TypeError): RestoreWorkExecution()
    with pytest.raises(FrozenInstanceError): result._raw = b'{}'
    value['restore']['result'] = 'invented'
    assert result.as_dict()['restore']['result'] == 'restored'


@pytest.mark.parametrize('fault,code', [('missing', 2), ('denied', 7), ('non_bool', 7), ('mutated', 7),
                                     ('wrong_actor', 6), ('source', 6), ('inventory', 6)])
def test_fresh_native_gates_refuse_before_any_write(recorded, tmp_path, fault, code):
    options, plan, selection, changed, _ = fixture(tmp_path)
    _, _, store = stored(tmp_path, plan, selection)
    changes = {}
    if fault == 'missing': changes['authority'] = None
    elif fault == 'denied': changes['authority'] = RecoveryAuthority('synthetic-denied', '1', lambda r: False)
    elif fault == 'non_bool': changes['authority'] = RecoveryAuthority('synthetic-nonbool', '1', lambda r: 1)
    elif fault == 'mutated':
        def alter(request):
            request['actor'] = RECOVERY_ACTOR
            return True
        changes['authority'] = RecoveryAuthority('synthetic-mutating', '1', alter)
    elif fault == 'wrong_actor': changes['actor'] = RECOVERY_ACTOR
    elif fault == 'source': (options['source_root'] / options['source_path']).write_bytes(b'changed source')
    else: (options['project_root'] / changed[0]).write_bytes(b'changed inventory')
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(RestoreError) as caught:
        run(store, **changes)
    assert caught.value.exit_code == code and not caught.value.mutation_possible
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('fault', ['tasks', 'progress', 'runtime', 'unprotected', 'source_overlap'])
def test_only_the_bound_closed_execution_path_can_reach_restore(recorded, tmp_path, monkeypatch, fault):
    options, plan, selection, _, _ = fixture(tmp_path)
    initial = None
    if fault == 'tasks':
        request = request_for(plan, selection)
        build = prepare_restore_work(registry(), request, plan=plan,
                                     affected_journals=selection).as_dict()['tool_build']
        initial = create_restore_work_manifest(registry(), request, plan=plan,
            affected_journals=selection, tool_build=build,
            units=[{'key': 'untrusted-task', 'phase': 'execute', 'range': {'shell': 'never execute'}}])
    initial, location, store = stored(tmp_path, plan, selection, initial=initial,
        directory=options['source_root'] / 'work' if fault == 'source_overlap' else None)
    if fault == 'progress':
        candidate = partition_work_manifest(initial, {initial.entries('tasks')[0]['unit_id']: b'{"pretended":true}'})
        store.publish(candidate)
    elif fault == 'runtime':
        monkeypatch.setattr(_build, 'BUILD_METADATA', {**_build.BUILD_METADATA, 'build_sha256': '5' * 64})
    elif fault == 'unprotected':
        store = CheckpointStore(WorkDirectory(initial, protected_roots=(ProjectBoundary(options['source_root']),),
                                              directory=location.path), initial)
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(RestoreError) as caught:
        run(store)
    assert caught.value.exit_code == (7 if fault in ('unprotected', 'source_overlap') else 6)
    if fault == 'tasks': assert caught.value.reason == 'restore_work_execution_plan_required'
    assert inventory(tmp_path) == before


def abrupt_work(value):
    _build.BUILD_METADATA = {'format_version': 1, 'hash_algorithm': 'specroad-dev-payload-v1',
                             'build_sha256': '4' * 64}
    raw = b64decode(value['raw']); data = json.loads(raw)
    initial = read_restore_work_manifest(raw, {k: b64decode(v) for k, v in value['objects'].items()},
        registry=registry(), expected_tool_build=data['tool_build'])
    location = WorkDirectory(initial, protected_roots=(ProjectBoundary(value['project']),),
                             directory=value['directory'])
    store = CheckpointStore(location, initial)
    boundary = value['boundary']
    if boundary != 'returned':
        method = 'create' if boundary == 'audit' else 'publish'
        native = getattr(RestoreStore, method); seen = 0
        def crash(self, *args):
            nonlocal seen
            result = native(self, *args)
            if method == 'publish' or args[0].endswith('/completed.json'):
                seen += 1
                if seen == (2 if boundary == 'full' else 1): os._exit(87)
            return result
        setattr(RestoreStore, method, crash)
    run(store)
    if boundary == 'returned': os._exit(87)
    raise AssertionError('Native crash boundary was not reached')


def interrupt_work(initial, location, plan, boundary):
    repo = Path(__file__).resolve().parents[1]
    code = '''
import sys, json
from pathlib import Path
sys.path[:0] = [str(Path(sys.argv[1]) / 'src'), str(Path(sys.argv[1]) / 'tests')]
from test_work_restore_execution import abrupt_work
abrupt_work(json.load(sys.stdin))
'''
    value = {'raw': b64encode(initial.raw).decode(),
        'objects': {k: b64encode(v).decode() for k, v in initial.objects.items()},
        'project': plan.data['project_root'], 'directory': str(location.path), 'boundary': boundary}
    run = subprocess.run([sys.executable, '-I', '-B', '-c', code, str(repo)],
        input=json.dumps(value), capture_output=True, text=True, check=False, timeout=240)
    assert run.returncode == 87, run.stderr


@pytest.mark.parametrize('boundary', ['partial', 'full', 'audit', 'returned'])
def test_real_process_exit_uses_native_journal_before_lost_source_and_retains_work(recorded, tmp_path, boundary):
    options, plan, selection, changed, old = fixture(tmp_path)
    initial, location, store = stored(tmp_path, plan, selection)
    root = options['project_root']; before_images = {p: (root / p).read_bytes() for p in changed}
    work_before = inventory(location.path)
    interrupt_work(initial, location, plan, boundary)
    assert inventory(location.path) == work_before and store.read().raw == initial.raw
    (options['source_root'] / options['source_path']).unlink()
    observations = []
    def allow(request):
        observations.append(request)
        assert request.get('original_request', request.get('restore_request', request))['actor'] == ACTOR
        return True
    result = run(store, actor=RECOVERY_ACTOR, **takeover(plan),
        authority=RecoveryAuthority('synthetic-recovery-host', '2', allow)).as_dict()['restore']
    assert observations and result['request']['actor'] == ACTOR
    assert result['source_observation']['status'] == 'unavailable_or_changed'
    if boundary == 'partial':
        assert result['result'] == 'rolled_back' and result['recovery_required']
        assert {p: (root / p).read_bytes() for p in changed} == before_images
        assert (root / old / 'journal.json').read_bytes() == b'{damaged'
        assert observe_operational_preflight(ProjectBoundary(root))['recovery_required']
    else:
        assert result['result'] == 'restored' and not result['recovery_required']
        assert all((root / p).read_bytes() == raw for p, raw in files(plan, 'target').items())
        assert not (root / old).exists()
    # Current Recovery actions are separately bound by the native event records.
    assert any(request.get('actor') == RECOVERY_ACTOR for request in observations)
    if boundary != 'returned':
        events = [json.loads(path.read_bytes()) for path in (root / '.specroad/recovery').glob('**/actions/*/intent.json')]
        assert any(event['details']['request']['actor'] == RECOVERY_ACTOR
                   and event['original_execution']['request']['actor'] == ACTOR for event in events)
    assert store.read().raw == initial.raw and inventory(location.path) == work_before
    project_before = inventory(root)
    replay = run(store, actor=RECOVERY_ACTOR).as_dict()['restore']
    assert replay['replayed'] and replay['result'] == result['result']
    assert inventory(root) == project_before


def test_other_work_original_actor_cannot_adopt_existing_native_execution(recorded, tmp_path):
    options, plan, selection, _, _ = fixture(tmp_path)
    interrupted(plan, selection, 'publish', count=2)
    request = with_options(request_for(plan, selection), **{'--actor-id': 'different-original'})
    _, _, store = stored(tmp_path, plan, selection, request=request)
    current = takeover(plan); before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(RestoreError) as caught:
        run(store, actor=RECOVERY_ACTOR, **current)
    assert caught.value.exit_code == 6 and caught.value.reason == 'restore_original_actor_conflict'
    assert caught.value.recovery_required and inventory(tmp_path) == before


def test_saved_takeover_is_not_a_current_request(recorded, tmp_path):
    options, plan, selection, _, _ = fixture(tmp_path)
    interrupted(plan, selection, 'publish', count=2)
    current = takeover(plan)
    request = with_options(request_for(plan, selection), **{
        '--force': True, '--expected-lock-sha256': current['expected_lock_sha256'],
        '--reason': 'Only an old saved request, not the current consent'})
    _, _, store = stored(tmp_path, plan, selection, request=request)
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(RestoreError) as caught:
        run(store, actor=RECOVERY_ACTOR)
    assert caught.value.exit_code == 5 and caught.value.recovery_required
    assert inventory(tmp_path) == before
    result = run(store, actor=RECOVERY_ACTOR, **current).as_dict()['restore']
    assert result['result'] == 'restored'


@pytest.mark.parametrize('when', [2, 3])
@pytest.mark.parametrize('damage', ['pointer', 'build', 'work_root'])
def test_host_callback_cannot_change_work_binding_before_native_writes(recorded, tmp_path, monkeypatch, when, damage):
    options, plan, selection, changed, _ = fixture(tmp_path)
    _, location, store = stored(tmp_path, plan, selection)
    original = {p: (options['project_root'] / p).read_bytes() for p in changed}
    calls = []
    def check(request):
        calls.append(request)
        if len(calls) == when:
            if damage == 'pointer': (location.path / 'work.json').write_bytes(b'changed by synthetic host')
            elif damage == 'work_root': (location.path / 'root.json').write_bytes(b'changed by synthetic host')
            else: monkeypatch.setattr(_build, 'BUILD_METADATA', {**_build.BUILD_METADATA, 'build_sha256': '5' * 64})
        return True
    with pytest.raises(RestoreError) as caught:
        run(store, authority=RecoveryAuthority('synthetic-changing-host', '1', check))
    assert caught.value.exit_code == (7 if damage == 'work_root' else 6) and len(calls) == when
    assert caught.value.mutation_possible == (when == 3)
    assert {p: (options['project_root'] / p).read_bytes() for p in changed} == original
    if when == 3:
        assert caught.value.recovery_required
        assert observe_operational_preflight(ProjectBoundary(options['project_root']))['recovery_required']
