"""Read-only independent manifest reconstruction for unpublished discard recovery.

No ordinary model loader, target planner, host policy or implicit profile
selection. The journal supplies explicit selection and expected bindings; live
resource bytes supply the semantic root. Fresh membership brackets every read.
"""
from hashlib import sha256

from ..graph.scope_descriptors import ScopeDescriptor
from ..model.attachments import AttachmentDescriptor
from ..model.language_package_values import LanguagePackage
from ..model.language_registry import LanguageRegistry
from ..model.manifest_resources import project_json_resource
from ..model.model_manifest import ProjectReadBinding, ManifestResource, assemble_model_manifest
from ..model.paths import PathClass
from ..profiles import ProfileResource, compose_profiles
from ..storage.json_syntax import parse_json_object
from ..storage.project import ProjectSource
from ._journal_io import _read
from ._recovery_inventory import verified_membership
from ._staging_files import _image
from .recovery_values import RecoveryError


def observe_discard_basis(files, journal, *, include_images=False):
    data = journal.data
    if data['state'] not in ('building', 'prepared'):
        raise RecoveryError('discard_restart_prepared_required', exit_code=6)
    selection = data.get('discard_basis')
    if selection is None:
        raise RecoveryError('discard_restart_basis_required', exit_code=2)
    if data['state'] == 'building' and selection['format_version'] != 'discard-basis-v2':
        raise RecoveryError('discard_restart_images_required', exit_code=2)
    with verified_membership(files, journal, phase='base'):
        inventory = {item['path']: item for item in data['target_inventory']}
        for entry in data['files']:
            if entry['existed_before']:
                inventory[entry['path']] = {'path': entry['path'], 'size': entry['before_size'],
                                            'sha256': entry['before_sha256']}
            else:
                inventory.pop(entry['path'])
        raw_files, tokens = {}, {}
        for path, item in sorted(inventory.items()):
            parts = tuple(path.split('/'))
            with files.directory(parts[:-1]) as parent:
                if parent is None:
                    raise RecoveryError('discard_basis_file_missing', path=path, exit_code=6)
                ident = _image(parent, parts[-1], item['size'], item['sha256'])
                raw = _read(parent, parts[-1], expected_identity=ident)
                if len(raw) != item['size'] or sha256(raw).hexdigest() != item['sha256']:
                    raise RecoveryError('discard_basis_file_changed', path=path, exit_code=6)
                raw_files[path] = raw
                tokens[path] = {'identity': ident, 'size': len(raw), 'sha256': item['sha256']}
        source = ProjectSource(files.boundary.root, expected_project_id=data['project_id'])
        if (source.configuration_bytes != raw_files.get('specroad.json')
                or source.boundary._root_identity != files.boundary._root_identity):
            raise RecoveryError('discard_basis_root_changed', exit_code=6)
        operations = data['authoring_binding']['operations']
        if any(op['op'] == 'representation_normalize' for op in operations):
            _normalization_images(source, data, raw_files)
        elif any(source.classify(e['path']) is not PathClass.ARTIFACT for e in data['files']):
            raise RecoveryError('discard_basis_operation_unsupported', exit_code=6)
        root_hash = _manifest(source, raw_files, selection, data['authoring_binding']['scope_descriptor'])
        if root_hash != data['base_model_root_sha256']:
            raise RecoveryError('discard_basis_root_mismatch', exit_code=6)
        if selection['format_version'] == 'discard-basis-v2':
            from ._discard_basis_contract import staging_images
            target = {**raw_files, **staging_images(selection)}
            if _manifest(source, target, selection, data['authoring_binding']['scope_descriptor']) != data['target_model_root_sha256']:
                raise RecoveryError('discard_staging_root_mismatch', exit_code=6)
        # Every byte observation, not merely the configuration, must still hold
        # after profile composition and semantic projection.
        for path, item in sorted(inventory.items()):
            parts = tuple(path.split('/'))
            with files.directory(parts[:-1]) as parent:
                if parent is None:
                    raise RecoveryError('discard_basis_file_missing', path=path, exit_code=6)
                _image(parent, parts[-1], item['size'], item['sha256'], identity=tokens[path]['identity'])
        source.check_current()
    observation = {'files': tokens, 'base_model_root_sha256': root_hash}
    if include_images:
        from ._discard_basis_contract import staging_images
        return observation, raw_files, staging_images(selection)
    return observation


