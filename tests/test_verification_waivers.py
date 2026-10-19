"""Versioned, time-bound human waivers, separate from verification success."""
from dataclasses import FrozenInstanceError
import json

import pytest

from specroad.changes.json_patch import JsonPatch
from specroad.configurations import resolve_configuration
from specroad.graph.relations import SourceRelations
from specroad.graph.scope_descriptors import ScopeDescriptor
from specroad.model.canonical import canonical_json_sha256
from specroad.model.errors import ModelError
from specroad.storage.domain_artifact import DomainArtifact
from specroad.verification import (VerificationWaiver, WaiverContext, HumanWaiverReview,
    WaiverReviewVerification, WaiverReviewVerifier, WaiverAssessment,
    waiver_content_projection, waiver_content_sha256, prepare_verification_waiver,
    prepare_verification_plan_update, assess_verification_waiver)
from specroad.validation import validate_model
from support.artifacts import artifact_bytes
from support.domain import domain_value, waiver as legacy_waiver, relation
from support.model_validation import doc, profile
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import no_write_attempts
from support.records import record_value, ref
from support.targets import SCOPE

NOW = '2026-10-19T12:00:00Z'
DEADLINE = '2026-10-20T12:00:00Z'
HUMAN = {'actor_type': 'human', 'actor_id': 'reviewer'}


def subject(value=None, kind='requirement'):
    return DomainArtifact(artifact_bytes(domain_value(kind) if value is None else value))


def context(record, *, at=NOW, scope=None, configuration=None):
    return WaiverContext(record, ScopeDescriptor(SCOPE if scope is None else scope),
                        evaluated_at=at, configuration=configuration)


def fixture(kind='requirement', *, scope=None, configuration=None):
    base = subject(kind=kind)
    candidate = prepare_verification_waiver(context(base, scope=scope, configuration=configuration),
        reason='Deferred until the approved deadline', expires_at=DEADLINE, human_review_id='human:waiver-17')
    operation = prepare_verification_plan_update(base, 'waived', waiver=candidate)
    active = subject(JsonPatch(operation.data['patch']).apply(base.data).data)
    review = HumanWaiverReview({'review_id': 'human:waiver-17', 'subject_id': base.id,
        'waiver_sha256': candidate.sha256, 'reviewer': HUMAN, 'reviewed_at': NOW, 'decision': 'confirmed'})
    return active, candidate, review


def trusted():
    return WaiverReviewVerifier('test-host-review', '1', lambda ctx, review:
        WaiverReviewVerification(ctx.sha256, review.sha256, True, True))


def assess(record, review=None, *, verifier=None, **kwargs):
    return assess_verification_waiver(context(record, **kwargs), review=review, verifier=verifier).data


@pytest.mark.parametrize('kind', ['requirement', 'capability', 'task'])
def test_valid_human_waiver_is_separate_from_passed_or_stored_result(kind):
    active, candidate, review = fixture(kind)
    before = active.source_bytes
    with no_write_attempts(): result = assess(active, review, verifier=trusted())
    assert result['waiver_result'] == 'waived' and result['reasons'] == []
    assert result['review_verified'] and result['waiver_sha256'] == candidate.sha256
    assert result['evaluated_at'] == NOW and result['configuration_sha256'] is None
    assert not any(result[key] for key in ('full_verification_evaluated', 'scope_membership_evaluated',
        'configuration_applicability_evaluated', 'release_readiness_evaluated', 'write_authorized', 'approval_granted'))
    assert 'verification_result' not in result and 'verification_result' not in active.data
    assert 'passed' not in result.values() and active.source_bytes == before


@pytest.mark.parametrize('at,expected', [
    ('2026-10-20T11:59:59.999999999Z', 'waived'),
    (DEADLINE, 'ineffective'), ('2026-10-20T12:00:00.000000000Z', 'ineffective'),
    ('2026-10-20T12:00:00.000000001Z', 'ineffective'), ('2027-01-01T00:00:00Z', 'ineffective')])
def test_deadline_is_exclusive_and_compared_without_a_clock(at, expected):
    active, _, review = fixture()
    result = assess(active, review, verifier=trusted(), at=at)
    assert result['waiver_result'] == expected
    assert ('waiver_expired' in result['reasons']) == (expected == 'ineffective')


@pytest.mark.parametrize('at,expired', [('2026-10-20T12:00:00.123456788Z', False),
    ('2026-10-20T12:00:00.123456789Z', True), ('2026-10-20T12:00:00.123456790Z', True)])
