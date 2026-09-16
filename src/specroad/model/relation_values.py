"""Neutral relation identity values; no entropy, project or disk access."""

from dataclasses import dataclass
from .errors import ModelError
from .identity_tokens import decode128

RANDOM_SCHEME = "random128-v1"
DERIVED_SCHEME = "derived128-v1"


def _relation_id(value):
    if type(value) is not str or not value.startswith("REL-"):
        raise ModelError("invalid_relation_id", pointer="/relation_id")
    decode128(value[4:])
    return value


@dataclass(frozen=True)
class RelationIdentity:
    relation_id: str
    id_scheme: str

    def __post_init__(self):
        _relation_id(self.relation_id)
        if type(self.id_scheme) is not str or self.id_scheme not in (RANDOM_SCHEME, DERIVED_SCHEME):
            raise ModelError("unsupported_relation_id_scheme", pointer="/id_scheme")

    @property
    def id(self):
        return self.relation_id

    def as_fields(self):
        return {"relation_id": self.relation_id, "id_scheme": self.id_scheme}

