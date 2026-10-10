"""Bind one ordinary update's proposed target to the existing lifecycle kernel.

This is not stored-approval verification or a general lifecycle service. Other
non-draft subjects/states still need an explicitly supplied semantic service.
"""
from ..model.canonical import canonical_json_sha256
from ..validation import ModelGate
from ._metadata_policy import bind_policy
from .lifecycle import prepare_change_lifecycle
from .target_model import TargetModel
from .target_values import TargetError
from .values import ChangeOperation


def prepare_update_lifecycle_gate(model, operation, *, metadata_policy_version, actor, planned_at):
    """Return a pure gate owning the original model, operation and audit inputs.

    Each check reruns the real fold/metadata policy and compares the complete
    supplied target. A previous successful result is never reused as a ticket.
    The only supported non-draft subject is this update's proposed artifact;
    unchanged approvals or special lifecycle records are not certified here.
    """
    if type(model) is not TargetModel or type(operation) is not ChangeOperation:
        raise TargetError('update_lifecycle_inputs_required')
    owned = model.snapshot()
    operation = ChangeOperation(operation.data)
    if operation.op != 'update':
        raise TargetError('update_operation_required')
    metadata = bind_policy(metadata_policy_version, actor, planned_at)
    identity = operation.data['target']
    resources = canonical_json_sha256({'model_sources_sha256': owned._sources_sha256,
        'operation': operation.data, 'metadata': metadata})

    def dependencies(context):
        return context.dependency_result({key: list(context.all_ids) for key in context.subjects})

    def check(context):
        if (context.subjects != (identity,)
                or context.artifact(identity)['maturity'] != 'proposed'):
            return context.result([{'reason': 'update_lifecycle_subject_not_supported',
                                    'severity': 'error'}])
        folded = prepare_change_lifecycle(owned.artifacts, [operation.data],
            **metadata, source_files=owned.source_files, **owned.reservations)
        expected = {a['id']: a for a in folded.artifacts}
        actual = {key: context.artifact(key) for key in context.all_ids}
        if canonical_json_sha256(expected) != canonical_json_sha256(actual):
            return context.result([{'reason': 'update_lifecycle_target_mismatch',
                                    'severity': 'error', 'artifact_id': identity}])
        return context.result()

    return ModelGate('lifecycle', 'bound-update-lifecycle-v1', dependencies, check, resources)