def test_submicrosecond_deadline_is_not_rounded(at, expired):
    active, waiver, review = fixture()
    data = waiver.data; data['expiry_condition']['expires_at'] = '2026-10-20T12:00:00.123456789Z'
    changed = VerificationWaiver(data)
    active = subject({**active.data, 'verification_waiver': changed.data})
    review = HumanWaiverReview({**review.data, 'waiver_sha256': changed.sha256})
    result = assess(active, review, verifier=trusted(), at=at)
    assert ('waiver_expired' in result['reasons']) == expired
    assert result['waiver_result'] == ('ineffective' if expired else 'waived')


@pytest.mark.parametrize('time', [None, True, '2026-10-19', '2026-10-19T12:00:00',
    '2026-10-19T12:00:00+00:00', '2026-10-19t12:00:00Z', '2026-10-19T12:00:00z',
    '2026-02-30T12:00:00Z', '2026-10-19T25:00:00Z', '2026-06-30T23:59:60Z',
    '2026-10-19T12:00:00.1234567890Z'])
def test_ambiguous_or_invalid_evaluation_time_is_rejected(time):
    with pytest.raises(ModelError): context(subject(), at=time)


@pytest.mark.parametrize('expires', [NOW, '2026-10-18T12:00:00Z'])
def test_new_candidate_cannot_start_expired(expires):
    with pytest.raises(ModelError) as caught:
        prepare_verification_waiver(context(subject()), reason='Reason', expires_at=expires, human_review_id='review')
    assert caught.value.reason == 'waiver_deadline_not_future'


def test_evaluation_time_must_be_supplied_explicitly():
    with pytest.raises(TypeError): WaiverContext(subject(), ScopeDescriptor(SCOPE))


@pytest.mark.parametrize('change', [
    {'revision': 2}, {'created_at': '2026-10-18T00:00:00Z'}, {'updated_at': NOW},
    {'created_by': HUMAN}, {'updated_by': HUMAN}, {'maturity': 'proposed'},
    {'implementation_status': 'implemented'}])
def test_subject_audit_and_workflow_changes_keep_the_human_exception(change):
    active, _, review = fixture()
    changed = subject({**active.data, **change})
    assert waiver_content_sha256(changed) == waiver_content_sha256(active)
    assert canonical_json_sha256(changed.data) != canonical_json_sha256(active.data)
    assert assess(changed, review, verifier=trusted())['waiver_result'] == 'waived'


@pytest.mark.parametrize('status', ['not_planned', 'planned', 'running', 'not_applicable'])
def test_plan_status_does_not_change_content_but_deactivates_waiver(status):
    active, _, review = fixture()
    changed = subject({**active.data, 'verification_plan_status': status})
    assert waiver_content_sha256(changed) == waiver_content_sha256(active)
    result = assess(changed, review, verifier=trusted())
    assert result['waiver_result'] == 'ineffective' and result['reasons'] == ['waiver_not_active']


@pytest.mark.parametrize('kind,change', [
    ('requirement', {'statement': 'New required behavior'}),
    ('requirement', {'normative_force': 'must_not'}), ('requirement', {'priority': 'low'}),
    ('requirement', {'criticality': 'critical'}), ('requirement', {'rationale': 'New reason'}),
    ('requirement', {'scope': {'area': 'changed'}}), ('requirement', {'exceptions': ['Emergency']}),
    ('requirement', {'thresholds': [{'limit': 5}]}), ('requirement', {'language': 'de'}),
    ('requirement', {'applicability': {'kind': 'literal', 'value': False}}),
    ('requirement', {'title': 'Changed title'}), ('requirement', {'owner': 'other-owner'}),
    ('requirement', {'relations': [relation('verified_by', ref('VER'))]}),
    ('requirement', {'extensions': {'sample.data': {'revision': 9}}}),
    ('capability', {'description': 'Changed capability'}), ('capability', {'outcome': 'Changed outcome'}),
    ('task', {'description': 'Changed task'}), ('task', {'done_criteria': ['New acceptance']}),
])
def test_fachliche_changes_invalidate_old_content_binding(kind, change):
    active, _, review = fixture(kind)
    changed = subject({**active.data, **change})
    result = assess(changed, review, verifier=trusted())
    assert result['waiver_result'] == 'ineffective' and 'waiver_content_changed' in result['reasons']


