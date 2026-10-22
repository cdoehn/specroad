"""Native Release blocker decisions, current human proofs and exact failures.

External authentication is an explicit synthetic fixture, never a real approval.
All readiness, scope, review binding and verification decisions use native code.
"""
from copy import deepcopy
from dataclasses import replace
import json

import pytest

from specroad.changes import TargetModel
from specroad.configurations import resolve_configuration
from specroad.graph.relations import SourceRelations
from specroad.graph.scope_descriptors import ScopeDescriptor
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.model.errors import ModelError
from specroad.planning import (ReleaseReadinessContext, assess_release_readiness,
    HumanReleaseBlockerReview, ReleaseBlockerReviewContext)
from specroad.validation import ReviewVerifier, ReviewVerification
from support.domain import approved_value, domain_value
from support.records import record_value, ref
from support.relations import edge
from support.read_only import no_write_attempts
from support.targets import model
from test_relation_review_status import review as relation_review
from test_release_readiness import (release_case, context, services, native_bindings, gates,
                                   findings, RELEASE, SCOPE_RELEASE, NOW, POLICY)
from test_verification_evaluation import INPUTS, descriptor

HUMAN = {'actor_type': 'human', 'actor_id': 'explicit-test-reviewer'}


def refresh_reviews(values):
    values = [v for v in values if v['artifact_type'] != 'relation_review']
    index = {v['id']: v for v in values}
    for source in list(values):
        for relation in source['relations']:
            if relation['target'] in index:
                values.append(relation_review({**source, 'relations': [relation]},
                    index[relation['target']], number=300 + len(values)))
    return values


def blocker_case(kind='risk', status='accepted', *, criteria=None):
    values, _ = release_case()
    factory = approved_value if kind == 'risk' else record_value
    extra = ({'acceptance_rationale': 'Explicit residual risk decision is required.'} if kind == 'risk' else
             {'resolution_criteria': ['Investigated', 'Corrected'] if criteria is None else criteria})
    subject = factory(kind, maturity='approved', **{kind + '_status': status}, **extra)
    values.append(subject)
    requirement = next(v for v in values if v['artifact_type'] == ('requirement' if kind == 'risk' else 'verification'))
    requirement['relations'].append(edge('mitigates' if kind == 'risk' else 'references', subject['id'], number=71))
    decision = {'subject_id': subject['id'], 'subject_sha256': canonical_json_sha256(subject),
        'decision': ('issue_resolved' if kind == 'issue' else
                     'risk_accepted' if status == 'accepted' else 'risk_eliminated'),
        'reason': 'Explicit tested decision; no inferred acceptance.',
        'scope_descriptor': deepcopy(SCOPE_RELEASE), 'configuration_sha256': None,
        'human_review_id': 'human:blocker:' + kind}
    values[0]['readiness_policy']['blocker_decisions'] = [decision]
    return refresh_reviews(values), decision


def passive(decision, *, criteria=None, **changes):
    if criteria is None:
        criteria = {'risk_eliminated': True} if decision['decision'] == 'risk_eliminated' else (
            {'residual_risk_accepted': True} if decision['decision'] == 'risk_accepted' else
            {'resolution_criteria': [True, True]})
    return HumanReleaseBlockerReview({'review_id': decision['human_review_id'],
        'subject_id': decision['subject_id'], 'decision_sha256': canonical_json_sha256({
            'format_version': 'release-blocker-decision-v1', 'release_id': RELEASE, 'decision': decision}),
        'reviewer': HUMAN, 'reviewed_at': NOW, 'decision': 'confirmed', 'criteria': criteria, **changes})


def trusted(**changes):
    return ReviewVerifier('synthetic-release-review', '1',
        lambda c, r: ReviewVerification(c.input_sha256, r.sha256,
                                       changes.get('human', True), changes.get('current', True)))


def assess(values, reviews=(), verifier=None, **options):
    ctx = context(values)
    return assess_release_readiness(ctx, gates=services(ctx), blocker_reviews=list(reviews),
                                   blocker_verifier=verifier, **options)


@pytest.mark.parametrize('kind,status,criteria', [
    ('risk', 'mitigated', None), ('risk', 'closed', None), ('risk', 'accepted', None),
    ('issue', 'resolved', ['Investigated', 'Corrected']), ('issue', 'closed', 'Verified resolution')])
