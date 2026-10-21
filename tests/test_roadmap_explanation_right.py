"""Complete machine paths, explicit gaps and the live read-only command boundary."""
import importlib
import json
from unittest.mock import patch

import pytest

from specroad.changes import project_lock
from specroad.cli.application import dispatch_result, execute_request
from specroad.cli.commands import builtin_registry
from specroad.cli.result_schemas import validate_result_document
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.model.errors import ModelError
from specroad.model.paths import artifact_path
from specroad.model.schema_catalog import SchemaCatalog
from specroad.planning import explain_project_roadmap, explain_roadmap
from support.domain import domain_value
from support.inspection import inspection_project
from support.model import put
from support.portable import build_distribution
from support.processes import run_cli, run_python
from support.project_locks import options
from support.read_only import inventory, no_write_attempts
from support.relations import aid, edge, rid
from test_roadmap_explanation import explanation_values, paths, supplied

live = importlib.import_module('specroad.planning.project_explanation')


def project(root, values=None, depth=8, **limits):
    inspection_project(root, artifacts=explanation_values() if values is None else values)
    config = json.loads((root / 'specroad.json').read_bytes())
    config['resource_limits'] = {**limits, 'trace_depth': depth}
    put(root, 'specroad.json', canonical_json_bytes(config))
    return root


def route(purpose, nodes, relations=(), inverse=()):
    return (purpose, tuple(aid(kind, n) for kind, n in nodes),
            tuple(rid(n) for n in relations), tuple(inverse))


def task_routes():
    t, c, r, d, g, n, a, r2, s, m, m2, rel, rel2, risk, comp = (
        ('task', 1), ('capability', 1), ('requirement', 1), ('decision', 1),
        ('goal', 1), ('need', 1), ('assumption', 1), ('requirement', 2),
        ('source', 1), ('milestone', 1), ('milestone', 2), ('release', 1),
        ('release', 2), ('risk', 1), ('component', 1))
    return {
        route('context', [t]), route('context', [t, c], [6], [True]),
        route('context', [t, r], [7], [True]), route('context', [t, d], [9], [True]),
        route('context', [t, c, g], [6, 14], [True, False]),
        route('context', [t, r, g], [7, 15], [True, False]),
        route('context', [t, r, n], [7, 16], [True, False]),
        route('context', [t, d, a], [9, 18], [True, False]),
        route('context', [t, r, r2], [7, 20], [True, False]),
        route('context', [t, d, a, s], [9, 18, 22], [True, False, False]),
        route('assignment', [t, m], [4], [False]),
        route('assignment', [t, m, rel], [4, 1], [False, False]),
        route('assignment', [t, c, rel2], [6, 5], [True, False]),
        route('assignment', [t, r, m2], [7, 8], [True, False]),
        route('assignment', [t, r, m2, rel2], [7, 8, 2], [True, False, False]),
        route('parent', [t, c], [3], [False]),
        route('dependency', [t, comp], [11], [False]),
        route('risk', [t, risk], [10], [False]),
        route('risk', [t, r, risk], [7, 12], [True, False]),
        route('risk', [t, d, risk], [9, 13], [True, False])}


def signatures(data):
    return {(row['purpose'], tuple(a['id'] for a in row['path']['artifacts']),
        tuple(r['relation_id'] for r in row['path']['relations']), tuple(row['path']['inverse']))
        for row in data['paths']}


@pytest.mark.parametrize('depth', [0, 1, 2, 3, 8])
def test_public_explanation_has_the_complete_independent_node_and_path_set(tmp_path, depth):
    root = project(tmp_path / 'project', depth=depth)
    before = inventory(root)
    with no_write_attempts(): result = explain_project_roadmap(root, aid('task', 1))
    assert result.exit_code == 0 and result.complete
    payload = result.as_dict()['result']; data = payload['explanation']
    expected = {row for row in task_routes() if len(row[2]) <= depth}
    assert signatures(data) == expected and len(data['paths']) == len(expected)
    assert {r['artifact_id'] for r in data['artifacts']} == {key for row in expected for key in row[1]}
    assert {r['relation_id'] for r in data['relations']} == {key for row in expected for key in row[2]}
    assert data['context_ids'] == sorted({row[1][-1] for row in expected if row[0] == 'context'})
    assert payload['explanation_sha256'] == canonical_json_sha256(data)
    assert payload['coverage']['input_sha256'] == data['input_sha256']
    assert payload['coverage']['artifact_count'] == len(explanation_values())
    assert payload['coverage']['source_bytes_rechecked'] and not payload['coverage']['atomic_snapshot']
    assert not data['project_files_verified'] and not data['approval_granted']
    assert inventory(root) == before


