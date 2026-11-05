"""Detached relation candidates and original conflict observations."""
from dataclasses import dataclass
from hashlib import sha256
from ..model.canonical import canonical_json_bytes as jcs
from ..model.errors import ModelError
from ..storage.json_syntax import parse_json_object


@dataclass(frozen=True, init=False)
class RelationMergeResult:
    _encoded: bytes

    @classmethod
    def _create(cls, sources, history_hash, candidates, conflicts):
        result = object.__new__(cls)
        object.__setattr__(result, '_encoded', jcs({
            'source_bindings': sources.binding, 'source_bindings_sha256': sources.sha256,
            'history_sha256': history_hash, 'relations': None if conflicts else candidates,
            'conflicts': conflicts, 'ready': False, 'write_authorized': False}))
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
    def merged(self):
        return not self.conflicts

    @property
    def relations(self):
        if not self.merged:
            raise ModelError('unresolved_relation_merge')
        return self.data['relations']

    @property
    def ready(self):
        return False

    @property
    def write_authorized(self):
        return False

    def __bool__(self):
        raise TypeError('Relation candidates do not authorize a merge or write')