def test_only_exact_confirmed_completion_can_remove_a_release_blocker(kind, status, criteria):
    values, decision = blocker_case(kind, status, criteria=criteria)
    criteria_value = None if kind == 'risk' else {'resolution_criteria': [True] * (1 if type(criteria) is str else len(criteria))}
    r = passive(decision, criteria=criteria_value); before = deepcopy(values)
    with no_write_attempts(): result = assess(values, [r], trusted())
    data = result.data
    assert data['ready'], [(g['gate_id'], g['findings']) for g in data['gates'] if g['findings']]
    assert data['status'] == 'ready' and result.exit_code == 0 and not data['provisional']
    contribution = gates(result)[kind + 's']['evidence_bindings'][0]
    assert contribution['review_verified'] and contribution['status'] == 'passed'
    assert contribution['decision_sha256'] == r.data['decision_sha256']
    assert contribution['input_sha256'] == contribution['verification']['input_sha256'] == data['input_sha256']
    assert values == before and not data['release_baseline_authorized'] and not data['write_authorized']


@pytest.mark.parametrize('kind', ['risk', 'issue'])
@pytest.mark.parametrize('status', ['open', 'in_progress'])
def test_open_blockers_cannot_be_excused_by_reason_probability_or_a_review(kind, status):
    values, decision = blocker_case(kind, status)
    if kind == 'risk':
        subject = next(v for v in values if v['id'] == decision['subject_id']); subject['probability'] = 0
        subject['impact'] = 'low'; decision['subject_sha256'] = canonical_json_sha256(subject)
    else:
        next(v for v in values if v['id'] == decision['subject_id'])['permanent_status_reason'] = 'Accepted work item'
    result = assess(values, [passive(decision)], trusted())
    assert not result.data['ready'] and gates(result)[kind + 's']['status'] == 'failed'
    assert kind + '_status_open' in findings(result)


@pytest.mark.parametrize('field,value,reason', [
    ('subject_sha256', '0' * 64, 'blocker_decision_subject_changed'),
    ('scope_descriptor', {**SCOPE_RELEASE, 'boundary_policy': 'partial'}, 'blocker_decision_scope_mismatch'),
    ('configuration_sha256', '1' * 64, 'blocker_decision_configuration_mismatch'),
    ('decision', 'risk_eliminated', 'blocker_decision_status_mismatch')])
def test_decision_bindings_are_exact_not_wildcards(field, value, reason):
    values, d = blocker_case(); d[field] = value
    result = assess(values, [passive(d)], trusted())
    assert reason in findings(result) and gates(result)['risks']['status'] == 'incomplete'
    assert not result.data['ready']


@pytest.mark.parametrize('change', ['status', 'revision', 'description', 'scope', 'review_id', 'reason'])
def test_old_review_is_never_rebound_after_subject_or_policy_changes(change):
    values, d = blocker_case(); r = passive(d)
    subject = next(v for v in values if v['id'] == d['subject_id'])
    if change == 'status': subject['risk_status'] = 'closed'
    elif change == 'revision': subject['revision'] += 1
    elif change == 'description': subject['description'] += ' changed'
    elif change == 'scope': d['scope_descriptor']['configuration_id'] = ref('CFG')
    elif change == 'review_id': d['human_review_id'] = 'human:new-decision'
    else: d['reason'] = 'A different decision'
    result = assess(values, [r], trusted())
    assert not result.data['ready'] and gates(result)['risks']['status'] == 'incomplete'
    assert not gates(result)['risks']['evidence_bindings'][0]['review_verified']


@pytest.mark.parametrize('case,reason,state', [
    ('missing_review', 'blocker_review_missing', 'incomplete'),
    ('missing_verifier', 'blocker_review_verifier_unavailable', 'incomplete'),
    ('wrong_subject', 'blocker_review_binding_mismatch', 'incomplete'),
    ('wrong_hash', 'blocker_review_binding_mismatch', 'incomplete'),
    ('ai', 'blocker_review_nonhuman', 'failed'),
    ('rejected', 'blocker_review_rejected', 'failed'),
    ('future', 'blocker_review_in_future', 'incomplete'),
    ('revoked', 'blocker_review_not_authenticated_or_current', 'incomplete'),
    ('unauthenticated', 'blocker_review_not_authenticated_or_current', 'incomplete'),
    ('error', 'blocker_review_verification_failed', 'incomplete'),
    ('unbound', 'blocker_review_verifier_unbound', 'incomplete'),
    ('untyped', 'blocker_review_verifier_unbound', 'incomplete'),
    ('forged_boolean', 'blocker_review_verification_failed', 'incomplete')])
