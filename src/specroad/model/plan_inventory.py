"""Owned projected identities; no second graph, ID allocation or file writer."""
from dataclasses import dataclass
from .plan_projection import PlanProjection
from .errors import ModelError
from .identity_inventory import IdentityInventory
from .canonical import canonical_json_bytes
from ..storage.json_syntax import parse_json_object


@dataclass(frozen=True, init=False)
class PlanProjectionInventory:
    _encoded: bytes

    def __init__(self, values, *, id_prefix):
        if type(values) not in (tuple, list):
            raise ModelError('plan_projection_sequence_required')
        projections = [PlanProjection(v, id_prefix=id_prefix) for v in values]
        data = [p.data for p in projections]
        # Use the same project-wide identity collision rule as native artifacts.
        IdentityInventory(id_prefix, [v['id'] for v in data], [], [])
        displays, relations, claims = set(), set(), set()
        for value in data:
            owner = value['id'] if value['artifact_type'] == 'implementation_plan' else value['plan_id']
            key = owner, value['display_id']
            if key in displays:
                raise ModelError('duplicate_plan_display_id', pointer='/display_id')
            displays.add(key)
            rows = [*value['prerequisites'], *value.get('requirement_bindings', []), *value['relations']]
            identifiers = [r['relation_id'] for r in rows]
            if 'parent_relation_id' in value:
                identifiers.append(value['parent_relation_id'])
            for identity in identifiers:
                if identity in relations:
                    raise ModelError('duplicate_plan_relation_id')
                relations.add(identity)
            for claim in value.get('coverage_claims', []):
                key = owner, claim['claim_id']
                if key in claims:
                    raise ModelError('duplicate_plan_claim_id')
                claims.add(key)
        object.__setattr__(self, '_encoded', canonical_json_bytes({'projections': data}))

    @property
    def projections(self):
        return tuple(PlanProjection(v) for v in parse_json_object(self._encoded)['projections'])
