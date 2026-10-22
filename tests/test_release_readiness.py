"""Eight gates over real native observations and explicit synthetic host proofs.

Fixtures are not attestations of real human approval or external CI execution.
No verification result, relation status or Task Done outcome is mocked.
"""
from copy import deepcopy
from dataclasses import replace

import pytest

from specroad.graph.scope_descriptors import ScopeDescriptor
from specroad.graph.relations import SourceRelations
from specroad.graph.review_status import RelationReviewStatuses
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.model.errors import ModelError
from specroad.planning import (ReleaseReadinessContext, assess_release_readiness,
    TaskDoneContext, HumanTaskDoneReview, prepare_task_implementation, task_done_read_gate)
from specroad.validation import ModelGate, ModelDocument, ApprovalContext, HumanRequirementReview
from specroad.validation._approval_review import observe_human_review
from specroad.verification import VerificationEvaluation
from specroad.storage.language_registry import bundled_language_registry, registry_binding
from specroad.changes import TargetModel
from specroad.profiles import compose_profiles
from support.domain import approved_value, domain_value
from support.records import record_value, ref
from support.relations import edge
from support.targets import model, SCOPE
from support.closure import observe
from support.read_only import no_write_attempts
from support.model import configuration_value
from support.approval import review_data as requirement_review_data
from test_release_scope import bindings_for
from test_relation_review_status import review
from test_task_implementation import verifier, review_data
from test_verification_evaluation import INPUTS, descriptor
from test_verification_run_selection import observation

NOW = '2026-10-22T00:00:00Z'
RELEASE = ref('REL')
SCOPE_RELEASE = {**SCOPE, 'scope_kind': 'release', 'selector': {'release_id': RELEASE}}
POLICY = {'format_version': '1.0.0', 'blocker_decisions': []}


def release_case():
    values = [approved_value('release', scope_descriptor=SCOPE_RELEASE, readiness_policy=POLICY)]
    keys = []
    for number, kind, prefix in [(1, 'capability', 'CAP'), (2, 'task', 'TASK'),
                                (3, 'requirement', 'REQ')]:
        contract_id, evidence_id = ref('VER', str(number)), ref('EVD', str(number))
        key = {'subject_artifact_id': ref(prefix), 'contract_id': contract_id,
               'test_id': None, 'check_id': 'overall'}
        keys.append(key)
        values.append(approved_value(kind, implementation_status='implemented',
            verification_plan_status='planned', relations=[
                edge('scheduled_for', RELEASE, number=number * 10),
                edge('verified_by', contract_id, number=number * 10 + 1)]))
        values.append(record_value('verification', id=contract_id, maturity='approved',
            configuration_policy='independent',
            subjects=[key['subject_artifact_id']],
            relations=[edge('produces', evidence_id, number=number * 10 + 2)]))
    evaluation = descriptor(required_runs=[{**key, 'run_ids': ['ci:expected']} for key in keys])
    values[5]['relations'].extend([edge('implemented_by', ref('TASK'), number=40),
                                  edge('derived_from', ref('DEC'), number=41)])
    values.append(approved_value('decision'))
    values[0]['readiness_policy'] = {**POLICY, 'verification_evaluation': evaluation.data}
    for number, key in enumerate(keys, 1):
        evidence = observation(values, evaluation, key, token=str(number),
                               run='ci:expected', result='passed')
        evidence['configuration_policy'] = 'independent'
        values.append(evidence)
    index = {v['id']: v for v in values}
    for source in list(values):
        for relation in source['relations']:
            values.append(review({**source, 'relations': [relation]}, index[relation['target']],
                                 number=len(values) + 100))
    return values, evaluation


def native_bindings(supplied):
    inventory = bindings_for(supplied).inventory
    statuses = RelationReviewStatuses(tuple(SourceRelations(d.content) for d in supplied.documents))
    reviews = {r['relation_id']: (() if r['selected_review_id'] is None else
               (r['selected_review_id'],)) for r in statuses.data['relations']}
    return observe(inventory, reviews=reviews)


