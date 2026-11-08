"""17.l.W: complete source parity, exact target bytes and genuine Work progress."""
from support.merge_matrix import template, recorded, source_kinds, work_windows
from base64 import b64decode
from hashlib import sha256
import json

import pytest

from specroad.cli.result_schemas import validate_result_document
from specroad.merge.preparation import prepare_merge
from specroad.merge import prepare_merge_target, resolve_merge_conflict
from specroad.model.canonical import canonical_json_bytes as jcs
from specroad.model.errors import ModelError
from specroad.work.merge import resume_merge_work, merge_work_result
from specroad.work.resume import WorkResumeError
from specroad.work.manifest import partition_work_manifest
from support.merge_preparation import baseline_template, baseline_document_gate, adapter_case, store_for, finish
from support.merge_resolution import PLAN_ID, ACTOR, WHEN
from support.merge_target import small_seed, replace, inputs
from support.domain import domain_value
from support.inspection import inspection_project
from support.languages import small_restore_registry
from support.records import record_value, block_value
from support.read_only import inventory, no_write_attempts
from test_baseline_creation import preview


@pytest.mark.parametrize('variant,reason', [
    ('valid', None),
    ('missing-primary', 'document_primary_missing'),
    ('orphan-section', 'document_section_parent_cardinality'),
    ('unsupported-block', 'merge_fixture_document_specialist_required'),
], ids=['valid', 'missing-primary', 'orphan-section', 'unsupported-block'])
def test_native_baseline_document_gate_checks_real_target_without_authority(tmp_path, variant, reason):
    values = [record_value('document'), domain_value('goal')]
    if variant == 'missing-primary':
        values[0]['document_role'] = 'supporting'
    elif variant == 'orphan-section':
        values.append(record_value('section'))
    elif variant == 'unsupported-block':
        values.append(block_value('prose'))
    model = inspection_project(tmp_path/'project', artifacts=values,
                               language_registry=small_restore_registry())
    before = inventory(tmp_path)
    with no_write_attempts():
        unavailable = preview(model)
        actual = preview(model, gates=(baseline_document_gate(model),))
    assert inventory(tmp_path) == before
    def document_stage(result):
        return next(stage for stage in result['assessment']['validation']['source_report']['stages']
                    if stage['stage'] == 'document_model')
    assert unavailable['target_validated'] is False
    assert document_stage(unavailable)['status'] == 'unavailable'
    assert actual['write_state'] == 'not_committed' and not actual['approval_granted']
    stage = document_stage(actual)
    if reason is None:
        assert actual['target_validated'] is True and stage['status'] == 'passed', actual['diagnostics']
    else:
        assert actual['target_validated'] is False and stage['status'] == 'failed'
        assert reason in {finding['reason'] for finding in stage['diagnostics']}


@source_kinds
def test_each_native_source_kind_has_identical_complete_target_bytes(tmp_path, template, kind):
    sources, history, _ = adapter_case(tmp_path/'input', template, kind)
    before = inventory(tmp_path)
    result = prepare_merge(sources, plan_id=PLAN_ID, history=history)
    assert inventory(tmp_path) == before
    assert result['target']['target_validated'] is True, result['target']
    assert {row['path']: b64decode(row['bytes_base64']) for row in result['target_files']} == template[0]
    assert result['target']['expected_target_model_root_sha256'] == sources.ours.binding['model_root_sha256']
    assert json.loads(b64decode(result['plan_bytes_base64']))['conflicts'] == []
    assert result['changed'] is False
    assert result['source_observation'] == 'sealed_snapshot'
    assert all(result[field] is False for field in ('project_writes_performed', 'write_authorized', 'approval_granted'))


def test_result_contract_accepts_only_boolean_or_null_change(tmp_path, template):
    sources, history, _ = adapter_case(tmp_path/'input', template, 'local')
    result = prepare_merge(sources, plan_id=PLAN_ID, history=history)
    assert result['target']['target_validated'] is True
    # Public structural contract, including JSON booleans versus Python's
    # numerically equal 0/1; the trusted schema engine remains strict.
    for value in (False, True, None):
        validate_result_document('merge-preparation-v1', dict(result, changed=value))
    for value in (0, 1, 'false', [], {}):
        with pytest.raises(ModelError):
            validate_result_document('merge-preparation-v1', dict(result, changed=value))


