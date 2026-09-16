"""Immutable audit values; no revision advancement or resource publication."""

from dataclasses import dataclass
import math

from .errors import ModelError
from .audit_fields import ACTOR_TYPES, _valid_utc

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


@dataclass(frozen=True)
class UtcTimestamp:
    value: str

    def __post_init__(self):
        if not _valid_utc(self.value):
            raise ModelError("invalid_utc_timestamp")

