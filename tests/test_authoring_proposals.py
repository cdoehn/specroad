"""Same native target, isolated draft, real writer/receipt and preserved defaults."""
import pytest
from specroad.authoring.execution import apply_authoring_plan
from specroad.authoring.proposals import prepare_authoring_proposal
from specroad.changes import PublicationAuthority
from specroad.model.canonical import canonical_json_bytes as jcs
from specroad.proposals.context import ProposalContext, reconstruct_proposal_target
from support.authoring_execution import KINDS, scenario, preview, saved
from support.authoring_proposals import planned, metadata
from support.read_only import no_write_attempts, inventory


@pytest.mark.parametrize('kind', KINDS)
def test_same_complete_authoring_plan_and_defaults_are_embedded(tmp_path, kind):
    model, command, op, options, _, _ = scenario(tmp_path/'source', kind)
    plan = saved(preview(model, command, op, options)); before = inventory(tmp_path/'source')
    with no_write_attempts():
        proposal = prepare_authoring_proposal(plan, model, command_id=command,
            proposal_fields=metadata(plan), gates=options['gates'])
    inner = proposal.data['change_plan']
    for key in ('operations', 'result_artifacts', 'preconditions', 'actor', 'planned_at', 'request_id'):
        assert inner[key] == plan.data[key]
    target = reconstruct_proposal_target(ProposalContext(proposal.original, model))
    assert {a['id']: a for a in target.artifacts}.items() >= {
        row['artifact']['id']: row['artifact'] for row in plan.data['result_artifacts']}.items()
    assert proposal.data['revision'] == proposal.data['content_revision'] == 1
    assert proposal.data['proposal_status'] == proposal.data['maturity'] == 'draft'
    assert proposal.data['reviews'] == proposal.data['control_history'] == []
    assert not proposal.write_authorized and inventory(tmp_path/'source') == before


def test_native_writer_changes_only_the_draft_and_replays_exact_receipt(tmp_path):
    root = tmp_path/'source'; model, plan, gates = planned(root)
    calls = []
    def authorize(request):
        from specroad.changes import inspect_project_lock
        assert inspect_project_lock(root).data['record']['kind'] == 'writer'
        calls.append(request.plan.sha256)
        assert [op.op for op in request.plan.operations] == ['proposal_create']
        return True
    options = dict(command_id='artifact.update', proposal_fields=metadata(plan), gates=gates,
        as_proposal=True, authority=PublicationAuthority('owned-test-host', '1', authorize))
    result = apply_authoring_plan(plan, model, transaction_id='txn-proposal-create', **options)
    assert result['write_state'] == 'committed' and not result['approval_granted']
    assert result['completion']['current_target_verified'] and calls
    for path, raw in model.source_files.items():
        assert (root/path).read_bytes() == raw
    assert (root/result['proposal_path']).read_bytes() == jcs(result['proposal'])
    before = inventory(root); count = len(calls)
    replay = apply_authoring_plan(plan, model, transaction_id='txn-proposal-retry', **options)
    assert replay['replayed'] and replay['completion']['receipts'] == result['completion']['receipts']
    assert not replay['completion']['current_target_verified']
    assert inventory(root) == before and len(calls) == count
