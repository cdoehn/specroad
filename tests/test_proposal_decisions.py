"""Human decision/quorum through the actual writer, checks and public entrypoints."""
import json
from base64 import b64decode
from hashlib import sha256

import pytest

from specroad.cli.application import dispatch_result, execute_request
from specroad.cli.invocation_context import InvocationContextBuilder
from specroad.cli.result_schemas import validate_result_document
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.model.errors import ModelError
from specroad.proposals.history import assess_proposal
from specroad.authoring._inspection_snapshot import InspectionSnapshot
from support.proposal_decisions import ReviewCase
from support.read_only import inventory


def test_distinct_humans_reach_quorum_with_exactly_one_revision_per_decision(tmp_path):
    case = ReviewCase(tmp_path / 'project')
    before = case.original
    initial = inventory(case.root)
    first = case.decide()
    assert (first['proposal_status'], first['revision']) == ('in_review', 3)
    assert first['review_validity'] == dict(current_approval=False, effective_human_approvals=1, minimum_human_approvals=2)
    assert case.original.data['control_history'] == before.data['control_history']
    assert len(case.original.data['reviews']) == 1
    second = case.decide('reviewer-two')
    assert (second['proposal_status'], second['revision']) == ('approved', 4)
    assert second['review_validity'] == dict(current_approval=True, effective_human_approvals=2, minimum_human_approvals=2)
    final = case.original.data
    assert final['content_revision'] == before.data['content_revision']
    assert case.original.binding == before.binding
    assert final['change_plan'] == before.data['change_plan']
    assert final['control_history'][:-1] == before.data['control_history']
    assert final['control_history'][-1]['from'] == 'in_review'
    assert final['control_history'][-1]['to'] == 'approved'
    current = {row[0]: row for row in inventory(case.root)}
    for row in initial:
        if row[0] != before.path:
            assert current[row[0]] == row
    for index, row in enumerate(final['reviews']):
        raw = b64decode(row['result_bytes_base64'], validate=True)
        proof = json.loads(raw)
        assert row['result_sha256'] == sha256(raw).hexdigest()
        assert raw == canonical_json_bytes(proof)
        assert proof['result_sha256'] == canonical_json_sha256({k: v for k, v in proof.items() if k != 'result_sha256'})
        assert row['binding'] == before.binding.data
        assert row['observed_revision'] == index + 2
        assert row['comment'].endswith('statement and normative_force')
        assert proof['native_check']['qualification'] == 'complete_native_model_and_plan_checks'
        assert not proof['native_check']['write_authorized']
    model = InspectionSnapshot(case.root, None).model
    observed = assess_proposal(case.original, case.inputs(model, case.original), model, services=case.services)
    assert observed['current_approval'] and observed['effective_human_approvals'] == 2
    validate_result_document('proposal-review-v1', second)
    assert second['completion']['current_target_verified'] is True


def test_review_dry_run_qualifies_without_journal_receipt_or_proposal_writes(tmp_path):
    case = ReviewCase(tmp_path / 'project', minimum=1)
    before = inventory(case.root)
    result = case.decide(dry_run=True, authority=None, comment=None)
    assert inventory(case.root) == before
    assert result['proposal_status'] == 'approved' and result['dry_run']
    assert result['completion'] is None and not result['project_writes_performed']
    assert result['comment'] is None
    validate_result_document('proposal-review-v1', result)
    # Public field validation must preserve the optional text contract.
    for invalid in (0, True, [], {}):
        with pytest.raises(ModelError):
            validate_result_document('proposal-review-v1', {**result, 'comment': invalid})
    assert case.original.data['revision'] == 2


def test_explicit_rejection_is_a_human_decision_and_keeps_content_binding(tmp_path):
    case = ReviewCase(tmp_path / 'project')
    before = case.original
    result = case.decide(decision='rejected', comment='The proposed statement is not acceptable')
    assert result['proposal_status'] == 'rejected' and not result['approval_granted']
    assert case.original.binding == before.binding
    assert case.original.data['reviews'][-1]['decision'] == 'rejected'
    assert case.original.data['control_history'][-1]['to'] == 'rejected'


def test_argv_and_structured_review_share_real_host_context_and_dry_run_contract(tmp_path):
    case = ReviewCase(tmp_path / 'project', minimum=1)
    context = InvocationContextBuilder(restore_services=case.services)
    options = {'--expected-revision': '2', '--decision': 'approved', '--actor-type': 'human',
               '--actor-id': 'reviewer', '--dry-run': True, '--comment': 'Explicit decision'}
    before = inventory(case.root)
    # Relative input follows the caller's cwd, independently of project selection.
    for cwd, operand, selected_options in (
            (case.root, case.original.path, options),
            (tmp_path, 'project/' + case.original.path, {**options, '--project': str(case.root)})):
        argv = ['proposal', 'review', operand]
        for key, value in selected_options.items():
            argv.extend([key] if value is True else [key, value])
        first = dispatch_result(argv, cwd=cwd, context_builder=context)
        assert first.exit_code == 0, first.as_dict()
        second = execute_request({'command_id': 'proposal.review', 'arguments': {'proposal': operand},
                                  'options': selected_options}, cwd=cwd, context_builder=context).result
        assert second.exit_code == 0, second.as_dict()
        assert first.result == second.result
        for result in (first, second):
            assert result.project['project_root'] == str(case.root)
            assert result.result['dry_run'] and not result.result['project_writes_performed']
            assert result.result['completion'] is None
            validate_result_document('proposal-review-v1', result.as_dict()['result'])
        assert case.original.data['revision'] == 2
        assert inventory(case.root) == before
