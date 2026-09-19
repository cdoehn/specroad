"""Guarded closure worklist: no seed/dependency bypasses the same admission gate.

This composes the existing deterministic identity frontier. It is an in-memory
graph traversal boundary, not a checkpoint, transaction or test scheduler.
"""
from ..model.errors import ModelError
from ._closure_frontier import IdentityFrontier
from .scope_admission import require_artifact_admissible


class AdmissionFrontier:
    def __init__(self, descriptor, records, resources):
        self._descriptor = descriptor
        self._records = records
        self._resources = resources
        self._frontier = IdentityFrontier(())

    def admit(self, target, *, source_id=None, relation_id=None, pointer=''):
        """Validate before de-duplication or scheduling, including repeated edges."""
        if target.kind == 'artifact':
            record = self._records.get(target.identity)
            if record is None:
                raise ModelError('closure_bound_artifact_missing', pointer=pointer)
            require_artifact_admissible(self._descriptor, record.identity,
                                       source_id=source_id, relation_id=relation_id,
                                       pointer=pointer)
        elif target.identity not in self._resources:
            raise ModelError('closure_bound_resource_missing', pointer=pointer)
        self._frontier.extend((target,))

    def __bool__(self):
        return bool(self._frontier)

    def take(self):
        return self._frontier.take()

    @property
    def visited(self):
        return self._frontier.visited

    @property
    def processing_order(self):
        return self._frontier.processing_order
