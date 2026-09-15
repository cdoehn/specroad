"""Artifact identity allocation against an explicit project inventory.

These are pure model operations, not a project scan or atomic filesystem claim.
The future transaction engine must bind/recheck the inventories and publish the
returned reservation with the artifact. No counter, network or branch is used.
"""

from dataclasses import dataclass
import re
import secrets

from .artifact_types import artifact_type, artifact_types
from .errors import ModelError
from .paths import artifact_path

ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
RANDOM_SCHEME = "random128-v1"
LEGACY_SCHEME = "legacy-sequential-v1"


def encode128(value):
    """Encode exactly sixteen octets, preserving all 128 bits and leading zeros."""
    if type(value) is not bytes or len(value) != 16:
        raise ModelError("entropy_bytes_required")
    number = int.from_bytes(value, "big")
    output = []
    for _ in range(26):
        output.append(ALPHABET[number & 31])
        number >>= 5
    return "".join(reversed(output))


def decode128(token):
    """Only canonical uppercase tokens; no Crockford input aliases or padding."""
    if (type(token) is not str or len(token) != 26 or token[0] not in "01234567"
            or any(character not in ALPHABET for character in token)):
        raise ModelError("invalid_identity_token")
    number = 0
    for character in token:
        number = (number << 5) | ALPHABET.index(character)
    return number.to_bytes(16, "big")


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


def _inventory_ids(values, prefix):
    if isinstance(values, (str, bytes, dict)):
        raise ModelError("identity_inventory_required")
    try:
        values = tuple(values)
    except TypeError as error:
        raise ModelError("identity_inventory_required") from error
    kinds = {item.prefix: item.artifact_type for item in artifact_types()}
    for identity in values:
        if type(identity) is not str:
            raise ModelError("invalid_inventory_identity")
        parts = identity.split("-")
        if len(parts) != 3 or parts[1] not in kinds:
            raise ModelError("invalid_inventory_identity")
        artifact_path(kinds[parts[1]], identity, prefix)
    return frozenset(values)


@dataclass(frozen=True)
class IdentityInventory:
    """All three sets are explicit. Historical IDs remain unavailable forever."""
    id_prefix: str
    current_ids: frozenset
    archived_ids: frozenset
    reserved_ids: frozenset

    def __post_init__(self):
        _prefix(self.id_prefix)
        for field in ("current_ids", "archived_ids", "reserved_ids"):
            object.__setattr__(self, field, _inventory_ids(getattr(self, field), self.id_prefix))

    def contains(self, identity):
        return identity in self.current_ids or identity in self.archived_ids or identity in self.reserved_ids

    def reserve(self, identity):
        if not isinstance(identity, ArtifactIdentity) or identity.id_prefix != self.id_prefix:
            raise ModelError("reservation_project_mismatch")
        if identity.id_scheme != RANDOM_SCHEME:
            raise ModelError("new_identity_must_be_random")
        if self.contains(identity.id):
            raise ModelError("identity_already_used")
        return IdentityInventory(self.id_prefix, self.current_ids, self.archived_ids,
                                 self.reserved_ids | {identity.id})


@dataclass(frozen=True)
class IdentityAllocation:
    identity: ArtifactIdentity
    inventory: IdentityInventory


def allocate_artifact_identity(kind, inventory):
    """Allocate and return an owned reservation; caller input stays unchanged."""
    if not isinstance(inventory, IdentityInventory):
        raise ModelError("identity_inventory_required")
    definition = artifact_type(kind)
    while True:
        try:
            random = secrets.token_bytes(16)
        except OSError as error:
            raise ModelError("entropy_unavailable") from error
        token = encode128(random)
        candidate = ArtifactIdentity(inventory.id_prefix + "-" + definition.prefix + "-" + token,
                                     RANDOM_SCHEME, kind, inventory.id_prefix)
        if not inventory.contains(candidate.id):
            return IdentityAllocation(candidate, inventory.reserve(candidate))