def context(values, *, evaluation=None, **options):
    registry = bundled_language_registry(); binding = registry_binding(registry)
    original = model(values)
    profile = compose_profiles(original.profile_resources,
        core_key=original.profile.profile_chain[0], language_registry=registry)
    supplied = TargetModel(canonical_json_bytes(configuration_value(language_registry=binding)),
        original.binding, original.documents, profile=profile,
        resource_files=[*original.resource_files, ModelDocument(binding['path'], registry.source_bytes)])
    return ReleaseReadinessContext(supplied, RELEASE, scope_bindings=native_bindings(supplied),
        evaluated_at=NOW, inputs=dict(INPUTS), input_roles={p: 'input' for p in INPUTS},
        evaluation=evaluation, **options)


def services(ctx, *, approved_hashes=None, done_verifier=None, approval_verifier=None):
    """Explicit test-host approval history, plus native currentness/Done checks.

    The independent immutable hash inventory stands for a trusted approval
    history provider; changing its contents or withholding it must block.
    Core still validates all type-specific fields/minimum relations itself.
    """
    supplied = ctx._model
    assert ctx._verification is not None, ctx.data['scope_error']
    expected = frozenset(canonical_json_sha256(a) for a in supplied.artifacts)
    approved = expected if approved_hashes is None else frozenset(approved_hashes)
    resources = canonical_json_sha256(sorted(approved))
    requirement_context = ApprovalContext(ref(), supplied.documents, profile=supplied.profile, mode='stored')
    requirement_review = HumanRequirementReview(requirement_review_data(requirement_context))

    def dependencies(target):
        return target.dependency_result({key: [] for key in target.subjects})

    def approval(target):
        return target.result([{'reason': 'approval_history_binding_missing', 'artifact_id': key,
                               'severity': 'error'} for key in target.subjects
                              if canonical_json_sha256(target.artifact(key)) not in approved])

    def evidence(target):
        checked = {row['id']: row for row in supplied.artifacts}
        issues = []
        for key in target.subjects:
            if canonical_json_sha256(target.artifact(key)) != canonical_json_sha256(checked[key]):
                issues.append({'reason': 'evidence_source_changed', 'artifact_id': key, 'severity': 'error'})
        # Native aggregation, not a stored result label, supplies freshness.
        for subject in ctx._verification.data['aggregation']['subjects']:
            for check in subject['checks']:
                for run in check['active_runs']:
                    for ev in run['evidence']:
                        if ev['evidence_id'] in target.subjects and ev['freshness'] != 'current':
                            issues.append({'reason': 'evidence_context_not_current',
                                'artifact_id': ev['evidence_id'], 'severity': 'error'})
        return target.result(issues)

    def relation_reviews(target):
        rows = RelationReviewStatuses(tuple(SourceRelations(canonical_json_bytes(target.artifact(key)))
            for key in target.all_ids)).data['relations']
        current = {r['selected_review_id'] for r in rows if r['status'] == 'current'}
        issues = [{'reason': 'relation_review_not_current', 'artifact_id': key,
                   'severity': 'error'} for key in target.subjects if key != ref() and key not in current]
        if ref() in target.subjects:
            actual = ApprovalContext(ref(), target.documents, profile=supplied.profile, mode='stored')
            review_issues, _, _, _ = observe_human_review(actual, requirement_review,
                verifier() if approval_verifier is None else approval_verifier)
            issues.extend({'reason': item['reason'], 'artifact_id': ref(), 'severity': 'error'}
                          for item in review_issues)
        return target.result(issues)

    preparations = []
    for value in supplied.artifacts:
        if value['artifact_type'] != 'task':
            continue
        done = TaskDoneContext(supplied, value['id'], scope_descriptor=ScopeDescriptor(SCOPE))
        raw = review_data(done); raw['criteria'] = [True] * len(value['done_criteria'])
        preparations.append(prepare_task_implementation(done, review=HumanTaskDoneReview(raw),
            verifier=verifier() if done_verifier is None else done_verifier))
    return [ModelGate('lifecycle', 'fixture-history-v1', dependencies, approval, resources),
        ModelGate('evidence_currentness', 'native-verification-fixture-v1', dependencies, evidence,
                  ctx._verification.sha256),
        ModelGate('review_currentness', 'native-relation-fixture-v1', dependencies, relation_reviews,
                  supplied._sources_sha256), task_done_read_gate(supplied, preparations)]


def gates(report):
    return {row['gate_id']: row for row in report.data['gates']}


def findings(report):
    return {f['reason'] for row in report.data['gates'] for f in row['findings']}


