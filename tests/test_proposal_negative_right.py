"""Negative reviews cannot fabricate history, reuse stale approval, or bypass gates."""
import json
from base64 import b64decode, b64encode
from dataclasses import replace
from hashlib import sha256

import pytest

from specroad.authoring._inspection_snapshot import InspectionSnapshot
from specroad.changes import PublicationAuthority
from specroad.changes._target_materialization import materialize_target
from specroad.model.audit_values import Actor, Revision, UtcTimestamp
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.proposals import ProposalOriginal, ProposalContext
from specroad.proposals._decision_control import read_review_observations
from specroad.proposals._decision_evidence import assessment, operation, NEGATIVE_VERSION
from specroad.proposals.history import assess_proposal
from specroad.proposals.review_decision import review_project
from specroad.proposals.revisions import ProposalRevision
from specroad.validation import ModelDocument
from support.proposal_decisions import ReviewCase
from support.read_only import inventory, no_write_attempts


def test_already_withdrawn_approval_cannot_be_withdrawn_again(tmp_path):
    case = ReviewCase(tmp_path / 'project')
    case.decide()
    case.decide(decision='withdrawn')
    before = inventory(case.root)
    with pytest.raises(Exception) as error:
        case.decide(decision='withdrawn')
    assert error.value.exit_code == 7
    assert inventory(case.root) == before


def test_historical_own_approval_can_be_withdrawn_when_no_longer_effective(tmp_path):
    case = ReviewCase(tmp_path / 'project')
    case.decide()
    case.current_decisions = False
    result = case.decide(decision='withdrawn')
    assert result['proposal_status'] == 'in_review'
    assert result['review_validity']['effective_human_approvals'] == 0
    assert [r['decision'] for r in case.original.data['reviews']] == ['approved', 'withdrawn']


def test_changed_content_keeps_old_reviews_without_reusing_their_approval(tmp_path):
    case = ReviewCase(tmp_path / 'project', minimum=1)
    case.decide()
    before = case.original
    snapshot = InspectionSnapshot(case.root, None)
    candidate = before.data; candidate['rationale'] = 'New substantive rationale needs a new review'
    after = ProposalRevision(before, candidate, expected_revision=Revision(before.data['revision']),
        actor=Actor('human', 'synthetic-author'), planned_at=UtcTimestamp('2026-11-12T00:00:00Z')).after
    model = materialize_target(snapshot.model, (ModelDocument(after.path, after.source_bytes),))
    inputs = case.inputs(snapshot.model, before)
    inputs = replace(inputs, originals=(*inputs.originals, after),
        contexts=(*inputs.contexts, ProposalContext(after, model)))
    with no_write_attempts():
        report = assess_proposal(after, inputs, model, services=case.services)
    assert after.data['proposal_status'] == 'draft' and after.data['content_revision'] == 2
    assert after.data['reviews'] == before.data['reviews']
    assert report['historical_valid'] and not report['current_approval']
    assert report['effective_human_approvals'] == 0
    assert all(not row['binding_current'] for row in report['reviews'])
    assert not report['write_authorized'] and not report['apply_performed']


@pytest.mark.parametrize('fault', ['external-revocation', 'stale-basis'])
def test_visible_approved_does_not_hide_changed_qualification(tmp_path, fault):
    case = ReviewCase(tmp_path / 'project', minimum=1)
    case.decide()
    if fault == 'external-revocation':
        case.current_decisions = False
    else:
        model = InspectionSnapshot(case.root, None).model
        goal = next(d for d in model.documents if json.loads(d.content)['artifact_type'] == 'goal')
        value = json.loads(goal.content); value['statement'] = 'New specification basis'
        (case.root / goal.path).write_bytes(canonical_json_bytes(value))
    before = inventory(case.root)
    model = InspectionSnapshot(case.root, None).model
    with no_write_attempts(), pytest.raises(Exception) as error:
        assess_proposal(case.original, case.inputs(model, case.original), model, services=case.services)
    assert error.value.reason == ('proposal_current_quorum_not_met' if fault == 'external-revocation'
                                  else 'proposal_current_basis_stale')
    with pytest.raises(Exception):
        case.decide(decision='withdrawn')
    assert case.original.data['proposal_status'] == 'approved' and inventory(case.root) == before


def test_withdrawal_receipt_replays_exactly_once_and_rejects_changed_request(tmp_path):
    case = ReviewCase(tmp_path / 'project', minimum=1)
    case.decide()
    options = case.options(decision='withdrawn', request_id='withdraw-request')
    first = review_project(case.root, case.original.data['id'], **options)
    case.capture(); before = inventory(case.root)
    second = review_project(case.root, case.original.data['id'], **options)
    assert second['replayed'] and not second['project_writes_performed']
    assert first['revision'] == second['revision'] == 4
    assert first['review_validity'] == second['review_validity']
    for changed in ({'comment': 'Different reason'}, {'decision': 'rejected'}, {'expected_revision': 4},
                    {'actor': {'actor_type': 'human', 'actor_id': 'other'}}):
        with pytest.raises(Exception) as error:
            review_project(case.root, case.original.data['id'], **dict(options, **changed))
        assert error.value.exit_code == 6
    assert inventory(case.root) == before


