"""Prepare the whole supplied project using its existing canonical root.

Unlike a selected scope, a complete project needs no inferred dependency
selection: every supplied normative input is retained. The native publication
gate must still prove the live inventory, validation and unchanged bytes.
"""
from .._metadata import MODEL_SCHEMA_VERSION, __version__
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.errors import ModelError
from ..model.paths import artifact_path
from ..model.semantic_configuration import semantic_configuration
from .baseline import BaselineManifest
from .objects import SnapshotObject


def build_project_baseline_manifest(model, *, baseline_id, configuration_id=None):
    """Prepare working data only; a supplied TargetModel grants no authority."""
    from ..changes.target_model import TargetModel, _default_scope
    if type(model) is not TargetModel:
        raise ModelError('baseline_target_model_required')
    model = model.snapshot()
    artifact_path('baseline', baseline_id, model.configuration.id_prefix)
    if baseline_id in {a['id'] for a in model.artifacts} | set(model.reserved_artifact_ids):
        raise ModelError('baseline_identity_already_present')
    if model.language_packages:
        raise ModelError('baseline_language_package_snapshot_provider_required')
    selection = None
    if configuration_id is not None:
        from ..configurations import resolve_configuration, evaluate_configuration
        from ..graph.relations import SourceRelations
        from ..graph.references import RelationReferences
        records = tuple(SourceRelations(d.content, path=d.path) for d in model.documents)
        selection = resolve_configuration(records, configuration_id)
        evaluated = evaluate_configuration(records, configuration_id).data
        if not evaluated['consistent']:
            raise ModelError('baseline_configuration_dependency_excluded')
        retained = set(evaluated['applicable_artifact_ids'])
        if not {r['id'] for r in selection.manifest['configurations']} <= retained:
            raise ModelError('baseline_configuration_chain_not_retained')
        selected = tuple(r for r in records if r.identity.id in retained)
        # The native provider has a closed project scope. Missing non-owning
        # targets also require an explicit boundary provider; never drop edges.
        RelationReferences(selected)
        archives = {row['object_path'] for r in selected if r.identity.artifact_type == 'baseline'
                    for row in r.data.get('manifest', []) if 'object_path' in row}
        all_archives = {r.data['path'] for r in model.resources if r.data['kind'] == 'archive'}
        model = TargetModel(model.configuration_bytes, model.binding,
            tuple(d for d in model.documents if d.path in {r.path for r in selected}),
            profile=model.profile, attachments=model.attachment_descriptors,
            resource_files=tuple(d for d in model.resource_files
                                if d.path not in all_archives or d.path in archives),
            language_packages=model.language_packages)
    manifest = model.manifest(model.artifacts, _default_scope())
    value = manifest.data
    if selection is not None:
        from ..model.manifest_projection import project_manifest_value
        from ..model.model_manifest import ModelManifest
        manifest = ModelManifest(project_manifest_value(model.binding.project_id,
            {**_default_scope(), 'configuration_id': selection.configuration_id},
            value['artifacts'], value['resources'], value['attachments'], value['boundary_references'],
            selection.scope_sha256(model.configuration), value['profile_sha256'],
            archive_objects=value.get('archive_objects', ())))
        value = manifest.data
    objects, rows = {}, []

    def include(role, raw, metadata, path=None, *, binary=False):
        item = SnapshotObject(raw) if binary else SnapshotObject.from_json(raw)
        ref = item.reference
        if metadata.get('sha256', ref.sha256) != ref.sha256:
            raise ModelError('baseline_object_binding_mismatch', path=path)
        if ref.path in objects and objects[ref.path].content != item.content:
            raise ModelError('snapshot_object_content_collision')
        objects[ref.path] = item
        rows.append({'role': role, **{k: v for k, v in metadata.items() if k != 'kind'},
            'object_path': ref.path, 'sha256': ref.sha256, 'size': ref.size,
            'media_type': metadata.get('media_type', 'application/octet-stream' if binary else 'application/json'),
            **({'source_path': path} if path is not None else {})})

    files = model.source_files
    for record in value['artifacts']:
        path = artifact_path(record['artifact_type'], record['id'], model.configuration.id_prefix)
        include('artifact', files[path], record, path)
    resources = {r.data.get('path', (r.data.get('id'), r.data.get('version'))): r.data
                 for r in model.resources}
    from ..model.manifest_resources import project_json_resource
    for document in model.resource_files:
        record = resources.get(document.path)
        if record is None:
            record = project_json_resource(model.configuration, document.path,
                                           document.content, model.binding).data
        include(record['kind'], document.content, record, document.path,
                binary=record['kind'] in ('attachment', 'archive', 'language_registry'))
    semantic = semantic_configuration(model.configuration)
    configuration_hash = canonical_json_sha256(semantic)
    include('semantic_configuration', canonical_json_bytes(semantic),
            {'sha256': configuration_hash}, 'specroad.json')
    if selection is not None:
        include('effective_configuration', canonical_json_bytes(selection.manifest), selection.binding)
    include('effective_profile', model.profile.canonical_bytes, {'sha256': value['profile_sha256']})
    include('model_manifest', manifest.canonical_bytes, {'sha256': manifest.sha256})
    rows.sort(key=lambda r: (r['role'].encode('utf-8'),
        r.get('id', r.get('source_path', '')).encode('utf-8'), r.get('version', '').encode('utf-8')))
    result = object.__new__(BaselineManifest)
    object.__setattr__(result, '_encoded', canonical_json_bytes({
        'baseline_manifest_version': 'baseline-manifest-v1', 'schema_version': MODEL_SCHEMA_VERSION,
        'tool_version': __version__, 'project_id': model.binding.project_id,
        'baseline_kind': 'working', 'baseline_id': baseline_id,
        'scope_descriptor': value['scope_descriptor'], 'scope_sha256': manifest.scope_sha256,
        'model_manifest': value, 'model_root_sha256': manifest.sha256,
        'configuration_hash': configuration_hash, 'profile_sha256': value['profile_sha256'],
        **({'configuration_binding': selection.binding} if selection is not None else {}),
        'profiles': model.profile.data['profiles'], 'boundary_references': value['boundary_references'],
        'manifest': rows}))
    object.__setattr__(result, 'objects', tuple(objects[p] for p in sorted(objects)))
    return result
