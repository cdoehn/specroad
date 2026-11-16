"""Native completion replay and publication of an already checked decision.

Only the common guarded writer performs writes. An error retains the
interruption state; this adapter never retries or rolls back.
"""
from .. import changes
from ..changes import (prepare_publication_check, prepare_authoring_request, resolve_normative_request, read_transaction_completion)
from ..changes._lock_files import LockFiles
from ..changes._publication_observation import _root
from ..changes._target_materialization import publication_target
from ..changes.receipt_read import _read_confirmed_request, _CompletionProof
from ..validation import ModelDocument
from ._review_result import _result
from .values import require


def _replay(source, proposal_id, expected_revision, actor, request_id):
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
        require(binding['command_id'] == 'proposal review start' and len(operations) == 1
            and operations[0]['op'] == 'proposal_control'
            and operations[0]['target'] == proposal_id
            and operations[0]['expected_revision'] == expected_revision
            and binding['actor'] == actor,
            'proposal_request_conflict', exit_code=6)
        request = prepare_authoring_request(command_id='proposal review start', actor=actor,
            operations=operations, request_id=request_id)
        resolution = resolve_normative_request(source, request).data
        require(resolution['action'] == 'replay' and resolution['receipt'] == {
            'path': receipt.path, 'sha256': receipt.sha256}, 'proposal_request_conflict', exit_code=6)
        proof.check()
        completion = read_transaction_completion(source, transaction)
        proof.check()
        return _result(operations[0], completion, replayed=True)


def _publish(snapshot, checked, gates, *, policy, held, transaction_id, authority):
    package_files = tuple(ModelDocument(p, raw) for p, raw in snapshot.raw.items()
                          if p not in snapshot.model.source_files)
    preflight = prepare_publication_check(checked.plan, snapshot.model, policy=policy,
        gates=gates, package_files=package_files)
    from ..changes.guarded_write import publish_guarded_change
    return publish_guarded_change(preflight, held_lock=held, authority=authority, gates=gates)