def test_missing_membership_and_implementation_are_explicit_without_inferred_origins():
    task = domain_value('task', id=aid('task', 1), relations=[edge('part_of', aid('capability', 1), number=1)])
    cap = domain_value('capability', id=aid('capability', 1), relations=[
        edge('scheduled_for', aid('release', 1), number=2),
        edge('addresses', aid('goal', 1), number=3)])
    values = [task, cap, domain_value('release', id=aid('release', 1)), domain_value('goal', id=aid('goal', 1))]
    data = explain_roadmap(supplied(values), task['id']).data
    assert data['missing_planning_references'] == [
        {'artifact_id': task['id'], 'reason': 'no_explicit_schedule'},
        {'artifact_id': task['id'], 'reason': 'no_requirement_or_decision_implementation'}]
    assert data['open_items'] == ['no_requirement_path_within_depth', 'no_goal_path_within_depth']
    assert data['goal_ids'] == data['requirement_ids'] == []
    assert {r['purpose'] for r in data['paths']} == {'context', 'parent'}
    assert all(row['artifact_id'] != aid('release', 1) for row in data['artifacts'])


def test_missing_planning_references_are_limited_to_context_and_use_actual_links():
    values = explanation_values()
    values.append(domain_value('task', id=aid('task', 99)))
    data = explain_roadmap(supplied(values), aid('task', 1)).data
    assert data['missing_planning_references'] == [
        {'artifact_id': aid('requirement', 2), 'reason': 'no_explicit_schedule'}]
    assert explain_roadmap(supplied(values, depth=0), aid('task', 1)).data['missing_planning_references'] == []


def test_soft_limits_do_not_drop_branches_parallel_edges_or_paths(tmp_path):
    values = [domain_value('task', id=aid('task', 1)), domain_value('goal', id=aid('goal', 1))]
    for n in range(1, 34):
        values.append(domain_value('requirement', id=aid('requirement', n), relations=[
            edge('implemented_by', aid('task', 1), number=n),
            edge('addresses', aid('goal', 1), number=100+n)]))
    root = project(tmp_path / 'project', values, 2, model_bytes=1, relation_count=1, query_result_count=1)
    result = explain_project_roadmap(root, aid('task', 1)); assert result.exit_code == 0
    data = result.as_dict()['result']['explanation']
    expected = {route('context', [('task', 1)])}
    for n in range(1, 34):
        expected.add(route('context', [('task', 1), ('requirement', n)], [n], [True]))
        expected.add(route('context', [('task', 1), ('requirement', n), ('goal', 1)], [n, 100+n], [True, False]))
    assert signatures(data) == expected and len(data['paths']) == 67


def test_origin_and_dependency_cycles_terminate_without_returning_cyclic_walks():
    values = explanation_values()
    values[13]['relations'].append(edge('derived_from', aid('decision', 1), number=26))
    values[9]['relations'].append(edge('depends_on', aid('task', 1), number=27))
    data = explain_roadmap(supplied(values, depth=10000), aid('task', 1)).data
    assert signatures(data) == task_routes()
    assert all(len(row[1]) == len(set(row[1])) for row in signatures(data))


