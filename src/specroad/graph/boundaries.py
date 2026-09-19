"""Complete passive references for weak targets outside a partial selection.

These values are not authenticated origin evidence and do not authorize writes.
Every stored relation has a relation ID; this API never accepts its omission.
"""
from dataclasses import dataclass
import json

from ..model.canonical import canonical_json_sha256
from ..model.errors import ModelError
from .relations import Relation, SourceRelations
from ._boundary_contract import encode_boundary, require_relation_target


@dataclass(frozen=True, init=False)
class BoundaryReference:
    """Owned, immutable seven-field record; hash syntax is not provenance."""
    _encoded: bytes

    def __init__(self, value):
        object.__setattr__(self, '_encoded', encode_boundary(value))

    @property
    def data(self):
        return json.loads(self._encoded)

    @property
    def key(self):
        value = self.data
        return tuple(value[name] for name in ('source_id', 'relation_id', 'target_id'))

    @property
    def order_key(self):
        return tuple(part.encode('utf-8') for part in self.key)


def boundary_for_relation(relation, target):
    """Bind a validated stored weak edge to its actual omitted origin target."""
    if type(relation) is not Relation or type(target) is not SourceRelations:
        raise ModelError('boundary_source_values_required')
    require_relation_target(relation, target.identity)
    return BoundaryReference({
        'source_id': relation.source.id, 'relation_id': relation.identity.id,
        'relation_type': relation.type, 'target_id': target.identity.id,
        'target_type': target.identity.artifact_type, 'reason': 'boundary_policy_partial',
        'origin_target_sha256': canonical_json_sha256(target.data),
    })
