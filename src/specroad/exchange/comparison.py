"""Pure decisions for import-conflict-policy-v1, not an import/write authority.

Callers supply projections in the same selected mapping space and a unique
native identity from NativeIdentityIndex (or None for an unmatched lookup).
Mapping resource/hash selection remains the mapping service's responsibility.
The comparison does not infer projections, manufacture history, or issue a
revision. The eventual complete target must pass the ordinary writer gates.
"""
from dataclasses import dataclass
from hashlib import sha256

from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..profiles._contract import IDENTITY, SEMVER
from ..storage.json_syntax import parse_json_object
from ._comparison_policy import compare_projections
from ._identity_errors import ImportIdentityError, _error
from ._import_identity import ExternalIdentity


_STRATEGIES = ("error", "skip", "update_if_unchanged", "create_new_revision")


def _projection(value, name):
    if type(value) is not dict:
        raise ImportIdentityError("import_projection_object_required", pointer="/" + name)
    try:
        encoded = canonical_json_bytes(value)
        return encoded, parse_json_object(encoded)
    except ModelError as error:
        raise _error(error, prefix="/" + name) from error


def _mapping_key(value):
    if type(value) is not str or value.count("@") != 1:
        raise ImportIdentityError("mapping_exact_key_required", pointer="/mapping_id")
    name, version = value.split("@")
    if IDENTITY.fullmatch(name) is None or SEMVER.fullmatch(version) is None:
        raise ImportIdentityError("mapping_exact_key_required", pointer="/mapping_id")


@dataclass(frozen=True, init=False)
class ImportComparison:
    """Owned observation of one lookup and its explicit policy decision.

    Invalid input raises ImportIdentityError. Valid business rejections retain
    both the comparison and strategy action, with diagnostics and exit_code 3.
    A skipped divergent object is therefore still an unresolved conflict.
    None is an explicit unmatched lookup, never permission to create an object.
    Every returned data object is detached from the inputs and this value.
    """
    _encoded: bytes

    def __init__(self, identity, *, mapping_id, strategy, local_projection, source_projection):
        if type(strategy) is not str or strategy not in _STRATEGIES:
            raise ImportIdentityError("explicit_import_strategy_required", pointer="/strategy")
        _mapping_key(mapping_id)
        local_bytes, local = _projection(local_projection, "local_projection")
        source_bytes, source = _projection(source_projection, "source_projection")
        try:
            stored = None if identity is None else ExternalIdentity(identity).data
        except ModelError as error:
            raise _error(error, prefix="/identity") from error
        result = compare_projections(
            stored, mapping_id=mapping_id, strategy=strategy,
            local_bytes=local_bytes, source_bytes=source_bytes, local=local, source=source,
        )
        # Validate the complete observation with the shared reader before
        # installing it. Its envelope also consumes reader nesting capacity;
        # a rejected reinitialization must retain the previous complete value.
        try:
            encoded = canonical_json_bytes(result)
            parse_json_object(encoded)
        except ModelError as error:
            raise _error(error) from error
        object.__setattr__(self, "_encoded", encoded)

    @property
    def data(self):
        try:
            return parse_json_object(self._encoded)
        except ModelError as error:
            raise _error(error) from error

    @property
    def sha256(self):
        return sha256(self._encoded).hexdigest()