def test_missing_primary_document_remains_negative_after_complete_work(recorded, tmp_path):
    files = small_seed(tmp_path/'seed', values=[domain_value('goal')])
    sources, history, _, _ = inputs(tmp_path/'input', [files, files, files])
    expected = prepare_merge(sources, plan_id=PLAN_ID, history=history)
    before = inventory(tmp_path/'input')
    result, code = finish(store_for(tmp_path/'work', sources, history, fail_on_change=True), 100000)
    assert code == 0 and result == expected and inventory(tmp_path/'input') == before
    assert result['target']['checks_complete'] is True
    assert result['target']['target_validated'] is False
    assert any(row['reason'] == 'document_primary_missing' for row in result['target']['conflicts'])
    assert result['target_files'] == [] and result['changed'] is None
    assert all(result[key] is False for key in ('project_writes_performed', 'approval_granted', 'write_authorized'))
    validate_result_document('merge-preparation-v1', result)


@work_windows
@source_kinds
def test_direct_and_partitioned_work_keep_identical_all_phase_results(recorded, tmp_path, template, kind, window):
    sources, history, _ = adapter_case(tmp_path/'input', template, kind)
    expected = prepare_merge(sources, plan_id=PLAN_ID, history=history)
    before = inventory(tmp_path/'input')
    store = store_for(tmp_path/'work', sources, history)
    actual, code = finish(store, window)
    assert code == 0 and jcs(actual) == jcs(expected)
    assert inventory(tmp_path/'input') == before
    terminal = inventory(tmp_path/'work')
    assert resume_merge_work(store).as_dict()['state'] == 'completed'
    assert merge_work_result(store)[0] == actual and inventory(tmp_path/'work') == terminal


def test_real_independent_changes_survive_work(recorded, tmp_path):
    files = small_seed(tmp_path/'seed')
    values = inputs(tmp_path/'input', [files, replace(files, 'goal', title='ours'),
                                     replace(files, 'goal', statement='theirs')])
    sources, history, plan, metadata = values
    expected_target = prepare_merge_target(metadata.canonical_bytes, plan.canonical_bytes, sources,
        history=history, expected_metadata_sha256=metadata.sha256, expected_plan_sha256=plan.sha256)
    store = store_for(tmp_path/'work', sources, history, fail_on_change=True)
    result, code = finish(store, 100000)
    assert code == 1 and result['changed'] is True
    actual = {row['path']: b64decode(row['bytes_base64']) for row in result['target_files']}
    assert actual == expected_target.files
    goal = next(json.loads(raw) for path, raw in actual.items() if path.startswith('spec/goals/'))
    assert goal['title'] == 'ours' and goal['statement'] == 'theirs'


def test_large_source_is_completely_bound_across_multiple_integrity_blocks(recorded, tmp_path):
    files = replace(small_seed(tmp_path/'seed'), 'goal', statement='x'*70000)
    sources, history, _, _ = inputs(tmp_path/'input', [files, files, files])
    expected = prepare_merge(sources, plan_id=PLAN_ID, history=history)
    store = store_for(tmp_path/'work', sources, history)
    tasks = store.read().entries('tasks')
    assert {task['range']['role'] for task in tasks
            if task['phase'] == 'input_integrity' and task['range']['offset'] == 65536} == {'base', 'ours', 'theirs'}
    result, code = finish(store, 3)
    assert code == 0 and result == expected
    assert {row['path']: b64decode(row['bytes_base64']) for row in result['target_files']} == files


def test_unresolved_conflicts_are_complete_negative_results_without_target_bytes(recorded, tmp_path):
    files = small_seed(tmp_path/'seed')
    sources, history, plan, _ = inputs(tmp_path/'input', [files,
        replace(files, 'goal', title='left'), replace(files, 'goal', title='right')])
    expected = prepare_merge(sources, plan_id=PLAN_ID, history=history)
    assert plan.data['conflicts']
    result, code = finish(store_for(tmp_path/'work', sources, history), 100000)
    assert code == 0 and result == expected
    assert result['target']['target_validated'] is False and result['target_files'] == []
    assert result['changed'] is None and result['metadata']['conflicts']


