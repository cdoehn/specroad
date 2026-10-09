"""Restored result controls, hostile final parts and late compatibility changes."""

import json

import pytest

from specroad import _build
from specroad.cli.application import execute_request
from specroad.cli.commands import builtin_registry
from specroad.cli.requests import CommandRequest
from specroad.cli.results import CommandResult
from specroad.model.canonical import canonical_json_bytes
from specroad.work.finalization import finalize_read_only_work
from specroad.work.manifest import (WorkManifestError, _put, complete_work_manifest,
                                   partition_work_manifest, read_work_successor)
from specroad.work.resume import WorkResumeError, resume_read_only_work
from support.read_only import inventory, no_write_attempts
from test_work_finalization import complete_units, declared_failure
from test_work_manifest import BUILD, sealed
from test_work_resume import recorded, setup
from test_work_resume_right import setup as normative_setup


FALSE_CONTROLS = [
    ('partial_scope', 'only a local subset'), ('delivery', 'external'),
    ('work_id', 'WORK-00000000000000000000000000'), ('completed_units', 1),
    ('total_units', 2), ('remaining_manifest_sha256', '0' * 64),
    ('checkpoint', '/missing/unverified-checkpoint'),
    ('next_action', {'command_id':'work.resume','arguments':{'work_dir':'/missing/work'}}),
    ('failure_kind', 'policy'),
]


@pytest.mark.parametrize('field,claim', FALSE_CONTROLS, ids=[x[0] for x in FALSE_CONTROLS])
@pytest.mark.parametrize('operation', ['candidate', 'resume', 'finalize'])
def test_self_hashed_success_cannot_smuggle_partial_external_or_continuation_controls(recorded, tmp_path, monkeypatch, field, claim, operation):
    initial, _, location, store = setup(tmp_path)
    request = CommandRequest('version');unit = initial.entries('tasks')[0]['unit_id']
    original = execute_request(request).result.as_dict()
    document = json.loads(canonical_json_bytes(original));document['summary'][field] = claim
    record = {'format_version':'read-only-handler-evidence-v1','unit_id':unit,
        'request':request.as_dict(),'tool_build':initial.as_dict()['tool_build'],
        'exit_code':0,'outcome':original if operation == 'candidate' else document}
    saved = partition_work_manifest(initial, {unit:canonical_json_bytes(record)})
    store.publish(saved);before = inventory(location.path)
    def forbidden(*args, **kwargs):
        raise AssertionError('false completion caused a new execution')
    monkeypatch.setattr('specroad.work.resume.execute_request', forbidden)
    if operation == 'candidate':
        with no_write_attempts(), pytest.raises(WorkManifestError):
            complete_work_manifest(saved, document, exit_code=0)
    else:
        entry = resume_read_only_work if operation == 'resume' else finalize_read_only_work
        with no_write_attempts(), pytest.raises(WorkResumeError) as caught:
            entry(store)
        assert caught.value.exit_code == 6
    assert inventory(location.path) == before and store.read().raw == saved.raw


def test_noncontrol_command_details_remain_valid_and_byte_preserved(recorded, tmp_path):
    _, _, _, store = setup(tmp_path);step = resume_read_only_work(store)
    document = step.as_dict()['command_outcome'];document['summary']['fixture_detail'] = {'measured':None}
    with no_write_attempts():
        candidate = complete_work_manifest(step.manifest, document, exit_code=0)
    record = json.loads(candidate.objects[candidate.as_dict()['result_parts'][0]['sha256']])
    assert record['outcome'] == document


@pytest.mark.parametrize('entry', [resume_read_only_work, finalize_read_only_work], ids=['resume','finalize'])
def test_validly_rehashed_final_result_cannot_replace_actual_confirmed_handler_output(recorded, tmp_path, entry):
    _, _, location, store = setup(tmp_path);step = resume_read_only_work(store)
    document = step.as_dict()['command_outcome'];document['result']['program_version'] = 'changed result fixture'
    # A data candidate is not execution proof, even when published consistently.
    candidate = complete_work_manifest(step.manifest, document, exit_code=0)
    store.publish(candidate);before = inventory(location.path)
    with no_write_attempts(), pytest.raises(WorkResumeError) as caught:
        entry(store)
    assert caught.value.reason == 'final_result_differs_from_confirmed_handler'
    assert caught.value.exit_code == 6 and inventory(location.path) == before


@pytest.mark.parametrize('change', ['binding', 'parent', 'generation', 'missing_diagnostic',
                                    'reordered_diagnostics', 'changed_diagnostic', 'extra_result', 'format'])
