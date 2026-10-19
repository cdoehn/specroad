"""Waiver currentness, hostile callbacks and actual guarded writer behavior."""
import json

import pytest

from specroad.authoring.update import update_artifact
from specroad.changes import (ChangeOperation, ChangePlanError, PublicationAuthority,
    PublicationCheckError, TargetError, TargetModel)
from specroad.configurations import resolve_configuration
from specroad.graph.relations import SourceRelations
from specroad.model.canonical import canonical_json_bytes
from specroad.model.paths import artifact_path
from specroad.storage.domain_artifact import DomainArtifact
from specroad.validation import ModelDocument, ModelGate
from specroad.verification import (HumanWaiverReview, VerificationWaiver,
    WaiverReviewVerifier, WaiverReviewVerification, assess_verification_waiver,
    prepare_verification_plan_update, prepare_verification_waiver, waiver_content_sha256)
from support.artifacts import artifact_bytes
from support.domain import domain_value, waiver as legacy_waiver
from support.read_only import inventory, no_write_attempts
from support.records import record_value, ref
from support.targets import SCOPE
from test_artifact_creation import project
from test_artifact_update import arguments, ACTOR, TIME
from test_verification_waivers import (NOW, DEADLINE, HUMAN, subject, context,
    fixture, trusted, assess)


@pytest.mark.parametrize('target,field,value', [
    ('context', 'evaluated_at', DEADLINE),
    ('context', 'content_sha256', '0' * 64),
    ('context', 'configuration_sha256', '0' * 64),
    ('context', 'scope_descriptor', {**SCOPE, 'boundary_policy': 'partial'}),
    ('review', 'decision', 'rejected'),
    ('review', 'reviewer', {'actor_type': 'ai', 'actor_id': 'agent'}),
    ('review', 'waiver_sha256', '0' * 64),
    ('review', 'reviewed_at', DEADLINE),
    ('original_context', 'evaluated_at', DEADLINE),
    ('original_review', 'decision', 'rejected'),
    ('verifier', 'verifier_id', 'replacement'),
    ('verifier', 'version', '2'),
    ('verifier', 'check', None),
])
def test_changed_review_inputs_cannot_activate_or_rebind_the_observation(target, field, value):
    active, _, review = fixture(); ctx = context(active)
    original_context, original_review = ctx.data, review.data
    input_hash, review_hash = ctx.sha256, review.sha256
    def check(c, r):
        assert c is not ctx and r is not review
        assert c.data == original_context and r.data == original_review
        confirmation = WaiverReviewVerification(input_hash, review_hash, True, True)
        changed = {'context': c, 'review': r, 'original_context': ctx,
                   'original_review': review, 'verifier': verifier}[target]
        if target == 'verifier': object.__setattr__(changed, field, value)
        else:
            data = changed.data; data[field] = value
            object.__setattr__(changed, '_encoded', canonical_json_bytes(data))
        return confirmation
    verifier = WaiverReviewVerifier('host', '1', check)
    result = assess_verification_waiver(ctx, review=review, verifier=verifier).data
    assert result['waiver_result'] == 'ineffective' and not result['review_verified']
    assert result['reasons'] == ['waiver_review_inputs_changed']
    assert result['input_sha256'] == input_hash and result['review_sha256'] == review_hash
    assert result['evaluated_at'] == NOW and result['scope_descriptor'] == SCOPE
    assert result['content_sha256'] == original_context['content_sha256']
    if target != 'original_context': assert ctx.data == original_context
    if target != 'original_review': assert review.data == original_review


@pytest.mark.parametrize('field', ['authenticated_human', 'current'])
@pytest.mark.parametrize('value', [1, 'true', [True], {'confirmed': True}])
def test_forged_typed_verifier_booleans_are_not_confirmation(field, value):
    active, _, review = fixture()
    def check(c, r):
        result = WaiverReviewVerification(c.sha256, r.sha256, True, True)
        object.__setattr__(result, field, value)
        return result
    result = assess(active, review, verifier=WaiverReviewVerifier('host', '1', check))
    assert result['reasons'] == ['waiver_review_verification_failed']
    assert result['waiver_result'] == 'ineffective' and not result['review_verified']


@pytest.mark.parametrize('value', [None, True, {'authenticated_human': True, 'current': True}])
def test_untyped_host_return_is_not_evidence(value):
    active, _, review = fixture()
    result = assess(active, review, verifier=WaiverReviewVerifier('host', '1', lambda c, r: value))
    assert result['reasons'] == ['waiver_review_verifier_unbound']
    assert result['waiver_result'] == 'ineffective'


