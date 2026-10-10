"""Owned native transition and retirement inputs, without publication effects."""
from ._common import _text
from .errors import ChangePlanError
from .request_ids import AuthoringError
from .values import ChangeOperation
from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..model.identity_values import artifact_identity
from ..storage.json_syntax import parse_json_object

_UNSPECIFIED = object()


def normalize_transition_input(artifact, *, to, reason=_UNSPECIFIED):
    """Own the original target/from and an explicit requested maturity."""
    try:
        base = parse_json_object(canonical_json_bytes(artifact))
        metadata = {}
        if reason is not _UNSPECIFIED:
            _text(reason, '/metadata/reason')
            metadata['reason'] = reason
        return ChangeOperation({'op': 'transition', 'target': artifact_identity(base).id,
            'from': base.get('maturity'), 'to': to, 'metadata': metadata})
    except ChangePlanError:
        raise
    except ModelError as error:
        raise AuthoringError(error.reason, pointer=error.pointer, exit_code=3) from error


def normalize_retire_input(artifact, *, reason, expected_revision=_UNSPECIFIED,
                           expected_sha256=_UNSPECIFIED):
    """Require explicit revision/hash guards; None is not an omitted guard."""
    try:
        base = parse_json_object(canonical_json_bytes(artifact))
        value = {'op': 'retire', 'target': artifact_identity(base).id, 'reason': reason}
        if expected_revision is not _UNSPECIFIED:
            value['expected_revision'] = expected_revision
        if expected_sha256 is not _UNSPECIFIED:
            value['expected_sha256'] = expected_sha256
        return ChangeOperation(value)
    except ChangePlanError:
        raise
    except ModelError as error:
        raise AuthoringError(error.reason, pointer=error.pointer, exit_code=3) from error
