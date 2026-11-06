"""Owned passive metadata values; no policy selection or source acquisition."""
from dataclasses import dataclass
from hashlib import sha256
from ..model.canonical import canonical_json_bytes as jcs
from ..model.errors import ModelError
from ..storage.json_syntax import parse_json_object as parsed

@dataclass(frozen=True, init=False)
class MergeMetadata:
    _encoded: bytes
    _files: tuple

    @classmethod
    def _create(cls, data, files):
        value = object.__new__(cls)
        object.__setattr__(value, '_encoded', jcs(data))
        object.__setattr__(value, '_files', tuple(sorted(files.items())))
        return value

    @property
    def data(self):
        return parsed(self._encoded)

    @property
    def canonical_bytes(self):
        return self._encoded

    @property
    def sha256(self):
        return sha256(self._encoded).hexdigest()

    @property
    def files(self):
        if not self.data['metadata_complete']:
            raise ModelError('merge_metadata_incomplete')
        return dict(self._files)

    @property
    def ready(self):
        return False

    @property
    def write_authorized(self):
        return False

    @property
    def approval_granted(self):
        return False

    def __bool__(self):
        raise TypeError('Merge metadata is not target validation or write authority')
