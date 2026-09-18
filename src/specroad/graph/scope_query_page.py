"""Neutral page binding shared by future query resolvers and seed selection.

The page adapter never evaluates filters or authenticates query outcomes.
"""
from dataclasses import dataclass
from ..model.errors import ModelError
from .scope_descriptors import ScopeDescriptor
from ._scope_selector_contract import _artifact_id
from .scope_inputs import ScopeSeedInputs, _sequence


@dataclass(frozen=True, init=False)
class QuerySeedPage:
    """Bind the actual page supplied by a trusted query engine to its inputs.

    Membership, pagination and bindings are checked here; filter evaluation and
    ordering correctness must be established by the query engine. No metadata
    supplied by a project is treated as executable code or as proof of success.
    """
    descriptor_sha256: str
    inputs_sha256: str
    artifact_ids: tuple
    total: int

    def __init__(self, descriptor, inputs, artifact_ids, *, total):
        if type(descriptor) is not ScopeDescriptor or descriptor.scope_kind != 'query':
            raise ModelError('query_scope_descriptor_required')
        if type(inputs) is not ScopeSeedInputs:
            raise ModelError('scope_seed_inputs_required')
        if descriptor.data['configuration_id'] is not None:
            raise ModelError('configured_query_resolver_required')
        ids = _sequence(artifact_ids)
        known = {record.identity.id for record in inputs.records}
        for value in ids:
            _artifact_id(value)
            if value not in known:
                raise ModelError('query_seed_missing')
        if len(set(ids)) != len(ids):
            raise ModelError('duplicate_query_seed')
        query = descriptor.data['selector']['query']
        if (type(total) is not int or total < 0 or total > len(known)
                or len(ids) != max(0, min(query['limit'], total - query['offset']))):
            raise ModelError('query_seed_pagination_mismatch')
        for name, value in (('descriptor_sha256', descriptor.sha256), ('inputs_sha256', inputs.fingerprint),
                            ('artifact_ids', ids), ('total', total)):
            object.__setattr__(self, name, value)