def test_complete_release_with_native_capability_task_done_and_evidence_is_ready():
    values, _ = release_case(); before = deepcopy(values); ctx = context(values)
    supplied = services(ctx)
    with no_write_attempts(): result = assess_release_readiness(ctx, gates=supplied)
    data = result.data
    assert data['ready'], [f for row in data['gates'] for f in row['findings']]
    assert data['status'] == 'ready' and result.exit_code == 0 and not data['provisional']
    assert list(gates(result)) == ['scope', 'approval', 'implementation', 'verification',
                                  'coverage', 'risks', 'issues', 'relations']
    assert all(row['status'] == ('not_applicable' if key in ('risks', 'issues') else 'passed')
               for key, row in gates(result).items())
    assert gates(result)['verification']['subject_ids'] == [ref('CAP'), ref(), ref('TASK')]
    assert data['input_sha256'] == canonical_json_sha256(data['binding'])
    assert not any(data[key] for key in ('project_files_verified', 'release_baseline_authorized',
                                        'write_authorized', 'approval_granted'))
    assert values == before
    assert assess_release_readiness(ctx, gates=list(reversed(supplied))).data == data
    with pytest.raises(TypeError): bool(result)


@pytest.mark.parametrize('gate', ['lifecycle', 'task_done', 'evidence_currentness', 'review_currentness'])
def test_missing_provider_blocks_even_with_all_success_labels(gate):
    values, _ = release_case(); ctx = context(values)
    result = assess_release_readiness(ctx, gates=[g for g in services(ctx) if g.gate_id != gate])
    assert not result.data['ready'] and result.data['status'] == 'incomplete'
    assert 'validation_required_gate_unavailable' in findings(result)


def test_stored_approved_labels_do_not_replace_bound_history_observations():
    values, _ = release_case(); ctx = context(values)
    result = assess_release_readiness(ctx, gates=services(ctx, approved_hashes=[]))
    assert not result.data['ready'] and gates(result)['approval']['status'] == 'failed'
    assert 'approval_history_binding_missing' in findings(result)


@pytest.mark.parametrize('kind,status,expected', [
    ('risk', 'open', 'failed'), ('risk', 'in_progress', 'failed'),
    ('risk', 'accepted', 'incomplete'), ('risk', 'legacy_done', 'incomplete'),
    ('issue', 'open', 'failed'), ('issue', 'in_progress', 'failed'),
    ('issue', 'resolved', 'incomplete'), ('issue', 'legacy_done', 'incomplete')])
def test_blockers_never_disappear_through_labels_or_terminal_words(kind, status, expected):
    values, _ = release_case()
    make = domain_value if kind == 'risk' else record_value
    values.append(make(kind, maturity='approved', **{kind + '_status': status},
        **({'permanent_status_reason': 'Keep visible', 'resolution_criteria': ['Investigate']} if kind == 'issue' else {})))
    # Include through an explicit required dependency, independently of policy.
    values[2]['relations'].append(edge('references', values[-1]['id'], number=51))
    ctx = context(values); result = assess_release_readiness(ctx, gates=services(ctx))
    assert not result.data['ready'] and gates(result)[kind + 's']['status'] == expected


@pytest.mark.parametrize('change', ['failure', 'stale', 'missing_subject', 'missing_configuration', 'missing_run'])
def test_native_evidence_failures_block_verification_and_coverage(change):
    values, _ = release_case()
    value = next(v for v in values if v['artifact_type'] == 'evidence')
    if change == 'failure': value['result'] = 'failed'
    elif change == 'stale': value['subjects'][0]['verification_context_sha256'] = 'f' * 64
    elif change == 'missing_subject': value['subjects'] = value['subjects'][1:]
    elif change == 'missing_configuration': del value['configuration_hash']
    elif change == 'missing_run': value['run_context']['run_id'] = 'ci:unexpected'
    ctx = context(values); result = assess_release_readiness(ctx, gates=services(ctx))
    assert not result.data['ready']
    assert gates(result)['verification']['status'] in ('failed', 'incomplete')
    assert gates(result)['coverage']['status'] in ('failed', 'incomplete')


def test_required_external_component_and_its_review_remain_release_obligations():
    values, _ = release_case(); component = domain_value('component', maturity='draft')
    values[1]['relations'].append(edge('depends_on', component['id'], number=55)); values.append(component)
    ctx = context(values); result = assess_release_readiness(ctx, gates=services(ctx))
    assert component['id'] in result.data['binding']['release_scope']['external_required_artifact_ids']
    assert 'artifact_not_approved' in findings(result) and 'artifact_not_implemented' in findings(result)
    assert 'relation_unreviewed' in findings(result) and not result.data['ready']


