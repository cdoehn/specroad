"""Construct one immutable Evidence value from explicit, owned run inputs.

The caller reserves a new ID using the existing allocator. Construction returns
the complete recorded/approved value at once; there is no mutable draft state.
This is not the recording command: the writer must bind the inventory, perform
authorization and run-history/idempotency checks, and publish atomically.
"""
from ..configurations import EffectiveConfiguration
from ..model.audit import actor as read_actor, new_artifact_audit
from ..model.audit_values import UtcTimestamp
from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..model.identities import ArtifactIdentity, IdentityAllocation, IdentityInventory
from ..model.versions import SCHEMA_VERSION
from ..storage.domain_artifact import DomainArtifact
from ..storage.record_artifact import RecordArtifact
from ._context_subject import owned_subject, subject_binding
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


def prepare_evidence_record(subjects, contract, *, allocation, configuration,
                            actor, planned_at, title, result, produced_at,
                            producer, tool, environment, origin, run_context,
                            test=None):
    """Prepare a bound measurement for explicitly listed requirement subjects.

    Subject/contract/test hashes are computed from their actual owned bytes,
    never accepted from caller hash fields. Configuration policy comes from the
    supplied contract. The producer supplies an already namespace-qualified
    run_id and the measured product-state hash; neither is inferred or rewritten.
    This local binding neither proves an external run nor resolves project-wide
    required checks. Unknown run context is unsupported in this first slice.

    A distinct measurement needs a fresh allocation. Reconstructing the same
    allocation and inputs is deterministic, but does not authorize a repeated
    write. Request replay and persistent ID claims belong to the native writer.
    """
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
    if run_context is None:
        raise ModelError('bound_evidence_run_context_required', pointer='/run_context')
    value = {'schema_version': SCHEMA_VERSION, 'artifact_type': 'evidence',
        'id': identity.id, 'id_scheme': identity.id_scheme, 'title': title,
        'maturity': 'approved', 'evidence_state': 'recorded',
        'relations': [], 'extensions': {},
        **new_artifact_audit(actor=read_actor(actor),
                             planned_at=UtcTimestamp(planned_at)).as_fields(),
        'result': result, 'produced_at': produced_at, 'producer': producer,
        'tool': tool, 'environment': environment, 'origin': origin,
        'subjects': [subject_binding(item) for item in sorted(values, key=lambda v: v['id'])],
        'run_context': run_context,
        'configuration_hash': None if configuration is None else configuration.sha256,
        'configuration_policy': contract.data['configuration_policy']}
    # The schema owns exact run fields, timestamps, origins and producer/tool
    # validation. Serialize first to detach all caller-owned nested values.
    record = RecordArtifact(canonical_json_bytes(value), expected_type='evidence')
    run = record.data['run_context']
    if not any(slot['check_id'] == run['check_id'] and slot['test_id'] == run['test_id']
               for slot in contract.data['evidence_slots']):
        raise ModelError('verification_contract_check_mismatch', pointer='/run_context')
    if run['test_id'] != (None if test is None else test.data['id']):
        raise ModelError('evidence_test_binding_mismatch', pointer='/run_context/test_id')
    return record
