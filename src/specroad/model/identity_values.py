"""Immutable artifact identity values and the normal-update identity guard."""

from dataclasses import dataclass
import re

from .errors import ModelError
from .paths import artifact_path
from .identity_tokens import decode128

RANDOM_SCHEME = "random128-v1"
LEGACY_SCHEME = "legacy-sequential-v1"

def _prefix(value):
    if type(value) is not str or re.fullmatch(r"[A-Z][A-Z0-9]{1,7}", value) is None:
        raise ModelError("invalid_id_prefix", pointer="/id_prefix")
    return value


@dataclass(frozen=True)
class ArtifactIdentity:
    id: str
    id_scheme: str
    artifact_type: str
    id_prefix: str

    def __post_init__(self):
        _prefix(self.id_prefix)
        artifact_path(self.artifact_type, self.id, self.id_prefix)
        token = self.id.rsplit("-", 1)[-1]
        if self.id_scheme == RANDOM_SCHEME:
            decode128(token)
        elif self.id_scheme == LEGACY_SCHEME:
            if re.fullmatch(r"[0-9]{4}", token) is None:
                raise ModelError("identity_scheme_mismatch")
        else:
            raise ModelError("unsupported_id_scheme")

    @property
    def path(self):
        return artifact_path(self.artifact_type, self.id, self.id_prefix)


def artifact_identity(value):
    """Read only identity fields; display_id and other metadata are irrelevant."""
    if type(value) is not dict:
        raise ModelError("object_required")
    for name in ("id", "id_scheme", "artifact_type"):
        if name not in value:
            raise ModelError("missing_identity_field", pointer="/" + name)
    if type(value["id"]) is not str:
        raise ModelError("invalid_artifact_id", pointer="/id")
    prefix = value["id"].split("-", 1)[0]
    return ArtifactIdentity(value["id"], value["id_scheme"], value["artifact_type"], prefix)


def require_identity_unchanged(previous, proposed):
    """Reject identity mutation on normal updates; no generic migration escape.

    Filling missing legacy id_scheme belongs exclusively to the future migration
    workflow. This check is necessary but not sufficient to authorize an update.
    """
    before = artifact_identity(previous)
    after = artifact_identity(proposed)
    if before != after:
        raise ModelError("artifact_identity_immutable")
