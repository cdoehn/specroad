"""Construct one immutable Evidence value from explicit, owned run inputs.

The caller reserves a new ID using the existing allocator. Construction returns
the complete recorded/approved value at once; there is no mutable draft state.
This is not the recording command: the writer must bind the inventory, perform
authorization and run-history/idempotency checks, and publish atomically.
"""
from ..model.audit import actor as read_actor, new_artifact_audit
from ..model.audit_values import UtcTimestamp
from ..model.canonical import canonical_json_bytes
from ..model.versions import SCHEMA_VERSION
from ..storage.record_artifact import RecordArtifact
from ._evidence_inputs import construction_inputs, validate_record_binding
from ._subject_binding import subject_binding


def prepare_evidence_record(subjects, contract, *, allocation, configuration,
                            actor, planned_at, title, result, produced_at,
                            producer, tool, environment, origin, run_context,
                            test=None, unbound_reason=None):
    """Prepare a measurement for explicitly listed requirement subjects.

    Subject/contract/test hashes are computed from their actual owned bytes,
    never accepted from caller hash fields. Configuration policy comes from the
    supplied contract. The producer supplies an already namespace-qualified
    run_id and the measured product-state hash; neither is inferred or rewritten.
    This local binding neither proves an external run nor resolves project-wide
    required checks. Unknown product/run provenance is explicitly represented
    by run_context=None and a nonblank unbound_reason, never inferred from the
    supplied subjects or configuration. Partial run objects remain invalid.

    A distinct measurement needs a fresh allocation. Reconstructing the same
    allocation and inputs is deterministic, but does not authorize a repeated
    write. Request replay and persistent ID claims belong to the native writer.
    """
    identity, values, contract, test = construction_inputs(
        subjects, contract, allocation=allocation, configuration=configuration,
        run_context=run_context, test=test, unbound_reason=unbound_reason)
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
    if unbound_reason is not None:
        value['unbound_reason'] = unbound_reason
    # The schema owns exact run fields, timestamps, origins and producer/tool
    # validation. Serialize first to detach all caller-owned nested values.
    record = RecordArtifact(canonical_json_bytes(value), expected_type='evidence')
    return validate_record_binding(record, contract, test)
