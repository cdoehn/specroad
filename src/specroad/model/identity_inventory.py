"""Explicit immutable project ID inventories; no filesystem or entropy access."""

from dataclasses import dataclass

from .artifact_types import artifact_types
from .errors import ModelError
from .paths import artifact_path
from .identity_values import ArtifactIdentity, RANDOM_SCHEME, _prefix

def _inventory_ids(values, prefix, *, reject_duplicates=False):
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
    if reject_duplicates and len(set(values)) != len(values):
        raise ModelError("duplicate_artifact_id")
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
            object.__setattr__(self, field, _inventory_ids(getattr(self, field), self.id_prefix,
                               reject_duplicates=field == "current_ids"))

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

    def __post_init__(self):
        if (not isinstance(self.identity, ArtifactIdentity)
                or not isinstance(self.inventory, IdentityInventory)
                or self.identity.id_prefix != self.inventory.id_prefix
                or self.identity.id_scheme != RANDOM_SCHEME
                or self.identity.id not in self.inventory.reserved_ids
                or self.identity.id in self.inventory.current_ids
                or self.identity.id in self.inventory.archived_ids):
            raise ModelError("allocation_reservation_mismatch")


