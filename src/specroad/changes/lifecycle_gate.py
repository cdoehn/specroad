"""Lifecycle evidence bound to one native operation and its complete target."""
from ._metadata_policy import bind_policy
from .lifecycle import prepare_change_lifecycle
from .values import ChangeOperation
from ..model.canonical import canonical_json_sha256
from ..validation import ModelGate


def _prepare_lifecycle_gate(model, operation, *, actor, planned_at):
    """Recompute this operation's entire target on every semantic check.

    Only the requested standard subject is certified. Other non-draft subjects,
    specialist records and approval history still need their actual services.
    The native lifecycle fold retains all transition and approval refusals.
    """
    owned = model.snapshot()
    operation = ChangeOperation(operation.data)
    metadata = bind_policy('change-metadata-v1', actor, planned_at)
    identity = operation.data['target']
    maturity = 'retired' if operation.op == 'retire' else operation.data['to']
    resources = canonical_json_sha256({'model_sources_sha256': owned._sources_sha256,
        'operation': operation.data, 'metadata': metadata})

    def dependencies(context):
        return context.dependency_result({key: list(context.all_ids) for key in context.subjects})

    def check(context):
        if context.subjects != (identity,) or context.artifact(identity)['maturity'] != maturity:
            return context.result([{'reason': 'lifecycle_subject_not_supported', 'severity': 'error'}])
        folded = prepare_change_lifecycle(owned.artifacts, [operation.data],
            **metadata, source_files=owned.source_files, **owned.reservations)
        expected = {a['id']: a for a in folded.artifacts}
        actual = {key: context.artifact(key) for key in context.all_ids}
        if canonical_json_sha256(expected) != canonical_json_sha256(actual):
            return context.result([{'reason': 'lifecycle_target_mismatch',
                                    'severity': 'error', 'artifact_id': identity}])
        return context.result()

    return ModelGate('lifecycle', 'bound-authoring-lifecycle-v1', dependencies, check, resources)
