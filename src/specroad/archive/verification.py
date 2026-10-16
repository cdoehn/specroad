"""Read archived Baseline bytes and rebuild their precreation model root.

The record is an explicitly supplied immutable byte value. Neither the original
working tree nor Git is read. Integrity of this snapshot does not authenticate
its author, prove historical validation or grant publication/release authority.
"""
from hashlib import sha256

from ..model.attachments import AttachmentDescriptor
from ..model.canonical import canonical_json_bytes
from ..model.configuration import ProjectConfiguration
from ..model.errors import ModelError
from ..model.language_registry import LanguageRegistry
from ..model.model_manifest import ProjectReadBinding
from ..model.paths import project_path
from ..model.record_schemas import validate_record_fields
from ..model.semantic_configuration import semantic_configuration
from ..profiles import ProfileResource, compose_profiles
from ..security import ProjectBoundary
from ..storage.json_syntax import parse_json_object
from .objects import ObjectReference, read_snapshot_object
from .project_snapshot import build_project_baseline_manifest


_ROLES = frozenset(('artifact', 'profile', 'rule', 'mapping', 'attachment',
                   'archive', 'language_registry', 'semantic_configuration',
                   'effective_profile', 'model_manifest'))
_VALUES = frozenset(('semantic_configuration', 'effective_profile', 'model_manifest'))
_BINARY = frozenset(('attachment', 'archive', 'language_registry'))


def _configuration(value):
    """Supply inert, excluded operational fields solely to reuse validation.

    The generated path is never accessed. The exact semantic projection must
    round-trip; no default may silently change the stored hash inputs.
    """
    roots = value.get('managed_paths')
    if type(roots) is not list or any(type(p) is not str for p in roots):
        raise ModelError('baseline_semantic_configuration_invalid')
    used = {p.split('/', 1)[0].casefold() for p in roots}
    name, index = 'baseline-verification-output', 0
    while name in used:
        index += 1
        name = 'baseline-verification-output-' + str(index)
    configuration = ProjectConfiguration({**value, 'default_locale': 'und',
                                          'generated_path': name})
    if canonical_json_bytes(semantic_configuration(configuration)) != canonical_json_bytes(value):
        raise ModelError('baseline_semantic_configuration_invalid')
    if configuration.data.get('language_packages'):
        raise ModelError('baseline_language_package_snapshot_provider_required')
    return configuration