def _normalization_images(source, data, original):
    """Prove byte-only effects independently, including config/resource originals."""
    from ..model.paths import CURRENT_JSON_CLASSES
    from ..model.representation import NormalizationCandidate
    from ..model._representation_scope import _validate_format_input
    from ._discard_basis_contract import staging_images
    images = staging_images(data.get('discard_basis', {}))
    expected, seen = {}, set()
    for op in data['authoring_binding']['operations']:
        if op['op'] != 'representation_normalize':
            raise RecoveryError('discard_basis_operation_unsupported', exit_code=6)
        path = op['path']
        if path in seen or path not in original or source.classify(path) not in CURRENT_JSON_CLASSES:
            raise RecoveryError('discard_normalization_source_unbound', exit_code=6)
        seen.add(path)
        _validate_format_input(source.configuration, path, original[path], source.classify(path))
        candidate = NormalizationCandidate(path, original[path])
        if (candidate.expected_byte_sha256 != op['expected_byte_sha256'] or
                candidate.result_byte_sha256 != op['target_byte_sha256']):
            raise RecoveryError('discard_normalization_bytes_unbound', exit_code=6)
        if candidate.change_required:
            expected[path] = candidate.normalized_bytes
    if images != expected:
        raise RecoveryError('discard_normalization_images_unbound', exit_code=6)


def _manifest(source, raw_files, selection, scope):
    descriptor = ScopeDescriptor(scope).data
    if (descriptor['scope_kind'] != 'project' or descriptor['boundary_policy'] != 'closed'
            or descriptor['configuration_id'] is not None):
        raise RecoveryError('discard_complete_project_scope_required', exit_code=6)
    binding = ProjectReadBinding(source.configuration.project_id, str(source.boundary.root),
                                 source.boundary._root_identity)
    attachments = {a['path']: AttachmentDescriptor.from_data(a) for a in selection['attachments']}
    package_paths = selection['language_package_paths']
    if not (set(attachments) | set(package_paths)) <= set(raw_files):
        raise RecoveryError('discard_basis_resource_missing', exit_code=6)
    packages = [LanguagePackage(raw_files[path]) for path in package_paths]
    if any(source.classify(path) not in (PathClass.PROFILE, PathClass.RULE) for path in package_paths):
        raise RecoveryError('discard_basis_package_unmanaged', exit_code=6)
    registry_data = source.configuration.data.get('language_registry')
    registry, resources, profiles = None, [], []
    for path, raw in sorted(raw_files.items()):
        if path == 'specroad.json' or path in package_paths:
            continue
        if path in attachments:
            a = attachments[path]
            if len(raw) != a.size or sha256(raw).hexdigest() != a.sha256:
                raise RecoveryError('discard_basis_attachment_mismatch', path=path, exit_code=6)
            resources.append(ManifestResource(binding, {'kind': 'attachment', **a.data}))
        elif registry_data is not None and path == registry_data['path']:
            registry = LanguageRegistry(raw, expected_sha256=registry_data['sha256'],
                                        expected_version=registry_data['registry_version'])
            resources.append(ManifestResource(binding, {'kind': 'language_registry', 'path': path,
                'id': registry_data['registry_id'], 'version': registry.version,
                'size': len(raw), 'sha256': registry.sha256}))
        else:
            resources.append(project_json_resource(source.configuration, path, raw, binding))
            if source.classify(path) is PathClass.PROFILE:
                profiles.append(ProfileResource(raw))
            if source.classify(path) is PathClass.ARTIFACT:
                for item in parse_json_object(raw).get('attachments', []):
                    a = AttachmentDescriptor.from_data(item)
                    if attachments.get(a.path) != a:
                        raise RecoveryError('discard_basis_attachment_unbound', path=a.path, exit_code=6)
    if registry_data is not None and registry is None:
        raise RecoveryError('discard_basis_registry_missing', exit_code=6)
    chain = selection['profile_chain']
    profile = compose_profiles(profiles, core_key=chain[0], cli_profiles=chain[1:],
                               language_registry=registry, language_packages=packages)
    manifest = assemble_model_manifest(source.configuration, binding, resources,
        scope_descriptor=descriptor, effective_profile=profile.data)
    return manifest.sha256
