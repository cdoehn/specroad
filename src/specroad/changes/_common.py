"""Read-only model, identity and pointer checks shared by plan adapters."""
import re
from ..model.errors import ModelError
from ..model.artifact_types import artifact_types
from ..model.identity_values import ArtifactIdentity, artifact_identity
from ..model.paths import project_path
from ..model.record_contracts import RECORD_TYPES, SPECIAL_STATES
from ..model.record_schemas import validate_record_fields, require_generic_mutation
from ..model.domain_schemas import validate_domain_fields
from .errors import ChangePlanError
from ._patch_pointer import _pointer
from ._patch_policy import _CONTROLLED, _mutable_pointer, _patch


def _at(pointer, fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except ChangePlanError:
        raise
    except ModelError as error:
        raise ChangePlanError(error.reason, pointer=pointer + error.pointer) from error
    except (ValueError, TypeError, RecursionError) as error:
        raise ChangePlanError("invalid_change_plan_value", pointer=pointer) from error

def _text(value, pointer):
    if type(value) is not str or not value.strip() or "\0" in value:
        raise ChangePlanError("nonempty_text_required", pointer=pointer)

def _reference(value, pointer):
    _text(value, pointer)
    parts = value.split("-")
    if len(parts) != 3:
        raise ChangePlanError("invalid_artifact_reference", pointer=pointer)
    kind = next((item.artifact_type for item in artifact_types() if item.prefix == parts[1]), None)
    scheme = "legacy-sequential-v1" if re.fullmatch(r"[0-9]{4}", parts[2]) else "random128-v1"
    try:
        return ArtifactIdentity(value, scheme, kind, parts[0])
    except ModelError as error:
        raise ChangePlanError(error.reason, pointer=pointer) from error

def _artifact(value, pointer, expected_type=None):
    if type(value) is not dict:
        raise ChangePlanError("artifact_object_required", pointer=pointer)
    kind = value.get("artifact_type")
    validator = validate_record_fields if kind in RECORD_TYPES else validate_domain_fields
    _at(pointer, validator, value, expected_type=expected_type)
    return _at(pointer, artifact_identity, value)

def _generic(identity, pointer):
    if identity.artifact_type in SPECIAL_STATES:
        try:
            require_generic_mutation(identity.artifact_type, "patch")
        except ModelError as error:
            raise ChangePlanError(error.reason, pointer=pointer) from error




def _normalization_path(value, pointer):
    _at(pointer, project_path, value)
    if value == "specroad.json":
        return
    parts = value.split("/")
    if parts[0] in ("profiles", "rules", "mappings") and len(parts) > 1 and value.endswith(".json"):
        return
    if len(parts) == 3 and parts[0] == "spec" and parts[2].endswith(".json"):
        identity = _reference(parts[2][:-5], pointer)
        # A proposal's actual stored state decides mutability. The path alone
        # must not turn all active proposals into immutable originals.
        if identity.artifact_type != 'proposal':
            _generic(identity, pointer)
        if identity.path == value:
            return
    raise ChangePlanError("normalization_resource_not_supported", pointer=pointer)