def test_rehashed_final_data_cannot_lose_global_diagnostics_or_its_original_parent(change):
    initial, result = declared_failure();previous = complete_units(initial)
    final = complete_work_manifest(previous, result.as_dict(), exit_code=1)
    value = final.as_dict();objects = dict(final.objects)
    record = json.loads(objects[value['result_parts'][0]['sha256']])
    if change == 'binding':record['binding']['source_bindings']['scope'] = ['foreign']
    elif change == 'parent':record['source_checkpoint_sha256'] = '0' * 64
    elif change == 'generation':record['source_checkpoint_generation'] += 1
    elif change == 'format':record['format_version'] = 'future'
    elif change == 'extra_result':value['result_parts'].append(dict(value['result_parts'][0]))
    else:
        diagnostics = json.loads(objects[value['diagnostic_parts'][0]['sha256']])
        if change == 'missing_diagnostic':diagnostics['diagnostics'].pop()
        elif change == 'reordered_diagnostics':diagnostics['diagnostics'].reverse()
        else:diagnostics['diagnostics'][0]['code'] = 'FOREIGN'
        value['diagnostic_parts'] = [_put(canonical_json_bytes(diagnostics), objects)]
    if change != 'extra_result':
        value['result_parts'] = [_put(canonical_json_bytes(record), objects)]
    with no_write_attempts(), pytest.raises(WorkManifestError):
        read_work_successor(sealed(value), objects, previous=previous,
                            registry=initial._registry, expected_tool_build=BUILD)
    original = json.loads(final.objects[final.as_dict()['result_parts'][0]['sha256']])
    assert original['outcome'] == result.as_dict() and original['exit_code'] == 1


@pytest.mark.parametrize('boundary', ['context', 'publication'])
def test_runtime_change_at_finalization_boundary_keeps_actual_generation_without_returning_success(recorded, tmp_path, monkeypatch, boundary):
    _, _, location, store = setup(tmp_path);resume_read_only_work(store)
    def change_build():
        monkeypatch.setattr(_build, 'BUILD_METADATA', {'format_version':1,
            'hash_algorithm':'specroad-dev-payload-v1','build_sha256':'b' * 64})
    original = dict(_build.BUILD_METADATA)
    with monkeypatch.context() as scoped:
        if boundary == 'context':
            from specroad.cli.invocation_context import InvocationContextBuilder
            native = InvocationContextBuilder.prepare
            def changed(*args, **kwargs):
                answer = native(*args, **kwargs);change_build();return answer
            scoped.setattr(InvocationContextBuilder, 'prepare', changed)
        else:
            from specroad.work import checkpoints
            native = checkpoints.replace_bound_image
            def changed(*args, **kwargs):
                answer = native(*args, **kwargs);change_build();return answer
            scoped.setattr(checkpoints, 'replace_bound_image', changed)
        with pytest.raises(WorkResumeError) as caught:
            finalize_read_only_work(store)
    assert caught.value.reason == 'runtime_build_changed' and caught.value.exit_code == 6
    retained = store.read()
    assert retained.as_dict()['checkpoint_generation'] == (1 if boundary == 'context' else 2)
    assert retained.as_dict()['state'] == ('running' if boundary == 'context' else 'completed')
    monkeypatch.setattr(_build, 'BUILD_METADATA', original)
    def forbidden(*args, **kwargs):raise AssertionError('confirmed handler ran again')
    monkeypatch.setattr('specroad.work.resume.execute_request', forbidden)
    again = finalize_read_only_work(store)
    assert again.as_dict()['work_state'] == 'completed'
    assert again.finalized is (boundary == 'context')


@pytest.mark.parametrize('operation', ['candidate','live'])
def test_normative_preparation_cannot_be_closed_as_a_readonly_success_receipt(recorded, tmp_path, operation):
    _, _, _, initial, _, store = normative_setup(tmp_path)
    prepared = complete_units(initial);store.publish(prepared);before = inventory(tmp_path)
    if operation == 'candidate':
        claimed = CommandResult('change.apply', result={'fixture_claim':'success'}).as_dict()
        with no_write_attempts(), pytest.raises(WorkManifestError):
            complete_work_manifest(prepared, claimed, exit_code=0)
    else:
        with no_write_attempts(), pytest.raises(WorkResumeError):
            finalize_read_only_work(store)
    assert store.read().as_dict()['state'] == 'running' and inventory(tmp_path) == before
