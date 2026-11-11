"""Native completion replay and publication of an already checked decision.

Only the existing journal/staging/receipt primitives perform writes. An error
retains their recovery evidence; this adapter never retries or rolls back.
"""
from .. import changes
from ..changes import (prepare_publication_check, begin_building_journal,
    publish_prepared_journal, read_committing_journal, finalize_committing_journal,
    cleanup_completed_transaction, prepare_authoring_request,
    resolve_normative_request, read_transaction_completion)
from ..changes._lock_files import LockFiles
from ..changes.receipt_read import _read_confirmed_request, _CompletionProof
from ..validation import ModelDocument
from ._decision_result import result as _result
from .values import require


def replay(source, proposal_id, expected_revision, actor, request_id, decision, comment):
    if request_id is None:
        return None
    receipt = _read_confirmed_request(source, request_id)
    if receipt is None:
        return None
    transaction = receipt.data['transaction_id']
    with LockFiles(source.boundary.root) as files:
        proof = _CompletionProof(files, source, transaction)
        value = proof.journal.data
        require(value['receipts']['request'] == {'path': receipt.path, 'sha256': receipt.sha256},
                'proposal_request_receipt_changed', exit_code=6)
        binding = value['authoring_binding']
        operations = binding['operations']
        require(binding['command_id'] == 'proposal review' and len(operations) == 1
            and operations[0]['op'] == 'proposal_control'
            and operations[0]['target'] == proposal_id
            and operations[0]['expected_revision'] == expected_revision
            and binding['actor'] == actor
            and operations[0].get('review_decision', {}).get('decision') == decision
            and operations[0].get('review_decision', {}).get('comment') == comment,
            'proposal_request_conflict', exit_code=6)
        request = prepare_authoring_request(command_id='proposal review', actor=actor,
            operations=operations, request_id=request_id)
        resolution = resolve_normative_request(source, request).data
        require(resolution['action'] == 'replay' and resolution['receipt'] == {
            'path': receipt.path, 'sha256': receipt.sha256}, 'proposal_request_conflict', exit_code=6)
        proof.check()
        completion = read_transaction_completion(source, transaction)
        proof.check()
        return _result(operations[0], actor, completion, replayed=True)
