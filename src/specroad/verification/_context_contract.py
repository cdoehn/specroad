"""Read-only contract/check binding for an explicit configuration exception."""
from hashlib import sha256

from ..model.errors import ModelError
from .contracts import VerificationContract
from ._context_subject import owned_subject
from ._subject_binding import subject_binding, subject_context_sha256


def contract_check(data, record, contract):
    """Bind supplied contract policy to this subject and recorded check.

    This checks the explicit contract's local declaration, not the project's
    independently resolved required-check set or authoritative run selection.
    """
    if type(contract) is not VerificationContract:
        raise ModelError('typed_verification_contract_required')
    contract = owned_subject(contract)
    value = contract.data
    subject = data['subject']
    subject_id = subject['id']
    kind = subject['artifact_type']
    digest = subject_context_sha256(value)
    if kind in ('capability', 'requirement', 'task'):
        matches = subject_id in value['subjects']
    elif kind == 'test':
        matches = any(slot['test_id'] == subject_id for slot in value['evidence_slots'])
    else:
        matches = subject_id == value['id']
        if matches and digest != data['subject_binding']['verification_context_sha256']:
            raise ModelError('verification_contract_subject_context_mismatch')
    if not matches:
        raise ModelError('verification_contract_subject_mismatch')
    run = record['run_context']
    if run is None:
        raise ModelError('verification_contract_check_required', pointer='/run_context')
    slots = [slot for slot in value['evidence_slots']
             if slot['check_id'] == run['check_id'] and slot['test_id'] == run['test_id']]
    if not slots or (kind == 'test' and run['test_id'] != subject_id):
        raise ModelError('verification_contract_check_mismatch', pointer='/run_context')
    recorded = next((item for item in record['subjects'] if item['artifact_id'] == value['id']), None)
    reasons = []
    if recorded is None:
        reasons.append('contract_not_recorded')
    elif recorded['verification_context_sha256'] != digest:
        reasons.append('contract_context_changed')
    if record['configuration_policy'] == 'independent' and value['configuration_policy'] != 'independent':
        reasons.append('independent_contract_required')
    independent = value['configuration_policy'] == 'independent' and not reasons
    return {'contract': {**subject_binding(value),
                'source_sha256': sha256(contract.source_bytes).hexdigest(),
                'configuration_policy': value['configuration_policy']},
            'recorded_contract': recorded, 'contract_check': slots[0],
            'contract_configuration_independent': independent}, reasons