def test_invalid_or_unavailable_human_proofs_fail_closed(case, reason, state):
    values, d = blocker_case(); r = passive(d); v = trusted()
    if case in ('wrong_subject', 'wrong_hash', 'ai', 'rejected', 'future'):
        key, value = {'wrong_subject': ('subject_id', ref('RISK', '1')),
            'wrong_hash': ('decision_sha256', '0' * 64), 'ai': ('reviewer', {'actor_type': 'ai', 'actor_id': 'agent'}),
            'rejected': ('decision', 'rejected'), 'future': ('reviewed_at', '2026-10-22T00:00:00.000000001Z')}[case]
        r = HumanReleaseBlockerReview({**r.data, key: value})
    if case == 'missing_verifier': v = None
    elif case == 'revoked': v = trusted(current=False)
    elif case == 'unauthenticated': v = trusted(human=False)
    elif case in ('error', 'unbound', 'untyped', 'forged_boolean'):
        def check(c, r):
            if case == 'error': raise RuntimeError('private-host-detail')
            if case == 'untyped': return True
            proof = ReviewVerification('0' * 64 if case == 'unbound' else c.input_sha256, r.sha256, True, True)
            if case == 'forged_boolean': object.__setattr__(proof, 'current', 1)
            return proof
        v = ReviewVerifier('synthetic-release-review', '1', check)
    result = assess(values, [] if case == 'missing_review' else [r], v)
    assert not result.data['ready'] and gates(result)['risks']['status'] == state
    assert reason in findings(result)
    assert 'private-host-detail' not in json.dumps(result.data)


@pytest.mark.parametrize('kind,criteria,state', [
    ('risk', {}, 'incomplete'), ('risk', {'residual_risk_accepted': False}, 'failed'),
    ('risk', {'residual_risk_accepted': 1}, 'incomplete'),
    ('risk', {'residual_risk_accepted': True, 'other': True}, 'incomplete'),
    ('issue', {'resolution_criteria': []}, 'incomplete'),
    ('issue', {'resolution_criteria': [True]}, 'incomplete'),
    ('issue', {'resolution_criteria': [True, False]}, 'failed'),
    ('issue', {'resolution_criteria': [True, True, True]}, 'incomplete'),
    ('issue', {'resolution_criteria': [True, 1]}, 'incomplete')])
def test_completion_criteria_are_exact_and_boolean(kind, criteria, state):
    values, d = blocker_case(kind, 'resolved' if kind == 'issue' else 'accepted')
    result = assess(values, [passive(d, criteria=criteria)], trusted())
    assert not result.data['ready'] and gates(result)[kind + 's']['status'] == state


def test_issue_permanent_reason_does_not_substitute_for_resolution_criteria():
    values, d = blocker_case('issue', 'closed')
    subject = next(v for v in values if v['id'] == d['subject_id'])
    del subject['resolution_criteria']; subject['permanent_status_reason'] = 'Long term work'
    d['subject_sha256'] = canonical_json_sha256(subject)
    result = assess(values, [passive(d)], trusted())
    assert not result.data['ready'] and 'issue_resolution_criteria_missing' in findings(result)


def test_foreign_decision_subject_cannot_extend_the_native_release_scope():
    values, d = blocker_case(); foreign = domain_value('risk', id=ref('RISK', '1'))
    values.append(foreign); d['subject_id'] = foreign['id']; d['subject_sha256'] = canonical_json_sha256(foreign)
    result = assess(values, [passive(d)], trusted())
    assert foreign['id'] not in result.data['binding']['release_scope']['artifact_ids']
    assert 'blocker_decision_subject_outside_scope' in findings(result) and not result.data['ready']


