"""Real handler execution, retained output and fresh compatible processes."""

import base64
import errno
import json
from pathlib import Path
import subprocess
import sys

import pytest

from specroad import _build, runtime
from specroad.cli.application import execute_request
from specroad.cli.commands import builtin_registry
from specroad.cli.contracts import CommandClass, CommandSpec, EffectScope, PreflightProfile
from specroad.cli.registry import CommandRegistry
from specroad.cli.requests import CommandRequest
from specroad.work.checkpoints import CheckpointStore, CheckpointStorageError
from specroad.work.manifest import create_work_manifest
from specroad.work.resume import WorkResumeError, prepare_read_only_work, resume_read_only_work
from specroad.work.root import WorkDirectory
from support.read_only import inventory, no_write_attempts
from test_work_root import protected


ROOT = Path(__file__).resolve().parents[1]
REQUESTS = [CommandRequest('help'), CommandRequest('version'), CommandRequest('capabilities'),
    CommandRequest('command.describe', arguments={'command': 'version'}),
    CommandRequest('schema.list'), CommandRequest('schema.show', arguments={'schema_id': 'json-envelope-v2'})]


@pytest.fixture
def recorded(monkeypatch):
    # Explicit in-process compatibility fixture, not a claimed distribution hash.
    # Separate real-build tests below exercise the actual generated identity.
    monkeypatch.setattr(_build, 'BUILD_METADATA', {'format_version': 1,
        'hash_algorithm': 'specroad-dev-payload-v1', 'build_sha256': '4' * 64})


def setup(tmp_path, request=None, *, initial=None, publish=True):
    initial = prepare_read_only_work(request or CommandRequest('version')) if initial is None else initial
    roots = protected(tmp_path)
    location = WorkDirectory(initial, protected_roots=roots, directory=tmp_path / 'work')
    store = CheckpointStore(location, initial)
    if publish:
        store.publish(initial)
    return initial, roots, location, store


