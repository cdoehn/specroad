"""Roadmap facts from one supplied model; no second normative planning source."""
from dataclasses import FrozenInstanceError
from hashlib import sha256
import json
import shutil

import pytest

from specroad.model.canonical import canonical_json_sha256
from specroad.model.errors import ModelError
from specroad.model.paths import artifact_path
from specroad.planning import RoadmapProjection, project_roadmap
from support.domain import domain_value
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import inventory, no_write_attempts
from support.relations import aid, edge
from support.targets import model, SCOPE
from test_planning_relations import planning_values, stored


def roadmap_values():
    values = planning_values()
    values[5]['priority'] = 'high'
    risk = domain_value('risk', id=aid('risk', 1), probability=0.25, impact='high')
    component = domain_value('component', id=aid('component', 1))
    values[4]['relations'].extend([
        edge('mitigates', risk['id'], number=10),
        edge('depends_on', component['id'], number=11)])
    values[6]['relations'].append(edge('mitigates', risk['id'], number=12))
    values[7]['relations'].append(edge('mitigates', risk['id'], number=13))
    return [*values, risk, component]


def by_id(data, field='items'):
    return {row['artifact_id']: row for row in data[field]}


def test_roadmap_facts_bind_every_original_record_and_relation(tmp_path):
    values = roadmap_values(); supplied = stored(tmp_path / 'project', values)
    original = supplied.source_files
    with no_write_attempts(): report = project_roadmap(supplied)
    data = report.data
    assert data['format_version'] == 'roadmap-projection-v1'
    assert data['generated'] is True and data['normative'] is False
    assert data['project_id'] == supplied.binding.project_id and data['scope_descriptor'] == SCOPE
    assert data['input_sha256'] == supplied._sources_sha256
    assert data['model_root_sha256'] == supplied.manifest(supplied.artifacts, SCOPE).sha256
    assert [row['artifact_id'] for row in data['artifacts']] == sorted(v['id'] for v in supplied.artifacts)
    for row in data['artifacts']:
        value = next(v for v in supplied.artifacts if v['id'] == row['artifact_id'])
        assert row['path'] == artifact_path(value['artifact_type'], value['id'], 'SR')
        assert row['revision'] == value['revision']
        assert row['source_sha256'] == sha256(original[row['path']]).hexdigest()
        assert row['record_sha256'] == canonical_json_sha256(value)
    assert len(data['relations']) == 13
    assert {r['relation_id'] for r in data['relations']} == {edge(number=n)['relation_id'] for n in range(1, 14)}
    for row in data['relations']:
        source = json.loads(original[row['path']])
        relation = source['relations'][int(row['pointer'].split('/')[-1])]
        assert (row['source_id'], row['type'], row['target_id']) == (source['id'], relation['type'], relation['target'])
        assert row['relation_sha256'] == canonical_json_sha256(relation)
        assert row['source_sha256'] == sha256(original[row['path']]).hexdigest()
    assert report.sha256 == canonical_json_sha256(data) and supplied.source_files == original


def test_schedule_groups_are_direct_stored_assignments_not_release_closures():
    data = project_roadmap(model(roadmap_values())).data
    groups = {row['planning_id']: row for row in data['schedule_groups']}
    assert groups == {
        aid('release', 1): {'planning_id': aid('release', 1), 'artifact_type': 'release',
            'scheduled_artifact_ids': [], 'milestone_ids': [aid('milestone', 1)]},
        aid('release', 2): {'planning_id': aid('release', 2), 'artifact_type': 'release',
            'scheduled_artifact_ids': [aid('capability', 1)], 'milestone_ids': [aid('milestone', 2)]},
        aid('milestone', 1): {'planning_id': aid('milestone', 1), 'artifact_type': 'milestone',
            'scheduled_artifact_ids': [aid('task', 1)], 'milestone_ids': []},
        aid('milestone', 2): {'planning_id': aid('milestone', 2), 'artifact_type': 'milestone',
            'scheduled_artifact_ids': [aid('requirement', 1)], 'milestone_ids': []}}
    task = by_id(data)[aid('task', 1)]
    assert task['parent_ids'] == [aid('capability', 1)]
    assert task['scheduled_for_ids'] == [aid('milestone', 1)]
    assert task['implemented_subject_ids'] == sorted([aid('capability', 1), aid('requirement', 1), aid('decision', 1)])
    assert not data['release_closure_evaluated']


def test_multiple_schedule_targets_and_parallel_edges_keep_all_stored_identities():
    values = roadmap_values(); task = values[4]
    task['relations'].extend([
        edge('scheduled_for', aid('release', 2), number=14),
        edge('scheduled_for', aid('milestone', 1), number=15)])
    data = project_roadmap(model(values)).data
    assert by_id(data)[task['id']]['scheduled_for_ids'] == sorted([aid('release', 2), aid('milestone', 1)])
    edges = [r for r in data['relations'] if r['source_id'] == task['id'] and r['type'] == 'scheduled_for']
    assert len(edges) == 3
    assert {r['relation_id'] for r in edges} == {edge(number=n)['relation_id'] for n in (4, 14, 15)}


