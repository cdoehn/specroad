"""Native Release membership and external obligations, never readiness proof."""
from dataclasses import FrozenInstanceError
from hashlib import sha256
import json
import shutil

import pytest

from specroad.graph.closure_inputs import ClosureBindings, artifact_node, resource_node
from specroad.graph.relations import SourceRelations
from specroad.graph.scope_inputs import ScopeResource, ScopeSeedInputs
from specroad.model.canonical import canonical_json_sha256
from specroad.model.errors import ModelError
from specroad.planning import ReleaseScope, resolve_release_scope
from support.closure import observe
from support.domain import domain_value
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import inventory, no_write_attempts
from support.records import record_value
from support.relations import aid, edge
from support.targets import model, SCOPE
from test_planning_relations import stored
from test_verification_required_checks import condition


def release_values():
    return [
        domain_value('release', id=aid('release', 1)),
        domain_value('release', id=aid('release', 2)),
        domain_value('milestone', id=aid('milestone', 1),
            relations=[edge('part_of', aid('release', 1), number=1)]),
        domain_value('milestone', id=aid('milestone', 2),
            relations=[edge('part_of', aid('release', 2), number=2)]),
        domain_value('task', id=aid('task', 1),
            relations=[edge('scheduled_for', aid('milestone', 1), number=3)]),
        domain_value('task', id=aid('task', 2),
            relations=[edge('part_of', aid('release', 1), number=4)]),
        domain_value('task', id=aid('task', 3),
            relations=[edge('part_of', aid('milestone', 1), number=5)]),
        domain_value('requirement', id=aid('requirement', 1), relations=[
            edge('scheduled_for', aid('release', 1), number=6),
            edge('depends_on', aid('component', 1), number=7)]),
        domain_value('requirement', id=aid('requirement', 2),
            relations=[edge('scheduled_for', aid('release', 2), number=8)]),
        domain_value('component', id=aid('component', 1),
            relations=[edge('depends_on', aid('component', 2), number=9)]),
        domain_value('component', id=aid('component', 2)),
        domain_value('capability', id=aid('capability', 1), relations=[
            edge('scheduled_for', aid('release', 1), number=10),
            edge('depends_on', aid('requirement', 1), number=11)])]


def bindings_for(supplied):
    resources = [ScopeResource('fixture-resource:' + str(i), r.data['kind'], r.data['sha256'],
        r.data.get('version') if r.data['kind'] in ('profile', 'rule', 'mapping') else None,
        active=r.data['kind'] == 'profile') for i, r in enumerate(supplied.resources)]
    inputs = ScopeSeedInputs(supplied.configuration,
        [SourceRelations(d.content, path=d.path) for d in supplied.documents], resources)
    # Empty observations are justified by this owned synthetic fixture only.
    return observe(inputs)


def resolve(supplied, **options):
    return resolve_release_scope(supplied, aid('release', 1),
        scope_bindings=bindings_for(supplied), **options)


def test_release_seeds_include_milestones_schedules_and_task_memberships():
    supplied = model(release_values())
    with no_write_attempts(): report = resolve(supplied)
    data = report.data
    expected = {aid('release', 1), aid('milestone', 1), aid('requirement', 1),
                aid('capability', 1), *(aid('task', n) for n in (1, 2, 3))}
    assert data['seed_artifact_ids'] == sorted(expected)
    assert data['artifact_ids'] == sorted(expected | {aid('component', 1), aid('component', 2)})
    assert data['scope_resolution']['seed_artifact_ids'] == data['seed_artifact_ids']
    assert data['scope_resolution']['closure_complete'] is True
    assert data['scope_descriptor'] == {**SCOPE, 'scope_kind': 'release',
                                        'selector': {'release_id': aid('release', 1)}}
    assert data['input_sha256'] == supplied._sources_sha256
    assert data['project_model_root_sha256'] == supplied.manifest(supplied.artifacts, SCOPE).sha256
    assert data['scope_descriptor_sha256'] == canonical_json_sha256(data['scope_descriptor'])
    assert data['scope_resolution_sha256'] == canonical_json_sha256(data['scope_resolution'])
    assert 'scope_hash' not in data and data['configuration_hash'] is None


