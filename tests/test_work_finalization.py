"""Complete durable results, separate functional failures and retained work."""

from dataclasses import FrozenInstanceError
import errno
import json
import subprocess
import sys

import pytest

from specroad.cli.commands import builtin_registry
from specroad.cli.contracts import CommandClass, CommandProtocol, CommandSpec, EffectScope, PreflightProfile
from specroad.cli.registry import CommandRegistry
from specroad.cli.requests import CommandRequest
from specroad.cli.results import CommandResult, FailureKind
from specroad.diagnostics import Diagnostic
from specroad.model.canonical import canonical_json_bytes
from specroad.model.errors import ModelError
from specroad.runtime.consumption import WorkConsumption
from specroad.work.checkpoints import CheckpointStorageError
from specroad.work.finalization import ReadOnlyWorkCompletion, finalize_read_only_work
from specroad.work.manifest import (WorkManifestError, complete_work_manifest, create_work_manifest,
                                   partition_work_manifest, read_work_manifest, read_work_successor)
from specroad.work.progress import advance_read_only_work_outcome
from specroad.work.resume import WorkResumeError, resume_read_only_work
from support.read_only import inventory, no_write_attempts
from test_work_manifest import BUILD, SOURCES, sealed
from test_work_progress import unknown
from test_work_resume import PORTABLE, REQUESTS, ROOT, recorded, setup


@pytest.mark.parametrize('command_request', REQUESTS, ids=lambda value: value.command_id)
def test_actual_complete_handler_result_is_durably_finalized_once(recorded, tmp_path, monkeypatch, command_request):
    initial, roots, location, store = setup(tmp_path, command_request)
    unit = resume_read_only_work(store)
    protected = inventory(roots[0].root)
    def forbidden(*args, **kwargs):
        raise AssertionError('finalization reexecuted the completed handler')
    monkeypatch.setattr('specroad.work.resume.execute_request', forbidden)
    final = finalize_read_only_work(store)
    value = final.as_dict();current = final.manifest
    assert final.finalized and value['work_state'] == 'completed' and value['command_exit_code'] == 0
    assert value['checkpoint_generation'] == 2 and current.as_dict()['progress'] == {'completed_units':1,'total_units':1}
    assert value['command_outcome'] == unit.as_dict()['command_outcome']
    assert final.outcome_bytes == unit.outcome_bytes and store.read().raw == current.raw
    assert value['next_action'] == {'operation':'deliver_completed_work'}
    assert not value['semantic_receipt_created'] and not value['project_writes_performed']
    assert all(current.objects[digest] == raw for digest,raw in unit.manifest.objects.items())
    record = json.loads(current.objects[current.as_dict()['result_parts'][0]['sha256']])
    diagnostics = json.loads(current.objects[current.as_dict()['diagnostic_parts'][0]['sha256']])
    assert record['source_checkpoint_sha256'] == unit.manifest.as_dict()['checkpoint_sha256']
    assert record['source_checkpoint_generation'] == 1 and record['outcome'] == value['command_outcome']
    assert diagnostics['diagnostics'] == value['command_outcome']['diagnostics']
    before = inventory(location.path)
    again = finalize_read_only_work(store)
    resumed = resume_read_only_work(store)
    assert not again.finalized and again.manifest.raw == current.raw
    assert again.outcome_bytes == resumed.outcome_bytes == final.outcome_bytes and not resumed.executed
    assert resumed.as_dict()['work_state'] == 'completed' and inventory(location.path) == before
    assert inventory(roots[0].root) == protected


def test_pending_unit_cannot_publish_a_final_result_or_execute_work(recorded, tmp_path, monkeypatch):
    initial, _, _, store = setup(tmp_path);before = inventory(tmp_path)
    def forbidden(*args, **kwargs):
        raise AssertionError('finalization executed unfinished work')
    monkeypatch.setattr('specroad.work.resume.execute_request', forbidden)
    with no_write_attempts(), pytest.raises(WorkResumeError) as caught:
        finalize_read_only_work(store)
    assert caught.value.reason == 'unfinished_work_cannot_complete'
    assert store.read().raw == initial.raw and inventory(tmp_path) == before


def test_missing_work_is_not_created_to_claim_a_completion(recorded, tmp_path):
    _, _, _, store = setup(tmp_path, publish=False);before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(FileNotFoundError):
        finalize_read_only_work(store)
    assert inventory(tmp_path) == before


def declared_failure(*, complete=True):
    # Explicit trusted-planner data fixture, not an installed CLI validator or
    # a claim that these opaque unit records prove production graph execution.
    def forbidden(invocation):
        raise AssertionError('inert finalization invoked stored/planner code')
    registry = CommandRegistry((CommandSpec('fixture.validate', ('fixture','validate'),
        CommandClass.READ_ONLY, PreflightProfile.BOOTSTRAP, EffectScope.NONE, forbidden,
        protocol=CommandProtocol('version-info-v1', {'command_id':'fixture.validate'},
            handler_exit_codes=(0,1), diagnostic_codes=('FIXTURE_GLOBAL_ERROR','FIXTURE_LOCAL_INFO'))),))
    initial = create_work_manifest(registry, CommandRequest('fixture.validate'), tool_build=BUILD,
        source_bindings=SOURCES, inputs=[], units=[
            {'key':'local', 'phase':'local', 'range':{}},
            {'key':'global-closure', 'phase':'global-closure', 'range':{}}])
    result = CommandResult.failed('fixture.validate', FailureKind.POLICY, complete=complete,
        diagnostics=(Diagnostic('FIXTURE_GLOBAL_ERROR','error','global_closure','Labelled global error'),
                     Diagnostic('FIXTURE_LOCAL_INFO','info','local','Labelled local information')))
    return initial, result


