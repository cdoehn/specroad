"""Hostile evaluation choices must not define independent seeds or closure."""
from dataclasses import replace
from hashlib import sha256
import json

import pytest

from specroad.graph.closure_inputs import ClosureBindings, artifact_node
from specroad.graph.relations import SourceRelations
from specroad.graph.scope_descriptors import ScopeDescriptor
from specroad.graph.scope_inputs import ScopeResource, ScopeSeedInputs
from specroad.model.canonical import canonical_json_bytes
from specroad.model.configuration import ProjectConfiguration
from specroad.model.errors import ModelError
from specroad.query.selection import NormalizedQuery
from specroad.verification import (RequiredCheckCoverageError, VerificationEvaluationError,
    assess_required_check_coverage, resolve_required_checks)
from support.artifacts import artifact_bytes
from support.closure import observe
from support.domain import domain_value
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import no_write_attempts
from support.records import record_value, ref
from support.targets import model, SCOPE
from test_verification_required_checks import checks, condition, configured, edge, project, selected


def bindings_for(supplied):
    resources = [ScopeResource('fixture-resource:' + str(i), r.data['kind'], r.data['sha256'],
        r.data.get('version'), active=r.data['kind'] == 'profile') for i, r in enumerate(supplied.resources)]
    inventory = ScopeSeedInputs(supplied.configuration,
        [SourceRelations(d.content, path=d.path) for d in supplied.documents], resources)
    return observe(inventory)


def scope(*ids, kind='explicit', selector=None, policy='closed', configuration_id=None):
    if selector is None:
        selector = {'artifact_ids': sorted(ids or (ref(),)), 'resource_ids': []} if kind == 'explicit' else {}
    return ScopeDescriptor({**SCOPE, 'scope_kind': kind, 'selector': selector,
                            'boundary_policy': policy, 'configuration_id': configuration_id})


def requirement_checks():
    return [row for row in checks() if row['subject_artifact_id'] == ref()]


def assess(supplied, evaluation, descriptor=None, bindings=None, configuration_id=None):
    return assess_required_check_coverage(supplied, evaluation, configuration_id=configuration_id,
        scope_descriptor=scope() if descriptor is None else descriptor,
        scope_bindings=bindings_for(supplied) if bindings is None else bindings)


def test_explicit_seeds_resolve_native_strong_closure_before_key_comparison():
    supplied = model(project())
    with no_write_attempts():
        data = assess(supplied, selected(requirement_checks())).data
    required = data['required_set']; closure = required['scope_resolution']
    assert required['required_checks'] == requirement_checks()
    assert [r['artifact_id'] for r in required['subjects']] == [ref()]
    assert closure['seed_artifact_ids'] == [ref()]
    assert {r['identity'] for r in closure['members'] if r['kind'] == 'artifact'} == {
        ref(), ref('VER'), ref('TEST')}
    assert closure['closure_complete'] and not required['scope_providers_authenticated']
    assert required['scope_resolution_sha256'] == sha256(canonical_json_bytes(closure)).hexdigest()
    assert data['coverage_status'] == 'ready' and data['verification_result'] is None
    assert not required['project_required_checks_complete'] and not data['run_selection_evaluated']


@pytest.mark.parametrize('kind', ['project', 'specification', 'explicit'])
def test_independent_full_subject_scopes_preserve_every_required_check(kind):
    supplied = model(project()); descriptor = scope(ref(), ref('CAP'), ref('TASK'), kind=kind)
    data = assess(supplied, selected(), descriptor).data
    assert data['required_set']['required_checks'] == checks()
    assert data['required_set']['scope_descriptor'] == descriptor.data
    assert data['coverage_status'] == 'ready'


