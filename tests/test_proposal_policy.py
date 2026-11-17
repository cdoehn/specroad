"""Human decisions and approved agent writes keep their native authority boundary."""
import json

import pytest

from specroad.changes import AuthoringError, prepare_authoring_request
from specroad.cli.application import dispatch_result, execute_request
from specroad.cli.invocation_context import InvocationContextBuilder
from specroad.model.errors import ModelError
from specroad.proposals.review_decision import review_project
from support.proposal_apply import ApplyCase
from support.proposal_decisions import ReviewCase
from support.proposal_policy import no_foreign_execution
from support.read_only import inventory, no_write_attempts


@pytest.mark.parametrize('kind', ['ai', 'ci', 'tool'])
@pytest.mark.parametrize('dry_run', [False, True])
@pytest.mark.parametrize('request_id', [None, 'synthetic-review-request'])
def test_proposal_review_route_never_accepts_nonhuman_decisions(kind, dry_run, request_id):
    with no_write_attempts(), pytest.raises(AuthoringError) as failed:
        prepare_authoring_request(command_id='proposal review',
            actor={'actor_type': kind, 'actor_id': 'synthetic-reviewer'}, operations=[],
            request_id=request_id, dry_run=dry_run)
    assert failed.value.exit_code == 7
    assert failed.value.reason == 'human_review_required'


def test_human_review_and_agent_authoring_previews_remain_unprivileged():
    for command, kind in [('proposal review', 'human'), ('artifact update', 'ai')]:
        with no_write_attempts():
            request = prepare_authoring_request(command_id=command, operations=[],
                actor={'actor_type': kind, 'actor_id': 'synthetic-actor'}, dry_run=True)
        assert request.data['route'] == 'preview'
        assert not request.data['actor_authenticated']
        assert not request.data['write_authorized']


@pytest.mark.parametrize('kind', ['ai', 'ci', 'tool'])
@pytest.mark.parametrize('dry_run', [False, True])
def test_native_nonhuman_review_fails_before_project_or_host_access(tmp_path, kind, dry_run):
    with no_write_attempts(), pytest.raises(ModelError) as failed:
        review_project(tmp_path / 'absent', 'unread', expected_revision=1,
            decision='approved', actor={'actor_type': kind, 'actor_id': 'synthetic-reviewer'},
            planned_at='2026-11-17T00:00:00Z', change_plan_id='synthetic-review-plan',
            transaction_id='synthetic-review', dry_run=dry_run)
    assert failed.value.exit_code == 7
    assert failed.value.reason == 'human_review_required'
    assert not (tmp_path / 'absent').exists()


@pytest.mark.parametrize('kind', ['ai', 'ci'])
@pytest.mark.parametrize('structured', [False, True])
def test_public_nonhuman_review_without_host_authority_is_a_policy_refusal(tmp_path, kind, structured):
    case = ReviewCase(tmp_path / 'project', start=False)
    options = {'--expected-revision': '1', '--decision': 'approved',
        '--actor-type': kind, '--actor-id': 'synthetic-reviewer'}
    before = inventory(case.root)
    with no_write_attempts():
        if structured:
            result = execute_request({'command_id': 'proposal.review',
                'arguments': {'proposal': case.original.data['id']}, 'options': options},
                cwd=case.root).result
        else:
            args = ['proposal', 'review', case.original.data['id']]
            for key, value in options.items():
                args.extend([key, value])
            result = dispatch_result(args, cwd=case.root)
    assert result.exit_code == 7, result.as_dict()
    assert 'human_review_required' in str(result.as_dict())
    assert inventory(case.root) == before


@pytest.mark.parametrize('kind', ['ai', 'ci'])
def test_approved_agent_apply_without_git_uses_native_authority_and_receipts(tmp_path, kind):
    case = ApplyCase(tmp_path / 'project')
    assert not (case.root / '.git').exists()
    outside = tmp_path / 'outside.bin'
    outside.write_bytes(b'External resources are not Proposal targets.\x00\xff')
    before_outside = inventory(outside)
    options = {'--expected-revision': str(case.original.data['revision']),
        '--actor-type': kind, '--actor-id': 'synthetic-applier', '--request-id': 'policy-apply'}
    host = InvocationContextBuilder(restore_services=case.services, publication_authority=case.authority)
    with no_foreign_execution():
        if kind == 'ci':
            result = execute_request({'command_id': 'proposal.apply',
                'arguments': {'proposal': case.original.data['id']}, 'options': options},
                cwd=case.root, context_builder=host).result
        else:
            args = ['proposal', 'apply', case.original.data['id']]
            for key, value in options.items():
                args.extend([key, value])
            result = dispatch_result(args, cwd=case.root, context_builder=host)
    assert result.exit_code == 0, result.as_dict()
    value = result.result
    assert value['project_writes_performed'] and value['completion']['current_target_verified']
    assert not value['approval_granted'] and not value['write_authorized']
    assert case.requests and case.requests[-1].plan.data['actor']['actor_type'] == kind
    assert case.requests[-1].plan.data['request_id'] == 'policy-apply'
    applied = json.loads((case.root / case.original.path).read_bytes())
    assert applied['proposal_status'] == 'applied'
    assert applied['reviews'] == case.original.data['reviews']
    assert all(row['reviewer']['actor_type'] == 'human' for row in applied['reviews'])
    assert inventory(outside) == before_outside and not (case.root / '.git').exists()
