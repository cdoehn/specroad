"""Public passive merge preparation and native Work lifecycle; no host approval."""
from support.merge_matrix import template, recorded, source_kinds, representations
from support.merge_application import work
from pathlib import Path
from specroad.cli.results import thaw

import pytest

from specroad.cli.result_schemas import validate_result_document
from specroad.merge.preparation import prepare_merge
from specroad.model.canonical import canonical_json_bytes as jcs
from support.merge_preparation import baseline_template, adapter_case
from support.merge_resolution import PLAN_ID
from support.migration_cli import invoke, success
from support.read_only import inventory, no_write_attempts
from test_merge_sources import read_only_sources


def case(root, template, kind='local'):
    sources, history, request = adapter_case(root/'source', template, kind)
    inputs = root/'inputs'; inputs.mkdir()
    history_path = inputs/'history.json'; history_path.write_bytes(jcs(history))
    options = {'--history': str(history_path), '--plan-id': PLAN_ID}
    for role in ('base', 'ours', 'theirs'):
        options['--'+role] = str(request.root)
        options['--'+role+'-kind'] = kind
        if request.reference is not None:
            options['--'+role+'-ref'] = request.reference
    return sources, history, options


@source_kinds
@representations
def test_public_planner_matches_native_result_for_every_source(recorded, tmp_path, template, kind, representation):
    sources, history, options = case(tmp_path/'input', template, kind)
    expected = prepare_merge(sources, plan_id=PLAN_ID, history=history)
    before = inventory(tmp_path)
    with read_only_sources():
        actual = success(invoke('merge.plan', options, representation, authorize=False))
    assert jcs(actual) == jcs(expected) and inventory(tmp_path) == before
    assert actual['target']['target_validated'] is True, actual['target']
    assert actual['changed'] is False and actual['target_files']
    validate_result_document('merge-preparation-v1', actual)
    assert not actual['project_writes_performed'] and not actual['write_authorized']


def test_public_work_covers_all_phases_and_delivers_the_same_complete_result(recorded, tmp_path, template):
    sources, history, options = case(tmp_path/'input', template)
    expected = prepare_merge(sources, plan_id=PLAN_ID, history=history)
    before = inventory(tmp_path/'input'); directory = tmp_path/'work'
    first = invoke('merge.plan', {**options, '--work-dir': str(directory), '--step-wall-ms': '1'}, authorize=False)
    assert first.exit_code == 8, first
    status = success(work('status', directory))['data']
    previous = status['progress']['completed_units']
    total = status['progress']['total_units']
    prompt = success(work('prompt', directory))['data']
    assert prompt['control']['next_action']['command_id'] == 'work.resume'
    for _ in range(total+2):
        result = work('resume', directory)
        assert result.exit_code in (0, 8), result
        if result.exit_code == 0:
            document = success(result)
            assert jcs(document['data']) == jcs(expected)
            validate_result_document('work-command-v1', document)
            break
        progress = success(work('status', directory))['data']['progress']['completed_units']
        assert progress > previous
        previous = progress
    else:
        pytest.fail('Finite public merge Work did not deliver its complete result')
    assert inventory(tmp_path/'input') == before
    terminal = inventory(directory)
    assert success(work('resume', directory))['data'] == expected
    assert inventory(directory) == terminal


@pytest.mark.parametrize('missing', ['--base', '--ours', '--theirs', '--history', '--plan-id'])
def test_public_planning_requires_all_explicit_bindings(tmp_path, template, missing):
    _, _, options = case(tmp_path/'input', template)
    del options[missing]
    before = inventory(tmp_path)
    with no_write_attempts():
        result = invoke('merge.plan', options, authorize=False)
    assert result.exit_code == 2 and inventory(tmp_path) == before


def test_public_work_cannot_overlap_a_source_project(recorded, tmp_path, template):
    _, _, options = case(tmp_path/'input', template)
    before = inventory(tmp_path)
    with no_write_attempts():
        result = invoke('merge.plan', {**options, '--work-dir': str(Path(options['--ours'])/'work')}, authorize=False)
    assert result.exit_code == 7 and inventory(tmp_path) == before


def test_public_cancel_preserves_sources_and_does_not_authorize_execution(recorded, tmp_path, template):
    _, _, options = case(tmp_path/'input', template)
    before = inventory(tmp_path/'input'); directory = tmp_path/'work'
    assert invoke('merge.plan', {**options, '--work-dir': str(directory)}, authorize=False).exit_code == 8
    assert success(work('cancel', directory, {'--reason': 'Synthetic cancellation'}))['operation'] == 'cancel'
    assert work('resume', directory).exit_code != 0
    assert inventory(tmp_path/'input') == before


def test_public_resolution_hash_pair_cannot_be_omitted_or_invented(tmp_path, template):
    _, _, options = case(tmp_path/'input', template)
    before = inventory(tmp_path)
    with no_write_attempts():
        result = invoke('merge.plan', {**options, '--expected-plan-sha256': '0'*64}, authorize=False)
    assert result.exit_code == 2 and inventory(tmp_path) == before


def test_public_fail_on_change_keeps_complete_passive_target(tmp_path):
    from support.merge_target import small_seed, replace, inputs
    files = small_seed(tmp_path/'seed')
    sources, history, _, _ = inputs(tmp_path/'sources',
        [files, files, replace(files, 'goal', title='theirs')])
    path = tmp_path/'history.json'; path.write_bytes(jcs(history))
    options = {'--history': str(path), '--plan-id': PLAN_ID, '--fail-on-change': True}
    options.update({'--'+role: getattr(sources, role).source_root for role in ('base', 'ours', 'theirs')})
    before = inventory(tmp_path)
    result = invoke('merge.plan', options, authorize=False)
    assert result.exit_code == 1 and result.complete
    value = thaw(result.result)
    assert value['changed'] is True and value['target']['target_validated'] is True
    assert not value['project_writes_performed'] and inventory(tmp_path) == before
