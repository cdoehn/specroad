"""Local edges for a bound partial reader, without fabricated outside records.

Missing edges are checked when reached by the shared closure walker and by
exact boundary validation. Complete-origin inventories retain their strict API.
"""
from dataclasses import dataclass

from ..model.errors import ModelError
from ..model._bundle_scope_contract import PARTIAL
from .scope_descriptors import ScopeDescriptor
from .boundary_validation import _sources
from .references import ResolvedRelation


@dataclass(frozen=True)
class LocalScopeReferences:
    sources: tuple
    relations: tuple


def local_scope_references(records, descriptor):
    if type(descriptor) is not ScopeDescriptor or not PARTIAL.matches_scope(descriptor.data):
        raise ModelError('partial_scope_descriptor_required')
    index = _sources(records)
    local = tuple(ResolvedRelation(edge, record.identity, index[edge.target].identity)
                  for record in records for edge in record.relations if edge.target in index)
    return LocalScopeReferences(tuple(index[key].identity for key in sorted(index)),
                                tuple(sorted(local, key=lambda item: item.relation.key)))