@pytest.mark.parametrize('target', ['context', 'review'])
def test_broken_callback_inputs_do_not_escape_or_leak_exception_details(target):
    active, _, review = fixture(); ctx = context(active)
    input_hash, review_hash = ctx.sha256, review.sha256
    def check(c, r):
        object.__delattr__(c if target == 'context' else r, '_encoded')
        raise RuntimeError('private-host-detail-do-not-report')
    result = assess_verification_waiver(ctx, review=review,
        verifier=WaiverReviewVerifier('host', '1', check)).data
    assert result['reasons'] == ['waiver_review_verification_failed']
    assert result['input_sha256'] == input_hash and result['review_sha256'] == review_hash
    assert 'private-host-detail' not in json.dumps(result)
    assert ctx.sha256 == input_hash and review.sha256 == review_hash


def test_detached_data_edits_by_callback_have_no_effect_on_bound_inputs():
    active, _, review = fixture(); ctx = context(active)
    def check(c, r):
        c.data['subject'].clear(); r.data['reviewer'].clear()
        return WaiverReviewVerification(c.sha256, r.sha256, True, True)
    with no_write_attempts():
        result = assess_verification_waiver(ctx, review=review,
            verifier=WaiverReviewVerifier('host', '1', check)).data
    assert result == assess(active, review, verifier=trusted())


@pytest.mark.parametrize('case', ['inactive', 'missing', 'content', 'scope', 'expired',
    'legacy', 'foreign_review', 'nonhuman', 'rejected', 'future_review'])
def test_invalid_local_binding_never_calls_external_review_service(case):
    active, _, review = fixture(); kwargs = {}
    if case == 'inactive': active = subject({**active.data, 'verification_plan_status': 'planned'})
    elif case == 'missing':
        value = active.data; value.pop('verification_waiver'); value['verification_plan_status'] = 'planned'
        active = subject(value)
    elif case == 'content': active = subject({**active.data, 'statement': 'A changed obligation.'})
    elif case == 'scope': kwargs['scope'] = {**SCOPE, 'boundary_policy': 'partial'}
    elif case == 'expired': kwargs['at'] = DEADLINE
    elif case == 'legacy': active = subject({**active.data, 'verification_waiver': legacy_waiver()})
    else:
        changes = {'foreign_review': {'review_id': 'foreign'},
            'nonhuman': {'reviewer': {'actor_type': 'ci', 'actor_id': 'job'}},
            'rejected': {'decision': 'rejected'}, 'future_review': {'reviewed_at': DEADLINE}}[case]
        review = HumanWaiverReview({**review.data, **changes})
    calls = []
    def check(c, r):
        calls.append(True)
        return WaiverReviewVerification(c.sha256, r.sha256, True, True)
    result = assess(active, review, verifier=WaiverReviewVerifier('host', '1', check), **kwargs)
    assert result['waiver_result'] == 'ineffective' and result['reasons']
    assert calls == [] and not result['review_verified']


@pytest.mark.parametrize('change', ['audit', 'source_bytes', 'evaluation_time'])
def test_old_host_observation_cannot_be_replayed_on_new_evaluation_input(change):
    active, _, review = fixture(); previous = context(active); at = NOW
    observation = WaiverReviewVerification(previous.sha256, review.sha256, True, True)
    if change == 'audit': active = subject({**active.data, 'revision': 2, 'updated_at': NOW})
    elif change == 'source_bytes': active = DomainArtifact(active.source_bytes + b'\n')
    else: at = '2026-10-19T12:00:00.000000001Z'
    result = assess(active, review, at=at,
        verifier=WaiverReviewVerifier('host', '1', lambda c, r: observation))
    assert result['reasons'] == ['waiver_review_verifier_unbound']
    assert result['input_sha256'] != previous.sha256
    assert result['content_sha256'] == previous.data['content_sha256']
    assert assess(active, review, at=at, verifier=trusted())['waiver_result'] == 'waived'


def test_revocation_is_checked_again_for_the_same_context_without_success_cache():
    active, _, review = fixture(); current = [True]; calls = []
    def check(c, r):
        calls.append((c.sha256, r.sha256))
        return WaiverReviewVerification(c.sha256, r.sha256, True, current[0])
    verifier = WaiverReviewVerifier('host', '1', check)
    assert assess(active, review, verifier=verifier)['waiver_result'] == 'waived'
    current[0] = False
    result = assess(active, review, verifier=verifier)
    assert result['reasons'] == ['waiver_review_not_authenticated_or_current']
    assert result['waiver_result'] == 'ineffective' and len(calls) == 2 and calls[0] == calls[1]


