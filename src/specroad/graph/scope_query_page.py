"""Neutral page binding shared by future query resolvers and seed selection.

The page adapter never evaluates filters or authenticates query outcomes.
"""
from dataclasses import dataclass
from ..model.errors import ModelError
from .scope_descriptors import ScopeDescriptor
from ._scope_selector_contract import _artifact_id
from .scope_inputs import ScopeSeedInputs, _sequence
from ._scope_applicability import ScopeApplicability


@dataclass(frozen=True, init=False)
class QuerySeedPage:
    """Bind the actual page supplied by a trusted query engine to its inputs.

    Membership, applicability, pagination and bindings are checked here. The
    query engine must select and page the applicable inventory before supplying
    this value; ordinary query filters and ordering remain its responsibility.
    No metadata
    supplied by a project is treated as executable code or as proof of success.
    """
    descriptor_sha256: str
    inputs_sha256: str
    artifact_ids: tuple
    total: int

    def __init__(self, descriptor, inputs, artifact_ids, *, total):
        if type(descriptor) is not ScopeDescriptor:
            raise ModelError('query_scope_descriptor_required')
        data = descriptor.data
        base = data['selector']['base_scope_descriptor'] if data['scope_kind'] == 'configuration' else data
        if base['scope_kind'] != 'query':
            raise ModelError('query_scope_descriptor_required')
        if type(inputs) is not ScopeSeedInputs:
            raise ModelError('scope_seed_inputs_required')
        ids = _sequence(artifact_ids)
        known = {record.identity.id for record in inputs.records}
        eligible = known
        if data['configuration_id'] is not None:
            if data['configuration_id'] not in known:
                raise ModelError('scope_configuration_missing')
            applicability = ScopeApplicability(data['configuration_id'], inputs.records)
            eligible = {record.identity.id for record in inputs.records if applicability.includes(record)}
        for value in ids:
            _artifact_id(value)
            if value not in known:
                raise ModelError('query_seed_missing')
            if value not in eligible:
                raise ModelError('query_seed_configuration_excluded')
        if len(set(ids)) != len(ids):
            raise ModelError('duplicate_query_seed')
        query = base['selector']['query']
        if (type(total) is not int or total < 0 or total > len(eligible)
                or len(ids) != max(0, min(query['limit'], total - query['offset']))):
            raise ModelError('query_seed_pagination_mismatch')
        for name, value in (('descriptor_sha256', descriptor.sha256), ('inputs_sha256', inputs.fingerprint),
                            ('artifact_ids', ids), ('total', total)):
            object.__setattr__(self, name, value)