@pytest.mark.parametrize('runtime', ['core', 'pyz'])
def test_direct_cli_structured_and_isolated_runtimes_share_one_machine_contract(tmp_path, runtime):
    root = project(tmp_path / 'project')
    args = ['roadmap', 'explain', aid('task', 1), '--project', str(root), '--format=json']
    direct = explain_project_roadmap(root, aid('task', 1))
    cli = dispatch_result(args)
    request = execute_request({'command_id': 'roadmap.explain', 'arguments': {'id': aid('task', 1)},
                               'options': {'--project': str(root)}}).result
    if runtime == 'core': process = run_cli(args, tmp_path, capture=True)
    else:
        _, package = build_distribution(tmp_path / 'distribution')
        process = run_python(['-I', '-S', '-B', str(package), *args], tmp_path, capture=True)
    assert direct.exit_code == cli.exit_code == request.exit_code == process.returncode == 0, process.stderr
    data = direct.as_dict()['result']
    assert cli.as_dict()['result'] == request.as_dict()['result'] == json.loads(process.stdout)['result'] == data
    assert all(result.command == 'roadmap.explain' for result in (direct, cli, request))


def test_command_schema_and_capabilities_advertise_only_implemented_read_contracts(tmp_path):
    command = builtin_registry().resolve('roadmap.explain')
    assert command.command_class.value == 'read_only' and command.preflight_profile.value == 'project_read'
    assert command.effect_scope.value == 'none' and command.requires_project and not command.requires_git
    description = dispatch_result(['command', 'describe', 'roadmap.explain']).as_dict()['result']
    assert description['stdout']['result_schema'] == 'roadmap-explain-v1'
    assert description['work']['continuation_supported'] is False
    capabilities = dispatch_result(['capabilities']).as_dict()['result']['semantic']['capability_ids']
    assert 'cli.roadmap.explain' in capabilities
    root = project(tmp_path / 'project')
    payload = explain_project_roadmap(root, aid('task', 1)).as_dict()['result']
    catalog = SchemaCatalog(); catalog.validate('roadmap-explain-v1', payload)
    schema = catalog.show('roadmap-explain-v1')['schema']
    assert set(schema['required']) == set(payload) and not schema['additionalProperties']
    assert set(schema['properties']['explanation']['required']) == set(payload['explanation'])


@pytest.mark.parametrize('damage', ['extra', 'missing', 'approval', 'normative', 'depth',
    'purpose', 'provenance', 'revision', 'digest', 'rechecked'])
def test_result_schema_rejects_missing_provenance_or_false_authority(tmp_path, damage):
    root = project(tmp_path / 'project')
    data = explain_project_roadmap(root, aid('task', 1)).as_dict()['result']
    if damage == 'extra': data['execute'] = 'ignored?'
    elif damage == 'missing': data['explanation'].pop('paths')
    elif damage == 'approval': data['explanation']['approval_granted'] = True
    elif damage == 'normative': data['explanation']['normative'] = True
    elif damage == 'depth': data['explanation']['depth'] = -1
    elif damage == 'purpose': data['explanation']['paths'][0]['purpose'] = 'guessed_origin'
    elif damage == 'provenance': data['explanation']['relations'][0].pop('source_sha256')
    elif damage == 'revision': data['explanation']['artifacts'][0]['revision'] = True
    elif damage == 'digest': data['explanation_sha256'] = 'G' * 64
    else: data['coverage']['source_bytes_rechecked'] = False
    with pytest.raises(ModelError): validate_result_document('roadmap-explain-v1', data)


@pytest.mark.parametrize('tail', [[], ['extra', 'value'], ['x', '--depth=1'], ['x', '--configuration=y'], ['x', '--format=sarif']])
def test_invalid_requests_are_rejected_before_loading_a_project(tail):
    with patch.object(live, 'InspectionSnapshot', side_effect=AssertionError('load')):
        assert dispatch_result(['roadmap', 'explain', *tail]).exit_code == 2


@pytest.mark.parametrize('identifier', [None, [], 'label', aid('task', 99)])
def test_unknown_and_untyped_start_ids_do_not_become_empty_successes(tmp_path, identifier):
    root = project(tmp_path / 'project', depth=0)
    result = explain_project_roadmap(root, identifier)
    assert result.exit_code == 3 and not result.complete and result.result is None
    assert any(d.rationale == 'unknown_relation_view_artifact' for d in result.diagnostics)


