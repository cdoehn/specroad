"""Diagnostic: a missing terminal checkpoint is not passive completed work."""
import errno

import pytest

from specroad.cli.application import execute_request
from specroad.cli.commands import builtin_registry
from specroad.cli.requests import CommandRequest
from specroad.work._request_binding import _command
from specroad.work.checkpoints import CheckpointStore
from specroad.model.canonical import canonical_json_bytes
from specroad.work.manifest import _create_manifest, partition_work_manifest
from specroad.work.open_existing import protected_paths
from specroad.work.restore_execution import _build
from specroad.work.root import WorkDirectory
from support.read_only import inventory
from support.restore import restore_case
from test_restore_invocation import planning
from test_work_resume import recorded


@pytest.mark.parametrize('adapter', ['legacy', 'capture'])
@pytest.mark.parametrize('after', [False, True])
def test_last_planning_checkpoint_failure_keeps_active_and_terminal_work_distinct(recorded, tmp_path, monkeypatch, after, adapter):
    options, _, _ = restore_case(tmp_path)
    out = tmp_path / 'output'; out.mkdir()
    path = tmp_path / 'work'
    registry = builtin_registry()
    request = CommandRequest('recover.restore', planning(options, out))
    if adapter == 'legacy':
        initial = _create_manifest(registry, _command(registry, request, recovery=True),
            tool_build=_build(), source_bindings={'project_id': None, 'scope': ['project'],
                'model_root_sha256': None}, inputs=[], units=[{'key': phase, 'phase': phase,
                    'range': {'adapter': 'native-restore-planning-work-v1'}}
                for phase in ('source_capture', 'inventory_capture', 'qualify_plan', 'deliver_plan')])
    else:
        from specroad.work.restore_planning import prepare_planning_work
        initial = prepare_planning_work(registry, request)
    store = CheckpointStore(WorkDirectory(initial, protected_roots=(),
        protected_paths=protected_paths(initial), directory=path), initial)
    store.publish(initial)
    resume = CommandRequest('work.resume', {}, {'work_dir': str(path)})
    if adapter == 'capture':
        # Publish real captured originals through the ordinary manifest/store
        # API. Qualification and the failing delivery remain public commands.
        from specroad.work._restore_capture import capture
        captured = {}
        for task in initial.entries('tasks')[:-2]:
            captured[task['unit_id']] = canonical_json_bytes({
                'phase': task['phase'], 'work_id': initial.as_dict()['work_id'],
                'chunk': capture(request.options, task)})
        store.publish(partition_work_manifest(initial, captured))
    for _ in range(3 if adapter == 'legacy' else 1):
        result = execute_request(resume).result
        assert result.exit_code == 8, result
    native = CheckpointStore._publish_held
    reached = []
    def fail(self, held, candidate, expected):
        if candidate.as_dict()['state'] == 'completed':
            reached.append(True)
            if after:
                native(self, held, candidate, expected)
            raise OSError(errno.EIO, 'Synthetic terminal checkpoint I/O failure')
        return native(self, held, candidate, expected)
    with monkeypatch.context() as fault:
        fault.setattr(CheckpointStore, '_publish_held', fail)
        failed = execute_request(resume).result
    assert reached and failed.exit_code == 5, failed
    original_plan = (out / 'plans/original.json').read_bytes()
    origin = options['source_root'] / options['source_path']
    origin.write_bytes(b'changed original source')
    before = inventory(tmp_path)
    retry = execute_request(resume).result
    assert retry.exit_code == (0 if after else 6), retry
    if after:
        assert not retry.result['data']['checkpoint_changed']
        assert not retry.result['data']['native_execution_checked']
    assert inventory(tmp_path) == before
    assert (out / 'plans/original.json').read_bytes() == original_plan