@pytest.mark.parametrize('target', ['context', 'review', 'verifier'])
def test_mutating_callback_inputs_is_not_a_valid_observation(target):
    values, d = blocker_case(); r = passive(d)
    def check(c, review):
        proof = ReviewVerification(c.input_sha256, review.sha256, True, True)
        if target == 'verifier': object.__setattr__(v, 'version', 'changed')
        else: object.__setattr__(c if target == 'context' else review, '_encoded', b'{}')
        return proof
    v = ReviewVerifier('host', '1', check)
    result = assess(values, [r], v)
    assert not result.data['ready'] and 'blocker_review_inputs_changed' in findings(result)
    assert r.data['decision'] == 'confirmed'


def test_every_read_rechecks_current_effect_and_replay_of_old_proof_fails():
    values, d = blocker_case(); r = passive(d); observations = []
    def check(c, r):
        proof = ReviewVerification(c.input_sha256, r.sha256, True, True); observations.append(proof); return proof
    v = ReviewVerifier('host', '1', check)
    ctx = context(values); native = services(ctx)
    first = assess_release_readiness(ctx, gates=native, blocker_reviews=[r], blocker_verifier=v)
    assert first.data['ready'] and len(observations) == 1
    revoked = replace(v, check=lambda c, r: ReviewVerification(c.input_sha256, r.sha256, True, False))
    assert not assess_release_readiness(ctx, gates=native, blocker_reviews=[r], blocker_verifier=revoked).data['ready']
    changed = ReleaseReadinessContext(ctx._model, RELEASE, scope_bindings=native_bindings(ctx._model),
        evaluated_at='2026-10-22T00:00:00.000000001Z', inputs=dict(INPUTS), input_roles={p: 'input' for p in INPUTS})
    # The previous observation is bound to the original full Readiness input.
    replay = replace(v, check=lambda c, r: observations[0])
    result = assess_release_readiness(changed, gates=services(changed), blocker_reviews=[r], blocker_verifier=replay)
    assert not result.data['ready'] and 'blocker_review_verifier_unbound' in findings(result)


@pytest.mark.parametrize('policy', [{}, {'blocker_decisions': 'legacy free text'}, {'blocker_decisions': [None]}])
def test_legacy_policy_bytes_remain_readable_without_interpreting_unknown_decisions(policy):
    values, selected = release_case(); values[0]['readiness_policy'] = policy
    ctx = context(values, evaluation=selected); before = deepcopy(values)
    result = assess_release_readiness(ctx, gates=services(ctx))
    assert not result.data['ready'] and 'legacy_readiness_policy_unsupported' in findings(result)
    assert values == before


@pytest.mark.parametrize('broken', ['extra', 'version', 'duplicate_subject', 'missing', 'scope', 'hash'])
def test_malformed_versioned_policy_raises_native_model_error(broken):
    values, d = blocker_case(); policy = values[0]['readiness_policy']
    if broken == 'extra': policy['allow_open'] = True
    elif broken == 'version': policy['format_version'] = '2.0.0'
    elif broken == 'duplicate_subject': policy['blocker_decisions'].append(deepcopy(d))
    elif broken == 'missing': del d['reason']
    elif broken == 'scope': d['scope_descriptor'] = {}
    else: d['subject_sha256'] = 'bad'
    with no_write_attempts(), pytest.raises(ModelError) as caught: context(values)
    assert type(caught.value) is ModelError and caught.value.reason


def configured_case():
    scope = {**SCOPE_RELEASE, 'configuration_id': ref('CFG')}
    parent = record_value('configuration', id=ref('CFG', '1'), name='Parent')
    child = record_value('configuration', name='Child', parent=parent['id'])
    subject = approved_value('risk', risk_status='accepted', acceptance_rationale='Explicit human decision')
    values = [approved_value('release', scope_descriptor=scope, readiness_policy=deepcopy(POLICY),
                  relations=[edge('derived_from', ref('DEC'), number=80)]),
        approved_value('decision', relations=[edge('mitigates', subject['id'], number=81)]),
        subject, parent, child]
    configuration = resolve_configuration([SourceRelations(canonical_json_bytes(v)) for v in values], child['id'])
    d = {'subject_id': subject['id'], 'subject_sha256': canonical_json_sha256(subject),
         'decision': 'risk_accepted', 'reason': 'Bound current human acceptance',
         'scope_descriptor': scope, 'configuration_sha256': configuration.sha256,
         'human_review_id': 'human:configured'}
    # This scope has no Verification subjects. It stays provisional without
    # inventing an empty (invalid) evaluation descriptor.
    values[0]['readiness_policy'] = {**POLICY, 'blocker_decisions': [d]}
    return refresh_reviews(values), d


