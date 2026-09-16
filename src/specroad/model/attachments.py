"""Passive attachment declarations; integrity is verified by the storage layer."""

from dataclasses import dataclass
import re

from .errors import ModelError
from .paths import project_path


@dataclass(frozen=True)
class AttachmentDescriptor:
    path: str
    media_type: str
    size: int
    sha256: str

    def __post_init__(self):
        project_path(self.path)
        if (type(self.media_type) is not str or not self.media_type.strip()
                or any(ord(c) < 32 or ord(c) == 127 for c in self.media_type)):
            raise ModelError("invalid_attachment_media_type", path=self.path)
        try:
            self.media_type.encode("utf-8")
        except UnicodeError as error:
            raise ModelError("invalid_attachment_media_type", path=self.path) from error
        if type(self.size) is not int or self.size < 0:
            raise ModelError("invalid_attachment_size", path=self.path)
        if type(self.sha256) is not str or not re.fullmatch(r"[0-9a-f]{64}", self.sha256):
            raise ModelError("invalid_attachment_hash", path=self.path)

    @classmethod
    def from_data(cls, value):
        if type(value) is not dict or set(value) != {"path", "media_type", "size", "sha256"}:
            raise ModelError("invalid_attachment_descriptor")
        return cls(**value)

    @property
    def data(self):
        return {"path": self.path, "media_type": self.media_type,
                "size": self.size, "sha256": self.sha256}
