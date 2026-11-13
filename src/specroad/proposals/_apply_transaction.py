"""Read real completion proofs; publication uses the shared native writer."""
from ..changes import prepare_authoring_request, resolve_normative_request, read_transaction_completion
from ..changes._lock_files import LockFiles
from ..changes._publication_observation import _root
from ..changes.receipt_read import _CompletionProof, _read_confirmed_request
from ..validation import ModelDocument
from ._apply_control import operation_proof
from ._apply_result import _result
from .context import ProposalContext
from .publication import ProposalPublication, verify_proposal_publication
from .values import require


def _replay(source, proposal_id, expected_revision, actor, request_id, audit):
    if request_id is None:
        return None
    receipt = _read_confirmed_request(source, request_id)
    if receipt is None:
        return None
    with LockFiles(source.boundary.root) as files:
        proof = _CompletionProof(files, source, receipt.data['transaction_id'])
        value = proof.journal.data
        require(value['receipts']['request'] == {'path': receipt.path, 'sha256': receipt.sha256},
                'proposal_request_receipt_changed', exit_code=6)
        binding = value['authoring_binding']; operations = binding['operations']
        require(binding['command_id'] == 'proposal apply' and bool(operations)
            and operations[-1]['op'] == 'proposal_control'
            and operations[-1]['target'] == proposal_id
            and operations[-1]['expected_revision'] == expected_revision and binding['actor'] == actor,
            'proposal_request_conflict', exit_code=6)
        operation_proof(operations[-1])
        request = prepare_authoring_request(command_id='proposal apply', actor=actor,
            operations=operations, request_id=request_id)
        resolution = resolve_normative_request(source, request).data
        require(resolution['action'] == 'replay' and resolution['receipt'] == {
            'path': receipt.path, 'sha256': receipt.sha256}, 'proposal_request_conflict', exit_code=6)
        proof.check()
        completion = read_transaction_completion(source, value['transaction_id'])
        proof.check()
        return _result(operations, completion, audit, replayed=True)


def _verify_completion(transaction, plan, before, target, original, after):
    source = _root(target)
    with LockFiles(source.boundary.root) as files:
        proof = _CompletionProof(files, source, transaction)
        paths = [*proof.receipt_paths, proof.archive_path]
        receipts = tuple(ModelDocument(path, proof.read(path)) for path in paths)
        publication = ProposalPublication(plan, before, target, receipts)
        verify_proposal_publication(publication, original, after, ProposalContext(after, before))
        proof.check()