def test_missing_depth_is_reported_before_inventory_loading(tmp_path):
    root = project(tmp_path / 'project'); config = json.loads((root / 'specroad.json').read_bytes())
    config.pop('resource_limits'); put(root, 'specroad.json', canonical_json_bytes(config))
    with patch.object(live, 'InspectionSnapshot', side_effect=AssertionError('load')):
        result = explain_project_roadmap(root, aid('task', 1))
    assert result.exit_code == 3 and result.result is None
    assert any(d.rationale == 'roadmap_explanation_depth_not_configured' for d in result.diagnostics)


@pytest.mark.parametrize('depth', [-1, True, 1.5, '3'])
def test_invalid_depth_fails_without_coercion_or_a_default(tmp_path, depth):
    root = project(tmp_path / 'project', depth=depth)
    result = explain_project_roadmap(root, aid('task', 1))
    assert result.exit_code == 3 and result.result is None and not result.complete


@pytest.mark.parametrize('damage', ['missing_target', 'goal_schema', 'cycle', 'malformed'])
def test_invalid_unreachable_sources_prevent_a_complete_answer(tmp_path, damage):
    values = explanation_values()
    if damage == 'missing_target':
        values.append(domain_value('requirement', id=aid('requirement', 90), relations=[
            edge('addresses', aid('goal', 90), number=90)]))
    elif damage == 'cycle':
        values.extend(domain_value('requirement', id=aid('requirement', n), relations=[
            edge('refines', aid('requirement', 181-n), number=n)]) for n in (90, 91))
    root = project(tmp_path / 'project', values)
    name = artifact_path('goal', aid('goal', 2), 'SR')
    if damage == 'goal_schema':
        value = json.loads((root / name).read_bytes()); value.pop('statement')
        put(root, name, canonical_json_bytes(value))
    elif damage == 'malformed': put(root, name, b'{broken')
    before = inventory(root)
    result = explain_project_roadmap(root, aid('task', 1))
    assert result.exit_code == 3 and result.result is None and not result.complete
    assert inventory(root) == before


@pytest.mark.parametrize('phase', ['loaded', 'evaluated'])
@pytest.mark.parametrize('change', ['source', 'configuration', 'profile', 'addition', 'deletion'])
def test_changed_inventory_never_publishes_stale_explanations(tmp_path, phase, change):
    root = project(tmp_path / 'project'); steps = live._explain_steps(root, aid('task', 1))
    assert next(steps) == 'loaded'
    if phase == 'evaluated': assert next(steps) == 'evaluated'
    goal = artifact_path('goal', aid('goal', 2), 'SR')
    if change == 'source':
        data = json.loads((root / goal).read_bytes()); data['statement'] = 'Changed unrelated source'
        put(root, goal, canonical_json_bytes(data))
    elif change == 'configuration':
        data = json.loads((root / 'specroad.json').read_bytes()); data['resource_limits']['trace_depth'] = 7
        put(root, 'specroad.json', canonical_json_bytes(data))
    elif change == 'profile':
        path = root / 'profiles/core.json'; path.write_bytes(path.read_bytes() + b'\n')
    elif change == 'addition':
        value = domain_value('goal', id=aid('goal', 90))
        put(root, artifact_path('goal', value['id'], 'SR'), canonical_json_bytes(value))
    else: (root / goal).unlink()
    changed = inventory(root)
    with no_write_attempts():
        while True:
            try: next(steps)
            except StopIteration as completed: result = completed.value; break
    assert result.exit_code == 6 and result.result is None and not result.complete
    assert inventory(root) == changed


@pytest.mark.parametrize('stage', ['before', 'after'])
@pytest.mark.parametrize('blocked', ['writer', 'journal'])
def test_operational_blockers_do_not_load_or_publish_or_recover(tmp_path, stage, blocked):
    from contextlib import nullcontext
    root = project(tmp_path / 'project')
    steps = live._explain_steps(root, aid('task', 1))
    if stage == 'after':
        assert next(steps) == 'loaded' and next(steps) == 'evaluated'
    if blocked == 'journal': put(root, '.specroad/transactions/pending.json', b'incomplete')
    with project_lock(root, **options()) if blocked == 'writer' else nullcontext():
        before = inventory(root)
        with no_write_attempts(), patch.object(live, 'InspectionSnapshot', side_effect=AssertionError('load')):
            with pytest.raises(StopIteration) as completed: next(steps)
        result = completed.value.value
        assert result.exit_code == 5 and result.result is None and not result.complete
        assert inventory(root) == before


