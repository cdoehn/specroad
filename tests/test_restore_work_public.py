"""Public Restore/Work parity over durable native files and current host grants."""
import shutil

import pytest

from specroad.cli.application import execute, execute_request
from specroad.cli.commands import builtin_registry
from specroad.cli.invocation_context import InvocationContextBuilder
from specroad.cli.requests import CommandRequest
from specroad.cli.results import thaw
from specroad.cli.result_schemas import validate_result_document
from specroad.work.open_existing import open_restore_work
from support.read_only import inventory, no_write_attempts
from support.restore import restore_case, plan_for
from test_restore_invocation import planning, execution, authority
from test_restore_invocation_options import invocation
from test_work_resume import recorded


ACTOR = {'actor_type': 'human', 'actor_id': 'synthetic-current-host'}


def work(operation, path, *, options=None, host=None, actor=None, representation='mapping'):
    request = CommandRequest('work.' + operation, options or {},
                            {'file' if operation == 'restore' else 'work_dir': str(path)})
    context = InvocationContextBuilder(recovery_authority=host, recovery_actor=actor)
    if representation == 'mapping':
        return execute_request(request, context_builder=context).result
    args = ['work', operation, str(path)]
    for key, value in (options or {}).items():
        args.append(key)
        if value is not True:
            args.append(value)
    return execute(args, context_builder=context).result


def start(options, representation, host=None):
    call = execute if representation == 'argv' else execute_request
    return call(invocation(options, representation),
        context_builder=InvocationContextBuilder(recovery_authority=host)).result


def assert_historical_replay(replay, completed):
    original = thaw(completed.result['data'])
    historical = thaw(replay.result['data'])
    for key in ('native_execution_checked', 'checkpoint_changed'):
        assert historical.pop(key) is False
        original.pop(key)
    assert historical == original


@pytest.mark.parametrize('kind', ['project_bundle', 'baseline'])
@pytest.mark.parametrize('representation', ['argv', 'mapping'])
def test_planning_work_keeps_exact_original_and_delivers_full_plan(recorded, tmp_path, kind, representation):
    options, _, _ = restore_case(tmp_path, kind)
    expected = plan_for(options)
    out = tmp_path / 'out'; out.mkdir()
    location = tmp_path / 'work'
    before = inventory(options['project_root'])
    first = start({**planning(options, out), '--work-dir': str(location)}, representation)
    assert first.exit_code == 8, str(thaw(first.details))
    assert first.continuation.claim.completed_units == 1
    for completed in range(2, first.continuation.claim.total_units):
        result = work('resume', location, representation=representation)
        assert result.exit_code == 8, result
        assert result.continuation.claim.completed_units == completed
    final = work('resume', location, representation=representation)
    assert final.exit_code == 0, final
    assert thaw(final.result['data']['restore_plan']) == expected.data
    assert (out / 'plans/original.json').read_bytes() == expected.source_bytes
    assert (location / 'results/restore-plan.json').read_bytes() == expected.source_bytes
    assert inventory(options['project_root']) == before
    saved = inventory(location)
    shutil.rmtree(options['source_root'])
    with no_write_attempts():
        replay = work('resume', location, representation=representation)
    assert replay.exit_code == 0, replay
    assert final.result['data']['checkpoint_changed'] is True
    assert_historical_replay(replay, final)
    assert inventory(location) == saved


@pytest.mark.parametrize('representation', ['argv', 'mapping'])
def test_execution_resume_needs_current_authority_and_delivers_original_native_result(recorded, tmp_path, representation):
    options, _, _ = restore_case(tmp_path)
    plan = plan_for(options)
    out = tmp_path / 'out'; out.mkdir()
    location = tmp_path / 'work'
    first = start({**execution(options, plan, out), '--work-dir': str(location)}, representation, authority())
    assert first.exit_code == 8, str(thaw(first.details))
    assert first.continuation.claim.completed_units == 1
    before = inventory(options['project_root'])
    refused = work('resume', location, representation=representation)
    assert refused.exit_code == 2, refused
    assert inventory(options['project_root']) == before
    completed = work('resume', location, host=authority(), actor=ACTOR, representation=representation)
    assert completed.exit_code == 0, completed
    validate_result_document('work-command-v1', thaw(completed.result))
    assert completed.result['data']['execution']['expected_target_root'] == plan.data['expected_target_root']
    saved = inventory(location)
    shutil.rmtree(options['project_root']); shutil.rmtree(options['source_root'])
    with no_write_attempts():
        replay = work('resume', location, representation=representation)
    assert replay.exit_code == 0, replay
    assert completed.result['data']['native_execution_checked'] is True
    assert_historical_replay(replay, completed)
    assert inventory(location) == saved


