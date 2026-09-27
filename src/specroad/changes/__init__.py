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