def verify_baseline_snapshot(boundary, baseline_record):
    """Verify a supplied record and actual archived bytes, without any writes.

    Supports the unconfigured, closed, whole-project snapshots currently emitted
    by the native writer. Other scopes fail explicitly. Resource identities,
    effective profile, semantic configuration, manifest and root are rebuilt;
    success is limited to these bytes, not full validation or an atomic read.
    """
    # Keep the native target inventory dependency local: archive object values
    # are also imported while the changes package is being initialized.
    from ..changes.target_model import TargetModel, _default_scope
    from ..validation import ModelDocument

    if type(boundary) is not ProjectBoundary:
        raise ModelError('snapshot_object_boundary_required')
    if type(baseline_record) is not bytes:
        raise ModelError('baseline_record_bytes_required')
    record = parse_json_object(baseline_record)
    validate_record_fields(record, expected_type='baseline')
    if record['scope_descriptor'] != _default_scope():
        raise ModelError('baseline_verification_scope_unsupported')
    if not {'configuration_hash', 'profiles', 'tool_version'} <= record.keys():
        raise ModelError('baseline_snapshot_metadata_missing')

    rows, objects, references, values = record['manifest'], {}, {}, {}
    for row in rows:
        role = row.get('role')
        if type(role) is not str or role not in _ROLES:
            raise ModelError('baseline_snapshot_role_unsupported')
        if not {'object_path', 'sha256', 'size'} <= row.keys():
            raise ModelError('baseline_snapshot_reference_missing')
        reference = ObjectReference(row['sha256'], row['size'])
        if row['object_path'] != reference.path:
            raise ModelError('baseline_snapshot_object_path_mismatch')
        if reference.path in references and references[reference.path] != reference:
            raise ModelError('snapshot_reference_conflict', path=reference.path)
        references[reference.path] = reference
        if reference.path not in objects:
            try:
                objects[reference.path] = read_snapshot_object(boundary, reference)
            except FileNotFoundError as error:
                raise ModelError('snapshot_referenced_object_missing', path=reference.path) from error
        raw = objects[reference.path]
        if role not in _BINARY:
            value = parse_json_object(raw, path=reference.path)
            if canonical_json_bytes(value) != raw:
                raise ModelError('baseline_snapshot_json_not_canonical', path=reference.path)
            if role in _VALUES:
                if role in values:
                    raise ModelError('baseline_snapshot_duplicate_value')
                values[role] = value
        if role not in _VALUES:
            project_path(row.get('source_path'))
    if set(values) != _VALUES:
        raise ModelError('baseline_snapshot_value_missing')
    configuration = _configuration(values['semantic_configuration'])
    if sha256(canonical_json_bytes(values['semantic_configuration'])).hexdigest() != record['configuration_hash']:
        raise ModelError('baseline_configuration_hash_mismatch')
    profiles, files, documents, attachments, registry = [], [], [], [], None
    registry_binding = configuration.data.get('language_registry')
    for row in rows:
        role = row['role']
        if role in _VALUES:
            continue
        path, raw = row['source_path'], objects[row['object_path']]
        document = ModelDocument(path, raw)
        (documents if role == 'artifact' else files).append(document)
        if role == 'profile':
            profiles.append(ProfileResource(raw))
        elif role == 'attachment':
            if 'media_type' not in row:
                raise ModelError('baseline_attachment_metadata_missing')
            attachments.append(AttachmentDescriptor(path, row['media_type'], len(raw), row['sha256']))
        elif role == 'language_registry':
            if registry_binding is None or registry is not None or path != registry_binding['path']:
                raise ModelError('baseline_language_registry_mismatch')
            registry = LanguageRegistry(raw, expected_sha256=registry_binding['sha256'],
                                        expected_version=registry_binding['registry_version'])
    chain = values['effective_profile'].get('profiles')
    if (type(chain) is not list or not chain or any(type(p) is not dict or
            type(p.get('profile_id')) is not str or type(p.get('version')) is not str for p in chain)):
        raise ModelError('baseline_effective_profile_invalid')
    keys = [p['profile_id'] + '@' + p['version'] for p in chain]
    profile = compose_profiles(profiles, core_key=keys[0], cli_profiles=keys[1:],
                               language_registry=registry)
    if (profile.canonical_bytes != canonical_json_bytes(values['effective_profile'])
            or profile.data['profiles'] != record['profiles']):
        raise ModelError('baseline_effective_profile_mismatch')
    binding = ProjectReadBinding(configuration.project_id, str(boundary.root), boundary._root_identity)
    model = TargetModel(canonical_json_bytes(configuration.data), binding, documents,
        profile=profile, resource_files=files, attachments=attachments)
    rebuilt = build_project_baseline_manifest(model, baseline_id=record['id']).data
    if rebuilt['model_root_sha256'] != record['model_root_sha256']:
        raise ModelError('baseline_model_root_mismatch')
    if canonical_json_bytes(rebuilt['model_manifest']) != canonical_json_bytes(values['model_manifest']):
        raise ModelError('baseline_model_manifest_mismatch')
    if canonical_json_bytes(rebuilt['manifest']) != canonical_json_bytes(rows):
        raise ModelError('baseline_snapshot_manifest_mismatch')
    # Revisit every referenced object after reconstruction. An observation is
    # never cached across calls; concurrent changes cannot reuse old evidence.
    for path in sorted(references):
        try:
            fresh = read_snapshot_object(boundary, references[path])
        except FileNotFoundError as error:
            raise ModelError('snapshot_referenced_object_missing', path=path) from error
        if fresh != objects[path]:
            raise ModelError('baseline_snapshot_changed', path=path)
    return {'format_version': 'baseline-verification-v1', 'baseline_id': record['id'],
        'baseline_kind': record['baseline_kind'], 'record_sha256': sha256(baseline_record).hexdigest(),
        'scope_descriptor': record['scope_descriptor'], 'model_root_sha256': rebuilt['model_root_sha256'],
        'configuration_hash': rebuilt['configuration_hash'], 'profile_sha256': rebuilt['profile_sha256'],
        'checked_objects': len(objects), 'checked_bytes': sum(map(len, objects.values())),
        'checked_artifacts': len(documents), 'snapshot_integrity_verified': True,
        'validation_scope': 'supplied_baseline_record_and_archive_bytes',
        'project_completeness_verified': False, 'full_validation_passed': False,
        'atomic_snapshot': False, 'write_authorized': False, 'release_authorized': False}
