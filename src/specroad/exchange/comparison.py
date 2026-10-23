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
        local_hash, source_hash = sha256(local_bytes).hexdigest(), sha256(source_bytes).hexdigest()
        equal = local_bytes == source_bytes
        local_changed = source_changed = None
        if stored is None:
            comparison = "unmatched"
        elif "mapping_id" not in stored:
            comparison = "history_unavailable"
        elif stored["mapping_id"] != mapping_id:
            comparison = "mapping_mismatch"
        else:
            local_changed = local_hash != stored["last_imported_projection_sha256"]
            source_changed = source_hash != stored["last_source_projection_sha256"]
            if local_changed and source_changed:
                comparison = "converged" if equal else "diverged"
            elif local_changed:
                comparison = "local_changed"
            elif source_changed:
                comparison = "source_changed"
            else:
                comparison = "unchanged"

        diagnostics = []
        target = None
        refresh = False
        if comparison == "diverged":
            diagnostics.append({**ModelError("divergent_changes").diagnostic(),
                                "code": "SRV148", "exit_code": 3})
        if stored is None:
            action = "unmatched"
        elif strategy == "error":
            action = "reject"
            if not diagnostics:
                diagnostics.append(ImportIdentityError("known_identity").diagnostic())
        elif strategy == "skip":
            action = "skip"
        elif comparison in ("history_unavailable", "mapping_mismatch", "diverged"):
            action = "reject"
            if not diagnostics:
                diagnostics.append(ImportIdentityError(comparison, pointer="/identity/mapping_id").diagnostic())
        elif comparison == "local_changed":
            action = "retain_local"
        else:
            action = "noop" if comparison == "unchanged" else "adopt"
            target = local if action == "noop" else source
            refresh = True

        result = {
            "format_version": "import-conflict-policy-v1", "strategy": strategy,
            "mapping_id": mapping_id, "identity": stored,
            "comparison": comparison, "action": action,
            "local_changed": local_changed, "source_changed": source_changed,
            "targets_equal": equal, "local_projection_sha256": local_hash,
            "source_projection_sha256": source_hash,
            "local_projection": local, "source_projection": source,
            "target_projection": target, "baseline_refresh_allowed": refresh,
            "projection_changed": action == "adopt" and not equal,
            "diagnostics": diagnostics, "exit_code": 3 if diagnostics else 0,
            "publication_authorized": False,
        }
        object.__setattr__(self, "_encoded", canonical_json_bytes(result))

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def sha256(self):
        return sha256(self._encoded).hexdigest()
