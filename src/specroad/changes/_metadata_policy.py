"""Fixed policy dispatch; artifact data cannot register executable policies.

The regular strategy accepts one base identity and its folded candidate.
Future history-adoption strategies require their own bound inputs and may not
silently fall through to this regular authoring interface.
"""
from dataclasses import dataclass
from typing import Callable
from ..model.audit import actor as read_actor
from ..model.audit_values import UtcTimestamp, Revision
from ..model.audit_fields import AUDIT_FIELDS
from ..model.errors import ModelError
from ..model.identity_values import artifact_identity
from ._common import _generic
from .metadata_time import next_update_time
from .metadata_values import MetadataError

REGULAR_METADATA_POLICY = "change-metadata-v1"


def _regular_fields(old, value, binding, identity):
    try:
        _generic(artifact_identity(value), "/artifacts/" + identity)
    except ModelError as error:
        raise MetadataError(error.reason, pointer=error.pointer) from None
    if old is None:
        return "created", {
            "revision": 1,
            "created_at": binding["planned_at"],
            "updated_at": binding["planned_at"],
            "created_by": binding["actor"],
            "updated_by": binding["actor"],
        }
    # Operation-level guards observe the folded, not yet stamped state.
    if any(value[name] != old[name] for name in AUDIT_FIELDS):
        raise MetadataError("intermediate_audit_changed", pointer="/artifacts/" + identity)
    return "changed", {
        "revision": Revision(old["revision"]).value + 1,
        "created_at": old["created_at"],
        "created_by": old["created_by"],
        "updated_at": next_update_time(binding["planned_at"], old["updated_at"]),
        "updated_by": binding["actor"],
    }


@dataclass(frozen=True)
class _MetadataPolicy:
    version: str
    # Internal, trusted strategy; never a callback read from an input document.
    fields: Callable


_REGULAR = _MetadataPolicy(REGULAR_METADATA_POLICY, _regular_fields)


def select_policy(version):
    """Only an implemented strategy can be selected; no plugin registration."""
    if type(version) is not str or version != REGULAR_METADATA_POLICY:
        raise MetadataError("unsupported_regular_metadata_policy", pointer="/metadata_policy_version")
    return _REGULAR


def bind_policy(version, actor, planned_at):
    selected = select_policy(version)
    try:
        bound_actor = read_actor(actor).as_fields()
        UtcTimestamp(planned_at)
    except ModelError as error:
        raise MetadataError(error.reason, pointer=error.pointer) from None
    return {"metadata_policy_version": selected.version, "actor": bound_actor, "planned_at": planned_at}
