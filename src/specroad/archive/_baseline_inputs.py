"""Own and check the byte-backed inputs shared by Baseline manifest preparation.

No project discovery, publication, model-hash implementation or authority.
"""
from ..graph.closure_inputs import ClosureBindings
from ..graph.relations import SourceRelations
from ..graph.scope_closure import require_scope_closure_current
from ..graph.scope_inputs import ScopeResource, ScopeSeedInputs
from ..model.attachments import AttachmentDescriptor
from ..model.configuration import ProjectConfiguration
from ..model.errors import ModelError
from ..model.manifest_resources import project_json_resource
from ..model.model_manifest import ProjectReadBinding
from ..profiles import ProfileResource, compose_profiles
from ..profiles.composition_values import EffectiveProfile
from .objects import SnapshotObject


def _owned_inputs(configuration, binding, closure, dependencies, query_page):
    """Rebuild derived observations from actual bytes before accepting a scope."""
    configuration = ProjectConfiguration(configuration.data)
    binding = ProjectReadBinding(binding.project_id, binding.source_root, tuple(binding.root_identity))
    inventory = dependencies.inventory
    if type(inventory) is not ScopeSeedInputs:
        raise ModelError('baseline_inventory_required')
    records = []
    for source in inventory.records:
        if type(source) is not SourceRelations:
            raise ModelError('baseline_source_required')
        checked = SourceRelations(source.source_bytes, path=source.path)
        if checked != source:
            raise ModelError('baseline_source_binding_mismatch')
        records.append(checked)
    resources = []
    for resource in inventory.resources:
        if type(resource) is not ScopeResource:
            raise ModelError('baseline_scope_resource_required')
        resources.append(ScopeResource(**resource.data))
    owned = ScopeSeedInputs(configuration, records, resources,
                            archive_bindings=dict(inventory.archive_bindings))
    if owned.fingerprint != inventory.fingerprint:
        raise ModelError('baseline_inventory_binding_mismatch')
    attachments = {}
    for name, value in dependencies.attachments.items():
        if type(value) is not AttachmentDescriptor:
            raise ModelError('baseline_attachment_descriptor_required')
        attachments[name] = AttachmentDescriptor.from_data(value.data)
    fresh = ClosureBindings(owned, uses=dict(dependencies.uses),
        current_reviews=dict(dependencies.current_reviews), attachments=attachments)
    if fresh.fingerprint != dependencies.fingerprint:
        raise ModelError('baseline_dependency_binding_mismatch')
    require_scope_closure_current(closure, closure.seeds, fresh, query_page=query_page)
    return configuration, binding, fresh


def _checked_configuration(closure, dependencies):
    """Retain actual selected-chain records, not just their derived hash label."""
    identity = closure.seeds.descriptor.data['configuration_id']
    if identity is None:
        return None
    from ..configurations import resolve_configuration
    selected = resolve_configuration(dependencies.inventory.records, identity)
    chain = {item['id'] for item in selected.manifest['configurations']}
    if not chain <= set(closure.artifact_ids):
        raise ModelError('baseline_configuration_chain_not_retained')
    return selected


def _resource_objects(configuration, binding, closure, dependencies, payloads):
    if type(payloads) is not dict:
        raise ModelError('baseline_resource_payloads_required')
    inventory = {item.resource_id: item for item in dependencies.inventory.resources}
    needed = {name for name in closure.resource_ids if inventory[name].kind != 'attachment'}
    if set(payloads) != needed:
        raise ModelError('baseline_resource_payload_set_mismatch')
    records, values, profiles, paths = {}, {}, {}, set()
    for name in sorted(needed):
        resource = inventory[name]
        if resource.kind not in ('profile', 'rule', 'mapping'):
            raise ModelError('baseline_resource_provider_required')
        pair = payloads[name]
        if type(pair) is not tuple or len(pair) != 2:
            raise ModelError('baseline_resource_payload_required')
        path, raw = pair
        item = SnapshotObject.from_json(raw)
        record = project_json_resource(configuration, path, item.content, binding)
        if path.casefold() in paths:
            raise ModelError('baseline_resource_path_collision')
        paths.add(path.casefold())
        data = record.data
        if (data['kind'], data.get('version'), data['sha256']) != (
                resource.kind, resource.version, resource.sha256):
            raise ModelError('baseline_resource_binding_mismatch')
        records[name] = record
        values[name] = (path, item)
        if resource.kind == 'profile':
            profiles[name] = ProfileResource(item.content)
    return records, values, profiles


def _checked_profile(profile, profiles, dependencies):
    if type(profile) is not EffectiveProfile:
        raise ModelError('baseline_effective_profile_required')
    value = profile.data
    if value['language_registry'] is not None or value['language_packages']:
        raise ModelError('baseline_language_resource_provider_required')
    chain = profile.profile_chain
    if not chain:
        raise ModelError('baseline_effective_profile_required')
    active = {profiles[r.resource_id].key for r in dependencies.inventory.resources
              if r.kind == 'profile' and r.active and r.resource_id in profiles}
    if active != set(chain):
        raise ModelError('baseline_profile_selection_mismatch')
    checked = compose_profiles(list(profiles.values()), core_key=chain[0],
                               project_profiles=chain[1:])
    if checked.canonical_bytes != profile.canonical_bytes:
        raise ModelError('baseline_effective_profile_mismatch')
    return checked