def test_external_required_edges_keep_actual_direction_ids_pointers_and_bytes():
    supplied = model(release_values()); data = resolve(supplied).data
    external = data['external_required_dependencies']
    assert {(r['source_id'], r['target_id']) for r in external} == {
        (aid('requirement', 1), aid('component', 1)), (aid('component', 1), aid('component', 2))}
    assert data['external_required_artifact_ids'] == [aid('component', 1), aid('component', 2)]
    assert data['external_membership_basis'] == 'release_seed_artifact_ids'
    artifacts = {a['artifact_id']: a for a in data['artifacts']}
    assert set(artifacts) == set(data['artifact_ids'])
    for binding in artifacts.values():
        raw = supplied.source_files[binding['path']]; value = json.loads(raw)
        assert binding['record_sha256'] == canonical_json_sha256(value)
        assert binding['source_sha256'] == sha256(raw).hexdigest()
        assert (binding['revision'], binding['artifact_type']) == (value['revision'], value['artifact_type'])
    for row in data['required_dependencies']:
        raw = supplied.source_files[row['path']]; value = json.loads(raw)
        relation = value['relations'][int(row['pointer'].split('/')[-1])]
        assert (row['source_id'], row['target_id'], row['relation_id'], row['type']) == (
            value['id'], relation['target'], relation['relation_id'], 'depends_on')
        assert row['relation_sha256'] == canonical_json_sha256(relation)
        assert row['source_sha256'] == sha256(raw).hexdigest()
        assert row['target_record_sha256'] == artifacts[row['target_id']]['record_sha256']
    internal, = [r for r in data['required_dependencies'] if not r['external']]
    assert internal['source_id'] == aid('capability', 1) and internal['target_id'] == aid('requirement', 1)
    assert internal['source_is_release_seed'] and internal['target_is_release_seed']
    indirect, = [r for r in external if r['source_id'] == aid('component', 1)]
    assert not indirect['source_is_release_seed'] and not indirect['target_is_release_seed']


def test_shared_release_assignment_is_internal_without_changing_stored_edges():
    values = release_values()
    values[7]['relations'].append(edge('scheduled_for', aid('release', 2), number=12))
    values[8]['relations'].append(edge('depends_on', aid('requirement', 1), number=13))
    supplied = model(values)
    data = resolve_release_scope(supplied, aid('release', 2), scope_bindings=bindings_for(supplied)).data
    assert aid('requirement', 1) in data['seed_artifact_ids']
    row, = [r for r in data['required_dependencies'] if r['source_id'] == aid('requirement', 2)]
    assert row['target_is_release_seed'] and not row['external']
    assert {aid('component', 1), aid('component', 2)} <= set(data['artifact_ids'])


def test_reached_other_release_does_not_import_its_incoming_assignments():
    values = release_values()
    values[0]['relations'] = [edge('depends_on', aid('release', 2), number=12)]
    data = resolve(model(values)).data
    assert aid('release', 2) in data['artifact_ids'] and aid('release', 2) not in data['seed_artifact_ids']
    assert aid('milestone', 2) not in data['artifact_ids'] and aid('requirement', 2) not in data['artifact_ids']
    assert aid('release', 2) in data['external_required_artifact_ids']


def test_cycles_parallel_edges_and_transitive_dependencies_are_not_rewritten():
    values = release_values()
    values[9]['relations'].append(edge('depends_on', aid('component', 2), number=12))
    values[10]['relations'] = [edge('depends_on', aid('component', 1), number=13)]
    data = resolve(model(values)).data
    assert len(data['artifact_ids']) == len(set(data['artifact_ids'])) == 9
    assert {r['relation_id'] for r in data['external_required_dependencies']} == {
        edge(number=n)['relation_id'] for n in (7, 9, 12, 13)}
    assert not any(r['source_id'] == aid('requirement', 1) and r['target_id'] == aid('component', 2)
                   for r in data['required_dependencies'])


@pytest.mark.parametrize('maturity', ['rejected', 'retired'])
def test_reachable_inactive_dependencies_remain_visible(maturity):
    values = release_values(); values[10]['maturity'] = maturity
    assert aid('component', 2) in resolve(model(values)).data['external_required_artifact_ids']


def test_changed_external_source_rebinds_observation_without_authorizing_it():
    values = release_values(); before = resolve(model(values))
    values[10]['description'] = 'Changed mandatory component'
    after = resolve(model(values))
    assert before.data['artifact_ids'] == after.data['artifact_ids']
    assert before.data['input_sha256'] != after.data['input_sha256'] and before.sha256 != after.sha256
    assert before.data['scope_resolution_sha256'] != after.data['scope_resolution_sha256']


