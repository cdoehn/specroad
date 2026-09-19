"""Policy-aware fixed point over explicit complete dependency observations.

This module resolves stored outgoing edges. It does not invent reverse edges,
read a project, evaluate applicability, decide review currency, or build a
normative Scope-Hash. Those responsibilities stay with their existing/future
providers. `closure_complete` refers only to the supplied bound inventory.
"""
from dataclasses import dataclass

from ..model.canonical import canonical_json_sha256
from ..model.errors import ModelError
from .boundaries import boundary_for_relation
from .strong_closure import _resolve_closure_members


@dataclass(frozen=True)
class ScopeClosure:
    seeds: object
    bindings_sha256: str
    artifact_ids: tuple
    resource_ids: tuple
    attachments: tuple
    processing_order: tuple
    members: tuple
    boundary_references: tuple

    @property
    def data(self):
        return {
            'observation_version': 'scope-closure-observation-v1',
            'descriptor': self.seeds.descriptor.data,
            'seed_artifact_ids': list(self.seeds.artifact_ids),
            'seed_resource_ids': list(self.seeds.resource_ids),
            'seed_inputs_sha256': self.seeds.inputs_sha256,
            'bindings_sha256': self.bindings_sha256,
            'members': [member.data for member in self.members],
            'attachments': [item.data for item in self.attachments],
            'boundary_references': [item.data for item in self.boundary_references],
            'closure_complete': True,
        }

    @property
    def observation_sha256(self):
        return canonical_json_sha256(self.data)

    @property
    def closure_complete(self):
        return True

    @property
    def validation_scope(self):
        return 'closure_over_supplied_bindings'

    @property
    def atomic_snapshot(self):
        return False


def resolve_scope_closure(seeds, bindings, *, query_page=None):
    """Close weak edges or describe omitted targets; never downgrade strong edges.

    Targets already in the selected fixed point are internal, not boundaries.
    The complete origin inventory is required even for partial generation:
    missing targets or missing required providers remain model errors.
    """
    # The shared walker validates/recomputes seeds before reading their policy.
    from .strong_closure import _check_seeds
    _check_seeds(seeds, bindings, query_page)
    closed = seeds.descriptor.data['boundary_policy'] == 'closed'
    values = _resolve_closure_members(seeds, bindings, query_page=query_page, follow_weak=closed)
    weak_edges = values.pop('pending_weak_relations')
    included = set(values['artifact_ids'])
    records = {record.identity.id: record for record in bindings.inventory.records}
    edges = {edge.relation.identity.id: edge for edge in bindings.inventory.references.relations}
    boundaries = []
    if not closed:
        for source_id, relation_id, target_id in weak_edges:
            if target_id in included:
                continue
            target = records.get(target_id)
            edge = edges.get(relation_id)
            if (target is None or edge is None or edge.source.id != source_id
                    or edge.target.id != target_id):
                raise ModelError('boundary_origin_reference_missing')
            boundaries.append(boundary_for_relation(edge.relation, target))
    return ScopeClosure(**values, boundary_references=tuple(sorted(boundaries, key=lambda item: item.order_key)))
