"""Current native review inputs versus passive, original Restore evidence.

Human decisions and verifiers here are synthetic test fixtures, not real reviews.
"""
from hashlib import sha256
import shutil

import pytest

from specroad.changes.review_record import review_context, prepare_review_record
from specroad.model.identity_values import artifact_identity
from specroad.recovery import (RestoreServices, RequirementReviewInputs, RestorePlan,
    RestoreError, prepare_restore_plan, execute_restore, verify_restore_plan)
from specroad.validation import ApprovalContext, HumanRequirementReview
from support.approval import values, review_data, verifier, prerequisites, QUALITY_FIELDS
from support.records import record_value, ref
from support.restore import restore_case
from support.read_only import no_write_attempts, inventory
from test_restore_invocation import authority


def approved_project(tmp_path, kind='functional', source_kind='project_bundle'):
    records = values(kind, maturity='approved')
    requirement, source, verification = records
    source['content_sha256'] = sha256(b'original source').hexdigest()
    verification['subjects'] = [requirement['id']]
    if kind == 'quality':
        requirement['thresholds'] = [{'property': 'latency', 'method': 'timestamp difference',
            'comparison': 'lte', 'target': {'value': 5, 'unit': 'ms'}}]
    if kind == 'interface':
        from support.domain import domain_value
        component = domain_value('component')
        requirement['scope'] = {'boundary': component['id']}
        records.append(component)
    for index, edge in enumerate(requirement['relations']):
        context = review_context(records, requirement['id'], edge['relation_id'])
        identity = artifact_identity(record_value('relation_review', id=ref('RREV', str(index))))
        records.append(prepare_review_record(context, identity,
            actor={'actor_type': 'human', 'actor_id': 'synthetic-reviewer'},
            planned_at='2026-10-01T00:00:00Z', decision='confirmed', reason='Synthetic fixture'))
    records.append(record_value('document'))
    return restore_case(tmp_path, source_kind, values=records)[0]


def services(*, fault=None, calls=None, kind='functional'):
    def inputs(model, identity):
        if calls is not None:
            calls.append(identity)
        context = ApprovalContext(identity, model.documents, profile=model.profile,
            configuration=model.configuration.data, mode='stored',
            quality_fields=QUALITY_FIELDS if kind == 'quality' else (),
            interface_fields=('/scope/boundary',) if kind == 'interface' else ())
        data = review_data(context)
        if fault == 'rejected':
            data['decision'] = 'rejected'
        elif fault == 'nonhuman':
            data['reviewer']['actor_type'] = 'ai'
        elif fault == 'foreign':
            data['input_sha256'] = '0' * 64
        elif fault == 'criteria':
            data['criteria'] = {}
        return RequirementReviewInputs(context, HumanRequirementReview(data),
            verifier(authenticated=fault != 'unauthenticated', current=fault != 'stale'),
            () if fault == 'prerequisite' else prerequisites(context))
    return RestoreServices(requirement_review=inputs,
                           source_content=lambda model, record: b'original source')


@pytest.mark.parametrize('source_kind', ['project_bundle', 'baseline'])
@pytest.mark.parametrize('kind', ['functional', 'quality', 'interface'])
def test_current_complete_native_reviews_allow_plan_and_real_publication(tmp_path, source_kind, kind):
    options = approved_project(tmp_path, source_kind=source_kind, kind=kind)
    calls = []
    native = services(calls=calls, kind=kind)
    plan = prepare_restore_plan(**options, services=native)
    assert calls
    observed = len(calls)
    outcome = execute_restore(plan.source_bytes, expected_target_root=plan.data['expected_target_root'],
        authority=authority(), actor={'actor_type': 'human', 'actor_id': 'synthetic-owner'},
        services=native)
    assert outcome.data['result'] == 'restored'
    assert len(calls) > observed


@pytest.mark.parametrize('fault', ['rejected', 'nonhuman', 'foreign', 'criteria',
                                  'unauthenticated', 'stale', 'prerequisite'])
def test_current_approval_does_not_trust_a_stored_status_or_review_label(tmp_path, fault):
    options = approved_project(tmp_path)
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(RestoreError):
        prepare_restore_plan(**options, services=services(fault=fault))
    assert inventory(tmp_path) == before


def test_passive_plan_survives_root_loss_but_is_not_current_qualification(tmp_path):
    options = approved_project(tmp_path)
    plan = prepare_restore_plan(**options, services=services())
    shutil.rmtree(options['source_root'])
    shutil.rmtree(options['project_root'])
    with no_write_attempts():
        assert RestorePlan(plan.source_bytes).source_bytes == plan.source_bytes
        with pytest.raises(RestoreError, match='review_provider_required'):
            verify_restore_plan(plan.source_bytes)


def test_each_new_forward_attempt_rechecks_the_host_verifier_before_any_write(tmp_path):
    options = approved_project(tmp_path)
    plan = prepare_restore_plan(**options, services=services())
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(RestoreError):
        execute_restore(plan.source_bytes, expected_target_root=plan.data['expected_target_root'],
            authority=authority(), actor={'actor_type': 'human', 'actor_id': 'synthetic-owner'},
            services=services(fault='stale'))
    assert inventory(tmp_path) == before
