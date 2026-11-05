"""Owned lifecycle observations and protected-original byte subsets."""
from dataclasses import dataclass
from hashlib import sha256
from ..model.canonical import canonical_json_bytes as jcs
from ..model.errors import ModelError
from ..storage.json_syntax import parse_json_object


@dataclass(frozen=True, init=False)
class LifecycleMergeResult:
    _encoded: bytes
    _originals: tuple

    @classmethod
    def _create(cls, sources, history_hash, decisions, originals, conflicts):
        result = object.__new__(cls)
        object.__setattr__(result, '_encoded', jcs({
            'source_bindings': sources.binding, 'source_bindings_sha256': sources.sha256,
            'history_sha256': history_hash, 'metadata_policy_version': 'merge-metadata-v1',
            'decisions': decisions, 'conflicts': conflicts, 'ready': False,
            'write_authorized': False, 'approval_granted': False}))
        object.__setattr__(result, '_originals', tuple(sorted(originals.items())) if not conflicts else ())
        return result

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def canonical_bytes(self):
        return self._encoded

    @property
    def sha256(self):
        return sha256(self._encoded).hexdigest()

    @property
    def conflicts(self):
        return self.data['conflicts']

    @property
    def compatible(self):
        return not self.conflicts

    @property
    def originals(self):
        """Protected subset only, with exact source bytes; never a full target."""
        if not self.compatible:
            raise ModelError('unresolved_lifecycle_merge')
        return dict(self._originals)

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
        raise TypeError('History compatibility is not merge, write or review approval')
