"""Shared passive boundary field and endpoint contract; no IO or publication.

The value constructor, origin-based generator and partial reader reuse this
contract. Source inventory membership and actual target hashes remain explicit
caller checks rather than being inferred from an isolated reference record.
"""
import re

from ..model.artifact_types import artifact_type
from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..model.identity_values import ArtifactIdentity
from ..model.relation_values import _relation_id
from ._scope_selector_contract import _artifact_id, _text
from .references import ResolvedRelation
from .strong_closure import WEAK_RELATIONS

_FIELDS = frozenset(('source_id', 'relation_id', 'relation_type', 'target_id',
                     'target_type', 'reason', 'origin_target_sha256'))


def encode_boundary(value):
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
    return canonical_json_bytes(value)


def _target_identity(value):
    token = value['target_id'].rsplit('-', 1)[-1]
    scheme = 'legacy-sequential-v1' if len(token) == 4 else 'random128-v1'
    return ArtifactIdentity(value['target_id'], scheme, value['target_type'], value['target_id'].split('-')[0])



def require_relation_target(relation, target):
    """Apply the same stored-edge/endpoint contract without asserting existence."""
    return ResolvedRelation(relation, relation.source, target)


def require_boundary_match(data, relation):
    if data['relation_type'] != relation.type:
        raise ModelError('boundary_reference_mismatch')
    return require_relation_target(relation, _target_identity(data))
