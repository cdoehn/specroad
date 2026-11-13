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
    journal = begin_building_journal(preflight, held_lock=held,
        transaction_id=transaction_id, authority=authority, gates=gates)
    journal = changes.stage_building_journal(preflight, journal, held_lock=held,
        authority=authority, gates=gates)
    publication = publish_prepared_journal(preflight, journal, held_lock=held,
        authority=authority, gates=gates)
    # Publication may normalize configuration bytes. Bind to the exact
    # checked target, retaining root identity and configuration checks.
    target_source = _root(publication_target(preflight))
    committing = read_committing_journal(target_source, transaction_id,
        expected_sha256=publication.data['journal_sha256'], preflight=preflight)
    finalize_committing_journal(preflight, committing, held_lock=held, authority=authority, gates=gates)
    return cleanup_completed_transaction(preflight, transaction_id, held_lock=held, authority=authority)
