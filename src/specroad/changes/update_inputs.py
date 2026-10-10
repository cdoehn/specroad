"""Pure artifact update inputs shared by authoring and the change core."""
from .errors import ChangePlanError
from .field_patches import compile_field_patch
from .json_patch import JsonPatch
from .request_ids import AuthoringError
from .values import ChangeOperation
from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..model.identity_values import artifact_identity
from ..storage.json_syntax import parse_json_object

_UNSPECIFIED = object()


def normalize_artifact_update_input(artifact, *, patch=_UNSPECIFIED, options=_UNSPECIFIED,
        expected_revision=_UNSPECIFIED, expected_sha256=_UNSPECIFIED):
    """Own RFC-6902 values or ordered set/unset pairs with explicit guards.

    Presence and shape are checked here; the full planner checks the actual
    target and both supplied guards. None is not an omitted precondition.
    No revision, identity, time, lifecycle decision or live authority is inferred.
    """
    if (patch is _UNSPECIFIED) == (options is _UNSPECIFIED):
        raise AuthoringError('exactly_one_update_input_required')
    try:
        base = parse_json_object(canonical_json_bytes(artifact))
        value = {'op': 'update', 'target': artifact_identity(base).id, 'patch': []}
        if expected_revision is not _UNSPECIFIED:
            value['expected_revision'] = expected_revision
        if expected_sha256 is not _UNSPECIFIED:
            value['expected_sha256'] = expected_sha256
        ChangeOperation(value)  # Never infer a missing guard from the model.
        value['patch'] = (JsonPatch(patch) if options is _UNSPECIFIED
                          else compile_field_patch(base, options)).data
        return ChangeOperation(value)
    except ChangePlanError:
        raise
    except ModelError as error:
        raise AuthoringError(error.reason, pointer=error.pointer, exit_code=3) from error
