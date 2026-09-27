"""Immutable lifecycle candidates, not publication or approval authority."""
from dataclasses import dataclass
from ..srx._json_values import JsonSnapshot
from .errors import ChangePlanError
from .metadata_values import MetadataResult


class LifecycleError(ChangePlanError):
    """A failed plan returns no partially successful model or hidden reset."""
    def __init__(self, reason, *, pointer='', operation_index=None, input_kind='authoring'):
        super().__init__(reason, pointer=pointer, code='SRV030')
        self.operation_index = operation_index
        # The same contradictory request is usage error in authoring, model
        # error when already stored in a self-hashed plan (section 9.6.3).
        self.exit_code = 2 if reason == 'content_lifecycle_conflict' and input_kind == 'authoring' else 3

    def diagnostic(self):
        return {**super().diagnostic(), 'operation_index': self.operation_index,
                'partial_result_available': False, 'write_authorized': False}


@dataclass(frozen=True)
class LifecycleResult:
    _metadata: MetadataResult
    _decisions: JsonSnapshot
    _events: JsonSnapshot
    plan_sha256: str | None = None
    declared_artifacts_verified: bool = False

    @property
    def artifacts(self): return self._metadata.artifacts
    @property
    def candidates(self): return self._metadata.candidates
    @property
    def modified_ids(self): return self._metadata.modified_ids
    @property
    def policy(self): return self._metadata.policy
    @property
    def policy_sha256(self): return self._metadata.policy_sha256
    @property
    def base_artifacts_sha256(self): return self._metadata.base_artifacts_sha256
    @property
    def result_artifacts_sha256(self): return self._metadata.result_artifacts_sha256
    @property
    def operations_applied(self): return self._metadata.operations_applied
    @property
    def preconditions_checked(self): return self._metadata.preconditions_checked
    @property
    def decisions(self): return self._decisions.data
    @property
    def transition_events(self): return self._events.data
    @property
    def validation_scope(self): return 'standard_lifecycle_candidates_only'
    @property
    def metadata_applied(self): return True
    @property
    def lifecycle_checked(self): return True
    @property
    def approval_granted(self): return False
    @property
    def expected_result_root_verified(self): return False
    @property
    def project_complete(self): return False
    @property
    def history_complete(self): return False
    @property
    def write_authorized(self): return False
    @property
    def execution_ready(self): return False