def test_missing_required_artifact_cannot_make_empty_gates_not_applicable():
    values, _ = release_case(); values[0]['relations'].append(edge('depends_on', ref('COMP'), number=56))
    ctx = ReleaseReadinessContext(model(values), RELEASE, scope_bindings=None, evaluated_at=NOW)
    result = assess_release_readiness(ctx)
    assert not result.data['ready']
    assert all(row['status'] != 'not_applicable' for row in result.data['gates'])


@pytest.mark.parametrize('policy', [{}, {'old_allow': True}])
def test_legacy_policy_is_read_only_incomplete(policy):
    values, evaluation = release_case(); values[0]['readiness_policy'] = policy
    ctx = context(values, evaluation=evaluation); result = assess_release_readiness(ctx, gates=services(ctx))
    assert not result.data['ready'] and 'legacy_readiness_policy_unsupported' in findings(result)
    assert values[0]['readiness_policy'] == policy


@pytest.mark.parametrize('policy', [dict(POLICY, allow_open=True), dict(POLICY, format_version='2.0.0'),
                                   dict(POLICY, verification_evaluation=None)])
def test_closed_policy_rejects_extensions_unknown_versions_and_null_selection(policy):
    values, _ = release_case(); values[0]['readiness_policy'] = policy
    with pytest.raises(ModelError): context(values)


def test_stored_selection_conflict_keeps_native_code_six_and_provisional_is_explicit():
    values, selected = release_case(); alternate = selected.data
    alternate['required_runs'][0]['run_ids'] = ['ci:different']
    with pytest.raises(ModelError) as error:
        context(values, evaluation=VerificationEvaluation(canonical_json_bytes(alternate)))
    assert error.value.exit_code == 6
    values[0]['readiness_policy'] = POLICY
    ctx = context(values, evaluation=selected)
    assert assess_release_readiness(ctx, gates=services(ctx)).data['provisional']


def test_replaying_a_provider_observation_under_a_new_evaluation_time_is_incomplete():
    values, _ = release_case(); original = context(values); observed = []
    provided = services(original); lifecycle = provided[0]
    def capture(target):
        result = lifecycle.check(target); observed.append(result); return result
    provided[0] = replace(lifecycle, check=capture)
    assert assess_release_readiness(original, gates=provided).data['ready']
    other = ReleaseReadinessContext(original._model, RELEASE,
        scope_bindings=native_bindings(original._model), evaluated_at='2026-10-22T01:00:00Z',
        inputs=dict(INPUTS), input_roles={p: 'input' for p in INPUTS})
    provided = services(other); provided[0] = replace(provided[0], check=lambda target: observed[0])
    result = assess_release_readiness(other, gates=provided)
    assert not result.data['ready'] and 'validation_gate_result_unbound_or_incomplete' in findings(result)


def test_native_requirement_review_revocation_blocks_an_approved_release():
    values, _ = release_case(); ctx = context(values)
    result = assess_release_readiness(ctx, gates=services(ctx, approval_verifier=verifier(current=False)))
    assert not result.data['ready']
    assert 'approval_review_not_authenticated_or_current' in findings(result)


def test_done_review_is_rechecked_on_read_after_host_revocation():
    from specroad.validation import ReviewVerifier, ReviewVerification
    current = [True]
    service = ReviewVerifier('revocable-fixture', '1', lambda ctx, rev:
        ReviewVerification(ctx.input_sha256, rev.sha256, True, current[0]))
    values, _ = release_case(); ctx = context(values); provided = services(ctx, done_verifier=service)
    assert assess_release_readiness(ctx, gates=provided).data['ready']
    current[0] = False
    result = assess_release_readiness(ctx, gates=provided)
    assert not result.data['ready']
    assert 'task_done_review_not_authenticated_or_current' in findings(result)


@pytest.mark.parametrize('change', ['delete', 'rejected', 'context_changed'])
def test_native_relation_review_must_stay_exactly_current(change):
    values, _ = release_case()
    record = next(v for v in values if v['artifact_type'] == 'relation_review')
    if change == 'delete': values.remove(record)
    elif change == 'rejected': record['decision'] = 'rejected'
    else: record['source_context_sha256'] = 'f' * 64
    ctx = context(values); result = assess_release_readiness(ctx, gates=services(ctx))
    assert not result.data['ready'] and gates(result)['relations']['status'] == 'failed'
    assert any(reason in findings(result) for reason in ('relation_unreviewed', 'relation_suspect', 'relation_invalid'))