@pytest.mark.parametrize('fault', ['denied', 'missing-originals', 'late-decision-loss'])
def test_current_authority_and_originals_are_required_for_negative_write(tmp_path, monkeypatch, fault):
    case = ReviewCase(tmp_path / 'project', minimum=1)
    case.decide()
    options = case.options(decision='withdrawn')
    if fault == 'denied':
        options['authority'] = PublicationAuthority('synthetic-denied', '1', lambda request: False)
    elif fault == 'missing-originals':
        options['services'] = None
    else:
        from specroad.proposals import _decision_checks
        native = _decision_checks.assessment
        def lost(*args, **kwargs):
            case.current_decisions = False
            return native(*args, **kwargs)
        monkeypatch.setattr(_decision_checks, 'assessment', lost)
    before = inventory(case.root)
    with pytest.raises(Exception):
        review_project(case.root, case.original.data['id'], **options)
    assert inventory(case.root) == before


def test_real_negative_staging_failure_retains_original_and_recovery_journal(tmp_path, monkeypatch):
    from specroad import changes
    case = ReviewCase(tmp_path / 'project', minimum=1)
    case.decide()
    before = case.original.source_bytes
    native = changes.stage_building_journal
    def interrupt(*args, **kwargs):
        native(*args, **kwargs)
        raise OSError('synthetic-negative-staging-failure')
    monkeypatch.setattr(changes, 'stage_building_journal', interrupt)
    options = case.options(decision='withdrawn', request_id='negative-interrupted')
    with pytest.raises(OSError, match='synthetic-negative-staging-failure'):
        review_project(case.root, case.original.data['id'], **options)
    assert (case.root / case.original.path).read_bytes() == before
    journal = case.root / '.specroad/transactions' / options['transaction_id'] / 'journal.json'
    assert json.loads(journal.read_bytes())['state'] == 'prepared'
    observed = inventory(case.root)
    with pytest.raises(Exception):
        review_project(case.root, case.original.data['id'], **options)
    assert inventory(case.root) == observed


@pytest.fixture(scope='module')
def negative_originals(tmp_path_factory):
    # Completed immutable bytes only. Every live writer/authority test has its own project.
    case = ReviewCase(tmp_path_factory.mktemp('negative-originals') / 'project', minimum=1)
    case.decide(); context = case.contexts[-1]
    case.decide(decision='withdrawn')
    return case.original, context


@pytest.mark.parametrize('fault', ['row-version', 'proof-version', 'decision', 'actor', 'history',
    'status', 'approval', 'count', 'old-row', 'control', 'extra', 'hash'])
def test_new_negative_evidence_is_closed_versioned_and_bound_to_originals(negative_originals, fault):
    original, context = negative_originals
    value = original.data; row = value['reviews'][-1]
    proof = json.loads(b64decode(row['result_bytes_base64']))
    if fault == 'row-version': row['format_version'] = 'proposal-review-v1'
    elif fault == 'proof-version': proof['format_version'] = 'proposal-review-assessment-v1'
    elif fault == 'decision': row['decision'] = 'approved'
    elif fault == 'actor': row['reviewer']['actor_id'] = 'different-human'
    elif fault == 'history':
        proof['history']['reviews'].append(dict(proof['history']['reviews'][-1], review_index=1))
    elif fault == 'status': proof['history']['observed_status'] = 'in_review'
    elif fault == 'approval': proof['history']['current_approval'] = False
    elif fault == 'count': proof['history']['effective_human_approvals'] = True
    elif fault == 'old-row': value['reviews'][0]['comment'] = 'Rewritten old decision'
    elif fault == 'control': value['control_history'][-1]['from'] = 'in_review'
    elif fault == 'extra': row['authority'] = True
    elif fault == 'hash': row['result_sha256'] = '0' * 64
    if fault in ('proof-version', 'history', 'status', 'approval', 'count'):
        proof['result_sha256'] = canonical_json_sha256({k:v for k,v in proof.items() if k != 'result_sha256'})
        raw = canonical_json_bytes(proof)
        row['result_bytes_base64'] = b64encode(raw).decode()
        row['result_sha256'] = sha256(raw).hexdigest()
    tampered = ProposalOriginal(canonical_json_bytes(value), path=original.path)
    with pytest.raises(Exception):
        read_review_observations(tampered, context)


def test_generic_change_route_cannot_publish_a_negative_review(tmp_path):
    from specroad.changes import prepare_authoring_request
    case = ReviewCase(tmp_path / 'project')
    case.decide()
    actor = case.options()['actor']
    proof = assessment(InspectionSnapshot(case.root, None), case.original, case.services, version=NEGATIVE_VERSION)
    op = operation(case.original, proof, 'withdrawn', 'Own withdrawal', actor)
    before = inventory(case.root)
    with pytest.raises(Exception) as error:
        prepare_authoring_request(command_id='change apply', actor=actor, operations=[op])
    assert error.value.reason == 'proposal_control_specialist_required'
    assert inventory(case.root) == before
