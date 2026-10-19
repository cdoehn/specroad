"""Shared execution window for trusted, closed Work adapters.

Adapters validate their own plans, retained evidence and candidate manifests.
Only their in-process evaluator is called here; stored Work data supplies no
handler. CheckpointStore remains the sole publisher of the complete candidate.
"""
from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..runtime.control_points import PhaseBoundary
from ._data_contract import WorkManifestError
from .resume import WorkResumeError


class UnitWindow:
    """One invocation's unit boundaries and native-error provenance."""

    def __init__(self, call):
        self._call = call
        self.executed_unit_ids = []
        self._native_error = None

    def collect(self, tasks, evaluate):
        additions = {}
        for task in tasks:
            self._call.control(PhaseBoundary('work_unit', 'start'))
            try:
                row = evaluate(task)
            except ModelError as error:
                self._native_error = error
                raise
            additions[task['unit_id']] = canonical_json_bytes(row)
            self.executed_unit_ids.append(task['unit_id'])
            if self._call.control(PhaseBoundary('work_unit', 'end'))['soft_budget_exceeded']:
                break
        return additions

    def update(self, store, advance):
        try:
            return store._update(advance)
        except (WorkManifestError, ModelError) as error:
            # A real native model failure is not corrupt checkpoint evidence.
            if error is self._native_error:
                raise
            raise WorkResumeError('incompatible_work_contract', exit_code=6) from error
