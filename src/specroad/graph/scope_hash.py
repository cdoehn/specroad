"""Bind a revalidated resolved scope to the existing canonical manifest format.

No observation fingerprints, original formatting, absolute roots, current clock
or traversal order enter the semantic projection. The live providers must still
establish inventory completeness, resource authenticity and profile validity.
"""
from ..model.canonical import canonical_json_sha256
from ..model.configuration import ProjectConfiguration
from ..model.errors import ModelError
from ..model.model_manifest import ManifestResource, ModelManifest, ProjectReadBinding
from ..model.manifest_projection import project_manifest_value
from ..model.semantic_configuration import semantic_configuration
from .closure_inputs import ClosureBindings
from .scope_closure import ScopeClosure, require_scope_closure_current


def fingerprint_scope(configuration, binding, closure, dependencies, *,
                      effective_profile, resource_records=None, query_page=None):
    """Return the real Scope-Hash and model root, not a release/write approval.

    resource_records maps selected opaque inventory IDs to explicit typed
    ManifestResources. Attachment metadata comes from the closure bindings.
    No ID/version, registry path or archival content is inferred from a name.
    """
    if type(configuration) is not ProjectConfiguration or type(binding) is not ProjectReadBinding:
        raise ModelError('scope_hash_project_binding_required')
    if type(closure) is not ScopeClosure or type(dependencies) is not ClosureBindings:
        raise ModelError('scope_hash_complete_closure_required')
    inventory = dependencies.inventory
    config_hash = canonical_json_sha256(semantic_configuration(configuration))
    if (binding.project_id != configuration.project_id
            or inventory.project_id != binding.project_id
            or inventory.configuration_sha256 != config_hash):
        raise ModelError('scope_hash_project_mismatch')
    require_scope_closure_current(closure, closure.seeds, dependencies, query_page=query_page)
    if closure.seeds.descriptor.data['configuration_id'] is not None:
        # Fresh seed recomputation binds both semantic project policy and the
        # selected product configuration, including its complete parent chain.
        config_hash = closure.seeds.configuration_sha256
    if type(effective_profile) is not dict:
        raise ModelError('effective_profile_projection_required')
    if 'project_id' in effective_profile and effective_profile['project_id'] != binding.project_id:
        raise ModelError('scope_hash_project_mismatch')
    profiles_hash = canonical_json_sha256(effective_profile)
    resources = {} if resource_records is None else resource_records
    if type(resources) is not dict:
        raise ModelError('scope_hash_resource_mapping_required')
    source_index = {r.identity.id: r for r in inventory.records}
    resource_index = {r.resource_id: r for r in inventory.resources}
    needed = {identity for identity in closure.resource_ids
              if resource_index[identity].kind != 'attachment'}
    if set(resources) != needed:
        raise ModelError('scope_hash_resource_metadata_set_mismatch')
    artifacts, others, attachments = [], [], []
    for identity in closure.artifact_ids:
        source = source_index[identity]
        data = source.data
        artifacts.append({'kind': 'artifact', 'id': identity,
            'artifact_type': source.identity.artifact_type, 'revision': data['revision'],
            'sha256': canonical_json_sha256(data)})
    seen = set()
    for identity in sorted(needed):
        resource, record = resource_index[identity], resources[identity]
        if resource.kind == 'archive':
            # Archived bytes need the later verified archive/object provider;
            # a ZIP digest must not masquerade as its contained model resources.
            raise ModelError('scope_hash_archive_expansion_required')
        if type(record) is not ManifestResource or record.binding != binding:
            raise ModelError('scope_hash_resource_binding_mismatch')
        value = record.data
        if (value['kind'] != resource.kind or value['sha256'] != resource.sha256
                or value.get('version') != resource.version):
            raise ModelError('scope_hash_resource_binding_mismatch')
        key = value['kind'], value['id'], value['version']
        if key in seen:
            raise ModelError('duplicate_manifest_resource')
        seen.add(key); others.append(value)
    for descriptor in closure.attachments:
        attachments.append({'kind': 'attachment', **descriptor.data})
    return ModelManifest(project_manifest_value(binding.project_id, closure.seeds.descriptor.data,
        artifacts, others, attachments, [item.data for item in closure.boundary_references],
        config_hash, profiles_hash))
