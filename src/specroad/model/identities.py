"""Artifact identity allocation against an explicit project inventory.

These are pure model operations, not a project scan or atomic filesystem claim.
The future transaction engine must bind/recheck the inventories and publish the
returned reservation with the artifact. No counter, network or branch is used.
"""

import secrets

from .artifact_types import artifact_type
from .errors import ModelError
from .identity_tokens import ALPHABET, encode128, decode128
from .identity_values import (ArtifactIdentity, RANDOM_SCHEME, LEGACY_SCHEME,
                              artifact_identity, require_identity_unchanged)
from .identity_inventory import IdentityInventory, IdentityAllocation

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