def test_explicit_profile_and_current_review_inputs_are_followed_without_authentication_claim():
    values = release_values()
    review = record_value('relation_review', id=aid('relation_review', 1),
                          relation_id=edge(number=7)['relation_id'])
    supplied = model([*values, review]); bound = bindings_for(supplied)
    resource = bound.inventory.resources[0].resource_id
    observed = observe(bound.inventory, uses={artifact_node(aid('component', 1)): (resource_node(resource),)},
                       reviews={edge(number=7)['relation_id']: (review['id'],)})
    data = resolve_release_scope(supplied, aid('release', 1), scope_bindings=observed).data
    assert review['id'] in data['artifact_ids'] and review['id'] not in data['seed_artifact_ids']
    assert data['resource_ids'] == [resource]
    assert not data['scope_providers_authenticated'] and not data['approval_granted']


@pytest.mark.parametrize('missing', ['uses', 'reviews'])
def test_missing_explicit_dependency_observations_cannot_be_assumed_empty(missing):
    supplied = model(release_values()); bound = bindings_for(supplied)
    uses, reviews = dict(bound.uses), dict(bound.current_reviews)
    if missing == 'uses': uses.pop(artifact_node(aid('component', 1)))
    else: reviews.pop(edge(number=7)['relation_id'])
    incomplete = ClosureBindings(bound.inventory, uses=uses, current_reviews=reviews)
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        resolve_release_scope(supplied, aid('release', 1), scope_bindings=incomplete)
    assert caught.value.reason == {'uses': 'closure_usage_observation_missing',
                                  'reviews': 'closure_review_observation_missing'}[missing]


@pytest.mark.parametrize('change', ['source', 'omission', 'resources'])
def test_scope_inventory_must_match_exact_model_bytes_and_resource_inventory(change):
    values = release_values(); supplied = model(values)
    if change == 'source': values[10]['description'] = 'Foreign'
    if change == 'omission': values.pop(8)
    bound = bindings_for(model(values))
    if change == 'resources':
        bound = observe(ScopeSeedInputs(supplied.configuration, bound.inventory.records))
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        resolve_release_scope(supplied, aid('release', 1), scope_bindings=bound)
    assert caught.value.reason == ('verification_scope_resource_binding_mismatch' if change == 'resources'
                                   else 'verification_scope_inventory_mismatch')


@pytest.mark.parametrize('unbound', [None, {}, []])
def test_unbound_models_are_rejected(unbound):
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        resolve_release_scope(unbound, aid('release', 1), scope_bindings=None)
    assert caught.value.reason == 'release_scope_target_model_required'


def test_model_without_explicit_scope_bindings_cannot_publish_a_scope():
    supplied = model(release_values())
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        resolve_release_scope(supplied, aid('release', 1), scope_bindings=None)
    assert caught.value.reason == 'verification_scope_bindings_required'


def test_selected_release_must_exist_in_the_bound_model():
    supplied = model(release_values())
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        resolve_release_scope(supplied, aid('release', 9), scope_bindings=bindings_for(supplied))
    assert caught.value.reason == 'scope_seed_missing'


def test_excluded_required_dependency_fails_instead_of_silently_shortening_closure():
    values = release_values(); values[10]['applicability'] = condition('windows')
    values.append(record_value('configuration', id=aid('configuration', 1)))
    supplied = model(values)
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        resolve(supplied, configuration_id=aid('configuration', 1))
    assert caught.value.reason == 'scope_configuration_dependency' and caught.value.code == 'SRV141'


def test_configuration_filters_optional_seeds_and_is_bound_to_the_observation():
    values = release_values(); values[4]['applicability'] = condition('windows')
    values.append(record_value('configuration', id=aid('configuration', 1)))
    supplied = model(values); data = resolve(supplied, configuration_id=aid('configuration', 1)).data
    assert aid('task', 1) not in data['seed_artifact_ids'] and aid('task', 1) not in data['artifact_ids']
    assert {aid('component', 1), aid('component', 2)} <= set(data['artifact_ids'])
    assert data['configuration_hash'] and data['applicability_evaluated']
    assert data['scope_descriptor']['configuration_id'] == aid('configuration', 1)
    values[-1]['selection']['platform'] = 'windows'
    changed = resolve(model(values), configuration_id=aid('configuration', 1)).data
    assert aid('task', 1) in changed['seed_artifact_ids']
    assert changed['configuration_hash'] != data['configuration_hash']


def test_excluded_selected_release_is_not_an_empty_success():
    values = [domain_value('release', id=aid('release', 1), applicability=condition('windows')),
              record_value('configuration', id=aid('configuration', 1))]
    supplied = model(values)
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        resolve(supplied, configuration_id=aid('configuration', 1))
    assert caught.value.reason == 'release_scope_release_excluded'


