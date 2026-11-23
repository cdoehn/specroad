"""Explicit explanation inputs for native raw-command Proposal redirection."""
from copy import deepcopy
from ..changes.request_ids import AuthoringError
from ..model.identities import allocate_artifact_identity
from ..model.identity_values import artifact_identity
from ..model.canonical import canonical_json_bytes as jcs
from ..proposals.change_ids import allocate_change_id


def proposal_metadata(fields, sources, plan, *, recorded=None):
    if (type(fields) is not dict or set(fields) - {'title', 'rationale', 'changes', 'model_provenance'}
            or not {'title', 'rationale', 'changes'} <= set(fields)
            or type(fields['changes']) is not list or len(fields['changes']) != 1):
        raise AuthoringError('proposal_explicit_metadata_required')
    explanation = fields['changes'][0]
    if type(explanation) is not dict or set(explanation) != {
            'rationale', 'requirement_or_issue_ids', 'sources', 'assumptions', 'confidence'}:
        raise AuthoringError('proposal_explicit_explanation_required')
    identity = (allocate_artifact_identity('proposal', sources.identities).identity if recorded is None
                else artifact_identity(recorded))
    rows=[]
    from ..changes.plan_source_operation import explanation_targets
    if recorded is not None and len(recorded['changes']) != len(plan.operations):
        raise AuthoringError('proposal_request_conflict', exit_code=6)
    for index, operation in enumerate(plan.operations):
        change_id = allocate_change_id(tuple(row['change_id'] for row in rows)) if recorded is None else recorded['changes'][index]['change_id']
        targets = explanation_targets(operation.data) if operation.op == 'plan_edit' else list(operation.result_ids)
        rows.append({**deepcopy(explanation),'change_id':change_id,'targets':targets})
    result = {**deepcopy(fields), 'identity':identity, 'changes':rows}
    if recorded is not None:
        from ..proposals.authoring import prepare_proposal
        if prepare_proposal(change_plan=plan, **result).source_bytes != jcs(recorded):
            raise AuthoringError('proposal_request_conflict', exit_code=6)
    return result