def test_explicit_resolution_original_bytes_and_audit_are_retained(recorded, tmp_path):
    files = small_seed(tmp_path/'seed')
    sources, history, plan, _ = inputs(tmp_path/'input', [files,
        replace(files, 'goal', title='left'), replace(files, 'goal', title='right')])
    conflict = next(row for row in plan.data['conflicts'] if row['pointer'] == '/title')
    decision = resolve_merge_conflict(plan.canonical_bytes, sources, history=history,
        expected_plan_sha256=plan.sha256, conflict_id=conflict['conflict_id'], actor=ACTOR,
        resolved_at=WHEN, take='theirs')
    raw = json.dumps(decision.data, indent=2).encode()+b'\n'
    bindings = {'plan_raw': raw, 'expected_plan_sha256': sha256(raw).hexdigest()}
    expected = prepare_merge(sources, plan_id=PLAN_ID, history=history, **bindings)
    result, _ = finish(store_for(tmp_path/'work', sources, history, **bindings), 2)
    assert result == expected and b64decode(result['plan_bytes_base64']) == raw
    assert result['target']['target_validated'] is True
    assert json.loads(b64decode(result['plan_bytes_base64']))['resolutions'] == decision.data['resolutions']


def test_source_path_changes_after_sealing_do_not_rebind_passive_work(recorded, tmp_path, template):
    sources, history, request = adapter_case(tmp_path/'input', template, 'local')
    expected = prepare_merge(sources, plan_id=PLAN_ID, history=history)
    store = store_for(tmp_path/'work', sources, history)
    (request.root/'specroad.json').write_bytes(b'changed after sealing')
    before = inventory(tmp_path/'input')
    result, _ = finish(store, 100000)
    assert result == expected and inventory(tmp_path/'input') == before
    assert not result['write_authorized']


def test_resume_does_not_reexecute_finished_global_phases(recorded, tmp_path, template, monkeypatch):
    sources, history, _ = adapter_case(tmp_path/'input', template, 'local')
    store = store_for(tmp_path/'work', sources, history)
    tasks = store.read().entries('tasks')
    prefix = next(i for i, task in enumerate(tasks) if task['phase'] == 'inventory')
    resume_merge_work(store, max_units=prefix+1)
    import specroad.work.merge as adapter
    original = adapter.phase_result
    seen = []
    def observe(inputs, phase, previous, **kwargs):
        seen.append(phase)
        return original(inputs, phase, previous, **kwargs)
    monkeypatch.setattr(adapter, 'phase_result', observe)
    resume_merge_work(store)
    assert seen == ['comparison']


def test_rehashed_completed_phase_cannot_become_a_final_result(recorded, tmp_path, template):
    sources, history, _ = adapter_case(tmp_path/'input', template, 'local')
    store = store_for(tmp_path/'work', sources, history)
    tasks = store.read().entries('tasks')
    prefix = next(i for i, task in enumerate(tasks) if task['phase'] == 'inventory')
    resume_merge_work(store, max_units=prefix)
    current = store.read()
    task = current.entries('remaining')[0]
    store.publish(partition_work_manifest(current, {task['unit_id']: jcs({
        'adapter': 'merge-work-v1', 'phase': 'inventory', 'result': {'invented': True}})}))
    before = inventory(tmp_path/'input')
    with pytest.raises(WorkResumeError, match='phase_recomputation_mismatch'):
        finish(store, 100000)
    assert store.read().as_dict()['state'] == 'running' and inventory(tmp_path/'input') == before


@pytest.mark.parametrize('window', [0, -1, True, '1'])
def test_invalid_windows_preserve_checkpoint(recorded, tmp_path, template, window):
    sources, history, _ = adapter_case(tmp_path/'input', template, 'local')
    store = store_for(tmp_path/'work', sources, history)
    before = inventory(tmp_path/'work')
    with no_write_attempts(), pytest.raises(WorkResumeError):
        resume_merge_work(store, max_units=window)
    assert inventory(tmp_path/'work') == before