def test_empty_release_reports_only_itself_and_never_a_readiness_pass():
    supplied = model([domain_value('release', id=aid('release', 1))])
    data = resolve(supplied).data
    assert data['seed_artifact_ids'] == data['artifact_ids'] == [aid('release', 1)]
    assert data['required_dependencies'] == data['external_required_dependencies'] == []
    assert data['generated'] and not data['normative'] and data['release_closure_evaluated']
    for flag in ('scope_providers_authenticated', 'project_files_verified', 'full_validation_passed',
                 'applicability_evaluated', 'done_evidence_evaluated', 'verification_evaluated',
                 'release_readiness_evaluated', 'write_authorized', 'approval_granted'):
        assert data[flag] is False


def test_observation_is_owned_deterministic_and_cannot_be_used_as_a_boolean_gate():
    values = release_values(); expected = resolve(model(values))
    actual = resolve(model(list(reversed(values))))
    assert actual.data == expected.data and actual.sha256 == canonical_json_sha256(expected.data)
    detached = actual.data; detached['artifact_ids'].clear(); detached['required_dependencies'].clear()
    values[10]['description'] = 'Later caller mutation'
    assert actual.data == expected.data
    with pytest.raises(TypeError): bool(actual)
    with pytest.raises(TypeError): ReleaseScope(actual.data)
    with pytest.raises(FrozenInstanceError): actual._encoded = b'{}'


def test_release_provider_preserves_project_files_and_does_not_reopen_them(tmp_path):
    root = tmp_path / 'project'; supplied = stored(root, release_values()); before = inventory(tmp_path)
    with no_write_attempts(): expected = resolve(supplied)
    assert inventory(tmp_path) == before
    shutil.rmtree(root)
    with no_write_attempts(): actual = resolve(supplied)
    assert actual.data == expected.data and not root.exists()


@pytest.mark.parametrize('mode', ['core', 'pyz'])
def test_release_scope_has_identical_native_core_and_pyz_contracts(tmp_path, mode):
    supplied = model(release_values()); expected = resolve(supplied).data
    body = '''import json
from specroad.planning import resolve_release_scope
from specroad.changes import TargetModel
from specroad.graph.closure_inputs import ClosureBindings, artifact_node, resource_node
from specroad.graph.relations import SourceRelations
from specroad.graph.scope_inputs import ScopeResource, ScopeSeedInputs
from specroad.model.model_manifest import ProjectReadBinding
from specroad.profiles import ProfileResource, compose_profiles
from specroad.validation import ModelDocument
'''
    body += 'configuration=' + repr(supplied.configuration_bytes) + '\n'
    body += 'documents=' + repr([(d.path, d.content) for d in supplied.documents]) + '\n'
    body += 'resources=' + repr([(d.path, d.content) for d in supplied.resource_files]) + '\n'
    body += 'release_id=' + repr(aid('release', 1)) + '\n'
    body += '''profile=ProfileResource(dict(resources)['profiles/core.json'])
supplied=TargetModel(configuration,ProjectReadBinding('sample','/explicit/provider',(1,2)),
 [ModelDocument(p,b) for p,b in documents],profile=compose_profiles([profile],core_key=profile.key),
 resource_files=[ModelDocument(p,b) for p,b in resources])
observed=[ScopeResource('fixture-resource:'+str(i),r.data['kind'],r.data['sha256'],
 r.data.get('version') if r.data['kind'] in ('profile','rule','mapping') else None,
 active=r.data['kind']=='profile') for i,r in enumerate(supplied.resources)]
inputs=ScopeSeedInputs(supplied.configuration,
 [SourceRelations(d.content,path=d.path) for d in supplied.documents],observed)
uses={artifact_node(r.identity.id):() for r in inputs.records}
uses.update({resource_node(r.resource_id):() for r in inputs.resources})
reviews={r.relation.identity.id:() for r in inputs.references.relations}
bound=ClosureBindings(inputs,uses=uses,current_reviews=reviews)
print(json.dumps(resolve_release_scope(supplied,release_id,scope_bindings=bound).data,sort_keys=True))
'''
    if mode == 'core': result = run_core(body, tmp_path, capture=True)
    else:
        _, package = build_distribution(tmp_path / 'distribution')
        result = run_python(['-I', '-S', '-B', '-c',
            'import sys;sys.path.insert(0,' + repr(str(package)) + ')\n' + body], tmp_path, capture=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == expected