@pytest.mark.parametrize('foreign', [ref('CAP'), ref('TASK')])
def test_descriptor_cannot_replace_seed_subject_with_another_valid_project_subject(foreign):
    supplied = model(project()); rows = [r for r in checks() if r['subject_artifact_id'] == foreign]
    resolution = resolve_required_checks(supplied, configuration_id=None,
        scope_descriptor=scope(), scope_bindings=bindings_for(supplied))
    with pytest.raises(RequiredCheckCoverageError) as caught:
        assess(supplied, selected(rows))
    diagnostic = caught.value.diagnostic()
    assert isinstance(caught.value, VerificationEvaluationError)
    assert diagnostic['code'] == 'SRV175' and diagnostic['exit_code'] == 3
    assert diagnostic['missing_checks'] == requirement_checks()
    assert diagnostic['unexpected_keys'] == [{k: v for k, v in r.items() if k != 'dimension'} for r in rows]
    assert diagnostic['required_set_sha256'] == resolution.sha256
    assert caught.value.reason == 'unexpected_evaluation_required_key'
    changed = caught.value.details; changed['missing_checks'].clear()
    assert caught.value.diagnostic()['missing_checks'] == requirement_checks()


def test_missing_keys_are_not_confused_with_foreign_keys_when_no_foreign_key_exists():
    supplied = model(project()); rows = requirement_checks()
    data = assess(supplied, selected(rows[:1])).data
    assert data['missing_checks'] == rows[1:] and data['unexpected_keys'] == []
    assert data['coverage_status'] == 'incomplete'
    assert data['reasons'] == ['required_check_missing']


def test_multiple_extra_keys_and_missing_keys_are_reported_deterministically():
    supplied = model(project()); rows = [r for r in checks() if r['subject_artifact_id'] != ref()]
    reports = []
    for ordered in (rows, rows[::-1]):
        with pytest.raises(RequiredCheckCoverageError) as caught:
            assess(supplied, selected(ordered))
        reports.append(caught.value.diagnostic())
    assert reports[0] == reports[1]
    assert len(reports[0]['unexpected_keys']) == 2 and len(reports[0]['missing_checks']) == 4


@pytest.mark.parametrize('policy,expected', [('partial', requirement_checks()), ('closed', checks())])
def test_boundary_policy_controls_weak_dependencies_not_the_descriptor(policy, expected):
    records = project()
    records[0]['relations'].extend([
        dict(edge(ref('CAP'), 4), type='conflicts_with'),
        dict(edge(ref('TASK'), 5), type='conflicts_with')])
    supplied = model(records); descriptor = scope(policy=policy)
    data = assess(supplied, selected(expected), descriptor).data
    assert data['required_set']['required_checks'] == expected
    boundaries = data['required_set']['scope_resolution']['boundary_references']
    assert [b['target_id'] for b in boundaries] == ([ref('CAP'), ref('TASK')] if policy == 'partial' else [])


@pytest.mark.parametrize('policy', ['partial', 'closed'])
def test_required_dependency_subject_is_never_optional_in_a_partial_scope(policy):
    records = project(); records[0]['relations'].append(dict(edge(ref('CAP'), 4), type='depends_on'))
    supplied = model(records)
    data = assess(supplied, selected(requirement_checks()), scope(policy=policy)).data
    assert data['missing_checks'] == [checks()[0]]
    assert data['verification_result'] == 'incomplete'


def test_evidence_subject_closure_can_add_required_subjects_but_descriptor_ids_cannot():
    records = project(); records[1]['relations'] = [dict(edge(ref('EVD'), 4), type='produces')]
    records.append(record_value('evidence', subjects=[{'artifact_id': ref('CAP'), 'revision': 1,
        'artifact_sha256': 'a' * 64, 'verification_context_sha256': 'b' * 64}]))
    data = assess(model(records), selected(requirement_checks())).data
    assert data['missing_checks'] == [checks()[0]]
    assert data['verification_result'] == 'incomplete' and not data['run_selection_evaluated']


