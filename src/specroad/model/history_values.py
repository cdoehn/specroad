"""Neutral history observations from explicit, caller-bound origin observations.

An origin is NOT an artifact field, a signature or an authenticity claim. A
future trusted history/import provider must establish the creation event from
its actual ancestry/provenance. IDs, equal content and audit timestamps alone
never prove common history. This model cannot authorize import, merge or writes.
"""

from dataclasses import dataclass
from enum import Enum
import re

from .errors import ModelError
from .identity_values import ArtifactIdentity
from .relation_values import RelationIdentity


def _text(value):
    if type(value) is not str or not value.strip() or "\0" in value:
        raise ModelError("invalid_history_origin")
    try:
        value.encode("utf-8")
    except UnicodeError as error:
        raise ModelError("invalid_history_origin") from error


@dataclass(frozen=True)
class HistoryOrigin:
    subject_id: str
    namespace: str
    creation_event: str

    def __post_init__(self):
        for value in (self.subject_id, self.namespace, self.creation_event):
            _text(value)


@dataclass(frozen=True)
class HistoryObservation:
    identity: object
    content_sha256: str
    origin: object = None
    source: object = None

    def __post_init__(self):
        if not isinstance(self.identity, (ArtifactIdentity, RelationIdentity)):
            raise ModelError("history_identity_required")
        if (type(self.content_sha256) is not str
                or re.fullmatch(r"[0-9a-f]{64}", self.content_sha256) is None):
            raise ModelError("invalid_history_content_hash")
        if self.origin is not None and (
                not isinstance(self.origin, HistoryOrigin)
                or self.origin.subject_id != self.identity.id):
            raise ModelError("history_origin_binding_mismatch")
        if isinstance(self.identity, RelationIdentity):
            if not isinstance(self.source, ArtifactIdentity):
                raise ModelError("relation_history_source_required")
        elif self.source is not None:
            raise ModelError("artifact_history_has_no_source")


class HistoryComparison(str, Enum):
    DIFFERENT_IDENTITY = "different_identity"
    IDENTICAL_COPY = "identical_copy"
    SAME_HISTORY = "same_history"
    IDENTITY_CONFLICT = "identity_conflict"
    UNRESOLVED = "unresolved"