def minimal_services(ctx):
    from specroad.validation import ModelGate
    from specroad.graph.review_status import RelationReviewStatuses
    records = {v['id']: canonical_json_sha256(v) for v in ctx._model.artifacts}
    def deps(c): return c.dependency_result({key: [] for key in c.subjects})
    def history(c):
        return c.result([{'reason': 'fixture_history_changed', 'severity': 'error'}
                         for key in c.subjects if canonical_json_sha256(c.artifact(key)) != records[key]])
    def review_check(c):
        rows = RelationReviewStatuses(tuple(SourceRelations(d.content) for d in c.documents)).data['relations']
        current = {r['selected_review_id'] for r in rows if r['status'] == 'current'}
        return c.result([{'reason': 'review_not_current', 'severity': 'error'} for key in c.subjects if key not in current])
    return [ModelGate('lifecycle', 'explicit-fixture-history', deps, history, canonical_json_sha256(records)),
            ModelGate('review_currentness', 'native-relation-fixture', deps, review_check, ctx._model._sources_sha256)]


def test_configured_release_completion_binds_native_parent_manifest():
    values, d = configured_case(); ctx = context(values, configuration_id=ref('CFG'))
    result = assess_release_readiness(ctx, gates=minimal_services(ctx),
        blocker_reviews=[passive(d)], blocker_verifier=trusted())
    assert result.data['ready'], [(g['gate_id'], g['findings']) for g in result.data['gates'] if g['findings']]
    assert result.data['binding']['configuration_sha256'] == d['configuration_sha256']
    assert result.data['provisional'] and not result.data['release_baseline_authorized']
    assert gates(result)['verification']['status'] == gates(result)['implementation']['status'] == 'not_applicable'


@pytest.mark.parametrize('changed', ['parent', 'child', 'null'])
def test_changed_effective_configuration_cannot_inherit_an_old_acceptance(changed):
    values, d = configured_case(); r = passive(d)
    if changed == 'null': d['configuration_sha256'] = None
    else:
        identity = ref('CFG', '1') if changed == 'parent' else ref('CFG')
        next(v for v in values if v['id'] == identity)['name'] += ' changed'
    ctx = context(refresh_reviews(values), configuration_id=ref('CFG'))
    result = assess_release_readiness(ctx, gates=minimal_services(ctx), blocker_reviews=[r], blocker_verifier=trusted())
    assert not result.data['ready'] and 'blocker_decision_configuration_mismatch' in findings(result)


def test_risk_acceptance_does_not_hide_other_blockers_or_failed_verification():
    values, d = blocker_case()
    issue = record_value('issue', maturity='approved', resolution_criteria='Fix issue', issue_status='open')
    values.append(issue)
    next(v for v in values if v['artifact_type'] == 'verification')['relations'].append(edge('references', issue['id'], number=82))
    next(v for v in values if v['artifact_type'] == 'evidence')['result'] = 'failed'
    result = assess(refresh_reviews(values), [passive(d)], trusted())
    rows = gates(result)
    assert rows['risks']['status'] == 'passed'
    assert rows['issues']['status'] == rows['verification']['status'] == rows['coverage']['status'] == 'failed'
    assert result.data['status'] == 'blocked' and not result.data['ready']
    assert {'issue_status_open', 'verification_failed', 'evidence_result_failed'} <= findings(result)


@pytest.mark.parametrize('status', ['running', 'not_planned'])
def test_verification_plan_status_does_not_disappear_behind_passing_evidence(status):
    values, _ = release_case()
    next(v for v in values if v['artifact_type'] == 'capability')['verification_plan_status'] = status
    ctx = context(refresh_reviews(values)); result = assess_release_readiness(ctx, gates=services(ctx))
    assert gates(result)['verification']['status'] == 'incomplete' and not result.data['ready']
    assert 'verification_' + ('running' if status == 'running' else 'not_evaluated') in findings(result)


