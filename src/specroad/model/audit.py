"""Immutable audit inputs, without automatic clocks or revision advancement.

The new-artifact factory only prepares fields for a regular revision 1. It does
not create files or authorize authoring. Updates, merge, unchanged adoption and
migration must use the future operation-specific metadata policies (Annex K).
"""

from dataclasses import dataclass

from .errors import ModelError

from .audit_fields import ACTOR_TYPES, AUDIT_FIELDS, UTC_PATTERN
from .audit_values import Revision, Actor, UtcTimestamp


def actor(value):
    """Read a complete actor without resolving a login or authenticating it."""
    if type(value) is not dict:
        raise ModelError("actor_object_required")
    if value.keys() - {"actor_type", "actor_id"}:
        raise ModelError("unknown_actor_field")
    for name in ("actor_type", "actor_id"):
        if name not in value:
            raise ModelError("missing_actor_field", pointer="/" + name)
    return Actor(value["actor_type"], value["actor_id"])


@dataclass(frozen=True)
class ArtifactAudit:
    revision: Revision
    created_at: UtcTimestamp
    created_by: Actor
    updated_at: UtcTimestamp
    updated_by: Actor

    def __post_init__(self):
        for name, kind in (("revision", Revision), ("created_at", UtcTimestamp),
                           ("created_by", Actor), ("updated_at", UtcTimestamp), ("updated_by", Actor)):
            if not isinstance(getattr(self, name), kind):
                raise ModelError("typed_audit_value_required", pointer="/" + name)

    def as_fields(self):
        return {"revision": self.revision.value, "created_at": self.created_at.value,
                "created_by": self.created_by.as_fields(), "updated_at": self.updated_at.value,
                "updated_by": self.updated_by.as_fields()}


def artifact_audit(value):
    """Read audit fields only; retained historic revisions are never restamped."""
    if type(value) is not dict:
        raise ModelError("object_required")
    for name in AUDIT_FIELDS:
        if name not in value:
            raise ModelError("missing_audit_field", pointer="/" + name)
    parsed = {}
    for name, parse in (("revision", Revision), ("created_at", UtcTimestamp),
                        ("created_by", actor), ("updated_at", UtcTimestamp), ("updated_by", actor)):
        try:
            parsed[name] = parse(value[name])
        except ModelError as error:
            if name != "revision":
                error.pointer = "/" + name + error.pointer
            raise
    return ArtifactAudit(**parsed)


def new_artifact_audit(*, actor, planned_at):
    """Prepare a regular creation from explicit bound inputs, never wall time."""
    if not isinstance(actor, Actor):
        raise ModelError("typed_actor_required")
    if not isinstance(planned_at, UtcTimestamp):
        raise ModelError("typed_planned_at_required")
    return ArtifactAudit(Revision(1), planned_at, actor, planned_at, actor)