def complete_units(initial):
    return partition_work_manifest(initial, {row['unit_id']: canonical_json_bytes({'fixture_unit':row['key']})
                                            for row in initial.entries('remaining')})


def test_completed_data_retains_full_failed_outcome_and_every_provided_diagnostic():
    initial, result = declared_failure();previous = complete_units(initial)
    with no_write_attempts():
        final = complete_work_manifest(previous, result.as_dict(), exit_code=result.exit_code)
        restored = read_work_successor(final.raw, final.objects, previous=previous,
            registry=initial._registry, expected_tool_build=BUILD)
    assert restored.as_dict()['state'] == 'completed' and not restored.entries('remaining')
    record = json.loads(restored.objects[restored.as_dict()['result_parts'][0]['sha256']])
    diagnostics = json.loads(restored.objects[restored.as_dict()['diagnostic_parts'][0]['sha256']])
    assert record['exit_code'] == 1 and record['outcome']['status'] == 'failed'
    assert record['outcome'] == result.as_dict() and record['outcome']['summary']['complete'] is True
    assert diagnostics['diagnostics'] == result.as_dict()['diagnostics'] and len(diagnostics['diagnostics']) == 2
    assert restored.entries('completed') == previous.entries('completed')
    assert all(restored.objects[key] == raw for key,raw in previous.objects.items())


def test_local_completion_cannot_replace_the_explicit_remaining_global_phase():
    initial, result = declared_failure();first = initial.entries('tasks')[0]
    local = partition_work_manifest(initial, {first['unit_id']: b'{"fixture_local_passed":true}'})
    with no_write_attempts(), pytest.raises(WorkManifestError):
        complete_work_manifest(local, result.as_dict(), exit_code=1)
    assert local.as_dict()['state'] == 'running'
    assert [row['phase'] for row in local.entries('remaining')] == ['global-closure']
    assert local.as_dict()['result_parts'] == local.as_dict()['diagnostic_parts'] == []


@pytest.mark.parametrize('change', ['incomplete', 'wrong_command', 'wrong_code', 'continuation_code',
                                    'unknown_diagnostic', 'wrong_failure_kind'])
def test_incomplete_or_mismatched_machine_result_cannot_be_completed(change):
    initial, result = declared_failure();previous = complete_units(initial)
    document = result.as_dict();code = 1
    if change == 'incomplete':document['summary']['complete'] = False
    elif change == 'wrong_command':document['command'] = 'another.command'
    elif change == 'wrong_code':code = 0
    elif change == 'continuation_code':code = 8
    elif change == 'unknown_diagnostic':document['diagnostics'][0]['code'] = 'FOREIGN_CODE'
    else:document['summary']['failure_kind'] = 'environment'
    before = previous.raw
    with no_write_attempts(), pytest.raises((WorkManifestError, ModelError)):
        complete_work_manifest(previous, document, exit_code=code)
    assert previous.raw == before and previous.as_dict()['state'] == 'running'


def test_generic_planner_completions_do_not_authorize_the_closed_live_adapter(recorded, tmp_path):
    # Use the actual recorded build, but retain the explicitly different plan.
    _, _, _, template = setup(tmp_path)
    initial = create_work_manifest(builtin_registry(), CommandRequest('version'),
        tool_build=template._initial.as_dict()['tool_build'],
        source_bindings={'project_id':None,'scope':[],'model_root_sha256':None}, inputs=[],
        units=[{'key':'local','phase':'local','range':{}},
               {'key':'closure','phase':'global-closure','range':{}}])
    other = tmp_path/'other';other.mkdir()
    _, _, _, store = setup(other, initial=initial)
    store.publish(complete_units(initial));before = inventory(other)
    with no_write_attempts(), pytest.raises(WorkResumeError) as caught:
        finalize_read_only_work(store)
    assert caught.value.reason == 'unsupported_resume_plan' and inventory(other) == before