@pytest.mark.parametrize('relation_status', ['unreviewed', 'stale', 'rejected'])
def test_noncurrent_required_relations_remain_failed(relation_status):
    values, _ = release_case()
    first = next(v for v in values if v['artifact_type'] == 'relation_review')
    if relation_status == 'unreviewed': values.remove(first)
    elif relation_status == 'stale': first['source_context_sha256'] = '0' * 64
    else: first['decision'] = 'rejected'
    ctx = context(values); result = assess_release_readiness(ctx, gates=services(ctx))
    assert not result.data['ready'] and gates(result)['relations']['status'] == 'failed'
    native_status = {'unreviewed': 'unreviewed', 'stale': 'suspect', 'rejected': 'invalid'}[relation_status]
    assert 'relation_' + native_status in findings(result)


@pytest.mark.parametrize('case', ['missing', 'stale'])
def test_coverage_distinguishes_missing_evidence_and_stale_evidence(case):
    values, _ = release_case()
    first = next(v for v in values if v['artifact_type'] == 'evidence')
    if case == 'missing':
        values.remove(first)
        for v in values: v['relations'] = [r for r in v['relations'] if r['target'] != first['id']]
    else: first['subjects'][0]['verification_context_sha256'] = '0' * 64
    ctx = context(refresh_reviews(values)); result = assess_release_readiness(ctx, gates=services(ctx))
    assert not result.data['ready'] and gates(result)['coverage']['status'] == 'incomplete'
    assert ('evidence_missing' if case == 'missing' else 'evidence_stale') in findings(result)
    if case == 'stale': assert 'evidence_missing' not in findings(result)


def test_a_missing_descriptor_is_not_misreported_as_a_missing_contract():
    values, _ = release_case(); values[0]['readiness_policy'] = deepcopy(POLICY)
    ctx = context(refresh_reviews(values)); result = assess_release_readiness(ctx, gates=services(ctx))
    assert not result.data['ready'] and gates(result)['coverage']['status'] == 'incomplete'
    assert 'verification_contract_missing' not in {f['reason'] for f in gates(result)['coverage']['findings']}
    assert 'required_check_unselected' in findings(result)


@pytest.mark.parametrize('field,value', [('extra', True), ('reviewed_at', '2026-10-22T00:00:00+00:00'),
    ('reviewed_at', '2026-10-22T00:00:60Z'), ('reviewed_at', '2026-10-22T00:00:00.0000000001Z'),
    ('decision_sha256', 'F' * 64), ('decision', 'approved'), ('criteria', []), ('review_id', '')])
def test_passive_review_schema_never_accepts_ambiguous_inputs(field, value):
    _, d = blocker_case(); raw = passive(d).data; raw[field] = value
    with pytest.raises(ModelError) as caught: HumanReleaseBlockerReview(raw)
    assert type(caught.value) is ModelError and caught.value.reason


def test_untyped_and_duplicate_review_inputs_are_rejected_before_host_execution():
    values, d = blocker_case(); ctx = context(values); r = passive(d)
    for reviews in ({}, [r.data], [r, r]):
        with pytest.raises(ModelError): assess_release_readiness(ctx, blocker_reviews=reviews)
    with pytest.raises(ModelError): assess_release_readiness(ctx, blocker_verifier={'check': True})
    with pytest.raises(TypeError): bool(r)
    with pytest.raises(TypeError): ReleaseBlockerReviewContext()


@pytest.mark.parametrize('result', ['passed', 'failed'])
def test_stale_evidence_is_incomplete_and_never_an_active_failure(result):
    values, _ = release_case()
    ev = next(v for v in values if v['artifact_type'] == 'evidence')
    ev['result'] = result
    ev['subjects'][0]['verification_context_sha256'] = '0' * 64
    values = refresh_reviews(values)
    ctx = context(values); report = assess_release_readiness(ctx, gates=services(ctx))
    assert report.data['status'] == 'incomplete', [(g['gate_id'], g['findings']) for g in report.data['gates']]
    assert gates(report)['verification']['status'] == gates(report)['coverage']['status'] == 'incomplete'
    assert 'evidence_stale' in findings(report)
    assert 'verification_stale' in findings(report)
    if result == 'failed': assert 'evidence_result_failed' in findings(report)


