"""Immutable inventory observations, independent of filesystem enumeration.

The byte-sensitive binding is not a model root, signature or write permission.
"""

from dataclasses import dataclass

from .attachments import AttachmentDescriptor
from .hashes import canonical_json_sha256


@dataclass(frozen=True)
class ResourceEntry:
    path: str
    kind: str
    size: int
    sha256: str
    canonical_sha256: str | None = None
    media_type: str | None = None

    @property
    def data(self):
        return {"path": self.path, "kind": self.kind, "size": self.size,
                "sha256": self.sha256, "canonical_sha256": self.canonical_sha256,
                "media_type": self.media_type}


@dataclass(frozen=True)
class ResourceInventory:
    project_id: str
    entries: tuple[ResourceEntry, ...]
    # An observed read binding is not a reusable write capability.
    source_root: str
    root_identity: tuple
    explicit_attachments: tuple[AttachmentDescriptor, ...] = ()

    @property
    def atomic_snapshot(self):
        return False

    @property
    def data(self):
        return {"inventory_format_version": 1, "scope": "current_resources",
                "project_id": self.project_id,
                "resources": [value.data for value in self.entries]}

    @property
    def sha256(self):
        # This byte-sensitive inventory binding is NOT model_root_sha256.
        return canonical_json_sha256(self.data)


