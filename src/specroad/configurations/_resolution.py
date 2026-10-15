"""Record validation and parent-chain resolution, independent of result storage."""
from ._parents import resolve_parent_chain
from ..graph.relations import SourceRelations
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.errors import ModelError
from ..model._schema import _json_equal
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
    chain = resolve_parent_chain(configurations, selected)
    declared, effective = {}, {}
    for configuration in chain:
        value = configuration.data
        for index, dimension in enumerate(value['dimensions']):
            name = dimension['name']
            if name in declared:
                if canonical_json_bytes(dimension) != canonical_json_bytes(declared[name]):
                    raise ModelError('inherited_dimension_changed', path=configuration.path,
                                     pointer='/dimensions/' + str(index))
            else:
                declared[name] = dimension
        for name, choice in value['selection'].items():
            if name not in declared:
                raise ModelError('unknown_dimension', path=configuration.path, pointer='/selection')
            if not any(_json_equal(choice, allowed) for allowed in declared[name]['allowed_values']):
                raise ModelError('invalid_dimension_selection', path=configuration.path, pointer='/selection')
            effective[name] = choice
    dimensions = list(declared.values())
    for dimension in dimensions:
        name = dimension['name']
        if name not in effective:
            if 'default' not in dimension:
                raise ModelError('missing_dimension_selection', path=selected.path, pointer='/selection')
            effective[name] = dimension['default']
    value = selected.data
    data = {'configuration_id': selected.id, 'configuration_revision': value['revision'],
            'name': value['name'], 'dimensions': dimensions, 'effective_values': effective}
    manifest = {'manifest_version': 'effective-configuration-v1', 'configuration_id': selected.id,
                'configurations': [{'id': record.id, 'revision': record.data['revision'],
                                    'sha256': canonical_json_sha256(record.data)} for record in chain],
                'dimensions': sorted(dimensions, key=lambda item: item['name'].encode('utf-8')),
                'effective_values': effective}
    return selected, data, manifest
