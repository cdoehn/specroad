"""Bound planning explanations with independent stored-edge/path expectations."""
from dataclasses import FrozenInstanceError
from hashlib import sha256
import json
import shutil

import pytest

from specroad.changes import TargetModel
from specroad.changes.target_values import TargetError
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.model.errors import ModelError
from specroad.model.paths import artifact_path
from specroad.planning import RoadmapExplanation, explain_roadmap, project_roadmap
from support.domain import domain_value
from support.model import configuration_value, put
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import inventory, no_write_attempts
from support.relations import aid, artifact, edge, rid
from support.targets import model, SCOPE
from test_planning_relations import stored
from test_roadmap_projection import roadmap_values


def explanation_values():
    values = roadmap_values()
    values[5]['relations'].append(edge('addresses', aid('goal', 1), number=14))
    values[6]['relations'].extend([
        edge('addresses', aid('goal', 1), number=15),
        edge('derived_from', aid('need', 1), number=16),
        edge('refines', aid('requirement', 2), number=20)])
    values[7]['relations'].append(edge('derived_from', aid('assumption', 1), number=18))
    return [*values,
        domain_value('goal', id=aid('goal', 1)), domain_value('goal', id=aid('goal', 2)),
        domain_value('need', id=aid('need', 1), relations=[edge('addresses', aid('goal', 1), number=17)]),
        domain_value('assumption', id=aid('assumption', 1), relations=[
            edge('derived_from', aid('need', 1), number=19),
            edge('derived_from', aid('source', 1), number=22)]),
        domain_value('requirement', id=aid('requirement', 2), relations=[
            edge('addresses', aid('goal', 1), number=21)]),
        artifact('source', 1),
        domain_value('task', id=aid('task', 2), relations=[
            edge('scheduled_for', aid('milestone', 1), number=23)]),
        domain_value('requirement', id=aid('requirement', 3), relations=[
            edge('implemented_by', aid('task', 2), number=24),
            edge('addresses', aid('goal', 2), number=25)])]


def supplied(values=None, *, depth=8):
    return model(explanation_values() if values is None else values,
                 config=configuration_value(resource_limits={'trace_depth': depth}))


def paths(data, purpose, target):
    return {(tuple(a['id'] for a in row['path']['artifacts']),
             tuple(r['relation_id'] for r in row['path']['relations']), tuple(row['path']['inverse']))
            for row in data['paths'] if row['purpose'] == purpose and row['target_id'] == target}


def test_task_explanation_binds_real_sources_and_original_path_directions():
    source = supplied(); original = source.source_files
    with no_write_attempts(): report = explain_roadmap(source, aid('task', 1))
    data = report.data
    assert data['format_version'] == 'roadmap-explanation-v1'
    assert data['generated'] and not data['normative']
    assert data['project_id'] == source.binding.project_id and data['scope_descriptor'] == SCOPE
    assert data['input_sha256'] == source._sources_sha256
    assert data['model_root_sha256'] == source.manifest(source.artifacts, SCOPE).sha256
    assert data['roadmap_sha256'] == project_roadmap(source).sha256
    assert data['artifact_id'] == aid('task', 1) and data['depth'] == 8
    assert report.sha256 == canonical_json_sha256(data)
    relations = {row['relation_id']: row for row in data['relations']}
    for row in data['artifacts']:
        raw = original[row['path']]; value = json.loads(raw)
        assert row['source_sha256'] == sha256(raw).hexdigest()
        assert row['record_sha256'] == canonical_json_sha256(value)
        assert row['revision'] == value['revision'] and row['artifact_id'] == value['id']
        assert all(value[key] == stored for key, stored in row['stored'].items())
    for row in relations.values():
        value = json.loads(original[row['path']])
        relation = value['relations'][int(row['pointer'].split('/')[-1])]
        assert (row['source_id'], row['type'], row['target_id']) == (value['id'], relation['type'], relation['target'])
        assert row['source_sha256'] == sha256(original[row['path']]).hexdigest()
        assert row['relation_sha256'] == canonical_json_sha256(relation)
    for row in data['paths']:
        path = row['path']; nodes = path['artifacts']
        assert nodes[0]['id'] == aid('task', 1) and nodes[-1]['id'] == row['target_id']
        for i, (relation, inverse) in enumerate(zip(path['relations'], path['inverse'])):
            edge_data = relations[relation['relation_id']]
            pair = (edge_data['source_id'], edge_data['target_id'])
            assert (nodes[i]['id'], nodes[i + 1]['id']) == (pair[::-1] if inverse else pair)
    assert source.source_files == original
    assert not any(data[key] for key in ('project_files_verified', 'full_validation_passed',
        'applicability_evaluated', 'done_evidence_evaluated', 'verification_evaluated',
        'release_closure_evaluated', 'release_readiness_evaluated', 'write_authorized', 'approval_granted'))