def test_provenance_capture_time_is_audit_but_actual_source_values_are_bound():
    base = domain_value('requirement', provenance=[{'locator': 'source:contract',
        'excerpt': 'Required behavior', 'captured_at': NOW}])
    original = waiver_content_sha256(subject(base))
    base['provenance'][0]['captured_at'] = DEADLINE
    assert waiver_content_sha256(subject(base)) == original
    base['provenance'][0]['excerpt'] = 'New behavior'
    assert waiver_content_sha256(subject(base)) != original


def test_nested_semantic_fields_named_like_audit_are_not_excluded_recursively():
    base = domain_value('requirement', extensions={'sample.contract': {'revision': 1, 'updated_at': NOW}})
    original = waiver_content_sha256(subject(base))
    base['extensions']['sample.contract']['updated_at'] = DEADLINE
    assert waiver_content_sha256(subject(base)) != original


def test_hash_projection_has_explicit_domain_and_does_not_contain_own_waiver():
    active, _, _ = fixture()
    projected = waiver_content_projection(active)
    assert projected['hash_algorithm'] == 'waiver-content-hash-v1'
    assert projected['artifact'] == {key: value for key, value in active.data.items() if key in (
        'schema_version', 'id', 'id_scheme', 'artifact_type', 'title', 'language', 'relations',
        'extensions', 'requirement_kind', 'normative_force', 'statement', 'priority', 'criticality')}
    assert active.data['verification_waiver']['artifact_sha256'] == canonical_json_sha256(projected)
    assert active.data['verification_waiver']['artifact_sha256'] != canonical_json_sha256(active.data)


@pytest.mark.parametrize('change', [{'boundary_policy': 'partial'}, {'scope_kind': 'specification'}])
def test_even_equally_populated_but_different_scope_does_not_inherit_waiver(change):
    active, _, review = fixture()
    result = assess(active, review, verifier=trusted(), scope={**SCOPE, **change})
    assert result['waiver_result'] == 'ineffective' and result['reasons'] == ['waiver_scope_mismatch']


def config(selection='linux'):
    record = SourceRelations(artifact_bytes(record_value('configuration', selection={'platform': selection})))
    return resolve_configuration([record], record.identity.id)


def test_configuration_binds_selected_identity_and_actual_chain_hash():
    first, second = config(), config('windows')
    scope = {**SCOPE, 'configuration_id': first.configuration_id}
    active, candidate, review = fixture(scope=scope, configuration=first)
    assert candidate.data['configuration_sha256'] == first.sha256
    assert assess(active, review, verifier=trusted(), scope=scope, configuration=first)['waiver_result'] == 'waived'
    changed = assess(active, review, verifier=trusted(), scope=scope, configuration=second)
    assert changed['reasons'] == ['waiver_configuration_mismatch']
    assert changed['waiver_result'] == 'ineffective'


def test_unconfigured_waiver_does_not_mean_all_configurations():
    active, _, review = fixture(); selected = config()
    result = assess(active, review, verifier=trusted(),
        scope={**SCOPE, 'configuration_id': selected.configuration_id}, configuration=selected)
    assert result['waiver_result'] == 'ineffective'
    assert result['reasons'] == ['waiver_scope_mismatch', 'waiver_configuration_mismatch']


@pytest.mark.parametrize('case', ['missing', 'foreign', 'unselected'])
def test_ambiguous_configuration_input_is_not_inferred(case):
    selected = config(); scope = {**SCOPE, 'configuration_id': selected.configuration_id}
    if case == 'missing': selected = None
    elif case == 'foreign': scope['configuration_id'] = ref('CFG', '1')
    else: scope = SCOPE
    with pytest.raises(ModelError): context(subject(), scope=scope, configuration=selected)


@pytest.mark.parametrize('field,value,reason', [
    ('review_id', 'other-review', 'waiver_review_binding_mismatch'),
    ('subject_id', ref('REQ', '1'), 'waiver_review_binding_mismatch'),
    ('waiver_sha256', '0' * 64, 'waiver_review_binding_mismatch'),
    ('reviewer', {'actor_type': 'ai', 'actor_id': 'assistant'}, 'waiver_review_nonhuman'),
    ('decision', 'rejected', 'waiver_review_rejected'),
    ('reviewed_at', DEADLINE, 'waiver_review_in_future')])
def test_review_is_bound_to_actual_human_decision(field, value, reason):
    active, _, review = fixture()
    review = HumanWaiverReview({**review.data, field: value})
    result = assess(active, review, verifier=trusted())
    assert result['waiver_result'] == 'ineffective' and result['reasons'] == [reason]


