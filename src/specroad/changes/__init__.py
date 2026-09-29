"""Pure Change Plan contracts; planning/execution/publication stay separate."""
from .core import ChangePlan, ChangeOperation, prepare_change_plan
from .schema import change_plan_schema, operation_schema, OPERATION_TYPES
from .errors import ChangePlanError

__all__ = ["ChangePlan", "ChangeOperation", "prepare_change_plan", "change_plan_schema",
           "operation_schema", "OPERATION_TYPES", "ChangePlanError"]

from .patching import (JsonPatch, JsonPatchError, PatchResult, UpdatePreview,
                       apply_json_patch, compile_field_patch, preview_update)
__all__ += ["JsonPatch", "JsonPatchError", "PatchResult", "UpdatePreview",
            "apply_json_patch", "compile_field_patch", "preview_update"]

from .patching import preview_update_bytes, preview_field_update
__all__ += ["preview_update_bytes", "preview_field_update"]

from .folding import fold_operations, fold_plan_fields, SUPPORTED_FOLD_OPERATIONS
from .folding_values import OperationFold, FoldedArtifact, FoldError
__all__ += ["fold_operations", "fold_plan_fields", "SUPPORTED_FOLD_OPERATIONS",
            "OperationFold", "FoldedArtifact", "FoldError"]

from .metadata import prepare_change_metadata, REGULAR_METADATA_POLICY
from .metadata_values import MetadataResult, MetadataArtifact, MetadataError
__all__ += ["prepare_change_metadata", "REGULAR_METADATA_POLICY", "MetadataResult",
            "MetadataArtifact", "MetadataError"]

from .metadata import prepare_plan_metadata, prepare_change_metadata_bytes
__all__ += ["prepare_plan_metadata", "prepare_change_metadata_bytes"]

from .lifecycle import prepare_change_lifecycle, lifecycle_content_sha256, LIFECYCLE_POLICY_VERSION
from .lifecycle_values import LifecycleResult, LifecycleError
__all__ += ['prepare_change_lifecycle', 'lifecycle_content_sha256', 'LIFECYCLE_POLICY_VERSION',
            'LifecycleResult', 'LifecycleError']

from .lifecycle import prepare_plan_lifecycle, prepare_change_lifecycle_bytes
__all__ += ['prepare_plan_lifecycle', 'prepare_change_lifecycle_bytes']

from .target import TargetModel, assess_change_target, prepare_change_target
from .target_values import TargetPolicy, TargetAssessment, TargetError
__all__ += ['TargetModel', 'TargetPolicy', 'TargetAssessment', 'TargetError', 'assess_change_target']

__all__ += ['prepare_change_target']

from .execution import (ChangeBackend, PublicationRequest, PublicationReceipt,
    ChangeExecutionResult, ChangeExecutionError, dry_run_change,
    apply_change_plan, execute_change_request)
__all__ += ['ChangeBackend', 'PublicationRequest', 'PublicationReceipt',
    'ChangeExecutionResult', 'ChangeExecutionError', 'dry_run_change',
    'apply_change_plan', 'execute_change_request']

from .execution import execute_change_plan_bytes
__all__ += ['execute_change_plan_bytes']

from .authoring import (AuthoringError, NormativeRequestId, AuthoringRequest,
    normalize_request_id, normalize_authoring_actor, prepare_authoring_request,
    bind_plan_authoring)
__all__ += ['AuthoringError', 'NormativeRequestId', 'AuthoringRequest',
    'normalize_request_id', 'normalize_authoring_actor', 'prepare_authoring_request',
    'bind_plan_authoring']

from .locking import (project_lock, inspect_project_lock, recover_project_lock, HeldProjectLock,
                      ProjectLockError, LockKind, LockRecord, OwnerIdentity)
__all__ += ['project_lock', 'inspect_project_lock', 'recover_project_lock', 'HeldProjectLock',
            'ProjectLockError', 'LockKind', 'LockRecord', 'OwnerIdentity']

from .publication_check import (PublicationCheckError, PublicationAuthority, PublicationPreflight,
    PublicationRecheck, prepare_publication_check, recheck_publication, publish_after_recheck)

from .journal import (BuildingJournal, JournalError, prepare_building_journal,
    verify_building_journal, begin_building_journal, read_building_journal, journal_path)

# Durable staging remains distinct from publication/commit and recovery.
from .staging_values import PreparedJournal, StagingError
from .staging import stage_building_journal, read_prepared_journal, verify_prepared_journal
