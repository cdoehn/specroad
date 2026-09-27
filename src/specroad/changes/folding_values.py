"""Immutable field-fold candidates, not finalized Change Plans or write tickets."""
from dataclasses import dataclass
from ..srx._json_values import JsonSnapshot
from .errors import ChangePlanError


class FoldError(ChangePlanError):
    """Failed ordered evaluation; no partially successful model is returned."""
    def __init__(self, reason, *, pointer="", code="SRV070", operation_index=None,
                 operations_completed=0):
        super().__init__(reason, pointer=pointer, code=code)
        self.operation_index = operation_index
        self.operations_completed = operations_completed

    def diagnostic(self):
        return {**super().diagnostic(), "operation_index": self.operation_index,
                "operations_completed": self.operations_completed,
                "partial_result_available": False, "write_authorized": False}


@dataclass(frozen=True)
class FoldedArtifact:
    """Exactly one candidate per touched identity, before metadata/lifecycle policy."""
    id: str
    _value: JsonSnapshot
    base_sha256: str | None
    candidate_sha256: str
    operation_indices: tuple[int, ...]

    @property
    def data(self):
        return self._value.data

    @property
    def changed(self):
        return self.base_sha256 != self.candidate_sha256


@dataclass(frozen=True)
class OperationFold:
    _model: JsonSnapshot
    candidates: tuple[FoldedArtifact, ...]
    operations_applied: int
    preconditions_checked: int
    plan_sha256: str | None = None

    @property
    def artifacts(self):
        return self._model.data

    @property
    def modified_ids(self):
        return tuple(item.id for item in self.candidates if item.changed)

    @property
    def validation_scope(self):
        return "ordered_field_candidates_only"

    @property
    def metadata_applied(self):
        return False

    @property
    def lifecycle_checked(self):
        return False

    @property
    def declared_results_verified(self):
        return False

    @property
    def expected_result_root_verified(self):
        return False

    @property
    def project_complete(self):
        return False

    @property
    def write_authorized(self):
        return False

    @property
    def execution_ready(self):
        return False
