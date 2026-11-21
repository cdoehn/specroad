"""Negative, stale and revocable host observations cannot authorize a write."""
from dataclasses import replace
import json

import pytest

from specroad.authoring.requirement_approval import approve_requirement
from specroad.changes import (AuthoringError, LifecycleError, TargetError, ChangeOperation,
    PublicationCheckError, PublicationAuthority, assess_change_target)
from specroad.changes.requirement_approval import (APPROVAL_GATE, ApprovalPrerequisiteProvider,
    bind_requirement_approval)
from specroad.validation import (ApprovalContext, ApprovalPrerequisite, HumanRequirementReview,
    ModelDocument, ModelGate, ReviewVerifier, ReviewVerification)
from specroad.validation.approval_values import PREREQUISITES
from specroad.model.canonical import canonical_json_bytes
from support.approval import prerequisites, verifier
from support.read_only import inventory, no_write_attempts
from support.requirement_approval import ready_project, registered
from test_requirement_reapproval import prepare, POLICY


@pytest.mark.parametrize('gate_id', PREREQUISITES)
@pytest.mark.parametrize('fault', ['missing', 'failed', 'stale', 'unavailable'])
def test_every_prerequisite_is_current_and_required_before_native_publication(tmp_path, gate_id, fault):
    model, operation, fields, _ = ready_project(tmp_path / 'project')
    def observe(ctx):
        result = []
        for p in prerequisites(ctx):
            if p.gate_id == gate_id:
                if fault == 'missing': continue
                p = replace(p, input_sha256='f' * 64) if fault == 'stale' else replace(p, status=fault)
            result.append(p)
        return result
    fields['prerequisite_provider'] = ApprovalPrerequisiteProvider('owned-damaged-service', '1', observe)
    before = inventory(tmp_path)
    with pytest.raises(TargetError, match='complete_target_validation_required'):
        approve_requirement(model, operation, **fields)
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('fault', ['nonhuman', 'rejected', 'compound', 'criteria', 'stale',
                                  'unauthenticated', 'not_current', 'unbound_verifier'])
def test_full_human_contract_cannot_be_replaced_by_an_actor_label(tmp_path, fault):
    model, operation, fields, _ = ready_project(tmp_path / 'project')
    data = fields['review'].data
    if fault == 'nonhuman': data['reviewer']['actor_type'] = 'ai'
    elif fault == 'rejected': data['decision'] = 'rejected'
    elif fault == 'compound': data['compound'] = True
    elif fault == 'criteria': data['criteria'].pop('single_testable_fact')
    elif fault == 'stale': data['requirement_sha256'] = 'f' * 64
    elif fault == 'unauthenticated': fields['verifier'] = verifier(authenticated=False)
    elif fault == 'not_current': fields['verifier'] = verifier(current=False)
    elif fault == 'unbound_verifier':
        fields['verifier'] = ReviewVerifier('foreign-result', '1',
            lambda ctx, rev: ReviewVerification('f' * 64, rev.sha256, True, True))
    fields['review'] = HumanRequirementReview(data)
    operation = bind_requirement_approval(operation, fields['context'], fields['review'])
    before = inventory(tmp_path)
    with pytest.raises(TargetError, match='complete_target_validation_required'):
        approve_requirement(model, operation, **fields)
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('fault', ['document_bytes', 'configuration', 'mode', 'input_hash', 'review_hash'])
def test_context_must_match_the_complete_original_model_and_plan_reference(tmp_path, fault):
    model, operation, fields, _ = ready_project(tmp_path / 'project')
    if fault in ('document_bytes', 'configuration', 'mode'):
        documents = model.documents
        if fault == 'document_bytes':
            documents = tuple(ModelDocument(d.path, d.content + b'\n') for d in documents)
        fields['context'] = ApprovalContext(operation.data['target'], documents, profile=model.profile,
            configuration={} if fault == 'configuration' else model.configuration.data,
            mode='stored' if fault == 'mode' else 'transition')
    else:
        value = operation.data
        value['metadata']['requirement_approval']['input_sha256' if fault == 'input_hash' else 'review_sha256'] = 'f' * 64
        operation = ChangeOperation(value)
    before = inventory(tmp_path)
    with pytest.raises(TargetError): approve_requirement(model, operation, **fields)
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('actor_type', ['ai', 'ci', 'tool'])
def test_nonhuman_direct_approval_actor_has_no_write_capability(tmp_path, actor_type):
    model, operation, fields, _ = ready_project(tmp_path / 'project')
    fields['actor'] = {'actor_type': actor_type, 'actor_id': 'synthetic-caller'}
    before = inventory(tmp_path)
    with pytest.raises(AuthoringError) as error:
        approve_requirement(model, operation, **fields)
    assert error.value.exit_code == 7 and inventory(tmp_path) == before


def test_a_same_named_success_callback_cannot_replace_the_native_gate(tmp_path):
    model, operation, fields, _ = ready_project(tmp_path / 'project')
    gates = registered(model, operation, fields)
    fake = ModelGate(APPROVAL_GATE, 'fake', lambda c: c.dependency_result({i: list(c.all_ids) for i in c.subjects}),
                     lambda c: c.result())
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(LifecycleError, match='approval_gate_required'):
        prepare(model, operation, fields, tuple(fake if g.gate_id == APPROVAL_GATE else g for g in gates))
    assert inventory(tmp_path) == before