@pytest.mark.parametrize('late', [False, True])
def test_publication_failure_keeps_actual_old_or_new_generation_without_false_return(recorded, tmp_path, monkeypatch, late):
    _, roots, location, store = setup(tmp_path);resume_read_only_work(store)
    protected = inventory(roots[0].root)
    from specroad.work import checkpoints
    native = checkpoints.replace_bound_image
    def refuse(*args, **kwargs):
        if late:native(*args, **kwargs)
        raise OSError(errno.EIO if late else errno.ENOSPC, 'Labelled final-publication failure')
    with monkeypatch.context() as scoped:
        scoped.setattr(checkpoints, 'replace_bound_image' if late else '_write_new', refuse)
        with pytest.raises(OSError):
            finalize_read_only_work(store)
    retained = store.read()
    assert retained.as_dict()['checkpoint_generation'] == (2 if late else 1)
    assert retained.as_dict()['state'] == ('completed' if late else 'running')
    def forbidden(*args, **kwargs):
        raise AssertionError('finalization recovery reexecuted the handler')
    monkeypatch.setattr('specroad.work.resume.execute_request', forbidden)
    recovered = finalize_read_only_work(store)
    assert recovered.finalized is not late and recovered.as_dict()['work_state'] == 'completed'
    assert inventory(roots[0].root) == protected


def test_lost_final_result_bytes_prevent_replaying_a_completed_claim(recorded, tmp_path):
    _, _, location, store = setup(tmp_path);resume_read_only_work(store)
    final = finalize_read_only_work(store)
    digest = final.manifest.as_dict()['result_parts'][0]['sha256']
    (location.path/'objects'/digest).unlink();before = inventory(location.path)
    with no_write_attempts(), pytest.raises(CheckpointStorageError):
        finalize_read_only_work(store)
    assert inventory(location.path) == before


def test_completed_manifest_is_terminal_and_cannot_create_an_empty_successor(recorded, tmp_path):
    _, _, _, store = setup(tmp_path);resume_read_only_work(store)
    current = finalize_read_only_work(store).manifest
    with no_write_attempts(), pytest.raises(WorkManifestError):
        complete_work_manifest(current, {}, exit_code=0)
    value = current.as_dict();value['checkpoint_generation'] += 1
    with no_write_attempts(), pytest.raises(WorkManifestError):
        read_work_successor(sealed(value), current.objects, previous=current,
            registry=builtin_registry(), expected_tool_build=value['tool_build'])


def test_returned_completion_is_frozen_and_does_not_expose_mutable_saved_bytes(recorded, tmp_path):
    _, _, _, store = setup(tmp_path);resume_read_only_work(store)
    result = finalize_read_only_work(store);before = result.as_dict()
    with pytest.raises(TypeError):ReadOnlyWorkCompletion()
    with pytest.raises(FrozenInstanceError):result.finalized = False
    detached = result.as_dict();detached['command_outcome']['command'] = 'foreign'
    assert result.as_dict() == before


def test_progress_reuse_reports_already_completed_work_without_another_finalization(recorded, tmp_path):
    _, _, location, store = setup(tmp_path);resume_read_only_work(store);finalize_read_only_work(store)
    before = inventory(location.path);call = WorkConsumption(sampler=unknown).begin({})
    try:result = advance_read_only_work_outcome(store, call)
    finally:call.finish()
    assert not result['global_finalization_required'] and not result['window']['global_finalization_required']
    assert not result['window']['progress_made'] and result['window']['step']['work_state'] == 'completed'
    assert inventory(location.path) == before


@pytest.mark.parametrize('kind', ['module', 'zipapp'])
def test_real_built_process_delivers_the_same_final_result_after_relocation(tmp_path, kind):
    output = tmp_path/'distribution'
    built = subprocess.run([sys.executable,'-I','-B',str(ROOT/'tools/build_core.py'),
                            '--output',str(output)], capture_output=True, text=True)
    assert built.returncode == 0, built.stderr
    distribution = output/('module' if kind == 'module' else 'specroad.pyz')
    packet,work,project = tmp_path/'initial.json',tmp_path/'work',tmp_path/'project';project.mkdir()
    code = PORTABLE.replace('step=resume_read_only_work(store,cwd=project)',
        "from specroad.work.finalization import finalize_read_only_work\n step=(finalize_read_only_work(store,cwd=project) if sys.argv[4]=='finalize' else resume_read_only_work(store,cwd=project))")
    def invoke(action):
        script = 'import sys;sys.path.insert(0,'+repr(str(distribution))+');'+code
        result = subprocess.run([sys.executable,'-I','-B','-c',script,str(packet),str(work),str(project),action],
                                capture_output=True,text=True)
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)
    initial = invoke('plan');unit = invoke('resume');first = invoke('finalize')
    before = inventory(project)
    moved = tmp_path/('moved-module' if kind == 'module' else 'moved.pyz');distribution.rename(moved);distribution=moved
    work.rename(tmp_path/'moved-work');work=tmp_path/'moved-work'
    project.rename(tmp_path/'moved-project');project=tmp_path/'moved-project'
    again = invoke('finalize');resumed = invoke('resume')
    assert first['finalized'] and not again['finalized'] and not resumed['executed']
    assert first['work_id'] == again['work_id'] == initial['work_id']
    assert first['checkpoint_generation'] == again['checkpoint_generation'] == resumed['checkpoint_generation'] == 2
    assert first['checkpoint_sha256'] == again['checkpoint_sha256'] == resumed['checkpoint_sha256']
    assert first['command_outcome'] == again['command_outcome'] == resumed['command_outcome'] == unit['command_outcome']
    assert first['work_state'] == again['work_state'] == resumed['work_state'] == 'completed'
    assert inventory(project) == before