def test_task_has_both_shortest_goal_paths_and_the_requirement_chain():
    data = explain_roadmap(supplied(), aid('task', 1)).data
    task, requirement, capability, goal = (aid(k, 1) for k in ('task', 'requirement', 'capability', 'goal'))
    assert paths(data, 'context', goal) == {
        ((task, requirement, goal), (rid(7), rid(15)), (True, False)),
        ((task, capability, goal), (rid(6), rid(14)), (True, False))}
    assert paths(data, 'context', aid('requirement', 2)) == {
        ((task, requirement, aid('requirement', 2)), (rid(7), rid(20)), (True, False))}
    assert data['goal_ids'] == [goal]
    assert data['requirement_ids'] == [requirement, aid('requirement', 2)] and data['open_items'] == []


def test_task_does_not_acquire_the_goals_of_a_sibling_on_the_same_milestone():
    data = explain_roadmap(supplied(), aid('task', 1)).data
    assert all(aid(k, n) not in data['context_ids'] for k, n in (
        ('task', 2), ('requirement', 3), ('goal', 2), ('milestone', 1), ('release', 1)))
    assert aid('milestone', 1) in {row['artifact_id'] for row in data['artifacts']}


@pytest.mark.parametrize('kind', ['release', 'milestone'])
def test_container_explanation_retains_member_assignment_and_task_origin_paths(kind):
    start = aid(kind, 1); data = explain_roadmap(supplied(), start).data
    prefix_nodes = (start, aid('milestone', 1)) if kind == 'release' else (start,)
    prefix_relations = (rid(1),) if kind == 'release' else ()
    prefix_inverse = (True,) if kind == 'release' else ()
    assert paths(data, 'context', aid('requirement', 3)) == {
        ((*prefix_nodes, aid('task', 2), aid('requirement', 3)),
         (*prefix_relations, rid(23), rid(24)), (*prefix_inverse, True, True))}
    assert data['goal_ids'] == [aid('goal', 1), aid('goal', 2)]
    assert not data['release_closure_evaluated']


def test_requirement_scheduled_in_another_release_does_not_schedule_its_task_there():
    data = explain_roadmap(supplied(), aid('release', 2)).data
    assert aid('requirement', 1) in data['requirement_ids']
    assert aid('task', 1) not in data['context_ids']
    assert all(row['artifact_id'] != aid('task', 1) for row in data['artifacts'])


def test_assignments_keep_their_exact_source_and_parentage_is_separate():
    data = explain_roadmap(supplied(), aid('task', 1)).data
    assert paths(data, 'assignment', aid('release', 1)) == {
        ((aid('task', 1), aid('milestone', 1), aid('release', 1)), (rid(4), rid(1)), (False, False))}
    assert paths(data, 'assignment', aid('milestone', 2)) == {
        ((aid('task', 1), aid('requirement', 1), aid('milestone', 2)), (rid(7), rid(8)), (True, False))}
    assert paths(data, 'parent', aid('capability', 1)) == {
        ((aid('task', 1), aid('capability', 1)), (rid(3),), (False,))}
    assert paths(data, 'assignment', aid('capability', 1)) == set()


def test_dependencies_are_direct_observations_without_transitive_release_closure():
    values = explanation_values()
    values[9]['relations'].append(edge('depends_on', aid('component', 2), number=26))
    values.append(domain_value('component', id=aid('component', 2)))
    data = explain_roadmap(supplied(values), aid('task', 1)).data
    assert data['dependency_ids'] == [aid('component', 1)]
    assert paths(data, 'dependency', aid('component', 1)) == {
        ((aid('task', 1), aid('component', 1)), (rid(11),), (False,))}
    assert all(row['artifact_id'] != aid('component', 2) for row in data['artifacts'])