def test_planning_binds_a_real_command_without_executing_or_allocating_work(recorded, tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('planning executed the command')
    monkeypatch.setattr('specroad.work.resume.execute_request', forbidden)
    before = inventory(tmp_path)
    with no_write_attempts():
        initial = prepare_read_only_work(CommandRequest('schema.list'))
    assert inventory(tmp_path) == before
    assert initial.as_dict()['checkpoint_generation'] == 0
    assert initial.as_dict()['progress'] == {'completed_units': 0, 'total_units': 1}
    assert initial.entries('inputs') == [] and initial.entries('completed') == []


@pytest.mark.parametrize('command_request', REQUESTS, ids=lambda value: value.command_id)
def test_each_supported_handler_runs_and_its_exact_saved_result_is_reused(recorded, tmp_path, monkeypatch, command_request):
    initial, roots, location, store = setup(tmp_path, command_request)
    expected = execute_request(command_request, cwd=tmp_path).result.as_dict()
    protected_before = inventory(roots[0].root)
    original = initial.as_dict()
    first = resume_read_only_work(store, cwd=tmp_path)
    assert first.executed and first.command_exit_code == 0
    assert json.loads(first.outcome_bytes) == expected
    current = first.manifest.as_dict()
    for name in ('work_id', 'command_id', 'command_class', 'normalized_arguments', 'actor',
                 'request_id', 'operations_sha256', 'plan_binding', 'tool_build',
                 'algorithm_versions', 'schema_versions', 'source_bindings',
                 'input_manifest_sha256', 'task_manifest_sha256'):
        assert current[name] == original[name]
    assert current['checkpoint_generation'] == 1
    assert current['progress'] == {'completed_units': 1, 'total_units': 1}
    assert current['state'] == 'running' and current['next_action']['operation'] == 'finalize_declared_work'
    assert first.manifest.entries('remaining') == []
    assert store.read().raw == first.manifest.raw
    stored_before = inventory(location.path)
    def forbidden(*args, **kwargs):
        raise AssertionError('saved handler was executed twice')
    monkeypatch.setattr('specroad.work.resume.execute_request', forbidden)
    again = resume_read_only_work(store, cwd=tmp_path)
    assert not again.executed and again.outcome_bytes == first.outcome_bytes
    assert again.manifest.raw == first.manifest.raw
    assert inventory(location.path) == stored_before
    assert inventory(roots[0].root) == protected_before
    detached = again.as_dict(); detached['command_outcome']['command'] = 'foreign'
    assert again.as_dict()['command_outcome']['command'] == command_request.command_id


def test_unrecorded_runtime_does_not_invent_build_compatibility(recorded, tmp_path, monkeypatch):
    _, _, _, store = setup(tmp_path)
    monkeypatch.setattr(_build, 'BUILD_METADATA', None)
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(WorkResumeError) as caught:
        resume_read_only_work(store)
    assert caught.value.as_dict() == {'reason': 'recorded_runtime_build_required', 'exit_code': 5}
    assert inventory(tmp_path) == before


def test_current_recorded_build_must_match_the_saved_work(recorded, tmp_path, monkeypatch):
    _, _, _, store = setup(tmp_path)
    monkeypatch.setattr(_build, 'BUILD_METADATA', {'format_version': 1,
        'hash_algorithm': 'specroad-dev-payload-v1', 'build_sha256': 'b' * 64})
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(WorkResumeError) as caught:
        resume_read_only_work(store)
    assert caught.value.reason == 'incompatible_runtime_build' and caught.value.exit_code == 6
    assert inventory(tmp_path) == before


def test_runtime_support_is_checked_again_before_any_work_write(recorded, tmp_path, monkeypatch):
    _, _, _, store = setup(tmp_path)
    def unavailable():
        raise runtime.UnsupportedRuntimeError('fixture current runtime unavailable')
    monkeypatch.setattr(runtime, 'check_runtime', unavailable)
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(runtime.UnsupportedRuntimeError):
        resume_read_only_work(store)
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('bound_root', [False, True])
def test_absent_or_unpublished_work_is_not_created_by_resume(recorded, tmp_path, bound_root):
    _, _, location, store = setup(tmp_path, publish=False)
    if bound_root:
        with location.for_checkpoint():
            pass
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises((FileNotFoundError, WorkResumeError)):
        resume_read_only_work(store)
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('command_request', [CommandRequest('environment.check'),
    CommandRequest('version', options={'--format': 'json'}), CommandRequest('unknown')])
def test_unimplemented_or_nonbootstrap_resume_is_not_declared(recorded, command_request):
    with no_write_attempts(), pytest.raises(WorkResumeError) as caught:
        prepare_read_only_work(command_request)
    assert caught.value.reason == 'unsupported_resume_request'


@pytest.mark.parametrize('change', ['different_unit', 'extra_unit', 'input'])
def test_a_generic_data_manifest_is_not_execution_authority(recorded, tmp_path, change):
    planned = prepare_read_only_work(CommandRequest('version'))
    value = planned.as_dict()
    units = [{k: v for k, v in planned.entries('tasks')[0].items() if k != 'unit_id'}]
    inputs = []
    if change == 'different_unit':
        units[0]['phase'] = 'foreign'
    elif change == 'extra_unit':
        units.append({'key': 'extra', 'phase': 'execute', 'range': {}})
    else:
        inputs.append({'root_id': 'foreign', 'path': 'data', 'raw': b'not required'})
    initial = create_work_manifest(builtin_registry(), CommandRequest('version'),
        tool_build=value['tool_build'], source_bindings=value['source_bindings'], inputs=inputs, units=units)
    _, _, _, store = setup(tmp_path, initial=initial)
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(WorkResumeError):
        resume_read_only_work(store)
    assert inventory(tmp_path) == before


def test_saved_registry_handlers_cannot_replace_fresh_core_handlers(recorded, tmp_path):
    called = []
    registry = CommandRegistry((CommandSpec('version', ('version',), CommandClass.READ_ONLY,
        PreflightProfile.BOOTSTRAP, EffectScope.NONE, lambda invocation: called.append(True) or 0),))
    planned = prepare_read_only_work(CommandRequest('version')); value = planned.as_dict()
    initial = create_work_manifest(registry, CommandRequest('version'), tool_build=value['tool_build'],
        source_bindings=value['source_bindings'], inputs=[], units=[
            {k: v for k, v in planned.entries('tasks')[0].items() if k != 'unit_id'}])
    _, _, _, store = setup(tmp_path, initial=initial)
    result = resume_read_only_work(store)
    assert result.executed and not called
    assert json.loads(result.outcome_bytes)['result']['build_sha256'] == '4' * 64


def test_command_failure_without_complete_result_cannot_advance_work(recorded, tmp_path):
    initial, _, location, store = setup(tmp_path,
        CommandRequest('schema.show', arguments={'schema_id': 'not-a-schema'}))
    before = inventory(location.path)
    with pytest.raises(WorkResumeError) as caught:
        resume_read_only_work(store)
    assert caught.value.reason == 'command_did_not_complete' and caught.value.exit_code == 2
    assert store.read().raw == initial.raw and inventory(location.path) == before


def test_work_mutex_remains_held_during_real_command_execution(recorded, tmp_path, monkeypatch):
    _, _, location, store = setup(tmp_path)
    native = execute_request
    probe = '''import os,fcntl,sys
fd=os.open(sys.argv[1],os.O_RDONLY|os.O_DIRECTORY)
try:
 try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
 except BlockingIOError:print('held')
 else:raise AssertionError('work lease lost')
finally:os.close(fd)
'''
    def checked(*args, **kwargs):
        child = subprocess.run([sys.executable, '-I', '-B', '-c', probe, str(location.path)],
                               capture_output=True, text=True)
        assert child.returncode == 0 and child.stdout.strip() == 'held', child.stderr
        with pytest.raises(BlockingIOError):
            resume_read_only_work(store)
        return native(*args, **kwargs)
    monkeypatch.setattr('specroad.work.resume.execute_request', checked)
    assert resume_read_only_work(store).executed
    assert not (location.path / 'work-lock.json').exists()


def test_publication_error_retains_previous_checkpoint_without_confirmed_result(recorded, tmp_path, monkeypatch):
    initial, _, location, store = setup(tmp_path)
    before = {p: p.read_bytes() for p in location.path.rglob('*') if p.is_file()}
    def unavailable(*args, **kwargs):
        raise OSError(errno.ENOSPC, 'injected work storage failure')
    with monkeypatch.context() as scoped:
        scoped.setattr('specroad.work.checkpoints._write_new', unavailable)
        with pytest.raises(OSError) as caught:
            resume_read_only_work(store)
    assert caught.value.errno == errno.ENOSPC
    assert store.read().raw == initial.raw
    assert all(path.read_bytes() == raw for path, raw in before.items())


def test_missing_necessary_checkpoint_bytes_never_execute_the_handler(recorded, tmp_path, monkeypatch):
    _, _, location, store = setup(tmp_path)
    pointer = json.loads((location.path / 'work.json').read_bytes())
    missing = location.path / 'checkpoints' / (pointer['checkpoint']['sha256'] + '.json')
    missing.unlink()
    def forbidden(*args, **kwargs):
        raise AssertionError('corrupt work executed')
    monkeypatch.setattr('specroad.work.resume.execute_request', forbidden)
    before = inventory(location.path)
    with no_write_attempts(), pytest.raises(CheckpointStorageError):
        resume_read_only_work(store)
    assert inventory(location.path) == before


PORTABLE = '''
import base64,json
from pathlib import Path
from specroad.cli.commands import builtin_registry
from specroad.cli.requests import CommandRequest
from specroad.security import ProjectBoundary
from specroad.work.manifest import read_work_manifest
from specroad.work.root import WorkDirectory
from specroad.work.checkpoints import CheckpointStore
from specroad.work.resume import prepare_read_only_work,resume_read_only_work
packet_path,work,project=map(Path,sys.argv[1:4])
if sys.argv[4]=='plan':
 initial=prepare_read_only_work(CommandRequest('schema.show',arguments={'schema_id':'json-envelope-v2'}))
 packet_path.write_text(json.dumps({'raw':base64.b64encode(initial.raw).decode(),
  'objects':{k:base64.b64encode(v).decode() for k,v in initial.objects.items()},
  'build':initial.as_dict()['tool_build']}))
else:
 packet=json.loads(packet_path.read_bytes())
 initial=read_work_manifest(base64.b64decode(packet['raw']),
  {k:base64.b64decode(v) for k,v in packet['objects'].items()},
  registry=builtin_registry(),expected_tool_build=packet['build'])
location=WorkDirectory(initial,protected_roots=(ProjectBoundary(project),),directory=work)
store=CheckpointStore(location,initial)
if sys.argv[4]=='plan':
 store.publish(initial);print(json.dumps(initial.as_dict()))
else:
 step=resume_read_only_work(store,cwd=project)
 print(json.dumps(step.as_dict()))
'''


@pytest.mark.parametrize('kind', ['module', 'zipapp'])
def test_real_built_distribution_resumes_in_new_process_and_new_compatible_paths(tmp_path, kind):
    output = tmp_path / 'distribution'
    built = subprocess.run([sys.executable, '-I', '-B', str(ROOT / 'tools/build_core.py'),
                            '--output', str(output)], capture_output=True, text=True)
    assert built.returncode == 0, built.stderr
    distribution = output / ('module' if kind == 'module' else 'specroad.pyz')
    packet, work, project = tmp_path / 'independent-binding.json', tmp_path / 'work', tmp_path / 'project'
    project.mkdir()
    def invoke(action):
        code = 'import sys;sys.path.insert(0,' + repr(str(distribution)) + ');' + PORTABLE
        result = subprocess.run([sys.executable, '-I', '-B', '-c', code,
            str(packet), str(work), str(project), action], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)
    initial = invoke('plan')
    before = inventory(project)
    moved = tmp_path / ('relocated-module' if kind == 'module' else 'relocated.pyz')
    distribution.rename(moved);distribution = moved
    work.rename(tmp_path / 'relocated-work');work = tmp_path / 'relocated-work'
    project.rename(tmp_path / 'relocated-project');project = tmp_path / 'relocated-project'
    resumed = invoke('resume');reused = invoke('resume')
    assert resumed['work_id'] == reused['work_id'] == initial['work_id']
    assert resumed['checkpoint_generation'] == reused['checkpoint_generation'] == 1
    assert resumed['executed'] is True and reused['executed'] is False
    assert resumed['checkpoint_sha256'] == reused['checkpoint_sha256']
    assert resumed['command_outcome'] == reused['command_outcome']
    assert resumed['command_outcome']['command'] == 'schema.show'
    assert resumed['command_outcome']['summary']['complete'] is True
    assert resumed['command_exit_code'] == 0 and resumed['work_state'] == 'running'
    assert inventory(project) == before and not (work / 'work-lock.json').exists()