@pytest.mark.parametrize('kind', ['release', 'document'])
def test_release_and_document_selection_use_native_seed_and_relation_rules(kind):
    records = project()
    if kind == 'release':
        records.append(domain_value('release'))
        records[0]['relations'].append(dict(edge(ref('REL'), 4), type='scheduled_for'))
        descriptor = scope(kind=kind, selector={'release_id': ref('REL')})
    else:
        document = next(r for r in records if r['artifact_type'] == 'document')
        document['relations'] = [dict(edge(ref('SEC'), 4), type='contains', position=0)]
        records.append(record_value('section', relations=[dict(edge(ref('BLOCK'), 5), type='contains', position=0)]))
        records.append(record_value('content_block', block_kind='artifact_ref',
            payload={'render_mode': 'summary'}, relations=[dict(edge(ref(), 6), type='references')]))
        descriptor = scope(kind=kind, selector={'document_id': ref('DOC')})
    data = assess(model(records), selected(requirement_checks()), descriptor).data
    assert data['required_set']['required_checks'] == requirement_checks()
    assert data['coverage_status'] == 'ready'


def test_query_is_recomputed_from_actual_records_before_closure_and_coverage():
    supplied = model(project())
    query = NormalizedQuery(filters={'type': ['requirement', 'capability']}, sort=['id:desc'], limit=1)
    descriptor = scope(kind='query', selector={'query': query.data})
    data = assess(supplied, selected(requirement_checks()), descriptor).data
    assert data['required_set']['scope_resolution']['seed_artifact_ids'] == [ref()]
    assert data['required_set']['required_checks'] == requirement_checks()
    with pytest.raises(RequiredCheckCoverageError):
        assess(supplied, selected([checks()[0]]), descriptor)


@pytest.mark.parametrize('attempt', ['embedded-evaluation', 'verification-filter', 'verification-sort'])
def test_query_cannot_use_verification_results_or_the_descriptor_to_define_obligations(attempt):
    query = NormalizedQuery(
        evaluation=selected().data if attempt == 'embedded-evaluation' else None,
        filters={'verification_result': ['passed']} if attempt == 'verification-filter' else None,
        sort=['verification_result'] if attempt == 'verification-sort' else [])
    with pytest.raises(ModelError) as caught:
        assess(model(project()), selected(), scope(kind='query', selector={'query': query.data}))
    assert caught.value.reason == {
        'embedded-evaluation': 'verification_scope_evaluation_not_independent',
        'verification-filter': 'query_filter_provider_required',
        'verification-sort': 'query_verification_provider_required'}[attempt]


@pytest.mark.parametrize('wrapper', [False, True])
def test_configuration_is_resolved_before_scope_and_cannot_be_chosen_by_evaluation(wrapper):
    records = project(); records[0]['applicability'] = condition('windows')
    effective = configured(records, 'windows'); supplied = model(records)
    descriptor = (scope(kind='configuration', selector={'base_scope_descriptor': scope().data},
                        configuration_id=ref('CFG')) if wrapper else scope(configuration_id=ref('CFG')))
    data = assess(supplied, selected(requirement_checks(), configuration=effective), descriptor,
                  configuration_id=ref('CFG')).data
    assert data['required_set']['required_checks'] == requirement_checks()
    assert data['required_set']['configuration_hash'] == effective.sha256
    assert data['coverage_status'] == 'ready'
    wrong = assess(supplied, selected(requirement_checks()), descriptor, configuration_id=ref('CFG')).data
    assert wrong['reasons'] == ['evaluation_configuration_mismatch']


def test_scope_and_explicit_configuration_disagreement_is_not_silently_repaired():
    records = project(); configured(records)
    with pytest.raises(ModelError) as caught:
        assess(model(records), selected(), scope(configuration_id=ref('CFG')))
    assert caught.value.reason == 'verification_scope_configuration_mismatch'


def test_conditional_non_subject_scope_seed_does_not_allow_an_unqualified_ready_claim():
    records = project(); document = next(r for r in records if r['artifact_type'] == 'document')
    document['applicability'] = condition('linux')
    # This seed and the requirement are independently selected; no relation is inferred.
    data = assess(model(records), selected(requirement_checks()), scope(ref(), ref('DOC'))).data
    assert data['required_set']['required_checks'] == requirement_checks()
    assert data['required_set']['unresolved_applicability'] == [ref('DOC')]
    assert data['coverage_status'] == 'incomplete'


