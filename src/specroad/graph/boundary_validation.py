"""Exact relation/boundary matching for supplied partial records.

This is reusable by future bundle readers. It is not archive verification, an
origin-root authentication step or proof that the local source set is complete.
Omitted target hashes can be checked only against explicitly supplied origin
records; without those, only the relation contract and hash shape are verified.
"""
from dataclasses import dataclass

from ..model.canonical import canonical_json_sha256
from ..model.errors import ModelError
from ..model.identity_values import ArtifactIdentity
from .boundaries import BoundaryReference
from .references import RelationReferences, ResolvedRelation
from .relations import SourceRelations
from .scope_descriptors import ScopeDescriptor
from .scope_inputs import _sequence
from .strong_closure import WEAK_RELATIONS


def _sources(values):
    records = _sequence(values)
    by_id = {}
    prefixes = set()
    relation_ids = set()
    externals = set()
    for record in records:
        if type(record) is not SourceRelations:
            raise ModelError('source_relations_required')
        if record.identity.id in by_id:
            raise ModelError('duplicate_artifact_id')
        by_id[record.identity.id] = record
        prefixes.add(record.identity.id_prefix)
        for relation in record.relations:
            if relation.identity.id in relation_ids:
                raise ModelError('duplicate_relation_id')
            relation_ids.add(relation.identity.id)
            for external in relation.data['external_identities']:
                key = tuple(external[name] for name in ('source_system', 'source_document', 'external_id'))
                if key in externals:
                    raise ModelError('duplicate_external_relation_identity')
                externals.add(key)
    if len(prefixes) > 1:
        raise ModelError('mixed_project_prefix')
    return by_id


def _target_identity(value):
    token = value['target_id'].rsplit('-', 1)[-1]
    scheme = 'legacy-sequential-v1' if len(token) == 4 else 'random128-v1'
    return ArtifactIdentity(value['target_id'], scheme, value['target_type'], value['target_id'].split('-')[0])


@dataclass(frozen=True)
class PartialRelationValidation:
    source_ids: tuple
    local_relations: tuple
    boundary_references: tuple
    origin_hashes_verified: bool

    @property
    def validation_scope(self):
        return 'partial_relation_bindings_only'


def validate_boundary_references(sources, declarations, *, descriptor, origin_sources=None):
    """Require exactly one correct declaration for every omitted weak target.

    Existing local targets require none. Strong targets must be present locally;
    even a correct origin hash never replaces a missing strong dependency.
    When origin_sources is supplied, require matching local source content and
    complete origin references, then check each omitted target's canonical hash.
    """
    if type(descriptor) is not ScopeDescriptor:
        raise ModelError('scope_descriptor_required')
    records = _sources(sources)
    boundaries = {}
    for index, declaration in enumerate(_sequence(declarations)):
        try:
            value = declaration if type(declaration) is BoundaryReference else BoundaryReference(declaration)
            if value.key in boundaries:
                raise ModelError('duplicate_boundary_reference')
            data = value.data
            if data['source_id'] not in records:
                raise ModelError('boundary_source_not_in_scope')
            if data['target_id'] in records:
                raise ModelError('boundary_target_already_in_scope')
            boundaries[value.key] = value
        except ModelError as error:
            error.pointer = '/boundary_references/' + str(index) + error.pointer
            raise
    partial = descriptor.data['boundary_policy'] == 'partial'
    if boundaries and not partial:
        raise ModelError('boundary_in_closed_scope')
    used = set()
    local = []
    for source_id in sorted(records, key=lambda item: item.encode('utf-8')):
        source = records[source_id]
        for relation in source.relations:
            target = records.get(relation.target)
            if target is not None:
                local.append(ResolvedRelation(relation, source.identity, target.identity))
                continue
            if relation.type not in WEAK_RELATIONS or not partial:
                raise ModelError('missing_relation_target', path=source.path, pointer='/relations')
            key = (source_id, relation.identity.id, relation.target)
            boundary = boundaries.get(key)
            if boundary is None:
                raise ModelError('boundary_reference_missing', path=source.path, pointer='/relations')
            data = boundary.data
            if data['relation_type'] != relation.type:
                raise ModelError('boundary_reference_mismatch')
            # Endpoint shape and matrix checks do not assert target existence.
            ResolvedRelation(relation, source.identity, _target_identity(data))
            used.add(key)
    if used != set(boundaries):
        raise ModelError('unexpected_boundary_reference')
    if origin_sources is not None:
        origin = _sources(origin_sources)
        RelationReferences(tuple(origin.values()))
        for source_id, source in records.items():
            if source_id not in origin:
                raise ModelError('boundary_origin_source_missing')
            if canonical_json_sha256(source.data) != canonical_json_sha256(origin[source_id].data):
                raise ModelError('boundary_origin_source_mismatch')
        for boundary in boundaries.values():
            data = boundary.data
            target = origin.get(data['target_id'])
            if target is None:
                raise ModelError('boundary_origin_target_missing')
            if (target.identity.artifact_type != data['target_type']
                    or canonical_json_sha256(target.data) != data['origin_target_sha256']):
                raise ModelError('boundary_origin_target_mismatch')
    return PartialRelationValidation(
        tuple(sorted(records, key=lambda item: item.encode('utf-8'))),
        tuple(sorted(local, key=lambda item: item.relation.key)),
        tuple(sorted(boundaries.values(), key=lambda item: item.order_key)),
        origin_sources is not None,
    )