def test_scope_bindings_are_mandatory_and_no_empty_gate_is_waived_without_them():
    values, _ = release_case()
    ctx = ReleaseReadinessContext(model(values), RELEASE, scope_bindings=None, evaluated_at=NOW)
    result = assess_release_readiness(ctx)
    assert not result.data['ready'] and gates(result)['scope']['status'] == 'incomplete'
    assert 'verification_scope_bindings_required' in findings(result)
    assert all(row['status'] != 'not_applicable' for row in result.data['gates'])


def test_changed_task_cannot_reuse_previous_native_done_gate():
    values, _ = release_case(); old = context(values)
    old_done = next(g for g in services(old) if g.gate_id == 'task_done')
    next(v for v in values if v['artifact_type'] == 'task')['revision'] += 1
    current = context(values)
    supplied = [old_done if g.gate_id == 'task_done' else g for g in services(current)]
    result = assess_release_readiness(current, gates=supplied)
    assert not result.data['ready'] and 'task_done_target_changed' in findings(result)


def test_unknown_applicability_never_becomes_an_empty_success():
    from test_verification_required_checks import condition
    values, _ = release_case(); values[1]['applicability'] = condition(True)
    ctx = context(values); result = assess_release_readiness(ctx, gates=services(ctx))
    assert not result.data['ready'] and gates(result)['scope']['status'] == 'incomplete'
    assert 'scope_applicability_unresolved' in findings(result)


@pytest.mark.parametrize('mode', ['core', 'pyz'])
def test_readiness_and_new_context_types_are_available_in_isolated_runtime(tmp_path, mode):
    import json
    from support.portable import build_distribution
    from support.processes import run_core, run_python
    from specroad.verification import VerificationContext
    from specroad.storage.domain_artifact import DomainArtifact
    release = approved_value('release', scope_descriptor=SCOPE_RELEASE, readiness_policy=POLICY)
    supplied = model([release])
    ctx = ReleaseReadinessContext(supplied, RELEASE, scope_bindings=bindings_for(supplied), evaluated_at=NOW)
    expected = {'readiness': assess_release_readiness(ctx).data,
        'contexts': [VerificationContext(DomainArtifact(canonical_json_bytes(domain_value(kind))),
            configuration=None).context_sha256 for kind in ('capability', 'task')]}
    body = '''import json
from specroad.planning import ReleaseReadinessContext, assess_release_readiness
from specroad.changes import TargetModel
from specroad.graph.closure_inputs import ClosureBindings, artifact_node, resource_node
from specroad.graph.relations import SourceRelations
from specroad.graph.scope_inputs import ScopeResource, ScopeSeedInputs
from specroad.model.model_manifest import ProjectReadBinding
from specroad.profiles import ProfileResource, compose_profiles
from specroad.validation import ModelDocument
from specroad.storage.domain_artifact import DomainArtifact
from specroad.verification import VerificationContext
'''
    body += 'configuration=' + repr(supplied.configuration_bytes) + '\n'
    body += 'documents=' + repr([(d.path, d.content) for d in supplied.documents]) + '\n'
    body += 'resources=' + repr([(d.path, d.content) for d in supplied.resource_files]) + '\n'
    body += 'subjects=' + repr([canonical_json_bytes(domain_value(k)) for k in ('capability', 'task')]) + '\n'
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
bound=ClosureBindings(inputs,uses=uses,current_reviews={})
'''
    body += 'ctx=ReleaseReadinessContext(supplied,' + repr(RELEASE) + ',scope_bindings=bound,evaluated_at=' + repr(NOW) + ')\n'
    body += "print(json.dumps({'readiness':assess_release_readiness(ctx).data,'contexts':[VerificationContext(DomainArtifact(b),configuration=None).context_sha256 for b in subjects]}))\n"
    if mode == 'core': result = run_core(body, tmp_path, capture=True)
    else:
        _, package = build_distribution(tmp_path / 'distribution')
        result = run_python(['-I', '-S', '-B', '-c',
            'import sys;sys.path.insert(0,' + repr(str(package)) + ')\n' + body], tmp_path, capture=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == expected
