"""Owned metadata candidates, never a write receipt or a lifecycle decision."""
from dataclasses import dataclass
from ..srx._json_values import JsonSnapshot
from .errors import ChangePlanError


class MetadataError(ChangePlanError):
    """The regular metadata policy cannot produce the requested result."""
    def __init__(self, reason, *, pointer=""):
        super().__init__(reason, pointer=pointer, code="SRV174")

    def diagnostic(self):
        return {**super().diagnostic(), "partial_result_available": False,
                "write_authorized": False}


@dataclass(frozen=True)
class MetadataArtifact:
    id: str
    _value: JsonSnapshot
    base_sha256: str | None
    candidate_sha256: str
    operation_indices: tuple[int, ...]
    disposition: str
    original_bytes: bytes | None = None

    @property
    def data(self):
        return self._value.data

    @property
    def changed(self):
        return self.disposition != "unchanged"


@dataclass(frozen=True)
class MetadataResult:
    _model: JsonSnapshot
    candidates: tuple[MetadataArtifact, ...]
    _policy: JsonSnapshot
    policy_sha256: str
    base_artifacts_sha256: str
    result_artifacts_sha256: str
    operations_applied: int
    preconditions_checked: int
    plan_sha256: str | None = None
    declared_artifacts_verified: bool = False

    @property
    def artifacts(self):
        return self._model.data

    @property
    def policy(self):
        return self._policy.data

    @property
    def modified_ids(self):
        return tuple(item.id for item in self.candidates if item.changed)

    @property
    def metadata_applied(self):
        return True

    @property
    def validation_scope(self):
        return "regular_metadata_candidates_only"

    @property
    def lifecycle_checked(self):
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