def test_risk_paths_preserve_each_mitigating_source_without_rating_or_approval():
    data = explain_roadmap(supplied(), aid('task', 1)).data
    assert data['risk_ids'] == [aid('risk', 1)]
    assert paths(data, 'risk', aid('risk', 1)) == {
        ((aid('task', 1), aid('risk', 1)), (rid(10),), (False,)),
        ((aid('task', 1), aid('requirement', 1), aid('risk', 1)), (rid(7), rid(12)), (True, False)),
        ((aid('task', 1), aid('decision', 1), aid('risk', 1)), (rid(9), rid(13)), (True, False))}
    risk = next(row for row in data['artifacts'] if row['artifact_id'] == aid('risk', 1))
    assert risk['stored']['probability'] == 0.25 and risk['stored']['risk_status'] == 'open'


def test_assumptions_and_sources_remain_explicit_derived_from_paths():
    data = explain_roadmap(supplied(), aid('task', 1)).data
    assert data['assumption_ids'] == [aid('assumption', 1)]
    assert paths(data, 'context', aid('source', 1)) == {
        ((aid('task', 1), aid('decision', 1), aid('assumption', 1), aid('source', 1)),
         (rid(9), rid(18), rid(22)), (True, False, False))}
    assumption = next(row for row in data['artifacts'] if row['artifact_id'] == aid('assumption', 1))
    assert assumption['stored']['validation_status'] == 'pending'


def test_parallel_implementation_links_remain_distinct_shortest_paths():
    values = explanation_values()
    values[6]['relations'].append(edge('implemented_by', aid('task', 1), number=28))
    data = explain_roadmap(supplied(values), aid('task', 1)).data
    assert paths(data, 'context', aid('requirement', 1)) == {
        ((aid('task', 1), aid('requirement', 1)), (rid(7),), (True,)),
        ((aid('task', 1), aid('requirement', 1)), (rid(28),), (True,))}
    assert len(paths(data, 'context', aid('goal', 1))) == 3


@pytest.mark.parametrize('depth', [0, 1, 2, 3])
def test_configured_depth_bounds_every_path_and_missing_origins_remain_open(depth):
    data = explain_roadmap(supplied(depth=depth), aid('task', 1)).data
    assert data['depth'] == depth
    assert all(len(row['path']['relations']) <= depth for row in data['paths'])
    assert data['goal_ids'] == ([aid('goal', 1)] if depth >= 2 else [])
    assert bool(paths(data, 'context', aid('source', 1))) == (depth >= 3)
    assert ('no_goal_path_within_depth' in data['open_items']) == (depth < 2)
    if depth == 0:
        assert data['context_ids'] == [aid('task', 1)]
        assert data['requirement_ids'] == data['dependency_ids'] == data['risk_ids'] == []


def test_missing_depth_does_not_invent_a_default():
    with no_write_attempts(), pytest.raises(ModelError) as error:
        explain_roadmap(model(explanation_values()), aid('task', 1))
    assert error.value.reason == 'roadmap_explanation_depth_not_configured'
    assert error.value.path == 'specroad.json' and error.value.pointer == '/resource_limits/trace_depth'


@pytest.mark.parametrize('identifier', [None, [], 'label', aid('task', 99)])
def test_unknown_or_untyped_identity_never_yields_an_explanation(identifier):
    with no_write_attempts(), pytest.raises(ModelError) as error:
        explain_roadmap(supplied(), identifier)
    assert error.value.reason == 'unknown_relation_view_artifact'


@pytest.mark.parametrize('value', [None, {}])
def test_explanation_requires_a_native_owned_model(value):
    with no_write_attempts(), pytest.raises(ModelError) as error:
        explain_roadmap(value, aid('task', 1))
    assert error.value.reason == 'roadmap_explanation_target_model_required'


@pytest.mark.parametrize('broken,reason', [('missing_target', 'missing_relation_target'), ('goal_schema', 'missing_field')])
def test_invalid_unreachable_inputs_block_an_answer_without_repair(broken, reason):
    values = explanation_values()
    if broken == 'missing_target':
        values.append(domain_value('requirement', id=aid('requirement', 8), relations=[
            edge('addresses', aid('goal', 99), number=28)]))
    else:
        goal = domain_value('goal', id=aid('goal', 8)); goal.pop('statement'); values.append(goal)
    source = supplied(values); before = source.source_files
    with no_write_attempts(), pytest.raises(ModelError) as error:
        explain_roadmap(source, aid('task', 1))
    assert error.value.reason == reason and source.source_files == before


