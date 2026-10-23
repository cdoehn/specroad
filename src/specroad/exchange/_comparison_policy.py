"""Shared, format-independent comparison of validated import projections.

ImportComparison supplies owned values and their canonical bytes. This kernel
classifies the two changes against their own history and applies the explicit
strategy; it neither decodes an exchange format nor updates native objects.
"""
from hashlib import sha256

from ..model.errors import ModelError
from ._identity_errors import ImportIdentityError


def compare_projections(stored, *, mapping_id, strategy, local_bytes, source_bytes,
                        local, source):
    """Return the passive policy observation for already validated inputs."""
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

    return {
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