@pytest.mark.parametrize('state', ['unselected', 'missing', 'failed', 'passed'])
def test_overall_evidence_cannot_discharge_an_additional_declared_dimension(state):
    from specroad.verification import VerificationEvaluation
    from test_verification_run_selection import observation
    values, selected = release_case()
    contract = next(v for v in values if v['id'] == ref('VER', '1'))
    contract['dimensions'].append('latency')
    contract['evidence_slots'].append({'check_id': 'latency', 'test_id': None, 'dimension': 'latency'})
    extra = {'subject_artifact_id': ref('CAP'), 'contract_id': contract['id'],
             'test_id': None, 'check_id': 'latency', 'run_ids': ['ci:expected']}
    descriptor_data = selected.data
    if state != 'unselected': descriptor_data['required_runs'].append(extra)
    selected = VerificationEvaluation(canonical_json_bytes(descriptor_data))
    values[0]['readiness_policy']['verification_evaluation'] = selected.data
    values = [v for v in values if v['artifact_type'] != 'evidence']
    if state in ('failed', 'passed'):
        contract['relations'].append(edge('produces', ref('EVD', '4'), number=90))
    for number, key in enumerate(selected.data['required_runs'], 1):
        if key['check_id'] == 'latency': continue
        # Evidence IDs follow subject kind, independent of descriptor ordering.
        token = {ref('CAP'): '1', ref('TASK'): '2', ref(): '3'}[key['subject_artifact_id']]
        observed = observation(values, selected, key, token=token, run='ci:expected', result='passed')
        observed['configuration_policy'] = 'independent'
        values.append(observed)
    if state in ('failed', 'passed'):
        observed = observation(values, selected, extra, token='4', run='ci:expected', result=state)
        observed['configuration_policy'] = 'independent'
        values.append(observed)
    values = refresh_reviews(values)
    ctx = context(values); report = assess_release_readiness(ctx, gates=services(ctx))
    assert report.data['ready'] is (state == 'passed'), [(g['gate_id'], g['findings']) for g in report.data['gates']]
    expected = 'passed' if state == 'passed' else 'failed' if state == 'failed' else 'incomplete'
    assert gates(report)['coverage']['status'] == expected
    assert 'verification_contract_missing' not in findings(report)
    if state == 'unselected': assert 'required_check_unselected' in findings(report)
    elif state == 'missing': assert 'evidence_missing' in findings(report)
    elif state == 'failed': assert 'required_check_failed' in findings(report)
    inventory = gates(report)['coverage']['evidence_bindings'][1]['required_checks']
    assert any(k['check_id'] == 'latency' and k['test_id'] is None for k in inventory)


@pytest.mark.parametrize('kind', ['capability', 'requirement', 'task'])
def test_a_valid_native_human_waiver_never_counts_as_release_verification(kind):
    from specroad.changes.json_patch import JsonPatch
    from specroad.storage.domain_artifact import DomainArtifact
    from specroad.verification import (WaiverContext, HumanWaiverReview,
        prepare_verification_waiver, prepare_verification_plan_update)
    from test_verification_waivers import trusted as waiver_verifier
    values, _ = release_case()
    index = next(i for i, v in enumerate(values) if v['artifact_type'] == kind)
    original = DomainArtifact(canonical_json_bytes(values[index]))
    waiver_context = WaiverContext(original, ScopeDescriptor(SCOPE_RELEASE), evaluated_at=NOW, configuration=None)
    waiver = prepare_verification_waiver(waiver_context, reason='Explicit fixture exception',
        expires_at='2026-10-23T00:00:00Z', human_review_id='human:release-waiver')
    op = prepare_verification_plan_update(original, 'waived', waiver=waiver)
    values[index] = JsonPatch(op.data['patch']).apply(original.data).data
    r = HumanWaiverReview({'review_id': 'human:release-waiver', 'subject_id': original.id,
        'waiver_sha256': waiver.sha256, 'reviewer': HUMAN, 'reviewed_at': NOW, 'decision': 'confirmed'})
    values = refresh_reviews(values)
    ctx = context(values, waiver_reviews={original.id: r}, waiver_verifier=waiver_verifier())
    with no_write_attempts(): report = assess_release_readiness(ctx, gates=services(ctx))
    gate = gates(report)['verification']
    subject = next(v['observation'] for v in gate['evidence_bindings'] if v['subject_id'] == original.id)
    assert subject['verification_result'] == 'waived'
    assert not report.data['ready'] and report.data['status'] == 'blocked' and gate['status'] == 'failed'
    assert 'verification_waived' in findings(report)