@pytest.mark.parametrize('field,value', [('reason', 'Changed exception'),
    ('human_review_id', 'other-review'),
    ('expiry_condition', {'kind': 'utc_deadline', 'expires_at': '2026-10-21T00:00:00Z'})])
def test_modifying_waiver_terms_requires_a_new_matching_review(field, value):
    active, waiver, review = fixture()
    modified = VerificationWaiver({**waiver.data, field: value})
    changed = subject({**active.data, 'verification_waiver': modified.data})
    assert waiver_content_sha256(changed) == waiver_content_sha256(active)
    assert assess(changed, review, verifier=trusted())['reasons'] == ['waiver_review_binding_mismatch']


@pytest.mark.parametrize('mode', ['missing-review', 'missing-verifier', 'unbound', 'revoked', 'unauthenticated', 'failure'])
def test_unverified_human_labels_and_failed_services_never_grant_exception(mode):
    active, _, review = fixture(); verifier = trusted()
    if mode == 'missing-review': review = None
    elif mode == 'missing-verifier': verifier = None
    else:
        def observe(ctx, human):
            if mode == 'failure': raise OSError('offline')
            return WaiverReviewVerification('0' * 64 if mode == 'unbound' else ctx.sha256,
                human.sha256, mode != 'unauthenticated', mode != 'revoked')
        verifier = WaiverReviewVerifier('test-host', '1', observe)
    result = assess(active, review, verifier=verifier)
    assert result['waiver_result'] == 'ineffective' and not result['review_verified'] and result['reasons']


@pytest.mark.parametrize('kind', ['requirement', 'capability', 'task'])
def test_legacy_waiver_remains_readable_and_is_not_implicitly_upgraded(kind):
    old = domain_value(kind, verification_plan_status='waived', verification_waiver=legacy_waiver())
    raw = artifact_bytes(old); record = DomainArtifact(raw)
    with no_write_attempts():
        result = assess(record)
        parsed = VerificationWaiver(record.data['verification_waiver'])
    assert record.source_bytes == raw and parsed.data == old['verification_waiver']
    assert result['waiver_result'] == 'ineffective' and result['reasons'] == ['legacy_waiver_unsupported']
    with pytest.raises(ModelError): prepare_verification_plan_update(record, 'waived')
    operation = prepare_verification_plan_update(record, 'planned')
    updated = JsonPatch(operation.data['patch']).apply(old).data
    assert updated['verification_waiver'] == old['verification_waiver']


def test_legacy_full_hash_cannot_be_relabelled_as_a_new_content_hash():
    active, waiver, review = fixture()
    fake = VerificationWaiver({**waiver.data, 'artifact_sha256': canonical_json_sha256(active.data)})
    changed = subject({**active.data, 'verification_waiver': fake.data})
    assert assess(changed, review, verifier=trusted())['reasons'] == ['waiver_content_changed']


@pytest.mark.parametrize('change', [
    {'format_version': '2.0.0'}, {'content_hash_algorithm': 'sha256'}, {'extra': True},
    {'expiry_condition': 'At next release'}, {'expiry_condition': {'kind': 'event', 'name': 'release'}},
    {'expiry_condition': {'kind': 'utc_deadline', 'expires_at': '2026-06-30T23:59:60Z'}},
    {'expiry_condition': {'kind': 'utc_deadline', 'expires_at': '2026-02-30T00:00:00Z'}},
    {'artifact_sha256': 'A' * 64}, {'configuration_sha256': True}, {'scope_descriptor': {'scope_kind': 'project'}}])
def test_new_waiver_never_accepts_unknown_or_text_only_contracts(change):
    _, waiver, _ = fixture()
    with pytest.raises(ModelError): VerificationWaiver({**waiver.data, **change})


@pytest.mark.parametrize('field', ['format_version', 'content_hash_algorithm', 'reason',
    'scope_descriptor', 'expiry_condition', 'human_review_id', 'artifact_sha256', 'configuration_sha256'])
def test_new_waiver_requires_every_declared_field(field):
    _, waiver, _ = fixture(); value = waiver.data; del value[field]
    with pytest.raises(ModelError): VerificationWaiver(value)