@pytest.mark.parametrize('change', ['parent_revision', 'parent_source', 'selected_id', 'parent_id'])
def test_identical_effective_values_do_not_allow_another_configuration_chain(change):
    parent = record_value('configuration', name='Parent', selection={'platform': 'linux'})
    child = record_value('configuration', id=ref('CFG', '1'), name='Child',
        parent=parent['id'], dimensions=[], selection={})
    def resolve(p, c):
        records = [SourceRelations(artifact_bytes(value)) for value in (p, c)]
        return resolve_configuration(records, c['id'])
    original = resolve(parent, child); scope = {**SCOPE, 'configuration_id': child['id']}
    active, _, review = fixture(scope=scope, configuration=original)
    if change == 'parent_revision': parent['revision'] += 1
    elif change == 'parent_source': parent['name'] = 'Revised parent metadata'
    elif change == 'selected_id': child['id'] = ref('CFG', '2')
    else: parent['id'] = ref('CFG', '2'); child['parent'] = parent['id']
    changed = resolve(parent, child)
    assert original.effective_values == changed.effective_values and original.sha256 != changed.sha256
    result = assess(active, review, scope={**scope, 'configuration_id': child['id']},
                    configuration=changed, verifier=trusted())
    assert 'waiver_configuration_mismatch' in result['reasons']
    assert result['waiver_result'] == 'ineffective'


@pytest.mark.parametrize('expires,at,expired', [
    ('2028-02-29T00:00:00Z', '2028-02-28T23:59:59.999999999Z', False),
    ('2028-03-01T00:00:00Z', '2028-02-29T23:59:59.999999999Z', False),
    ('2027-01-01T00:00:00Z', '2026-12-31T23:59:59.999999999Z', False),
    ('2026-10-20T12:00:00.1Z', '2026-10-20T12:00:00.099999999Z', False),
    ('2026-10-20T12:00:00.1Z', '2026-10-20T12:00:00.100000000Z', True),
    ('2026-10-20T12:00:00.000000001Z', '2026-10-20T12:00:00Z', False),
])
def test_calendar_and_fraction_boundaries_keep_exact_deadline_semantics(expires, at, expired):
    active, candidate, review = fixture()
    changed = VerificationWaiver({**candidate.data,
        'expiry_condition': {'kind': 'utc_deadline', 'expires_at': expires}})
    active = subject({**active.data, 'verification_waiver': changed.data})
    review = HumanWaiverReview({**review.data, 'waiver_sha256': changed.sha256})
    result = assess(active, review, at=at, verifier=trusted())
    assert result['waiver_result'] == ('ineffective' if expired else 'waived')
    assert result['reasons'] == (['waiver_expired'] if expired else [])


@pytest.mark.parametrize('reviewed,valid', [(NOW, True),
    ('2026-10-19T12:00:00.000000000Z', True), ('2026-10-19T12:00:00.000000001Z', False)])
def test_human_review_time_is_not_rounded_forward(reviewed, valid):
    active, _, review = fixture()
    review = HumanWaiverReview({**review.data, 'reviewed_at': reviewed})
    result = assess(active, review, verifier=trusted())
    assert result['waiver_result'] == ('waived' if valid else 'ineffective')
    assert result['reasons'] == ([] if valid else ['waiver_review_in_future'])


@pytest.mark.parametrize('kind', ['capability', 'requirement', 'task'])
def test_legacy_reissuance_needs_explicit_new_terms_and_a_matching_human_review(kind):
    old = subject(domain_value(kind, verification_plan_status='waived', verification_waiver=legacy_waiver()))
    raw = old.source_bytes
    candidate = prepare_verification_waiver(context(old), reason='Explicit new exception',
        expires_at=DEADLINE, human_review_id='human:new-waiver')
    operation = prepare_verification_plan_update(old, 'waived', waiver=candidate)
    from specroad.changes.json_patch import JsonPatch
    active = subject(JsonPatch(operation.data['patch']).apply(old.data).data)
    assert old.source_bytes == raw and old.data['verification_waiver'] == legacy_waiver()
    assert candidate.data['artifact_sha256'] == waiver_content_sha256(old)
    assert assess(active)['reasons'] == ['waiver_review_missing']
    review = HumanWaiverReview({'review_id': 'human:new-waiver', 'subject_id': old.id,
        'waiver_sha256': candidate.sha256, 'reviewer': HUMAN, 'reviewed_at': NOW, 'decision': 'confirmed'})
    assert assess(active, review)['reasons'] == ['waiver_review_verifier_unavailable']
    assert assess(active, review, verifier=trusted())['waiver_result'] == 'waived'