def test_priorities_and_dates_remain_explicit_fields_without_inheritance():
    data = project_roadmap(model(roadmap_values())).data; items = by_id(data)
    assert items[aid('capability', 1)]['stored']['priority'] == 'high'
    assert items[aid('requirement', 1)]['stored']['priority'] == 'mandatory'
    assert items[aid('release', 1)]['stored']['target_date'] == '2027-03-10'
    assert {key for key, row in items.items() if 'target_date' in row['stored']} == {aid('release', 1)}
    assert 'priority' not in items[aid('task', 1)]['stored']
    assert all('effort' not in row['stored'] and 'critical_path' not in row['stored'] for row in items.values())
    assert not any(data[key] for key in ('dates_estimated', 'effort_estimated', 'critical_path_evaluated'))


def test_parent_and_subject_links_do_not_hide_unscheduled_work():
    values = roadmap_values()
    for value in values:
        value['relations'] = [r for r in value['relations'] if r['type'] != 'scheduled_for']
    data = project_roadmap(model(values)).data
    assert data['unscheduled_ids'] == sorted([aid('capability', 1), aid('requirement', 1), aid('task', 1)])
    assert by_id(data)[aid('task', 1)]['parent_ids'] == [aid('capability', 1)]
    assert data['task_subject_links_complete'] and data['tasks_without_subject_links'] == []


@pytest.mark.parametrize('probability,impact,risk_status', [
    (0, 0, 'accepted'), (1, 8.5, 'open'), ('rare', 'catastrophic', 'awaiting-owner')])
def test_risk_fields_and_mitigation_edges_are_observations_not_ratings_or_approvals(probability, impact, risk_status):
    values = roadmap_values(); risk = values[-2]
    risk.update(probability=probability, impact=impact, risk_status=risk_status)
    data = project_roadmap(model(values)).data; row, = data['risks']
    assert row['artifact_id'] == risk['id']
    assert row['stored']['probability'] == probability and row['stored']['impact'] == impact
    assert row['stored']['risk_status'] == risk_status
    assert row['mitigated_by_ids'] == sorted([aid('task', 1), aid('requirement', 1), aid('decision', 1)])
    assert by_id(data)[aid('task', 1)]['mitigates_ids'] == [risk['id']]
    assert not data['release_readiness_evaluated'] and not data['approval_granted']


def test_disconnected_risks_still_appear_without_invented_mitigation():
    risk = domain_value('risk', id=aid('risk', 2))
    data = project_roadmap(model([*roadmap_values(), risk])).data
    row = by_id(data, 'risks')[risk['id']]
    assert row['mitigated_by_ids'] == [] and row['stored']['probability'] == 0.25
    assert len(data['relations']) == 13


def test_direct_dependencies_keep_orientation_and_bind_non_planning_endpoints():
    values = roadmap_values()
    values[0]['relations'].append(edge('depends_on', aid('release', 2), number=14))
    values[1]['relations'].append(edge('depends_on', aid('milestone', 2), number=15))
    data = project_roadmap(model(values)).data; items = by_id(data)
    assert items[aid('release', 1)]['dependency_ids'] == [aid('release', 2)]
    assert items[aid('release', 2)]['dependency_ids'] == [aid('milestone', 2)]
    assert items[aid('task', 1)]['dependency_ids'] == [aid('component', 1)]
    assert aid('component', 1) in by_id(data, 'artifacts') and aid('component', 1) not in items
    assert not any(r['source_id'] == aid('release', 1) and r['target_id'] == aid('milestone', 2) for r in data['relations'])


@pytest.mark.parametrize('kind,field,replacement', [
    ('capability', 'priority', 'low'), ('requirement', 'priority', 'medium'),
    ('release', 'target_date', '2028-01-02'), ('risk', 'probability', 0.8),
    ('risk', 'impact', 2.5), ('risk', 'risk_status', 'accepted')])
def test_changed_source_facts_replace_projection_facts_and_bindings(kind, field, replacement):
    values = roadmap_values(); before = project_roadmap(model(values))
    changed = next(v for v in values if v['artifact_type'] == kind); changed[field] = replacement
    after = project_roadmap(model(values)); field_name = 'risks' if kind == 'risk' else 'items'
    row = by_id(after.data, field_name)[changed['id']]
    assert row['stored'][field] == replacement
    assert row['record_sha256'] != by_id(before.data, field_name)[changed['id']]['record_sha256']
    assert after.sha256 != before.sha256 and after.data['input_sha256'] != before.data['input_sha256']


