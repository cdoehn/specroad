"""Immutable audit inputs, without automatic clocks or revision advancement.

The new-artifact factory only prepares fields for a regular revision 1. It does
not create files or authorize authoring. Updates, merge, unchanged adoption and
migration must use the future operation-specific metadata policies (Annex K).
"""

from dataclasses import dataclass
from datetime import date
import math
import re

from .errors import ModelError

ACTOR_TYPES = ("human", "ai", "ci", "tool")
AUDIT_FIELDS = ("revision", "created_at", "created_by", "updated_at", "updated_by")
UTC_PATTERN = r"^[0-9]{4}-[0-9]{2}-[0-9]{2}[Tt][0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?Z(?![\s\S])"


def _valid_utc(value):
    if type(value) is not str or re.fullmatch(UTC_PATTERN, value) is None:
        return False
    year, month, day = map(int, value[:10].split("-"))
    hour, minute, second = map(int, value[11:19].split(":"))
    try:
        date(year, month, day)
    except ValueError:
        return False
    if hour > 23 or minute > 59 or second > 60:
        return False
    # Candidate syntax only; no online leap-second registry is consulted.
    return second != 60 or (hour == 23 and minute == 59 and (month, day) in ((6, 30), (12, 31)))


@dataclass(frozen=True)
class Revision:
    value: int

    def __post_init__(self):
        # JSON Schema integer semantics also permit exact integral JSON numbers.
        if (type(self.value) not in (int, float) or self.value < 1
                or (type(self.value) is float and (not math.isfinite(self.value) or not self.value.is_integer()))):
            raise ModelError("invalid_revision", pointer="/revision")
        object.__setattr__(self, "value", int(self.value))


@dataclass(frozen=True)
class Actor:
    actor_type: str
    actor_id: str

    def __post_init__(self):
        if type(self.actor_type) is not str or self.actor_type not in ACTOR_TYPES:
            raise ModelError("invalid_actor_type", pointer="/actor_type")
        if type(self.actor_id) is not str or not self.actor_id.strip() or "\0" in self.actor_id:
            raise ModelError("invalid_actor_id", pointer="/actor_id")
        try:
            self.actor_id.encode("utf-8")
        except UnicodeError as error:
            raise ModelError("invalid_actor_id", pointer="/actor_id") from error

    def as_fields(self):
        return {"actor_type": self.actor_type, "actor_id": self.actor_id}


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
class UtcTimestamp:
    value: str

    def __post_init__(self):
        if not _valid_utc(self.value):
            raise ModelError("invalid_utc_timestamp")


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
