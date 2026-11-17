"""Resolve an exact prior draft request before current target qualification.

Native receipt/completion originals are mandatory. Stored roots identify the
historical request; they are never claimed as current target verification.
"""
from ..changes import prepare_authoring_request
from ..changes._lock_files import LockFiles
from ..changes.receipt_read import _read_confirmed_request, _CompletionProof
from ..changes.core import prepare_change_plan
from ..changes.normal_access import require_normal_access
from ..storage.project import ProjectSource
from ..proposals.authoring import prepare_proposal
from ..proposals._create_control import creation_mode, COMMAND
from ..proposals.values import require
from .plans import _operations


def replay_proposal(plan, model, *, command_id, proposal_fields):
    value = plan.data
    _operations(command_id, value['operations'])
    require_normal_access(model.binding.source_root, expected_project_id=model.binding.project_id)
    source = ProjectSource(model.binding.source_root, expected_project_id=model.binding.project_id)
    require(source.boundary._root_identity == model.binding.root_identity,
            'authoring_project_changed', exit_code=6)
    if value['request_id'] is None:
        return None
    receipt = _read_confirmed_request(source, value['request_id'])
    if receipt is None:
        return None
    with LockFiles(source.boundary.root) as files:
        proof = _CompletionProof(files, source, receipt.data['transaction_id'])
        journal = proof.journal.data
        binding = journal['authoring_binding']; operations = binding['operations']
        require(journal['receipts']['request'] == {'path': receipt.path, 'sha256': receipt.sha256}
            and binding['command_id'] == 'proposal create' and creation_mode(operations),
            'proposal_request_conflict', exit_code=6)
        record = operations[0]['record']
        # As with the native generic replay, compare the original request intent,
        # not a newly qualified target. Explanations and provenance are included.
        inner = {k: v for k, v in value.items() if k != 'change_plan_sha256'}
        inner.update(base=record['change_plan']['base'],
                     expected_result=record['change_plan']['expected_result'])
        require(type(proposal_fields) is dict and set(proposal_fields) <= {
            'identity', 'title', 'rationale', 'changes', 'model_provenance'}
            and {'identity', 'title', 'rationale', 'changes'} <= set(proposal_fields),
            'proposal_explicit_metadata_required')
        requested = prepare_proposal(change_plan=prepare_change_plan(inner), **proposal_fields)
        require(requested.data == record, 'proposal_request_conflict', exit_code=6)
        request = prepare_authoring_request(command_id='proposal create', actor=value['actor'],
            request_id=value['request_id'], operations=[{'op':'proposal_create','record':requested.data}])
        proof.check()
    from .execution import _replay
    result = _replay(source, request, COMMAND)
    require(result is not None, 'proposal_request_receipt_changed', exit_code=6)
    return {**result, 'proposal': requested.data, 'proposal_path': requested.original.path,
        'embedded_plan': requested.data['change_plan'], 'direct_plan_sha256': plan.sha256,
        'publication_kind': 'proposal_draft',
        'review_validity': {'current_approval': False, 'human_decision_required': True}}
