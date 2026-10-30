"""Actual native input bindings with explicitly synthetic original decisions."""
from copy import deepcopy
from dataclasses import replace
from hashlib import sha256

import pytest

from specroad.changes._target_materialization import materialize_target
from specroad.model.audit_values import Actor, UtcTimestamp
from specroad.model.canonical import canonical_json_bytes
from specroad.proposals import (ProposalContext, ProposalInputs, ProposalReviewObservation,
    ProposalControlObservation, ProposalVerification, ProposalVerifier, assess_proposal, ProposalError)
from specroad.proposals.history import native_check
from specroad.storage.json_syntax import parse_json_object
from specroad.validation import ModelDocument
from support.read_only import no_write_attempts
from test_proposal_originals import draft, original


HUMAN = Actor('human', 'synthetic-reviewer')


def verifier(*, current=True, origin=True, calls=None):
    def check(inputs):
        item = inputs.observation
        row = parse_json_object(item.row_bytes)
        if calls is not None:
            calls.append(inputs.sha256)
        assert row['binding'] == item.binding.data
        assert row['actor'] == (item.reviewer if type(item) is ProposalReviewObservation else item.actor).as_fields()
        if type(item) is ProposalReviewObservation:
            assert row['decision'] == item.decision and row['at'] == item.reviewed_at.value
            assert row['observed_revision'] == item.observed_revision
        else:
            assert item.result_bytes == inputs.native_result
            assert row['at'] == item.occurred_at.value
        return ProposalVerification(inputs.sha256, sha256(item.row_bytes).hexdigest(), origin, origin, current)
    return ProposalVerifier('synthetic-original-decisions', '1', check)


def history(tmp_path, *, actors=(HUMAN,), minimum=1, status='approved', decision='approved', draft_factory=draft):
    model, value = draft_factory(tmp_path)
    if minimum != 1:
        from specroad.changes.target_model import TargetModel
        configuration = model.configuration.data
        configuration['validation_policy']['minimum_human_proposal_approvals'] = minimum
        model = TargetModel(canonical_json_bytes(configuration), model.binding, model.documents,
            profile=model.profile, resource_files=model.resource_files)
        from specroad.proposals.context import specification_manifest
        from specroad.changes.core import prepare_change_plan
        plan = value['change_plan']; plan.pop('change_plan_sha256')
        plan['base']['model_root_sha256'] = specification_manifest(model).sha256
        plan['expected_result']['model_root_sha256'] = plan['base']['model_root_sha256']
        value['change_plan'] = prepare_change_plan(plan).data
        value['base'] = value['change_plan']['base']
        from specroad.proposals.values import content_sha256
        value['content_sha256'] = content_sha256(value)
    originals, contexts, reviews, controls = [], [], [], []
    first = original(value)
    originals.append(first); contexts.append(ProposalContext(first, model))

    def write(*, next_status, events, actor=HUMAN, review=None):
        before = originals[-1]
        context = contexts[-1]
        raw_result = native_check(context)
        value = deepcopy(before.data)
        value['revision'] += 1
        time = '2026-10-29T00:00:%02dZ' % value['revision']
        value['updated_at'], value['updated_by'] = time, actor.as_fields()
        value['proposal_status'] = next_status
        from specroad.model.record_contracts import SPECIAL_STATES
        value['maturity'] = SPECIAL_STATES['proposal'][1][next_status]
        start = len(value['control_history'])
        for old, new in events:
            value['control_history'].append({'from': old, 'to': new, 'reason': 'Synthetic observed check',
                'result_sha256': sha256(raw_result).hexdigest(), 'binding': before.binding.data,
                'actor': actor.as_fields(), 'at': time})
        if review is not None:
            value.setdefault('reviews', []).append({'binding': before.binding.data,
                'actor': actor.as_fields(), 'decision': review, 'at': time,
                'observed_revision': before.data['revision']})
        saved = original(value)
        originals.append(saved); contexts.append(ProposalContext(saved, model))
        for index, (old, new) in enumerate(events, start):
            controls.append(ProposalControlObservation(saved, index, context, actor,
                UtcTimestamp(time), old, new, 'Synthetic observed check', raw_result))
        if review is not None:
            reviews.append(ProposalReviewObservation(saved, len(reviews), context, actor,
                UtcTimestamp(time), review, before.data['revision']))

    write(next_status='in_review', events=[('draft', 'validated'), ('validated', 'checked'),
                                          ('checked', 'in_review')])
    for index, actor in enumerate(actors):
        final = index == len(actors) - 1
        end = status if final else 'in_review'
        events = [('in_review', end)] if end != 'in_review' else []
        write(next_status=end, events=events, actor=actor, review=decision)
    inputs = ProposalInputs(tuple(originals), tuple(contexts), tuple(reviews), tuple(controls), verifier())
    current = materialize_target(model, (ModelDocument(originals[-1].path, originals[-1].source_bytes),))
    return inputs, current