def test_confirmed_receipt_on_current_approved_model_does_not_require_reapproval(tmp_path):
    from test_negative_relation_review_right import current
    model, operation, fields, _ = ready_project(tmp_path / 'project')
    first = approve_requirement(model, operation, **fields)
    live = current(tmp_path / 'project', model)
    fields['verifier'] = ReviewVerifier('revoked-after-completion', '2',
        lambda ctx, review: pytest.fail('Confirmed receipt is historical'))
    fields['prerequisite_provider'] = ApprovalPrerequisiteProvider('unavailable-after-completion', '2',
        lambda ctx: pytest.fail('Confirmed receipt must not call services'))
    before = inventory(tmp_path)
    with no_write_attempts(): repeated = approve_requirement(live, operation, **fields)
    assert repeated['replayed']
    assert repeated['completion']['receipts'] == first['completion']['receipts']
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('after', [1, 2])
def test_revocation_between_planning_and_publication_is_rechecked(tmp_path, after):
    model, operation, fields, _ = ready_project(tmp_path / 'project')
    calls = []
    def observe(ctx, review):
        calls.append(ctx.input_sha256)
        return ReviewVerification(ctx.input_sha256, review.sha256, True, len(calls) <= after)
    fields['verifier'] = ReviewVerifier('revoking-service', '1', observe)
    before = inventory(tmp_path)
    with pytest.raises((TargetError, PublicationCheckError)):
        approve_requirement(model, operation, **fields)
    assert len(calls) == after + 1 and inventory(tmp_path) == before


@pytest.mark.parametrize('fault', ['throw', 'wrong_type', 'duplicate', 'unbound'])
def test_unavailable_or_malformed_provider_fails_closed_without_effects(tmp_path, fault):
    model, operation, fields, _ = ready_project(tmp_path / 'project')
    def observe(ctx):
        if fault == 'throw': raise OSError('owned unavailable service')
        if fault == 'wrong_type': return {'passed': True}
        values = list(prerequisites(ctx))
        return values + [values[0]] if fault == 'duplicate' else [replace(p, input_sha256='f' * 64) for p in values]
    fields['prerequisite_provider'] = ApprovalPrerequisiteProvider('broken-service', '1', observe)
    before = inventory(tmp_path)
    with pytest.raises(TargetError): approve_requirement(model, operation, **fields)
    assert inventory(tmp_path) == before


def test_other_host_gates_and_publication_authority_still_block(tmp_path):
    model, operation, fields, _ = ready_project(tmp_path / 'project')
    fields['authority'] = PublicationAuthority('deny', '1', lambda request: False)
    before = inventory(tmp_path)
    with pytest.raises(PublicationCheckError) as error:
        approve_requirement(model, operation, **fields)
    assert error.value.exit_code == 7 and inventory(tmp_path) == before
    fields['authority'] = PublicationAuthority('owned', '1', lambda request: True)
    fields['gates'] += (ModelGate('extension:independent-denial', '1',
        lambda c: c.dependency_result({i: list(c.all_ids) for i in c.subjects}),
        lambda c: c.result([{'reason': 'independent_denial', 'severity': 'error'}])),)
    with pytest.raises(TargetError): approve_requirement(model, operation, **fields)
    assert inventory(tmp_path) == before


def test_native_relation_currentness_is_required_even_when_external_services_say_passed(tmp_path):
    from test_negative_relation_review_right import rebuild
    from support.approval import review_data
    model, operation, fields, records = ready_project(tmp_path / 'project')
    values = model.artifacts
    for record in values:
        if record['id'] == records['confirmation']['review_id']: record['decision'] = 'rejected'
    # Owned fixture variation creates an inconsistent source, not a product edit.
    model = rebuild(tmp_path / 'project', model, values)
    ctx = ApprovalContext(operation.data['target'], model.documents, profile=model.profile,
                          configuration=model.configuration.data)
    review = HumanRequirementReview(review_data(ctx, reviewed_at=fields['planned_at']))
    fields.update(context=ctx, review=review, prerequisite_provider=ApprovalPrerequisiteProvider('owned', '1', prerequisites))
    operation = bind_requirement_approval(operation, ctx, review)
    before = inventory(tmp_path)
    with pytest.raises(TargetError): approve_requirement(model, operation, **fields)
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('guard', ['expected_revision', 'expected_sha256'])
def test_saved_plan_preconditions_are_not_waived_by_valid_approval(tmp_path, guard):
    from specroad.changes import prepare_change_target
    from specroad.changes.folding_values import FoldError
    from test_requirement_reapproval import SCOPE
    model, operation, fields, records = ready_project(tmp_path / 'project')
    condition = {'kind': 'artifact', 'artifact_id': operation.data['target'],
                 guard: 1 if guard == 'expected_revision' else 'f' * 64}
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(FoldError):
        prepare_change_target(model, [operation.data], policy=POLICY, gates=registered(model, operation, fields),
            change_plan_id=fields['change_plan_id'], request_id=fields['request_id'], actor=fields['actor'],
            planned_at=fields['planned_at'], scope_descriptor=SCOPE,
            metadata_policy_version='change-metadata-v1', preconditions=[condition])
    assert inventory(tmp_path) == before
