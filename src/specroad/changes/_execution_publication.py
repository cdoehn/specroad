"""Publication delegation is separate from planning and result projection.

The explicit host transaction owns real authorization/lock/receipt/durability.
This module checks request/input/receipt/readback bindings, never bypasses those
responsibilities with its own filesystem writer, retry or global rollback.
"""
from .execution_values import (ChangeBackend, PublicationRequest, PublicationReceipt,
    ChangeExecutionError, ChangeExecutionResult, _source_binding)
from .target_model import TargetModel
from .target import assess_change_target


def _same_handoff(actual, expected):
    if (type(actual) is not PublicationRequest or actual._encoded != expected._encoded or
            actual._plan_bytes != expected._plan_bytes or actual.documents != expected.documents):
        raise ChangeExecutionError('publication_request_changed', exit_code=6)


def publish_checked_change(plan, model, *, policy, gates, strict, backend, checked):
    request = PublicationRequest._create(checked, model)
    completed = None
    handoff = request.detached()
    try:
        with backend.transaction(handoff) as transaction:
            _same_handoff(handoff, request)
            current = transaction.read_model()
            if type(current) is not TargetModel:
                raise ChangeExecutionError('backend_model_required')
            current = current.snapshot()
            if _source_binding(current) != request.data['base']:
                raise ChangeExecutionError('publication_base_changed', exit_code=6)
            fresh = assess_change_target(plan, current, policy=policy, gates=gates, strict=strict)
            if not fresh.target_validated:
                return ChangeExecutionResult._create(fresh, dry_run=False)
            fresh_request = PublicationRequest._create(fresh, current)
            if fresh_request.sha256 != request.sha256:
                raise ChangeExecutionError('publication_assessment_changed', exit_code=6)
            # Gates are trusted, but their result cannot hide a changed source.
            latest = transaction.read_model()
            if type(latest) is not TargetModel or _source_binding(latest.snapshot()) != request.data['base']:
                raise ChangeExecutionError('publication_base_changed', exit_code=6)
            _same_handoff(handoff, request)
            outgoing = fresh_request.detached()
            receipt = transaction.publish(outgoing)
            _same_handoff(outgoing, request)
            if type(receipt) is PublicationReceipt:
                receipt = PublicationReceipt(receipt.request_sha256, receipt.target_root_sha256,
                    receipt.request_id, receipt.published_paths, receipt.receipt_id)
            if (type(receipt) is not PublicationReceipt or
                    receipt.request_sha256 != request.sha256 or
                    receipt.target_root_sha256 != request.data['target_root_sha256'] or
                    receipt.request_id != request.data['request_id'] or
                    set(receipt.published_paths) != set(request.data['changed_paths'])):
                raise ChangeExecutionError('publication_receipt_mismatch')
            after = transaction.read_model()
            if type(after) is not TargetModel:
                raise ChangeExecutionError('backend_model_required')
            after = after.snapshot()
            expected_files = dict(current.source_files)
            expected_files.update({d.path: d.content for d in fresh.documents})
            if (after.binding != current.binding or after.source_files != expected_files or
                    after.resources_sha256 != current.resources_sha256 or
                    after.manifest(after.artifacts, plan.data['base']['scope_descriptor']).sha256 != request.data['target_root_sha256']):
                raise ChangeExecutionError('publication_target_mismatch')
            completed = ChangeExecutionResult._create(fresh, dry_run=False, receipt=receipt, backend=backend)
        if completed is None:
            raise ChangeExecutionError('publication_not_confirmed')
        return completed
    except Exception as error:
        # Even entering/closing a supplied transaction can have side effects.
        # Never claim rollback, unmodified files or retry safety here.
        reason = error.reason if type(error) is ChangeExecutionError else 'transaction_backend_error'
        code = error.exit_code if type(error) is ChangeExecutionError else 5
        raise ChangeExecutionError(reason, exit_code=code, write_state='unknown') from error