def test_control_revisions_preserve_review_binding_and_real_distinct_quorum(tmp_path):
    inputs, model = history(tmp_path, actors=(HUMAN, Actor('human', 'synthetic-second')), minimum=2)
    with no_write_attempts():
        report = assess_proposal(inputs.originals[-1], inputs, model)
    assert report['historical_valid'] and report['current_approval']
    assert report['effective_human_approvals'] == 2
    assert not report['write_authorized'] and not report['apply_performed']


@pytest.mark.parametrize('actors', [(HUMAN,), (HUMAN, HUMAN), (HUMAN, Actor('ai', 'synthetic-ai'))])
def test_missing_duplicate_and_nonhuman_approvals_cannot_fill_quorum(tmp_path, actors):
    inputs, model = history(tmp_path, actors=actors, minimum=2)
    with no_write_attempts(), pytest.raises(ProposalError, match='quorum_not_met'):
        assess_proposal(inputs.originals[-1], inputs, model)


@pytest.mark.parametrize('fault', ['current', 'origin', 'binding', 'missing_context', 'missing_control', 'missing_review'])
def test_original_contexts_and_fresh_verifiers_are_required(tmp_path, fault):
    inputs, model = history(tmp_path)
    if fault == 'current':
        inputs = replace(inputs, verifier=verifier(current=False))
    elif fault == 'origin':
        inputs = replace(inputs, verifier=verifier(origin=False))
    elif fault == 'binding':
        def forged(binding):
            return ProposalVerification('0' * 64, '0' * 64, True, True, True)
        inputs = replace(inputs, verifier=ProposalVerifier('synthetic-forged', '1', forged))
    elif fault == 'missing_context':
        inputs = replace(inputs, contexts=inputs.contexts[:-1])
    elif fault == 'missing_control':
        inputs = replace(inputs, controls=inputs.controls[:-1])
    else:
        inputs = replace(inputs, reviews=())
    with no_write_attempts(), pytest.raises(ProposalError):
        assess_proposal(inputs.originals[-1], inputs, model)


def test_stale_current_basis_does_not_erase_valid_rejected_history(tmp_path):
    inputs, model = history(tmp_path, status='rejected', decision='rejected')
    goal = next(a for a in model.artifacts if a['artifact_type'] == 'goal')
    goal['statement'] = 'Subsequent valid project content'
    from specroad.model.paths import artifact_path
    model = materialize_target(model, (ModelDocument(artifact_path('goal', goal['id'], 'SR'),
                                                    canonical_json_bytes(goal)),))
    with no_write_attempts():
        report = assess_proposal(inputs.originals[-1], inputs, model)
    assert report['historical_valid'] and not report['current_basis_matches']
    assert not report['current_approval'] and report['reviews'][0]['decision'] == 'rejected'


def test_active_checks_reobserve_the_same_trusted_verifier(tmp_path):
    inputs, model = history(tmp_path)
    calls = []
    inputs = replace(inputs, verifier=verifier(calls=calls))
    assess_proposal(inputs.originals[-1], inputs, model)
    first = len(calls)
    assess_proposal(inputs.originals[-1], inputs, model)
    assert len(calls) == 2 * first and first > 0


