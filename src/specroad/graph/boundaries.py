"""Complete passive references for weak targets outside a partial selection.

These values are not authenticated origin evidence and do not authorize writes.
Every stored relation has a relation ID; this API never accepts its omission.
"""
from dataclasses import dataclass
import json
import re

from ..model.artifact_types import artifact_type
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.errors import ModelError
from ..model.identity_values import ArtifactIdentity
from ..model.relation_values import _relation_id
from ._scope_selector_contract import _artifact_id, _text
from .relations import Relation, SourceRelations
from .references import ResolvedRelation
from .strong_closure import WEAK_RELATIONS

_FIELDS = frozenset(('source_id', 'relation_id', 'relation_type', 'target_id',
                     'target_type', 'reason', 'origin_target_sha256'))


@dataclass(frozen=True, init=False)
class BoundaryReference:
    """Owned, immutable seven-field record; hash syntax is not provenance."""
    _encoded: bytes

    def __init__(self, value):
        if type(value) is not dict or set(value) != _FIELDS:
            raise ModelError('invalid_boundary_reference')
        _artifact_id(value['source_id'])
        _artifact_id(value['target_id'])
        _relation_id(value['relation_id'])
        artifact_type(value['target_type'])
        _artifact_id(value['target_id'], value['target_type'])
        if (value['source_id'].split('-')[0] != value['target_id'].split('-')[0]
                or value['source_id'] == value['target_id']):
            raise ModelError('boundary_endpoint_identity_mismatch')
        if type(value['relation_type']) is not str or value['relation_type'] not in WEAK_RELATIONS:
            raise ModelError('strong_relation_cannot_be_boundary')
        _text(value['reason'])
        digest = value['origin_target_sha256']
        if type(digest) is not str or re.fullmatch('[0-9a-f]{64}', digest) is None:
            raise ModelError('invalid_boundary_target_hash')
        object.__setattr__(self, '_encoded', canonical_json_bytes(value))

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
    ResolvedRelation(relation, relation.source, target.identity)
    return BoundaryReference({
        'source_id': relation.source.id, 'relation_id': relation.identity.id,
        'relation_type': relation.type, 'target_id': target.identity.id,
        'target_type': target.identity.artifact_type, 'reason': 'boundary_policy_partial',
        'origin_target_sha256': canonical_json_sha256(target.data),
    })
