"""Detached original request and exact historical replay binding."""
from copy import deepcopy
from ..model.canonical import canonical_json_bytes as jcs
from ..storage.json_syntax import parse_json_object as parsed
from .write_guard_values import require
from ._guarded_io import _read_path
from .receipt_values import request_receipt_path
from . import force_receipts


def native_binding(intent, expected_model_root, as_proposal, proposal_fields, execution_binding=None):
    require(type(intent) is dict and type(intent.get('command_id')) is str and type(as_proposal) is bool,
        'force_native_intent_required', exit_code=2)
    return dict(command_id=intent['command_id'], intent=deepcopy(intent),
        expected_model_root_sha256=expected_model_root, as_proposal=as_proposal,
        proposal_fields=deepcopy(proposal_fields), execution_binding=deepcopy(execution_binding))


def _previous(files, original, actor, request_id, force, project_id):
    if request_id is None:
        return None
    raw = _read_path(files, request_receipt_path(request_id), optional=True)
    if raw is None:
        from .force_operational_receipts import completed_attempts
        matches = [w for w in completed_attempts(files, include_incomplete=True, check_originals=True)
                   if w['marker']['request_id'] == request_id]
        if not matches:
            return None
        require(len(matches) == 1, 'request_force_binding_conflict', exit_code=6)
        write = matches[0]; value = write['plan']
        from ..force_operations import current
        call = current()
        selected = [] if call is None else [{'path': p, 'sha256': h} for p, h in call.owners]
        require(value.get('native_intent') == original and value['actor'] == actor
            and value['force'] == force.data and value['request_id'] == request_id
            and value.get('operational_binding') == {'owners': selected}
            and write['marker']['command_id'] == original['command_id'],
            'request_force_binding_conflict', exit_code=6)
        from .values import ChangePlan
        return ChangePlan(jcs(value))
    hint = parsed(raw)
    require(hint.get('format_version') == 'force-request-receipt-v1',
        'request_force_binding_conflict', exit_code=6)
    write = force_receipts.read_group(files, hint['transaction_id'], project_id=project_id)
    value = write['plan']
    require(value.get('native_intent') == original and value['actor'] == actor
        and value['force'] == force.data and value['request_id'] == request_id
        and write['marker']['command_id'] == original['command_id'],
        'request_force_binding_conflict', exit_code=6)
    from ..changes.values import ChangePlan
    return ChangePlan(jcs(value))