def test_nonprojected_hierarchy_cycle_keeps_the_shared_error_contract():
    values = explanation_values()
    values.extend([domain_value('requirement', id=aid('requirement', n), relations=[
        edge('refines', aid('requirement', 17 - n), number=28 + n)]) for n in (8, 9)])
    with no_write_attempts(), pytest.raises(ModelError) as error:
        explain_roadmap(supplied(values), aid('task', 1))
    assert error.value.reason == 'relation_hierarchy_cycle'


def test_changed_bound_input_is_not_used_as_a_fresh_explanation():
    source = supplied(); object.__setattr__(source, '_sources_sha256', '0' * 64)
    with no_write_attempts(), pytest.raises(TargetError) as error:
        explain_roadmap(source, aid('task', 1))
    assert error.value.reason == 'target_sources_changed'


def test_reassignment_updates_real_provenance_and_hashes_without_inheriting_dates():
    values = explanation_values(); before = explain_roadmap(supplied(values), aid('task', 1))
    values[4]['relations'][1]['target'] = aid('release', 2)
    after = explain_roadmap(supplied(values), aid('task', 1))
    assert paths(after.data, 'assignment', aid('release', 1)) == set()
    assert ((aid('task', 1), aid('release', 2)), (rid(4),), (False,)) in paths(after.data, 'assignment', aid('release', 2))
    assert before.sha256 != after.sha256 and before.data['model_root_sha256'] != after.data['model_root_sha256']
    task = next(row for row in after.data['artifacts'] if row['artifact_id'] == aid('task', 1))
    assert 'target_date' not in task['stored']


def test_explanations_are_owned_order_independent_and_cannot_authorize_changes():
    values = explanation_values(); report = explain_roadmap(supplied(values), aid('task', 1))
    other = explain_roadmap(supplied(list(reversed(values))), aid('task', 1))
    assert other.data == report.data and other.sha256 == report.sha256
    detached = report.data; detached['paths'].clear(); detached['artifacts'][0]['stored'].clear()
    assert report.data == other.data
    with pytest.raises(FrozenInstanceError): report._encoded = b'{}'
    with pytest.raises(TypeError): bool(report)
    with pytest.raises(TypeError): RoadmapExplanation(detached)


def test_live_project_bytes_are_preserved_and_are_not_required_for_supplied_paths(tmp_path):
    root = tmp_path / 'project'; base = stored(root, explanation_values())
    config = json.loads(base.configuration_bytes); config['resource_limits'] = {'trace_depth': 8}
    source = TargetModel(canonical_json_bytes(config), base.binding, base.documents,
                         profile=base.profile, resource_files=base.resource_files)
    put(root, 'specroad.json', source.configuration_bytes)
    put(root, 'roadmap.json', b'{"foreign":"preserved"}\n')
    before = inventory(tmp_path)
    with no_write_attempts(): report = explain_roadmap(source, aid('task', 1))
    assert inventory(tmp_path) == before
    shutil.rmtree(root)
    with no_write_attempts(): after = explain_roadmap(source, aid('task', 1))
    assert after.data == report.data and not root.exists()


@pytest.mark.parametrize('runtime', ['core', 'pyz'])
def test_native_explanation_contract_matches_isolated_core_and_pyz(tmp_path, runtime):
    source = supplied(); expected = explain_roadmap(source, aid('task', 1)).data
    body = '''import json
from specroad.planning import explain_roadmap
from specroad.changes import TargetModel
from specroad.model.model_manifest import ProjectReadBinding
from specroad.profiles import ProfileResource, compose_profiles
from specroad.validation import ModelDocument
'''
    body += 'configuration=' + repr(source.configuration_bytes) + '\n'
    body += 'documents=' + repr([(d.path, d.content) for d in source.documents]) + '\n'
    body += 'resources=' + repr([(d.path, d.content) for d in source.resource_files]) + '\n'
    body += '''profile=ProfileResource(dict(resources)['profiles/core.json'])
source=TargetModel(configuration,ProjectReadBinding('sample','/missing/project',(1,2)),
 [ModelDocument(p,b) for p,b in documents],profile=compose_profiles([profile],core_key=profile.key),
 resource_files=[ModelDocument(p,b) for p,b in resources])
'''
    body += 'print(json.dumps(explain_roadmap(source,' + repr(aid('task', 1)) + ').data,sort_keys=True))\n'
    if runtime == 'core': result = run_core(body, tmp_path, capture=True)
    else:
        _, package = build_distribution(tmp_path / 'distribution')
        result = run_python(['-I', '-S', '-B', '-c',
            'import sys;sys.path.insert(0,' + repr(str(package)) + ')\n' + body], tmp_path, capture=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == expected
