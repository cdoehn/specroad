"""Qualify originals, never re-label source bytes as current schema documents."""
from ..model.errors import ModelError
from ..graph.relations import SourceRelations
from ..migration.legacy_manifest import validate_legacy_manifest
from ..migration.legacy_values import LegacyManifest
from ..storage.json_syntax import parse_json_object


def qualified_legacy_records(legacy, documents):
    if legacy is None:
        return {}
    if type(legacy) is not LegacyManifest:
        raise ModelError('validation_native_legacy_manifest_required')
    checked = validate_legacy_manifest(dict(legacy._files), project_id=legacy.data['source']['project_id'])
    if checked._encoded != legacy._encoded or checked.byte_bindings != legacy.byte_bindings:
        raise ModelError('validation_legacy_binding_changed')
    registered = {row['path'] for row, original in checked._originals
                  if row['path'].startswith('spec/') and row['role'] == 'artifact'}
    provided = {d.path for d in documents}
    if not registered <= provided:
        raise ModelError('validation_legacy_inventory_incomplete')
    records = {}
    for doc in documents:
        if doc.path in registered:
            records[doc.path] = SourceRelations.from_legacy(checked.artifact(doc.path, doc.content))
    return records
