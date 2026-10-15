"""Resolve a root configuration's declared dimensions and selected values.

The supplied inventory determines name uniqueness. It is not proof of complete
project discovery. Parent resolution, applicability and scope gates are later
services; an inherited configuration cannot masquerade as a resolved root.
"""
from dataclasses import dataclass
from hashlib import sha256
import json

from ..graph.relations import SourceRelations
from ..model.errors import ModelError
from ..storage.record_artifact import RecordArtifact


@dataclass(frozen=True, init=False)
class EffectiveConfiguration:
    """Owned effective root values; no source mutation or configuration approval."""
    configuration_id: str
    source_sha256: str
    _encoded: bytes

    def __init__(self, records, configuration_id):
        if type(records) not in (list, tuple):
            raise ModelError('configuration_inventory_required')
        if type(configuration_id) is not str or not configuration_id:
            raise ModelError('configuration_id_required')
        configurations, identifiers, names = {}, set(), set()
        for record in records:
            if type(record) is not SourceRelations:
                raise ModelError('configuration_source_required')
            # Rebuild from original bytes, never a caller's cached projections.
            source = SourceRelations(record.source_bytes, path=record.path)
            if source.identity.id in identifiers:
                raise ModelError('duplicate_configuration_inventory_id', path=source.path)
            identifiers.add(source.identity.id)
            if source.identity.artifact_type != 'configuration':
                continue
            checked = RecordArtifact(source.source_bytes, expected_type='configuration', path=source.path)
            value = checked.data
            if value['name'] in names:
                raise ModelError('duplicate_configuration_name', path=source.path, pointer='/name')
            names.add(value['name'])
            configurations[checked.id] = checked
        if configuration_id not in configurations:
            raise ModelError('configuration_missing')
        selected = configurations[configuration_id]
        value = selected.data
        if value.get('parent') is not None:
            raise ModelError('configuration_parent_resolution_required', path=selected.path, pointer='/parent')
        dimensions = value['dimensions']
        effective = {}
        for dimension in dimensions:
            name = dimension['name']
            effective[name] = (value['selection'][name] if name in value['selection']
                               else dimension['default'])
        data = {'configuration_id': selected.id, 'configuration_revision': value['revision'],
                'name': value['name'], 'dimensions': dimensions, 'effective_values': effective}
        object.__setattr__(self, 'configuration_id', selected.id)
        object.__setattr__(self, 'source_sha256', sha256(selected.source_bytes).hexdigest())
        object.__setattr__(self, '_encoded', json.dumps(data, ensure_ascii=False,
                                                     allow_nan=False).encode('utf-8'))

    @property
    def data(self):
        return json.loads(self._encoded)

    @property
    def effective_values(self):
        return self.data['effective_values']

    @property
    def dimensions(self):
        return self.data['dimensions']

    @property
    def validation_scope(self):
        return 'supplied_root_configuration_only'


def resolve_configuration(records, configuration_id):
    """Materialize every declared root dimension using selection, then default.

Only explicitly selected IDs are resolved. No implicit configuration, file
access, parent fallback, applicability decision or project completeness claim.
    """
    return EffectiveConfiguration(records, configuration_id)
