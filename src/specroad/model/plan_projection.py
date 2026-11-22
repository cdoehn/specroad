"""Owned field projections addressed through one carrier, never shadow files."""
from dataclasses import dataclass
from .canonical import canonical_json_bytes, canonical_json_sha256
from .plan_schemas import validate_plan_fields
from .paths import artifact_path
from ..storage.json_syntax import parse_json_object


@dataclass(frozen=True, init=False)
class PlanProjection:
    _encoded: bytes

    def __init__(self, value, *, id_prefix=None):
        validate_plan_fields(value, id_prefix=id_prefix)
        object.__setattr__(self, '_encoded', canonical_json_bytes(value))

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def sha256(self):
        return canonical_json_sha256(self.data)

    @property
    def path(self):
        v = self.data
        return artifact_path(v['artifact_type'], v['id'], v['id'].split('-')[0], plan_id=v.get('plan_id'))

    @property
    def validation_scope(self):
        return 'plan_projection_fields_only'
