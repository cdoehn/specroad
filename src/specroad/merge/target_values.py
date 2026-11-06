"""Owned passive merge-validation values, with no write or review authority."""
from dataclasses import dataclass
from hashlib import sha256

from ..model.canonical import canonical_json_bytes as jcs
from ..model.errors import ModelError
from ..storage.json_syntax import parse_json_object as parsed


@dataclass(frozen=True, init=False)
class MergeTarget:
    """A passive validation observation, never a writer or an approval."""
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
    def target_validated(self):
        return self.data['target_validated']

    @property
    def files(self):
        if not self.target_validated:
            raise ModelError('merge_target_not_validated')
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
        raise TypeError('Target validation is not publication or approval')