@pytest.mark.parametrize('policy', ['closed', 'partial'])
def test_excluded_strong_dependency_is_not_downgraded_to_a_boundary(policy):
    records = project(); records[1]['applicability'] = condition('windows'); configured(records)
    with pytest.raises(ModelError) as caught:
        assess(model(records), selected(), scope(policy=policy, configuration_id=ref('CFG')),
               configuration_id=ref('CFG'))
    assert caught.value.reason == 'scope_configuration_dependency' and caught.value.code == 'SRV141'


def test_specification_scope_keeps_native_permanent_control_exclusions():
    records = project(); records.append(record_value('proposal'))
    records[1]['relations'] = [dict(edge(ref('PROP'), 4), type='references')]
    with pytest.raises(ModelError) as caught:
        assess(model(records), selected(), scope(kind='specification'))
    assert caught.value.reason == 'scope_control_dependency' and caught.value.code == 'SRV140'


@pytest.mark.parametrize('mutation', ['omit-record', 'changed-record', 'foreign-project', 'missing-resource',
                                    'changed-resource', 'inventory-hash', 'dependency-hash'])
def test_stale_or_reduced_scope_provider_inventory_is_rejected(mutation):
    supplied = model(project()); bindings = bindings_for(supplied); inventory = bindings.inventory
    records, resources = list(inventory.records), list(inventory.resources)
    config = supplied.configuration
    if mutation == 'omit-record':
        records = [r for r in records if r.identity.id != ref('TEST', '1')]
    if mutation == 'changed-record':
        changed = records[0].data; changed['title'] = 'changed provider'
        records[0] = SourceRelations(artifact_bytes(changed), path=records[0].path)
    if mutation == 'foreign-project':
        value = config.data; value['project_id'] = 'another-project'; config = ProjectConfiguration(value)
    if mutation == 'missing-resource': resources.clear()
    if mutation == 'changed-resource': resources[0] = replace(resources[0], sha256='0' * 64)
    if mutation not in ('inventory-hash', 'dependency-hash'):
        bindings = observe(ScopeSeedInputs(config, records, resources))
    elif mutation == 'inventory-hash': object.__setattr__(inventory, 'fingerprint', '0' * 64)
    else: object.__setattr__(bindings, 'fingerprint', '0' * 64)
    with pytest.raises(ModelError) as caught:
        assess(supplied, selected(requirement_checks()), bindings=bindings)
    assert caught.value.reason in ('verification_scope_inventory_mismatch',
        'verification_scope_resource_binding_mismatch', 'verification_scope_inventory_binding_mismatch',
        'verification_scope_dependency_binding_mismatch')


@pytest.mark.parametrize('provider', ['usage', 'reviews'])
def test_missing_dependency_provider_does_not_mean_no_dependency(provider):
    supplied = model(project()); bindings = bindings_for(supplied)
    uses, reviews = dict(bindings.uses), dict(bindings.current_reviews)
    if provider == 'usage': del uses[artifact_node(ref())]
    else: del reviews['REL-' + '0' * 26]
    incomplete = ClosureBindings(bindings.inventory, uses=uses, current_reviews=reviews)
    with pytest.raises(ModelError) as caught:
        assess(supplied, selected(requirement_checks()), bindings=incomplete)
    assert caught.value.reason == ('closure_usage_observation_missing' if provider == 'usage'
                                   else 'closure_review_observation_missing')


@pytest.mark.parametrize('argument,value', [('scope_descriptor', {}), ('scope_bindings', {}),
                                          ('scope_descriptor', None), ('scope_bindings', None)])
