"""Pure Apply result projection shared by preview, completion and replay."""
from ._apply_control import operation_proof
from ._check_report import _now
from .values import SPECIFICATION_SCOPE


def _result(operations, completion, audit, *, dry_run=False, replayed=False):
    from ..changes.values import ChangeOperation
    from ..cli.result_schemas import validate_result_document
    control = operations[-1]
    _, proof = operation_proof(control)
    created = set()
    affected = set()
    for op in operations:
        ids = ChangeOperation(op).result_ids
        affected.update(ids)
        if op['op'] in ('create', 'evidence_record', 'relation_review_record'):
            field = {'create': 'artifact', 'evidence_record': 'evidence', 'relation_review_record': 'record'}[op['op']]
            created.add(op[field]['id'])
    audit.update(proposal_id=control['target'], base={'scope_descriptor': SPECIFICATION_SCOPE, 'model_root_sha256': control['base_model_root_sha256']},
        ended_at=_now(), outcome='dry_run' if dry_run else 'replayed' if replayed else 'committed',
        created_ids=sorted(created), changed_ids=sorted(affected - created), removed_ids=[])
    value = dict(format_version='proposal-apply-v1', proposal_id=control['target'],
        revision=control['expected_revision'] + 1, content_revision=control['content_revision'],
        content_sha256=control['content_sha256'], base_model_root_sha256=control['base_model_root_sha256'],
        change_plan_sha256=control['change_plan_sha256'], proposal_status='applied', maturity='applied',
        dry_run=dry_run, replayed=replayed, project_writes_performed=not dry_run and not replayed,
        approval_granted=False, write_authorized=False,
        completion=None if completion is None else completion.data, audit=audit)
    validate_result_document('proposal-apply-v1', value)
    return value
