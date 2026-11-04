"""Native original-byte admission shared by complete in-memory readers."""
from ..graph.relations import SourceRelations
from ..model.canonical import canonical_json_sha256
from ..model.model_manifest import ManifestResource
from ..storage.json_syntax import parse_json_object
from .legacy_manifest import validate_legacy_manifest
from .plan_values import MANIFEST_PATH, require


def qualified(files, project_id):
    if MANIFEST_PATH not in files:
        return None
    return validate_legacy_manifest(dict(files), project_id=project_id)


def original(legacy, path, raw):
    if legacy is not None and path.startswith('spec/') and path in legacy.protected_paths:
        return legacy.artifact(path, raw)
    return None


def records(model):
    legacy = getattr(model, 'legacy_manifest', None)
    result = []
    for document in model.documents:
        item = original(legacy, document.path, document.content)
        result.append(SourceRelations.from_legacy(item) if item is not None else
                      SourceRelations(document.content, path=document.path))
    return tuple(result)


def artifact_resource(model, value):
    legacy = getattr(model, 'legacy_manifest', None)
    if legacy is not None:
        for document in model.documents:
            item = original(legacy, document.path, document.content)
            if item is not None and item.id == value['id']:
                require(value == item.navigation or value == item.data,
                        'legacy_original_projection_changed', path=document.path)
                return item.manifest_resource(model.binding)
    return ManifestResource(model.binding, {'kind': 'artifact', 'id': value['id'],
        'artifact_type': value['artifact_type'], 'revision': value['revision'],
        'sha256': canonical_json_sha256(value)})


def is_original(model, document):
    legacy = getattr(model, 'legacy_manifest', None)
    return original(legacy, document.path, document.content) is not None
