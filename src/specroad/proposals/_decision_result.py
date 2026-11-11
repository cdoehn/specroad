"""Review result projection shared by first publication, dry-run and replay."""
from ..cli.result_schemas import validate_result_document
from ._decision_evidence import outcome, operation_proof


def result(operation, actor, completion, *, dry_run=False, replayed=False):
    status, count, _ = outcome(operation, actor)
    _, proof = operation_proof(operation)
    value = dict(format_version='proposal-review-v1', proposal_id=operation['target'],
        revision=operation['expected_revision'] + 1, content_revision=operation['content_revision'],
        content_sha256=operation['content_sha256'], proposal_status=status, maturity=status,
        base_model_root_sha256=operation['base_model_root_sha256'],
        change_plan_sha256=operation['change_plan_sha256'], changed_change_ids=[],
        decision=operation['review_decision']['decision'], comment=operation['review_decision']['comment'],
        review_validity=dict(current_approval=status == 'approved', effective_human_approvals=count,
            minimum_human_approvals=proof['history']['minimum_human_approvals']),
        dry_run=dry_run, replayed=replayed, project_writes_performed=not dry_run and not replayed,
        approval_granted=status == 'approved', write_authorized=False,
        completion=None if completion is None else completion.data)
    validate_result_document('proposal-review-v1', value)
    return value