def test_reassigning_the_stored_schedule_replaces_only_the_projected_assignment():
    values = roadmap_values(); before = project_roadmap(model(values)).data
    values[4]['relations'][1]['target'] = aid('release', 2)
    after = project_roadmap(model(values)).data
    assert by_id(after)[aid('task', 1)]['scheduled_for_ids'] == [aid('release', 2)]
    assert by_id(after)[aid('task', 1)]['stored'] == by_id(before)[aid('task', 1)]['stored']
    assert after['model_root_sha256'] != before['model_root_sha256']


def test_projection_is_owned_order_independent_and_cannot_be_used_as_authority():
    values = roadmap_values(); supplied = model(values); expected = project_roadmap(supplied)
    actual = project_roadmap(model(list(reversed(values))))
    assert actual.data == expected.data and actual.sha256 == expected.sha256
    values[0]['target_date'] = '2029-12-31'
    detached = actual.data; detached['items'][0]['stored'].clear(); detached['risks'].clear()
    assert actual.data == expected.data
    with pytest.raises(FrozenInstanceError): actual._encoded = b'{}'
    with pytest.raises(TypeError): bool(actual)
    with pytest.raises(TypeError): RoadmapProjection(detached)
    assert not any(actual.data[key] for key in ('project_files_verified', 'full_validation_passed',
        'applicability_evaluated', 'done_evidence_evaluated', 'verification_evaluated',
        'release_readiness_evaluated', 'write_authorized', 'approval_granted'))


def test_empty_supplied_project_has_no_generated_schedule_or_required_roadmap_file():
    supplied = model([]); original = supplied.source_files
    with no_write_attempts(): data = project_roadmap(supplied).data
    assert all(data[key] == [] for key in ('items', 'risks', 'relations', 'schedule_groups', 'unscheduled_ids'))
    assert supplied.source_files == original and not data['normative']


@pytest.mark.parametrize('supplied', [None, {}, {'artifacts': []}])
def test_roadmap_rejects_unbound_dictionaries(supplied):
    with no_write_attempts(), pytest.raises(ModelError) as error: project_roadmap(supplied)
    assert error.value.reason == 'roadmap_target_model_required'


def test_risk_schema_is_checked_before_publishing_any_projection():
    values = roadmap_values(); values[-2].pop('impact')
    with no_write_attempts(), pytest.raises(ModelError) as error: project_roadmap(model(values))
    assert error.value.reason == 'missing_field' and error.value.pointer == '/impact'
    assert error.value.path == artifact_path('risk', aid('risk', 1), 'SR')


def test_missing_schedule_target_never_becomes_an_unbound_roadmap_item():
    values = roadmap_values(); values[4]['relations'][1]['target'] = aid('milestone', 3)
    with no_write_attempts(), pytest.raises(ModelError) as error: project_roadmap(model(values))
    assert error.value.reason == 'missing_relation_target'


def test_roadmap_does_not_write_or_reopen_the_live_project(tmp_path):
    root = tmp_path / 'project'; supplied = stored(root, roadmap_values()); before = inventory(tmp_path)
    with no_write_attempts(): expected = project_roadmap(supplied)
    assert inventory(tmp_path) == before
    shutil.rmtree(root)
    with no_write_attempts(): actual = project_roadmap(supplied)
    assert actual.data == expected.data and not root.exists()


@pytest.mark.parametrize('mode', ['core', 'pyz'])
def test_roadmap_projection_has_identical_native_core_and_pyz_contracts(tmp_path, mode):
    supplied = model(roadmap_values()); expected = project_roadmap(supplied).data
    body = '''import json
from specroad.planning import project_roadmap
from specroad.changes import TargetModel
from specroad.model.model_manifest import ProjectReadBinding
from specroad.profiles import ProfileResource, compose_profiles
from specroad.validation import ModelDocument
'''
    body += 'configuration=' + repr(supplied.configuration_bytes) + '\n'
    body += 'documents=' + repr([(d.path, d.content) for d in supplied.documents]) + '\n'
    body += 'resources=' + repr([(d.path, d.content) for d in supplied.resource_files]) + '\n'
    body += '''profile=ProfileResource(dict(resources)['profiles/core.json'])
supplied=TargetModel(configuration,ProjectReadBinding('sample','/explicit/provider',(1,2)),
 [ModelDocument(p,b) for p,b in documents],profile=compose_profiles([profile],core_key=profile.key),
 resource_files=[ModelDocument(p,b) for p,b in resources])
print(json.dumps(project_roadmap(supplied).data,sort_keys=True))
'''
    if mode == 'core': result = run_core(body, tmp_path, capture=True)
    else:
        _, package = build_distribution(tmp_path / 'distribution')
        result = run_python(['-I', '-S', '-B', '-c',
            'import sys;sys.path.insert(0,' + repr(str(package)) + ')\n' + body], tmp_path, capture=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == expected