@pytest.mark.parametrize('kind', ['requirement', 'capability', 'task'])
def test_workflow_update_contains_only_stored_fields_and_native_guards(kind):
    base = subject(kind=kind); active, waiver, _ = fixture(kind)
    operation = prepare_verification_plan_update(base, 'waived', waiver=waiver)
    assert operation.data['op'] == 'update' and operation.data['target'] == base.id
    assert operation.data['expected_revision'] == base.data['revision']
    assert operation.data['expected_sha256'] == canonical_json_sha256(base.data)
    assert {row['path'] for row in operation.data['patch']} == {'/verification_plan_status', '/verification_waiver'}
    assert JsonPatch(operation.data['patch']).apply(base.data).data == active.data
    assert base.data['verification_plan_status'] == 'not_planned'


@pytest.mark.parametrize('kind', ['requirement', 'capability', 'task'])
def test_calculated_result_cannot_be_persisted_as_a_normative_field(kind):
    active, _, review = fixture(kind)
    result = assess(active, review, verifier=trusted())
    for injected in ('passed', result):
        with pytest.raises(ModelError): subject({**active.data, 'verification_result': injected})
    with pytest.raises(ModelError): prepare_verification_plan_update(active, 'passed')


def test_versioned_review_identity_is_not_falsely_resolved_as_relation_review():
    active, _, _ = fixture()
    result = validate_model([doc(active.data)], profile=profile())
    assert next(stage for stage in result.data['stages']
                if stage['stage'] == 'identities_references')['status'] == 'passed'
    assert not any(d.get('pointer') == '/verification_waiver/human_review_id' for d in result.diagnostics)
    assert result.data['approval_granted'] is False
    assert assess(active)['reasons'] == ['waiver_review_missing']
    old = {**active.data, 'verification_waiver': legacy_waiver()}
    historical = validate_model([doc(old)], profile=profile())
    assert any(d.get('pointer') == '/verification_waiver/human_review_id'
               and d['reason'] == 'validation_field_target_missing' for d in historical.diagnostics)


def test_owned_values_cannot_be_mutated_through_their_data_properties():
    active, waiver, review = fixture(); ctx = context(active)
    assessment = assess_verification_waiver(ctx, review=review, verifier=trusted())
    for value in (waiver, review, ctx, assessment):
        before = value.data; digest = value.sha256
        value.data.clear()
        assert value.data == before and value.sha256 == digest
        with pytest.raises(FrozenInstanceError): value._encoded = b'{}'
        with pytest.raises(TypeError): bool(value)
    with pytest.raises(TypeError): WaiverAssessment()


def test_assessment_does_not_read_files_time_network_or_project_code(monkeypatch):
    active, _, review = fixture(); ctx = context(active)
    def no_read(*args, **kwargs): raise AssertionError('Unexpected file or clock read')
    with no_write_attempts(), monkeypatch.context() as patch:
        patch.setattr('builtins.open', no_read); patch.setattr('io.open', no_read)
        patch.setattr('time.time', no_read)
        result = assess_verification_waiver(ctx, review=review, verifier=trusted())
    assert result.data['waiver_result'] == 'waived'


@pytest.mark.parametrize('mode', ['core', 'pyz'])
def test_same_waiver_hash_and_assessment_in_isolated_core_and_pyz(tmp_path, mode):
    active, _, review = fixture(); expected = assess(active, review, verifier=trusted())
    body = '''import json
from specroad.verification import WaiverContext, HumanWaiverReview, WaiverReviewVerification, WaiverReviewVerifier, assess_verification_waiver
from specroad.storage.domain_artifact import DomainArtifact
from specroad.graph.scope_descriptors import ScopeDescriptor
'''
    body += 'ctx=WaiverContext(DomainArtifact(' + repr(active.source_bytes) + '),ScopeDescriptor(' + repr(SCOPE) + '),evaluated_at=' + repr(NOW) + ')\n'
    body += 'review=HumanWaiverReview(' + repr(review.data) + ')\n'
    body += "verifier=WaiverReviewVerifier('host','1',lambda c,r:WaiverReviewVerification(c.sha256,r.sha256,True,True))\n"
    body += 'print(json.dumps(assess_verification_waiver(ctx,review=review,verifier=verifier).data))\n'
    if mode == 'core': result = run_core(body, tmp_path, capture=True)
    else:
        _, package = build_distribution(tmp_path / 'distribution')
        result = run_python(['-I', '-S', '-B', '-c',
            'import sys;sys.path.insert(0,' + repr(str(package)) + ')\n' + body], tmp_path, capture=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == expected
