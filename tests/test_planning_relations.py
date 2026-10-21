"""Stored planning identities, common writer integration and non-authority."""
from dataclasses import FrozenInstanceError
from hashlib import sha256
import json
import shutil

import pytest

from specroad.authoring.creation import create_artifact
from specroad.authoring.inputs import normalize_artifact_create_input
from specroad.authoring.relations import add_relation
from specroad.changes import TargetModel, PublicationAuthority
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.model.errors import ModelError
from specroad.model.paths import artifact_path
from specroad.model.relation_identity import RelationInventory
from specroad.planning import PlanningRelations, assess_planning_relations
from specroad.validation import ModelDocument
from support.domain import domain_value
from support.model import put
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import inventory, no_write_attempts
from support.relations import aid, edge
from support.targets import model, SCOPE
from test_artifact_creation import project, arguments


def planning_values():
    first = domain_value('release', id=aid('release', 1), name='First', target_date='2027-03-10')
    second = domain_value('release', id=aid('release', 2), name='Second')
    milestones = [domain_value('milestone', id=aid('milestone', n),
        owner={'actor_type': 'human', 'actor_id': 'owner-' + str(n)}, done_criteria=['Stored criterion ' + str(n)],
        relations=[edge('part_of', release['id'], number=n)])
        for n, release in enumerate([first, second], 1)]
    task = domain_value('task', id=aid('task', 1),
        relations=[edge('part_of', aid('capability', 1), number=3),
                   edge('scheduled_for', milestones[0]['id'], number=4)])
    capability = domain_value('capability', id=aid('capability', 1),
        relations=[edge('scheduled_for', second['id'], number=5),
                   edge('implemented_by', task['id'], number=6)])
    requirement = domain_value('requirement', id=aid('requirement', 1),
        relations=[edge('implemented_by', task['id'], number=7),
                   edge('scheduled_for', milestones[1]['id'], number=8)])
    decision = domain_value('decision', id=aid('decision', 1),
        relations=[edge('implemented_by', task['id'], number=9)])
    return [first, second, *milestones, task, capability, requirement, decision]


def test_planning_reuses_exact_existing_identities_and_stored_edge_orientation():
    values = planning_values(); supplied = model(values); original = supplied.source_files
    with no_write_attempts(): report = assess_planning_relations(supplied)
    data = report.data
    assert data['scope_descriptor'] == SCOPE and data['project_id'] == supplied.binding.project_id
    assert data['input_sha256'] == supplied._sources_sha256
    assert data['model_root_sha256'] == supplied.manifest(values, SCOPE).sha256
    assert [row['artifact_id'] for row in data['artifacts']] == sorted(v['id'] for v in values)
    expected = {(v['id'], r['relation_id'], r['type'], r['target']) for v in values for r in v['relations']}
    assert {(r['source_id'], r['relation_id'], r['type'], r['target_id']) for r in data['relations']} == expected
    assert len(data['relations']) == len(expected) == 9
    for row in data['relations']:
        source = next(v for v in values if v['id'] == row['source_id'])
        relation = source['relations'][int(row['pointer'].split('/')[-1])]
        assert row['path'] == artifact_path(source['artifact_type'], source['id'], 'SR')
        assert row['source_sha256'] == sha256(original[row['path']]).hexdigest()
        assert row['relation_sha256'] == canonical_json_sha256(relation)
    assert supplied.source_files == original
    assert report.sha256 == canonical_json_sha256(data)


def test_release_milestone_owner_criteria_and_task_subjects_are_original_facts():
    values = planning_values(); data = assess_planning_relations(model(values)).data
    assert [(r['artifact_id'], r['name']) for r in data['releases']] == [
        (aid('release', 1), 'First'), (aid('release', 2), 'Second')]
    assert data['releases'][0]['target_date'] == '2027-03-10'
    assert 'target_date' not in data['releases'][1]
    for n, row in enumerate(data['milestones'], 1):
        assert row['release_id'] == aid('release', n)
        assert row['release_relation_id'] == edge(number=n)['relation_id']
        assert row['owner'] == {'actor_type': 'human', 'actor_id': 'owner-' + str(n)}
        assert row['done_criteria'] == ['Stored criterion ' + str(n)]
    task, = data['tasks']; original = values[4]
    for key in ('description', 'owner', 'implementation_status', 'verification_plan_status', 'done_criteria'):
        assert task[key] == original[key]
    assert task['implemented_subject_ids'] == sorted([aid('capability', 1), aid('requirement', 1), aid('decision', 1)])
    assert task['implementation_relation_ids'] == sorted(edge(number=n)['relation_id'] for n in (6, 7, 9))
    assert data['task_subject_links_complete'] and data['tasks_without_subject_links'] == []
    assert not any(data[key] for key in ('project_files_verified', 'full_validation_passed',
        'applicability_evaluated', 'done_evidence_evaluated', 'release_readiness_evaluated',
        'write_authorized', 'approval_granted'))