def test_capture_cannot_silently_switch_to_a_new_configuration(tmp_path):
    root = project(tmp_path / 'project'); capture = live.InspectionSnapshot
    def changed(*args):
        config = json.loads((root / 'specroad.json').read_bytes())
        config['resource_limits']['trace_depth'] = 3
        put(root, 'specroad.json', canonical_json_bytes(config))
        return capture(*args)
    with patch.object(live, 'InspectionSnapshot', side_effect=changed):
        result = explain_project_roadmap(root, aid('task', 1))
    assert result.exit_code == 6 and result.result is None
    assert any(d.rationale == 'roadmap_explanation_source_changed' for d in result.diagnostics)


def test_symlink_sources_are_rejected_without_reading_or_modifying_foreign_bytes(tmp_path):
    root = project(tmp_path / 'project'); name = artifact_path('goal', aid('goal', 2), 'SR')
    foreign = tmp_path / 'foreign.json'; (root / name).rename(foreign); (root / name).symlink_to(foreign)
    before = inventory(tmp_path)
    with no_write_attempts(): result = explain_project_roadmap(root, aid('task', 1))
    assert result.exit_code == 7 and result.result is None and not result.complete
    assert inventory(tmp_path) == before


def test_read_failures_remain_environment_errors_without_fabricated_paths(tmp_path):
    root = project(tmp_path / 'project')
    with patch.object(live, 'InspectionSnapshot', side_effect=PermissionError('owned refusal')):
        result = explain_project_roadmap(root, aid('task', 1))
    assert result.exit_code == 5 and result.result is None and not result.complete


def test_read_only_project_requires_no_state_directory_lock_entropy_or_process(tmp_path):
    root = project(tmp_path / 'project'); (root / '.specroad/locks').rmdir(); (root / '.specroad').rmdir()
    put(root, 'roadmap.json', b'{"foreign":"untouched"}\n')
    modes = [(p, p.stat().st_mode & 0o777) for p in [root, *root.rglob('*')]]
    try:
        for path, mode in modes: path.chmod(mode & ~0o222)
        before = inventory(root)
        with no_write_attempts(), patch('builtins.input', side_effect=AssertionError('stdin')), \
                patch('secrets.token_bytes', side_effect=AssertionError('entropy')), \
                patch('specroad.changes.locking.LockFiles.acquire', side_effect=AssertionError('lock')):
            direct = explain_project_roadmap(root, aid('task', 1))
            cli = dispatch_result(['roadmap', 'explain', aid('task', 1), '--project', str(root)])
        assert direct.exit_code == cli.exit_code == 0
        assert inventory(root) == before and not (root / '.specroad').exists()
    finally:
        for path, mode in modes: path.chmod(mode)


def test_live_results_are_detached_and_later_calls_observe_reassignment(tmp_path):
    root = project(tmp_path / 'project'); result = explain_project_roadmap(root, aid('task', 1))
    old = result.as_dict()['result']; detached = result.as_dict()['result']; detached['explanation']['paths'].clear()
    assert result.as_dict()['result'] == old
    name = artifact_path('task', aid('task', 1), 'SR'); value = json.loads((root / name).read_bytes())
    value['relations'][1]['target'] = aid('release', 2); put(root, name, canonical_json_bytes(value))
    current = explain_project_roadmap(root, aid('task', 1)); assert current.exit_code == 0
    new = current.as_dict()['result']
    assert paths(new['explanation'], 'assignment', aid('release', 1)) == set()
    assert old['explanation_sha256'] != new['explanation_sha256']
    assert old['coverage']['input_sha256'] != new['coverage']['input_sha256']