def test_scope_inputs_require_both_native_typed_values(argument, value):
    supplied = model(project()); options = dict(scope_descriptor=scope(), scope_bindings=bindings_for(supplied))
    options[argument] = value
    with pytest.raises(ModelError) as caught:
        resolve_required_checks(supplied, configuration_id=None, **options)
    assert caught.value.reason in ('verification_scope_descriptor_required', 'verification_scope_bindings_required')


def test_scope_results_are_owned_and_need_no_files_or_processes(monkeypatch):
    supplied = model(project()); bindings = bindings_for(supplied); descriptor = scope(); evaluation = selected(requirement_checks())
    def no_read(*args, **kwargs): raise AssertionError('No host lookup is authorized')
    with no_write_attempts(), monkeypatch.context() as patch:
        patch.setattr('builtins.open', no_read); patch.setattr('io.open', no_read)
        result = assess(supplied, evaluation, descriptor, bindings)
    original = result.data; changed = result.data; changed['required_set']['scope_resolution'].clear()
    assert result.data == original
    with pytest.raises(TypeError): bool(result)


@pytest.mark.parametrize('mode', ['core', 'pyz'])
def test_independent_scope_coverage_is_available_in_fresh_core_and_pyz(mode, tmp_path):
    supplied = model(project()); evaluation = selected(requirement_checks()); descriptor = scope()
    expected = assess(supplied, evaluation, descriptor).data
    body = '''import json
from specroad.changes import TargetModel
from specroad.verification import VerificationEvaluation, assess_required_check_coverage
from specroad.model.model_manifest import ProjectReadBinding
from specroad.profiles import ProfileResource, compose_profiles
from specroad.validation import ModelDocument
from specroad.graph.relations import SourceRelations
from specroad.graph.scope_inputs import ScopeResource, ScopeSeedInputs
from specroad.graph.scope_descriptors import ScopeDescriptor
from specroad.graph.closure_inputs import ClosureBindings, artifact_node, resource_node
'''
    body += 'config=' + repr(supplied.configuration_bytes) + '\n'
    body += 'documents=' + repr([(d.path, d.content) for d in supplied.documents]) + '\n'
    body += 'resources=' + repr([(d.path, d.content) for d in supplied.resource_files]) + '\n'
    body += 'core_key=' + repr(supplied.profile.profile_chain[0]) + '\n'
    body += 'evaluation=VerificationEvaluation(' + repr(evaluation.source_bytes) + ')\n'
    body += 'descriptor=ScopeDescriptor(' + repr(descriptor.data) + ')\n'
    body += '''profile=compose_profiles([ProfileResource(raw) for path,raw in resources],core_key=core_key)
owned=TargetModel(config,ProjectReadBinding('sample','/explicit/provider',(1,2)),
 [ModelDocument(path,raw) for path,raw in documents],profile=profile,
 resource_files=[ModelDocument(path,raw) for path,raw in resources])
resources=[ScopeResource('fixture-resource:'+str(i),r.data['kind'],r.data['sha256'],
 r.data.get('version'),active=r.data['kind']=='profile') for i,r in enumerate(owned.resources)]
inventory=ScopeSeedInputs(owned.configuration,[SourceRelations(d.content,path=d.path) for d in owned.documents],resources)
uses={artifact_node(r.identity.id):() for r in inventory.records}
uses.update({resource_node(r.resource_id):() for r in resources})
reviews={r.relation.identity.id:() for r in inventory.references.relations}
bindings=ClosureBindings(inventory,uses=uses,current_reviews=reviews)
print(json.dumps(assess_required_check_coverage(owned,evaluation,configuration_id=None,
 scope_descriptor=descriptor,scope_bindings=bindings).data))
'''
    if mode == 'core': result = run_core(body, tmp_path, capture=True)
    else:
        _, package = build_distribution(tmp_path / 'distribution')
        result = run_python(['-I', '-S', '-B', '-c',
            'import sys;sys.path.insert(0,' + repr(str(package)) + ')\n' + body], tmp_path, capture=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == expected
