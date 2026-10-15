"""Prepare byte-backed Baseline manifests over an explicitly resolved scope.

The caller supplies complete, current dependency observations and effective
project policy. This pure preparation neither discovers a project nor creates
a Baseline artifact. Validation, locking and journalled publication belong to
the specialized writer; a release label grants no readiness or write approval.
"""
from dataclasses import dataclass
from hashlib import sha256

from .._metadata import MODEL_SCHEMA_VERSION, __version__
from ..graph.closure_inputs import ClosureBindings
from ..graph.scope_closure import ScopeClosure
from ..graph.scope_hash import fingerprint_scope
from ..model.canonical import canonical_json_bytes
from ..model.configuration import ProjectConfiguration
from ..model.errors import ModelError
from ..model.manifest_resources import project_json_resource
from ..model.model_manifest import ProjectReadBinding
from ..model.paths import artifact_path
from ..model.semantic_configuration import semantic_configuration
from ..storage.json_syntax import parse_json_object
from .objects import SnapshotObject
from ._baseline_inputs import _owned_inputs, _resource_objects, _checked_profile


@dataclass(frozen=True, init=False)
class BaselineManifest:
    """Owned inert manifest and deduplicated objects, not a publication receipt."""
    _encoded: bytes
    objects: tuple

    def __init__(self, *args, **kwargs):
        raise TypeError('Use build_baseline_manifest with resolved inputs')

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def canonical_bytes(self):
        return self._encoded

    @property
    def sha256(self):
        return sha256(self._encoded).hexdigest()

    @property
    def model_root_sha256(self):
        return self.data['model_root_sha256']

    @property
    def assurance(self):
        return {'validation_scope': 'supplied_scope_and_object_bytes',
                'project_completeness_verified': False, 'atomic_snapshot': False,
                'full_validation_passed': False, 'write_authorized': False,
                'release_authorized': False}


def build_baseline_manifest(configuration, binding, closure, dependencies, *,
                            baseline_kind, effective_profile, resource_payloads,
                            attachment_payloads, query_page=None, baseline_id=None):
    """Bind every selected object to the existing scope/model hash projection.

    resource_payloads maps each selected non-attachment inventory identity to
    (project-relative path, original JSON bytes). attachment_payloads maps every
    selected attachment path to its exact bytes. Missing and surplus payloads
    fail. Language/archival providers and configured-scope snapshots remain
    explicit integration boundaries; they cannot produce a partial manifest.
    A writer supplies its planned baseline_id: it must be absent from the entire
    input inventory, including unselected controls. The identity is metadata,
    outside the precreation model root. Omitting it prepares only unnamed data.
    """
    if type(baseline_kind) is not str or baseline_kind not in ('working', 'release'):
        raise ModelError('baseline_kind_invalid')
    if type(configuration) is not ProjectConfiguration or type(binding) is not ProjectReadBinding:
        raise ModelError('baseline_project_binding_required')
    if type(closure) is not ScopeClosure or type(dependencies) is not ClosureBindings:
        raise ModelError('baseline_resolved_scope_required')
    configuration, binding, dependencies = _owned_inputs(
        configuration, binding, closure, dependencies, query_page)
    if baseline_id is not None:
        artifact_path('baseline', baseline_id, configuration.id_prefix)
        if baseline_id in {record.identity.id for record in dependencies.inventory.records}:
            raise ModelError('baseline_identity_already_present')
    if closure.seeds.descriptor.data['configuration_id'] is not None:
        raise ModelError('baseline_configured_scope_provider_required')
    records, resources, profiles = _resource_objects(
        configuration, binding, closure, dependencies, resource_payloads)
    profile = _checked_profile(effective_profile, profiles, dependencies)
    model = fingerprint_scope(configuration, binding, closure, dependencies,
        effective_profile=profile.data, resource_records=records, query_page=query_page)
    model_value = model.data
    objects, entries = {}, []

    def include(role, item, metadata, *, path=None, media_type='application/json'):
        reference = item.reference
        if reference.path in objects and objects[reference.path].content != item.content:
            raise ModelError('snapshot_object_content_collision')
        if 'sha256' in metadata and metadata['sha256'] != reference.sha256:
            raise ModelError('baseline_object_binding_mismatch')
        objects[reference.path] = item
        entry = {'role': role, **{k: v for k, v in metadata.items() if k != 'kind'},
                 'object_path': reference.path, 'sha256': reference.sha256,
                 'size': reference.size, 'media_type': media_type}
        if path is not None:
            entry['source_path'] = path
        entries.append(entry)

    sources = {item.identity.id: item for item in dependencies.inventory.records}
    for record in model_value['artifacts']:
        path = artifact_path(record['artifact_type'], record['id'], configuration.id_prefix)
        item = SnapshotObject.from_json(sources[record['id']].source_bytes)
        actual = project_json_resource(configuration, path, item.content, binding)
        if actual.data != record:
            raise ModelError('baseline_artifact_binding_mismatch', path=path)
        include('artifact', item, record, path=path)
    for name in sorted(resources):
        path, item = resources[name]
        record = records[name].data
        include(record['kind'], item, record, path=path)
    if type(attachment_payloads) is not dict:
        raise ModelError('baseline_attachment_payloads_required')
    attachments = model_value['attachments']
    if set(attachment_payloads) != {entry['path'] for entry in attachments}:
        raise ModelError('baseline_attachment_payload_set_mismatch')
    for record in attachments:
        item = SnapshotObject.from_attachment(attachment_payloads[record['path']])
        if item.reference.size != record['size'] or item.reference.sha256 != record['sha256']:
            raise ModelError('baseline_attachment_binding_mismatch', path=record['path'])
        include('attachment', item, record, path=record['path'], media_type=record['media_type'])
    semantic = SnapshotObject(canonical_json_bytes(semantic_configuration(configuration)))
    include('semantic_configuration', semantic, {'sha256': model_value['configuration_sha256']},
            path='specroad.json')
    include('effective_profile', SnapshotObject(profile.canonical_bytes),
            {'sha256': model_value['profile_sha256']})
    include('model_manifest', SnapshotObject(model.canonical_bytes), {'sha256': model.sha256})
    entries.sort(key=lambda row: (row['role'].encode('utf-8'),
                 row.get('id', row.get('source_path', '')).encode('utf-8'),
                 row.get('version', '').encode('utf-8')))
    value = {'baseline_manifest_version': 'baseline-manifest-v1',
             'schema_version': MODEL_SCHEMA_VERSION, 'tool_version': __version__,
             'project_id': configuration.project_id, 'baseline_kind': baseline_kind,
             'scope_descriptor': model_value['scope_descriptor'], 'scope_sha256': model.scope_sha256,
             'model_manifest': model_value, 'model_root_sha256': model.sha256,
             'configuration_hash': semantic.reference.sha256, 'profile_sha256': profile.sha256,
             'profiles': profile.data['profiles'],
             'boundary_references': model_value['boundary_references'], 'manifest': entries}
    if baseline_id is not None:
        value['baseline_id'] = baseline_id
    result = object.__new__(BaselineManifest)
    object.__setattr__(result, '_encoded', canonical_json_bytes(value))
    object.__setattr__(result, 'objects', tuple(objects[path] for path in sorted(objects)))
    return result
