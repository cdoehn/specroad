"""Validate explicit Evidence construction bindings, without assessing freshness.

These guards own and validate caller inputs before record assembly, then check
contract membership after native record validation. They do not select runs,
evaluate currentness or authorize persistent writes.
"""
from ..configurations import EffectiveConfiguration
from ..model.errors import ModelError
from ..model.identities import ArtifactIdentity, IdentityAllocation, IdentityInventory
from ..storage.domain_artifact import DomainArtifact
from ._context_subject import owned_subject
from .contracts import VerificationContract, VerificationTest


def _reservation(allocation):
    if type(allocation) is not IdentityAllocation:
        raise ModelError('evidence_identity_allocation_required')
    identity = allocation.identity
    inventory = allocation.inventory
    if type(identity) is not ArtifactIdentity or type(inventory) is not IdentityInventory:
        raise ModelError('evidence_identity_allocation_required')
    identity = ArtifactIdentity(identity.id, identity.id_scheme,
                                identity.artifact_type, identity.id_prefix)
    inventory = IdentityInventory(inventory.id_prefix, inventory.current_ids,
                                  inventory.archived_ids, inventory.reserved_ids)
    IdentityAllocation(identity, inventory)
    if identity.artifact_type != 'evidence':
        raise ModelError('new_evidence_identity_required')
    return identity, inventory


def construction_inputs(subjects, contract, *, allocation, configuration,
                        run_context, test, unbound_reason):
    """Return owned subjects and their validated explicit construction inputs."""
    identity, inventory = _reservation(allocation)
    if type(subjects) not in (list, tuple) or not subjects:
        raise ModelError('evidence_subjects_required', pointer='/subjects')
    if type(contract) is not VerificationContract:
        raise ModelError('typed_verification_contract_required')
    contract = owned_subject(contract)
    values = []
    for position, subject in enumerate(subjects):
        if type(subject) is not DomainArtifact:
            raise ModelError('typed_evidence_requirement_required',
                             pointer='/subjects/' + str(position))
        value = owned_subject(subject).data
        if value['id'] in {item['id'] for item in values}:
            raise ModelError('duplicate_subject', pointer='/subjects/' + str(position))
        if value['id'] not in contract.data['subjects']:
            raise ModelError('verification_contract_subject_mismatch',
                             pointer='/subjects/' + str(position))
        values.append(value)
    values.append(contract.data)
    if test is not None:
        if type(test) is not VerificationTest:
            raise ModelError('typed_verification_test_required')
        test = owned_subject(test)
        values.append(test.data)
    for value in values:
        if value['id'] not in inventory.current_ids:
            raise ModelError('evidence_subject_inventory_mismatch', pointer='/subjects')
    if configuration is not None and type(configuration) is not EffectiveConfiguration:
        raise ModelError('typed_verification_configuration_required')
    if run_context is None and unbound_reason is None:
        raise ModelError('bound_evidence_run_context_required', pointer='/run_context')
    if unbound_reason is not None:
        if run_context is not None:
            raise ModelError('bound_evidence_has_unbound_reason', pointer='/unbound_reason')
        if type(unbound_reason) is not str or not unbound_reason.strip():
            raise ModelError('evidence_unbound_reason_required', pointer='/unbound_reason')
    return identity, values, contract, test


def validate_record_binding(record, contract, test):
    """Check the complete native record against its supplied contract and test."""
    run = record.data['run_context']
    if run is None:
        # A supplied test is still bound to the explicit contract. With no test
        # supplied, do not invent one or select a check from the contract slots.
        if test is not None and not any(slot['test_id'] == test.data['id']
                                        for slot in contract.data['evidence_slots']):
            raise ModelError('evidence_test_binding_mismatch', pointer='/subjects')
        return record
    if not any(slot['check_id'] == run['check_id'] and slot['test_id'] == run['test_id']
               for slot in contract.data['evidence_slots']):
        raise ModelError('verification_contract_check_mismatch', pointer='/run_context')
    if run['test_id'] != (None if test is None else test.data['id']):
        raise ModelError('evidence_test_binding_mismatch', pointer='/run_context/test_id')
    return record