def stored_subject(root, kind='requirement', **changes):
    model, _ = project(root, 'verification')
    value = domain_value(kind, **changes); path = artifact_path(kind, value['id'], 'SR')
    previous = next(d for d in model.documents if json.loads(d.content)['artifact_type'] == 'requirement')
    raw = artifact_bytes(value)
    documents = [ModelDocument(path, raw) if d.path == previous.path else d for d in model.documents]
    if previous.path != path: (root / previous.path).unlink()
    (root / path).parent.mkdir(parents=True, exist_ok=True)
    (root / path).write_bytes(raw); (root / path).chmod(0o640)
    return TargetModel(model.configuration_bytes, model.binding, documents,
        profile=model.profile, resource_files=model.resource_files), DomainArtifact(raw, path=path)


def update_candidate(record):
    return prepare_verification_waiver(context(record), reason='Approved deferral',
        expires_at=DEADLINE, human_review_id='human:write-waiver')


@pytest.mark.parametrize('kind', ['capability', 'requirement', 'task'])
def test_native_writer_publishes_workflow_and_waiver_with_one_revision_and_no_approval(tmp_path, kind):
    root = tmp_path / 'project'; model, record = stored_subject(root, kind)
    candidate = update_candidate(record)
    operation = prepare_verification_plan_update(record, 'waived', waiver=candidate)
    before = inventory(root)
    result = update_artifact(model, operation, **arguments(root))
    actual = DomainArtifact((root / record.path).read_bytes(), path=record.path)
    assert actual.data == {**record.data, 'verification_plan_status': 'waived',
        'verification_waiver': candidate.data, 'revision': 2, 'updated_by': ACTOR, 'updated_at': TIME}
    assert result['completion']['commit_completed'] and result['completion']['cleanup_completed']
    assert waiver_content_sha256(record) == waiver_content_sha256(actual)
    assert 'verification_result' not in actual.data and actual.data['maturity'] == 'draft'
    assert assess(actual)['reasons'] == ['waiver_review_missing']
    after = {name: rest for name, *rest in inventory(root)}
    for name, *rest in before:
        if name != record.path: assert after[name] == rest
    assert (root / record.path).stat().st_mode & 0o777 == 0o640


@pytest.mark.parametrize('guard', ['revision', 'hash'])
def test_waiver_update_keeps_both_native_guards(tmp_path, guard):
    root = tmp_path / 'project'; model, record = stored_subject(root)
    operation = prepare_verification_plan_update(record, 'waived', waiver=update_candidate(record))
    fields = operation.data
    fields['expected_revision' if guard == 'revision' else 'expected_sha256'] = 99 if guard == 'revision' else '0' * 64
    before = inventory(root)
    with pytest.raises(ChangePlanError) as error:
        update_artifact(model, ChangeOperation(fields), **arguments(root))
    assert error.value.reason == ('expected_revision_mismatch' if guard == 'revision' else 'expected_hash_mismatch')
    assert inventory(root) == before


@pytest.mark.parametrize('barrier', ['authority', 'lifecycle', 'physical_base'])
def test_waiver_does_not_bypass_writer_gates(tmp_path, barrier):
    root = tmp_path / 'project'
    model, record = stored_subject(root, maturity='proposed' if barrier == 'lifecycle' else 'draft')
    operation = prepare_verification_plan_update(record, 'waived', waiver=update_candidate(record))
    options = arguments(root); expected = PublicationCheckError; lifecycle_calls = []
    if barrier == 'authority':
        options['authority'] = PublicationAuthority('deny', '1', lambda request: False)
    elif barrier == 'lifecycle':
        expected = TargetError
        def deny(c):
            lifecycle_calls.append(True)
            return c.result([{'severity': 'error', 'reason': 'host_denied'}])
        options['gates'] = [ModelGate('lifecycle', 'deny',
            lambda c: c.dependency_result({key: list(c.all_ids) for key in c.subjects}),
            deny)]
    else: (root / record.path).write_bytes(artifact_bytes({**record.data, 'statement': 'Concurrent edit.'}))
    before = inventory(root)
    with pytest.raises(expected): update_artifact(model, operation, **options)
    assert inventory(root) == before
    if barrier == 'lifecycle': assert lifecycle_calls


@pytest.mark.parametrize('kind', ['capability', 'requirement', 'task'])
@pytest.mark.parametrize('value', ['passed', {'waiver_result': 'waived', 'review_verified': True}])
def test_actual_writer_rejects_normative_verification_result(tmp_path, kind, value):
    root = tmp_path / 'project'; model, record = stored_subject(root, kind)
    operation = prepare_verification_plan_update(record, 'planned').data
    operation['patch'].append({'op': 'add', 'path': '/verification_result', 'value': value})
    before = inventory(root)
    with pytest.raises(ChangePlanError) as error:
        update_artifact(model, ChangeOperation(operation), **arguments(root))
    assert error.value.exit_code == 3 and error.value.reason == 'unknown_field'
    assert error.value.pointer == '/operations/0/candidate/verification_result'
    assert inventory(root) == before
