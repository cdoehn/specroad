"""Record validation and root-value resolution, independent of result storage."""
from ..graph.relations import SourceRelations
from ..model.errors import ModelError
from ..storage.record_artifact import RecordArtifact


def resolve_values(records, configuration_id):
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
    return selected, data