def test_status_prompt_cancel_are_passive_and_cancel_is_bound(recorded, tmp_path):
    options, _, _ = restore_case(tmp_path)
    out = tmp_path / 'out'; out.mkdir()
    location = tmp_path / 'work'
    first = start({**planning(options, out), '--work-dir': str(location)}, 'argv')
    assert first.exit_code == 8, str(thaw(first.details))
    before = inventory(tmp_path)
    with no_write_attempts():
        status = work('status', location)
        prompt = work('prompt', location)
    assert status.exit_code == prompt.exit_code == 0, (status, prompt)
    assert status.result['data']['progress']['completed_units'] == 1
    assert prompt.result['data']['control']['next_action']['command_id'] == 'work.resume'
    assert inventory(tmp_path) == before
    cancelled = work('cancel', location, options={'--reason': 'User cancels pending plan'})
    assert cancelled.exit_code == 0, cancelled
    assert cancelled.result['data']['state'] == 'cancelled'
    before = inventory(tmp_path)
    repeated = work('cancel', location, options={'--reason': 'Different reason'})
    assert repeated.exit_code == 6, repeated
    assert work('resume', location).exit_code == 6
    assert inventory(tmp_path) == before


def test_completed_work_package_restores_result_files_without_original_roots(recorded, tmp_path):
    options, _, _ = restore_case(tmp_path)
    out = tmp_path / 'out'; out.mkdir()
    location = tmp_path / 'work'
    assert start({**execution(options, plan_for(options), out), '--work-dir': str(location)},
                 'mapping', authority()).exit_code == 8
    completed = work('resume', location, host=authority(), actor=ACTOR)
    assert completed.exit_code == 0, completed
    transport = tmp_path / 'transport'; transport.mkdir()
    package = transport / 'work.zip'
    exported = work('export', location, options={'--output': str(package)})
    assert exported.exit_code == 0, exported
    assert exported.result['data']['external_backup_confirmed'] is False
    shutil.rmtree(options['project_root']); shutil.rmtree(options['source_root']); shutil.rmtree(location)
    relocated = tmp_path / 'relocated'
    restored = work('restore', package, options={'--output': str(relocated)})
    assert restored.exit_code == 0, thaw(restored.details)
    assert restored.result['data']['state'] == 'completed'
    with no_write_attempts():
        replay = work('resume', relocated)
    assert replay.exit_code == 0, replay
    assert_historical_replay(replay, completed)


def test_changed_original_capture_refuses_resume_without_replanning(recorded, tmp_path):
    options, _, _ = restore_case(tmp_path)
    out = tmp_path / 'out'; out.mkdir()
    location = tmp_path / 'work'
    first = start({**planning(options, out), '--work-dir': str(location)}, 'mapping')
    assert first.exit_code == 8, str(thaw(first.details))
    original = options['source_root'] / options['source_path']
    original.write_bytes(b'changed')
    # Qualification must compare the original captured source with its current
    # location, never replace the source by newly arrived bytes.
    for _ in range(first.continuation.claim.total_units):
        failed = work('resume', location)
        if failed.exit_code != 8:
            break
    assert failed.exit_code == 6, failed
    assert not (out / 'plans/original.json').exists()


def test_existing_work_directory_and_changed_resume_root_are_rejected(recorded, tmp_path):
    options, _, _ = restore_case(tmp_path)
    out = tmp_path / 'out'; out.mkdir()
    location = tmp_path / 'work'
    request = {**planning(options, out), '--work-dir': str(location)}
    first = start(request, 'mapping'); assert first.exit_code == 8, str(thaw(first.details))
    before = inventory(tmp_path)
    repeated = start(request, 'mapping')
    assert repeated.exit_code != 0 and repeated.exit_code != 8
    changed = work('resume', location, options={'--project': str(out)})
    assert changed.exit_code == 6, changed
    assert inventory(tmp_path) == before