@pytest.mark.parametrize('status,decision', [('stale', 'approved'), ('rejected', 'rejected')])
def test_terminal_negative_originals_keep_their_original_bytes(tmp_path, status, decision):
    inputs, model = history(tmp_path, status=status, decision=decision)
    raw = inputs.originals[-1].source_bytes
    with no_write_attempts():
        report = assess_proposal(inputs.originals[-1], inputs, model)
    assert report['historical_valid'] and not report['current_approval']
    assert report['observed_status'] == status
    assert inputs.originals[-1].source_bytes == raw


def test_current_approved_cannot_hide_a_different_actual_basis(tmp_path):
    inputs, model = history(tmp_path)
    goal = next(a for a in model.artifacts if a['artifact_type'] == 'goal')
    goal['statement'] = 'Subsequent project content'
    from specroad.model.paths import artifact_path
    model = materialize_target(model, (ModelDocument(artifact_path('goal', goal['id'], 'SR'),
                                                    canonical_json_bytes(goal)),))
    with no_write_attempts(), pytest.raises(ProposalError, match='current_basis_stale'):
        assess_proposal(inputs.originals[-1], inputs, model)


def test_content_edit_resets_status_and_does_not_reuse_previous_approvals(tmp_path):
    inputs, model = history(tmp_path)
    before = inputs.originals[-1]
    value = deepcopy(before.data)
    value.update(revision=value['revision'] + 1, content_revision=2,
                 updated_at='2026-10-29T00:00:04Z', rationale='New reviewed content is needed',
                 maturity='draft', proposal_status='draft')
    from specroad.proposals.values import content_sha256
    value['content_sha256'] = content_sha256(value)
    saved = original(value)
    inputs = replace(inputs, originals=(*inputs.originals, saved),
                     contexts=(*inputs.contexts, ProposalContext(saved, inputs.contexts[-1].basis)))
    model = materialize_target(model, (ModelDocument(saved.path, saved.source_bytes),))
    with no_write_attempts():
        report = assess_proposal(saved, inputs, model)
    assert report['historical_valid'] and not report['current_approval']
    assert report['effective_human_approvals'] == 0
    assert not report['reviews'][0]['binding_current']


def test_actual_withdrawal_removes_that_actor_from_quorum(tmp_path):
    inputs, model = history(tmp_path, actors=(HUMAN,), status='in_review')
    prior = inputs.originals[-1]
    context = inputs.contexts[-1]
    value = deepcopy(prior.data)
    time = '2026-10-29T00:00:04Z'
    value.update(revision=value['revision'] + 1, updated_at=time)
    value['reviews'].append({'binding': prior.binding.data, 'actor': HUMAN.as_fields(),
        'decision': 'withdrawn', 'at': time, 'observed_revision': prior.data['revision']})
    saved = original(value)
    observation = ProposalReviewObservation(saved, 1, context, HUMAN, UtcTimestamp(time),
                                            'withdrawn', prior.data['revision'])
    inputs = replace(inputs, originals=(*inputs.originals, saved),
        contexts=(*inputs.contexts, ProposalContext(saved, context.basis)),
        reviews=(*inputs.reviews, observation))
    model = materialize_target(model, (ModelDocument(saved.path, saved.source_bytes),))
    with no_write_attempts():
        report = assess_proposal(saved, inputs, model)
    assert report['historical_valid'] and report['effective_human_approvals'] == 0
    assert report['reviews'][-1]['decision'] == 'withdrawn'
    assert not report['current_approval']


def test_later_repetition_cannot_replace_the_original_review_observation(tmp_path):
    inputs, model = history(tmp_path, actors=(HUMAN, Actor('human', 'synthetic-second')), minimum=2)
    changed = replace(inputs.reviews[0], original=inputs.originals[-1])
    inputs = replace(inputs, reviews=(changed, *inputs.reviews[1:]))
    with no_write_attempts(), pytest.raises(ProposalError, match='original_revision_mismatch'):
        assess_proposal(inputs.originals[-1], inputs, model)