@pytest.mark.parametrize('gate,reason', [
    ('review_currentness', 'approval_human_review_rejected'),
    ('review_currentness', 'approval_nonhuman_review'),
    ('task_done', 'task_done_criteria_unconfirmed')])
def test_required_negative_review_is_failed_even_as_a_provider_warning(gate, reason):
    values, _ = release_case(); ctx = context(values)
    supplied = services(ctx)
    supplied = [replace(g, check=lambda c: c.result([{'reason': reason, 'severity': 'warning'}]))
                if g.gate_id == gate else g for g in supplied]
    report = assess_release_readiness(ctx, gates=supplied)
    target = 'implementation' if gate == 'task_done' else 'approval'
    assert report.data['status'] == 'blocked' and report.exit_code == 3
    assert gates(report)[target]['status'] == 'failed' and reason in findings(report)
    observed = next(v['observation'] for v in gates(report)[target]['evidence_bindings'] if v.get('stage') == gate)
    assert observed['status'] == 'passed' and observed['diagnostics'][0]['severity'] == 'warning'


def test_required_test_reference_cannot_be_replaced_by_evidence_or_an_empty_scope():
    values, _ = release_case()
    contract = next(v for v in values if v['artifact_type'] == 'verification')
    contract['evidence_slots'][0]['test_id'] = ref('TEST', '5')
    ctx = context(values)
    report = assess_release_readiness(ctx)
    assert not report.data['ready'] and report.data['status'] == 'blocked'
    assert all(g['status'] != 'not_applicable' for g in report.data['gates'])
    assert ctx.data['scope_error'] is not None
    assert gates(report)['scope']['evidence_bindings'][0]['scope_resolution_error'] == ctx.data['scope_error']
    assert 'test_id' in json.dumps(ctx.data['scope_error']), ctx.data['scope_error']


@pytest.mark.parametrize('severity', ['info', 'warning'])
def test_warning_level_minimum_relation_still_blocks_release(severity):
    from specroad.changes import TargetModel
    from specroad.model.canonical import canonical_json_bytes
    from specroad.profiles import ProfileResource, compose_profiles
    from specroad.validation import ModelDocument
    from specroad.storage.language_registry import bundled_language_registry
    from specroad.planning import ReleaseReadinessContext, assess_release_readiness
    from support.profiles import profile_data
    from support.profile_composition import relation
    from test_release_readiness import (release_case, context, services, native_bindings,
        RELEASE, NOW, INPUTS, gates)
    values, _ = release_case(); original = context(values)._model
    rule = relation(severity=severity, relation_types=['addresses'], endpoint_types=['goal'], minimum=1)
    resource = ProfileResource(canonical_json_bytes(profile_data(profile_id='core', relation_rules=[rule])))
    profile = compose_profiles([resource], core_key=resource.key,
                               language_registry=bundled_language_registry())
    supplied = TargetModel(original.configuration_bytes, original.binding, original.documents,
        profile=profile, resource_files=[ModelDocument(d.path, resource.source_bytes)
            if d.path=='profiles/core.json' else d for d in original.resource_files])
    ctx = ReleaseReadinessContext(supplied, RELEASE, scope_bindings=native_bindings(supplied),
        evaluated_at=NOW, inputs=dict(INPUTS), input_roles={p:'input' for p in INPUTS})
    report = assess_release_readiness(ctx, gates=services(ctx))
    observed = next(v['observation'] for v in gates(report)['relations']['evidence_bindings']
                    if v.get('stage')=='minimum_relations')
    assert observed['status']=='passed' and observed['diagnostics']
    assert all(d['severity']==severity for d in observed['diagnostics'])
    assert not report.data['ready'] and report.data['status']=='blocked'
    assert gates(report)['relations']['status']=='failed'
