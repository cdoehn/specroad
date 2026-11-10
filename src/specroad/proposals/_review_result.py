"""Review-start outcome projection; no approval or write grant."""
from ..cli.result_schemas import validate_result_document


def _result(operation, completion, *, dry_run=False, replayed=False):
    result = dict(format_version='proposal-review-start-v1', proposal_id=operation['target'],
        revision=operation['expected_revision'] + 1, content_revision=operation['content_revision'],
        content_sha256=operation['content_sha256'], proposal_status='in_review', maturity='in_review',
        base_model_root_sha256=operation['base_model_root_sha256'],
        change_plan_sha256=operation['change_plan_sha256'], changed_change_ids=[],
        review_validity=dict(current_approval=False, human_decision_required=True),
        dry_run=dry_run, replayed=replayed, project_writes_performed=not dry_run and not replayed,
        approval_granted=False, write_authorized=False,
        completion=None if completion is None else completion.data)
    validate_result_document('proposal-review-start-v1', result)
    return result
