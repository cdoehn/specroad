"""Immutable observations used by strong closure; never a filesystem resolver.

Usage and current-review selections must be supplied by their respective
services. An explicit empty observation is different from a missing provider.
Hashes bind these observations to source bytes; they do not authenticate them.
"""
from dataclasses import dataclass
from hashlib import sha256
from types import MappingProxyType

from ..model.attachments import AttachmentDescriptor
from ..model.canonical import canonical_json_sha256
from ..model.errors import ModelError
from ._scope_selector_contract import _artifact_id, _text
from .scope_inputs import ScopeSeedInputs, _sequence


@dataclass(frozen=True)
class ClosureNode:
    kind: str
    identity: str

    def __post_init__(self):
        if type(self.kind) is not str or self.kind not in ('artifact', 'resource'):
            raise ModelError('closure_node_kind_invalid')
        (_artifact_id if self.kind == 'artifact' else _text)(self.identity)

    @property
    def data(self):
        return {'kind': self.kind, 'identity': self.identity}

    @property
    def order_key(self):
        return self.identity.encode('utf-8'), self.kind.encode('ascii')


def artifact_node(identity):
    return ClosureNode('artifact', identity)


def resource_node(identity):
    return ClosureNode('resource', identity)


def _mapping(value, reason):
    if type(value) is not dict:
        raise ModelError(reason)
    return value


@dataclass(frozen=True, init=False)
class ClosureBindings:
    """Explicit resource-use and review observations for one source inventory.

    ``uses`` maps each visited node to all the normative resources it uses.
    It must include an explicit empty tuple for a source without such uses.
    ``current_reviews`` maps each relation of a visited artifact to the review
    IDs selected by the freshness evaluator, also explicitly empty when none
    are current. No persisted review is assumed current simply because it exists.
    ``attachments`` maps opaque resource IDs to already observed descriptors.
    This value does not read files, evaluate profiles/reviews or verify payloads.
    """
    inventory: ScopeSeedInputs
    uses: object
    current_reviews: object
    attachments: object
    fingerprint: str

    def __init__(self, inventory, *, uses, current_reviews, attachments=None):
        if type(inventory) is not ScopeSeedInputs:
            raise ModelError('closure_seed_inventory_required')
        nodes = {artifact_node(record.identity.id) for record in inventory.records}
        nodes.update(resource_node(value.resource_id) for value in inventory.resources)
        resource_index = {value.resource_id: value for value in inventory.resources}
        record_index = {record.identity.id: record for record in inventory.records}
        relations = {edge.relation.identity.id: edge for edge in inventory.references.relations}
        use_map = {}
        for source, targets in _mapping(uses, 'closure_usage_observations_required').items():
            if type(source) is not ClosureNode or source not in nodes:
                raise ModelError('closure_usage_source_missing')
            targets = _sequence(targets)
            for target in targets:
                if type(target) is not ClosureNode or target.kind != 'resource':
                    raise ModelError('closure_usage_resource_target_required')
                if target not in nodes:
                    raise ModelError('closure_bound_resource_missing')
            if len(set(targets)) != len(targets):
                raise ModelError('duplicate_closure_usage')
            use_map[source] = tuple(sorted(targets, key=lambda node: node.order_key))
        review_map = {}
        for relation_id, review_ids in _mapping(current_reviews, 'closure_review_observations_required').items():
            if type(relation_id) is not str or relation_id not in relations:
                raise ModelError('closure_review_relation_missing')
            review_ids = _sequence(review_ids)
            for review_id in review_ids:
                _artifact_id(review_id, 'relation_review')
                record = record_index.get(review_id)
                if record is None:
                    raise ModelError('closure_current_review_missing')
                if record.data.get('relation_id') != relation_id:
                    raise ModelError('closure_review_relation_mismatch')
            if len(set(review_ids)) != len(review_ids):
                raise ModelError('duplicate_closure_review')
            review_map[relation_id] = tuple(sorted(review_ids, key=lambda value: value.encode('utf-8')))
        attachment_map = {}
        for identity, descriptor in _mapping({} if attachments is None else attachments,
                                              'closure_attachment_observations_required').items():
            resource = resource_index.get(identity) if type(identity) is str else None
            if resource is None or resource.kind != 'attachment':
                raise ModelError('closure_attachment_resource_missing')
            if type(descriptor) is not AttachmentDescriptor or descriptor.sha256 != resource.sha256:
                raise ModelError('closure_attachment_binding_mismatch')
            attachment_map[identity] = descriptor
        if len({item.path for item in attachment_map.values()}) != len(attachment_map):
            raise ModelError('duplicate_closure_attachment_path')
        data = {
            'binding_version': 'strong-closure-inputs-v1', 'seed_inputs_sha256': inventory.fingerprint,
            'uses': [{'source': node.data, 'targets': [target.data for target in use_map[node]]}
                     for node in sorted(use_map, key=lambda item: item.order_key)],
            'current_reviews': {key: list(value) for key, value in review_map.items()},
            'attachments': {key: value.data for key, value in attachment_map.items()},
        }
        for name, value in (('inventory', inventory), ('uses', MappingProxyType(use_map)),
                            ('current_reviews', MappingProxyType(review_map)),
                            ('attachments', MappingProxyType(attachment_map)),
                            ('fingerprint', canonical_json_sha256(data))):
            object.__setattr__(self, name, value)

    @property
    def validation_scope(self):
        return 'explicit_dependency_observations_only'
