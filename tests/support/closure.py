"""Synthetic complete dependency observations, never real review approvals."""
from specroad.graph.closure_inputs import ClosureBindings, artifact_node, resource_node
from specroad.graph.scope_descriptors import ScopeDescriptor
from specroad.graph.scope_seeds import resolve_scope_seeds
from specroad.graph.strong_closure import resolve_strong_closure
from .scopes import inputs, descriptor
from .records import record_value
from .relations import aid


def source(kind='requirement', number=1, **changes):
    """Use record fields for automatic dependencies and an owned common envelope."""
    from .relations import artifact
    if kind in ('evidence', 'verification', 'relation_review', 'baseline'):
        return record_value(kind, id=aid(kind, number), **changes)
    return artifact(kind, number, **changes)


def observe(inventory, *, uses=None, reviews=None, attachments=None):
    # These empty observations are justified ONLY by the test fixture. Product
    # callers must obtain them from real resource/profile/review services.
    use_map = {artifact_node(record.identity.id): () for record in inventory.records}
    use_map.update({resource_node(value.resource_id): () for value in inventory.resources})
    use_map.update({} if uses is None else uses)
    review_map = {item.relation.identity.id: () for item in inventory.references.relations}
    review_map.update({} if reviews is None else reviews)
    return ClosureBindings(inventory, uses=use_map, current_reviews=review_map, attachments=attachments)


def selected(inventory, artifact_ids=(), resource_ids=(), *, kind='explicit', selector=None):
    if selector is None:
        selector = ({'artifact_ids': sorted(artifact_ids), 'resource_ids': sorted(resource_ids)}
                    if kind == 'explicit' else {})
    return resolve_scope_seeds(ScopeDescriptor(descriptor(kind, selector)), inventory)


def subject(identity):
    return {'artifact_id': identity, 'revision': 1,
            'artifact_sha256': 'a' * 64, 'verification_context_sha256': 'b' * 64}


def slot(identity=None, check_id='overall'):
    return {'check_id': check_id, 'test_id': identity, 'dimension': 'overall'}
