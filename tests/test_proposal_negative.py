"""Explicit human negative decisions, retained history and native transactions."""
import json
from base64 import b64decode

import pytest

from specroad.authoring._inspection_snapshot import InspectionSnapshot
from specroad.cli.application import dispatch_result, execute_request
from specroad.cli.invocation_context import InvocationContextBuilder
from specroad.cli.result_schemas import validate_result_document
from specroad.proposals.history import assess_proposal
from specroad.proposals.errors import ProposalError
from specroad.proposals.review_decision import review_project
from support.proposal_decisions import ReviewCase
from support.read_only import inventory


def test_own_withdrawal_under_quorum_preserves_history_and_can_be_reviewed_again(tmp_path):
    case = ReviewCase(tmp_path / 'project')
    case.decide()
    before = case.original
    result = case.decide(decision='withdrawn', comment='My previous approval is withdrawn')
    after = case.original
    assert result['proposal_status'] == 'in_review' and result['revision'] == 4
    assert not result['approval_granted'] and not result['review_validity']['current_approval']
    assert result['review_validity']['effective_human_approvals'] == 0
    assert after.binding == before.binding
    assert after.data['reviews'][:-1] == before.data['reviews']
    assert after.data['control_history'] == before.data['control_history']
    row = after.data['reviews'][-1]
    assert row['format_version'] == 'proposal-review-v2' and row['decision'] == 'withdrawn'
    assert json.loads(b64decode(row['result_bytes_base64']))['format_version'] == 'proposal-review-assessment-v2'
    assert result['completion']['current_target_verified']
    assert case.decide('reviewer-two')['proposal_status'] == 'in_review'
    assert case.decide()['proposal_status'] == 'approved'
    assert [r['decision'] for r in case.original.data['reviews']] == [
        'approved', 'withdrawn', 'approved', 'approved']


@pytest.mark.parametrize('decision', ['withdrawn', 'rejected'])
def test_negative_decision_after_approval_is_terminal_and_retains_content(tmp_path, decision):
    case = ReviewCase(tmp_path / 'project', minimum=1)
    case.decide()
    before = case.original
    result = case.decide(decision=decision, comment='Explicit human reason')
    assert result['proposal_status'] == 'rejected' and result['revision'] == 4
    assert not result['approval_granted'] and result['project_writes_performed']
    assert case.original.binding == before.binding
    assert case.original.data['change_plan'] == before.data['change_plan']
    assert case.original.data['reviews'][:-1] == before.data['reviews']
    assert case.original.data['control_history'][:-1] == before.data['control_history']
    event = case.original.data['control_history'][-1]
    assert (event['from'], event['to']) == ('approved', 'rejected')
    assert event['reason'] == ('human_withdrawal' if decision == 'withdrawn' else 'human_review')
    model = InspectionSnapshot(case.root, None).model
    report = assess_proposal(case.original, case.inputs(model, case.original), model, services=case.services)
    assert report['historical_valid'] and not report['current_approval']
    observed = inventory(case.root)
    with pytest.raises(Exception):
        case.decide(decision='withdrawn', comment='No mutation of a terminal revision')
    assert inventory(case.root) == observed


def test_explicit_rejection_of_draft_uses_existing_writer_without_review_start(tmp_path):
    case = ReviewCase(tmp_path / 'project', start=False)
    before = case.original
    result = case.decide(decision='rejected', comment=None)
    assert result['proposal_status'] == 'rejected' and result['revision'] == 2
    assert case.original.binding == before.binding
    assert [(e['from'], e['to']) for e in case.original.data['control_history']] == [('draft', 'rejected')]
    assert case.original.data['reviews'][0]['format_version'] == 'proposal-review-v2'
    assert result['completion']['current_target_verified'] and not result['approval_granted']


@pytest.mark.parametrize('own_approval', [False, True])
def test_one_human_cannot_withdraw_another_humans_approval(tmp_path, own_approval):
    case = ReviewCase(tmp_path / 'project')
    if own_approval:
        case.decide()
    before = inventory(case.root)
    with pytest.raises(Exception) as error:
        case.decide('other-human', decision='withdrawn', comment='Cannot withdraw for another person')
    assert error.value.exit_code == 7 and error.value.reason == 'proposal_own_approval_required'
    assert inventory(case.root) == before


@pytest.mark.parametrize('actor_type', ['ai', 'ci', 'tool'])
def test_machine_cannot_withdraw_even_using_the_human_actor_id(tmp_path, actor_type):
    case = ReviewCase(tmp_path / 'project')
    case.decide()
    before = inventory(case.root)
    options = case.options(decision='withdrawn')
    # The convenience helper takes a reviewer ID; supply a full actor to the native API.
    options['actor'] = {'actor_type': actor_type, 'actor_id': 'reviewer-one'}
    with pytest.raises(ProposalError) as error:
        review_project(case.root, case.original.data['id'], **options)
    assert error.value.exit_code == 7 and error.value.reason == 'human_review_required'
    assert inventory(case.root) == before


@pytest.mark.parametrize('comment', [None, '', ' \n '])
def test_withdrawal_requires_reason_before_accessing_project(tmp_path, comment):
    with pytest.raises(Exception) as error:
        review_project(tmp_path / 'not-created', 'unused', expected_revision=1, decision='withdrawn',
            actor={'actor_type': 'human', 'actor_id': 'reviewer'}, planned_at='2026-11-12T00:00:00Z',
            change_plan_id='plan', transaction_id='transaction', dry_run=True, comment=comment)
    assert error.value.exit_code == 2 and error.value.reason == 'proposal_withdrawal_reason_required'
    assert not (tmp_path / 'not-created').exists()


def test_public_argv_and_structured_withdrawal_share_dry_run_and_real_publication(tmp_path):
    case = ReviewCase(tmp_path / 'project', minimum=1)
    case.decide()
    context = InvocationContextBuilder(restore_services=case.services, publication_authority=case.authority)
    options = {'--expected-revision': '3', '--decision': 'withdrawn', '--actor-type': 'human',
        '--actor-id': 'reviewer-one', '--comment': 'Explicit withdrawal', '--dry-run': True}
    before = inventory(case.root)
    argv = ['proposal', 'review', case.original.data['id']]
    for key, value in options.items():
        argv.extend([key] if value is True else [key, value])
    first = dispatch_result(argv, cwd=case.root, context_builder=context)
    second = execute_request({'command_id': 'proposal.review', 'arguments': {'proposal': case.original.data['id']},
        'options': options}, cwd=case.root, context_builder=context).result
    assert first.exit_code == second.exit_code == 0, (first.as_dict(), second.as_dict())
    assert first.result == second.result
    assert first.result['proposal_status'] == 'rejected' and first.result['dry_run']
    assert first.result['completion'] is None and not first.result['project_writes_performed']
    for outcome in (first, second):
        validate_result_document('proposal-review-v1', outcome.as_dict()['result'])
    assert inventory(case.root) == before
    options.pop('--dry-run')
    committed = execute_request({'command_id': 'proposal.review', 'arguments': {'proposal': case.original.data['id']},
        'options': options}, cwd=case.root, context_builder=context).result
    assert committed.exit_code == 0, committed.as_dict()
    case.capture()
    assert case.original.data['revision'] == 4 and case.original.data['proposal_status'] == 'rejected'
    assert committed.result['completion']['current_target_verified']
    validate_result_document('proposal-review-v1', committed.as_dict()['result'])
