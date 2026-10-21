"""Bind the reviewed Done gate separately from ordinary status publication.

The caller supplies its model snapshot after checking the typed preparation
and reserved services. This module prepares the operation and its proof gate;
the ordinary writer continues to own authority, live checks and publication.
"""
from ..changes import prepare_change_lifecycle
from ..changes._metadata_policy import bind_policy
from ..graph.scope_descriptors import ScopeDescriptor
from ..model.canonical import canonical_json_sha256
from ..model.errors import ModelError
from ..validation import ModelGate
from .task_implementation import (
    _GATE, _confirmed, TaskDoneContext, prepare_task_implementation,
)


def prepare_done_update(model, prepared, *, actor, planned_at):
    """Rebind the exact intention and return its operation and native gate."""
    context = TaskDoneContext(model, prepared.data['task_id'],
        scope_descriptor=ScopeDescriptor(prepared.data['scope_descriptor']))
    current = prepare_task_implementation(context, review=prepared._review, verifier=prepared._verifier)
    if current.data != prepared.data:
        raise ModelError('task_implementation_preparation_changed')
    operation = current.operation
    metadata = bind_policy('change-metadata-v1', actor, planned_at)
    resources = canonical_json_sha256({'preparation_sha256': current.sha256, 'metadata': metadata})

    def dependencies(context):
        return context.dependency_result({key: list(context.all_ids) for key in context.subjects})

    def check(target):
        # One review certifies only its own Task, never an unreviewed neighbour
        # already labelled implemented in the supplied project. The reserved
        # hook is required by Core on every implemented Task, including drafts.
        missing = [key for key in target.subjects if key != context.data['task_id']]
        if missing:
            return target.result([{'reason': 'task_done_review_missing',
                'artifact_id': key, 'severity': 'error'} for key in missing])
        if target.configuration_data is not None:
            return target.result([{'reason': 'task_done_unconfigured_project_scope_required',
                                   'severity': 'error'}])
        _confirmed(context, prepared._review, prepared._verifier)
        folded = prepare_change_lifecycle(model.artifacts, [operation.data],
            **metadata, source_files=model.source_files, **model.reservations)
        expected = {row['id']: row for row in folded.artifacts}
        actual = {key: target.artifact(key) for key in target.all_ids}
        if canonical_json_sha256(expected) != canonical_json_sha256(actual):
            return target.result([{'reason': 'task_done_target_changed', 'severity': 'error'}])
        return target.result()

    gate = ModelGate(_GATE, 'bound-task-done-v2', dependencies, check, resources)
    return operation, gate