@pytest.mark.parametrize('maturity', ['draft', 'proposed', 'in_review', 'rejected', 'retired'])
def test_unlinked_task_is_an_explicit_incomplete_observation_not_an_invented_edge(maturity):
    task = domain_value('task', maturity=maturity)
    data = assess_planning_relations(model([task])).data
    assert data['tasks_without_subject_links'] == [task['id']]
    assert not data['task_subject_links_complete']
    assert data['tasks'][0]['implemented_subject_ids'] == []
    assert data['relations'] == [] and not data['done_evidence_evaluated']


def test_approved_task_requires_a_stored_requirement_or_decision_link():
    task = domain_value('task', maturity='approved')
    with no_write_attempts(), pytest.raises(ModelError) as error:
        assess_planning_relations(model([task]))
    assert error.value.reason == 'planning_task_implementation_required'
    assert error.value.path == artifact_path('task', task['id'], 'SR')


@pytest.mark.parametrize('kind,key', [('release', 'objective'), ('milestone', 'owner'),
    ('task', 'description'), ('task', 'owner'), ('task', 'done_criteria'), ('task', 'implementation_status')])
def test_planning_uses_shared_mandatory_field_contracts(kind, key):
    values = planning_values(); target = next(v for v in values if v['artifact_type'] == kind)
    target.pop(key)
    with no_write_attempts(), pytest.raises(ModelError) as error:
        assess_planning_relations(model(values))
    assert error.value.reason == 'missing_field' and error.value.pointer == '/' + key
    assert error.value.path == artifact_path(kind, target['id'], 'SR')


@pytest.mark.parametrize('count', [0, 2])
def test_milestone_never_selects_an_arbitrary_release(count):
    values = planning_values(); values[2]['relations'] = [
        edge('part_of', aid('release', n + 1), number=10 + n) for n in range(count)]
    with no_write_attempts(), pytest.raises(ModelError) as error:
        assess_planning_relations(model(values))
    assert error.value.reason == 'milestone_release_cardinality'


def test_reports_are_detached_and_inventory_order_is_not_planning_authority():
    values = planning_values(); report = assess_planning_relations(model(values))
    reversed_report = assess_planning_relations(model(list(reversed(values))))
    assert reversed_report.data == report.data and reversed_report.sha256 == report.sha256
    detached = report.data; detached['milestones'][0]['owner']['actor_id'] = 'foreign'
    detached['tasks'][0]['done_criteria'].clear(); detached['relations'].clear()
    assert report.data == reversed_report.data
    with pytest.raises(FrozenInstanceError): report._encoded = b'{}'
    with pytest.raises(TypeError): bool(report)
    with pytest.raises(TypeError): PlanningRelations(detached)


def stored(root, values):
    base, _ = project(root)
    documents = [ModelDocument(artifact_path(v['artifact_type'], v['id'], 'SR'),
        json.dumps(v, indent=3).encode() + b'\n') for v in values]
    supplied = TargetModel(base.configuration_bytes, base.binding, [*base.documents, *documents],
        profile=base.profile, resource_files=base.resource_files)
    for name, raw in supplied.source_files.items(): put(root, name, raw)
    return supplied


