"""Normalize an existing normative intent, without constructing a ChangePlan."""
from dataclasses import dataclass
from .authoring import prepare_authoring_request
from .receipt_values import ReceiptError


@dataclass(frozen=True)
class RequestIdentity:
    request_id: str | None
    operations_sha256: str
    applicable: bool


def request_identity(request):
    data = request.data
    if data.get('namespace') != 'normative_write':
        raise ReceiptError('normative_request_namespace_required', exit_code=2)
    normalized = prepare_authoring_request(command_id=data['command_id'], actor=data['actor'],
        operations=data['operations'], request_id=data['request_id'],
        dry_run=data['dry_run'], as_proposal=data['as_proposal']).data
    extra = set(data) - set(normalized)
    plan_fields = {'plan_sha256', 'base_model_root_sha256', 'scope_descriptor'}
    if extra and extra != plan_fields:
        raise ReceiptError('normative_request_fields_invalid', exit_code=2)
    if any(data.get(key) != value for key, value in normalized.items()):
        raise ReceiptError('normative_request_binding_changed', exit_code=2)
    return RequestIdentity(normalized['request_id'], normalized['operation_sequence_sha256'],
                           not normalized['dry_run'] and normalized['request_id'] is not None)
