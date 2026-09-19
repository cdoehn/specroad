"""Owned test selections for closure policy, not real bundle provenance."""
from specroad.graph.scope_descriptors import ScopeDescriptor
from specroad.graph.scope_seeds import resolve_scope_seeds
from .scopes import descriptor


def selection(inventory, identities=(), *, policy='partial', kind='explicit', selector=None,
              resource_ids=(), query_page=None):
    if selector is None:
        selector = {'artifact_ids': sorted(identities), 'resource_ids': sorted(resource_ids)} if kind == 'explicit' else {}
    return resolve_scope_seeds(ScopeDescriptor(descriptor(kind, selector, boundary_policy=policy)),
                               inventory, query_page=query_page)