@pytest.mark.parametrize('source_kind', ['capability', 'requirement', 'task'])
@pytest.mark.parametrize('target_kind', ['release', 'milestone'])
def test_common_writer_schedules_existing_subjects_without_artifact_copies(tmp_path, source_kind, target_kind):
    values = planning_values()
    # Remove existing scheduling edges while preserving Milestone ownership and Task links.
    for value in values: value['relations'] = [r for r in value['relations'] if r['type'] != 'scheduled_for']
    root = tmp_path / 'project'; supplied = stored(root, values)
    source = next(v for v in values if v['artifact_type'] == source_kind)
    target = next(v for v in values if v['artifact_type'] == target_kind)
    original = supplied.source_files; path = artifact_path(source_kind, source['id'], 'SR')
    relation_ids = [r['relation_id'] for v in supplied.artifacts for r in v['relations']]
    result = add_relation(supplied, source['id'], 'scheduled_for', target['id'],
        inventory=RelationInventory(relation_ids, (), ()), actor={'actor_type': 'human', 'actor_id': 'planner'},
        planned_at='2026-10-21T10:00:00Z', change_plan_id='CP-schedule', request_id='schedule-one',
        transaction_id='schedule-one', authority=PublicationAuthority('planning-host', '1', lambda r: True))
    assert result['write_state'] == 'committed' and result['completion']['current_target_verified']
    updated = json.loads((root / path).read_bytes())
    assert updated['id'] == source['id'] and updated['revision'] == source['revision'] + 1
    scheduled = [r for r in updated['relations'] if r['type'] == 'scheduled_for']
    assert len(scheduled) == 1 and scheduled[0]['target'] == target['id']
    assert scheduled[0]['relation_id'] == result['relation_id']
    for name, raw in original.items():
        if name != path: assert (root / name).read_bytes() == raw
    assert {p.relative_to(root).as_posix() for p in (root / 'spec').rglob('*.json')} == {
        d.path for d in supplied.documents}
    fresh = TargetModel(supplied.configuration_bytes, supplied.binding,
        [ModelDocument(d.path, (root / d.path).read_bytes()) for d in supplied.documents],
        profile=supplied.profile, resource_files=supplied.resource_files)
    with no_write_attempts(): observed = assess_planning_relations(fresh).data
    assert any(r['relation_id'] == result['relation_id'] and r['source_id'] == source['id'] and
        r['target_id'] == target['id'] for r in observed['relations'])


def test_common_creation_preserves_one_milestone_owner_and_release_link(tmp_path):
    root = tmp_path / 'project'; supplied, ids = project(root, 'milestone')
    fields = {'title': 'Delivery gate', 'objective': 'Deliver a reviewed parser.', 'owner': 'engineering',
        'done_criteria': ['Parser checks have been reviewed.'],
        'relations': [edge('part_of', domain_value('release')['id'], number=10)]}
    result = create_artifact(supplied, normalize_artifact_create_input('milestone', fields),
        **arguments(supplied, ids))
    assert result['write_state'] == 'committed'
    created = json.loads((root / result['path']).read_bytes())
    fresh = TargetModel(supplied.configuration_bytes, supplied.binding,
        [*supplied.documents, ModelDocument(result['path'], (root / result['path']).read_bytes())],
        profile=supplied.profile, resource_files=supplied.resource_files)
    row, = assess_planning_relations(fresh).data['milestones']
    assert row['artifact_id'] == created['id'] == result['artifact_id']
    assert row['owner'] == fields['owner'] and row['done_criteria'] == fields['done_criteria']
    assert row['release_id'] == domain_value('release')['id']
    for path, raw in supplied.source_files.items(): assert (root / path).read_bytes() == raw


def test_bound_planning_does_not_reopen_the_live_root_or_write_report_files(tmp_path):
    root = tmp_path / 'project'; supplied = stored(root, planning_values()); before = inventory(tmp_path)
    with no_write_attempts(): expected = assess_planning_relations(supplied)
    assert inventory(tmp_path) == before
    shutil.rmtree(root)
    with no_write_attempts(): actual = assess_planning_relations(supplied)
    assert actual.data == expected.data and not root.exists()


@pytest.mark.parametrize('mode', ['core', 'pyz'])
def test_native_planning_contract_is_identical_in_isolated_core_and_pyz(tmp_path, mode):
    supplied = model(planning_values()); expected = assess_planning_relations(supplied).data
    body = '''import json
from specroad.planning import assess_planning_relations
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
print(json.dumps(assess_planning_relations(supplied).data,sort_keys=True))
'''
    if mode == 'core': result = run_core(body, tmp_path, capture=True)
    else:
        _, package = build_distribution(tmp_path / 'distribution')
        result = run_python(['-I', '-S', '-B', '-c',
            'import sys;sys.path.insert(0,' + repr(str(package)) + ')\n' + body], tmp_path, capture=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == expected
