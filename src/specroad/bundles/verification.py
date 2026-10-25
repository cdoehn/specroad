"""Verify owned project-bundle bytes through the native model and closure.

No project discovery, extraction, temporary root or execution of payloads.
Partial scopes and nonempty portable receipt histories need their own reader
providers; container self-consistency must not stand in for those proofs.
"""
from ..changes.target_model import TargetModel
from ..exchange._export_scope import export_scope, resource_identity
from ..graph.scope_descriptors import ScopeDescriptor
from ..model.attachments import AttachmentDescriptor
from ..model.configuration import ProjectConfiguration
from ..model.domain_schemas import DOMAIN_TYPES, validate_domain_fields
from ..model.errors import ModelError
from ..model.language_package_values import LanguagePackage
from ..model.language_registry import LanguageRegistry
from ..model.model_manifest import ProjectReadBinding
from ..model.paths import PathClass, classify_path
from ..model.record_schemas import validate_record_fields
from ..profiles.composition import compose_profiles
from ..profiles.values import ProfileResource
from ..security import SafetyViolation
from ..srx.errors import SrxError
from ..storage.json_syntax import parse_json_object
from ..validation import ModelDocument
from .container import BundleContainer
from .errors import BundleError
from .manifest import require


def _project_model(container):
    files = container.files
    configuration = ProjectConfiguration(parse_json_object(files['specroad.json']))
    registry_binding = configuration.data.get('language_registry')
    registry_path = None if registry_binding is None else registry_binding['path']
    registry = None
    if registry_binding is not None:
        require(registry_path in files, 'bundle_language_registry_missing')
        registry = LanguageRegistry(files[registry_path], expected_sha256=registry_binding['sha256'],
                                    expected_version=registry_binding['registry_version'])
    documents, resources, profiles, packages, attachments = [], [], [], {}, {}
    for path, raw in files.items():
        if path == 'specroad.json':
            continue
        kind = classify_path(path, configuration)
        if kind is PathClass.RECEIPT:
            raise BundleError('bundle_portable_receipt_provider_required', code=None, exit_code=5)
        document = ModelDocument(path, raw)
        if kind is PathClass.ARTIFACT:
            value = parse_json_object(raw, path=path)
            require(type(value.get('artifact_type')) is str, 'bundle_artifact_type')
            (validate_domain_fields if value.get('artifact_type') in DOMAIN_TYPES
             else validate_record_fields)(value)
            documents.append(document)
            for item in value.get('attachments', []):
                attachment = AttachmentDescriptor.from_data(item)
                previous = attachments.get(attachment.path)
                require(previous is None or previous.data == attachment.data,
                        'bundle_attachment_conflict')
                attachments[attachment.path] = attachment
        elif path == registry_path:
            resources.append(document)
        elif kind is PathClass.PROFILE:
            if 'package_id' in parse_json_object(raw, path=path):
                package = LanguagePackage(raw)
                require(package.key not in packages, 'bundle_duplicate_language_package')
                packages[package.key] = package
            else:
                profiles.append(ProfileResource(raw))
                resources.append(document)
        elif kind in (PathClass.RULE, PathClass.MAPPING, PathClass.ATTACHMENT, PathClass.ARCHIVE_OBJECT):
            resources.append(document)
        else:
            raise BundleError('bundle_unsupported_payload')
    selected = []
    for key in configuration.data.get('language_packages', []):
        require(key in packages, 'bundle_language_package_missing')
        selected.append(packages[key])
    keys = tuple(key for key in configuration.data.get('profiles', []) if key not in ('core', 'core@0.2.0'))
    profile = compose_profiles(profiles, core_key='core@0.2.0', cli_profiles=keys,
                               language_registry=registry, language_packages=selected)
    # This is provenance for owned bytes, never an observed filesystem root.
    # The sentinel is excluded from native hashes and grants no disk authority.
    binding = ProjectReadBinding(configuration.project_id, 'bundle:' + container.sha256, (0, 0))
    return TargetModel(files['specroad.json'], binding, documents, profile=profile,
        resource_files=resources, attachments=tuple(attachments.values()), language_packages=selected)


def _verify(container, externally_bound):
    manifest = container.manifest
    if manifest['bundle_kind'] != 'project':
        raise BundleError('bundle_partial_verification_provider_required', code=None, exit_code=5)
    model = _project_model(container)
    descriptor = ScopeDescriptor(manifest['scope_descriptor'])
    closure, native, artifacts, _ = export_scope(model, descriptor)
    require(set(closure.artifact_ids) == {a['id'] for a in model.artifacts}
            and set(closure.resource_ids) == {resource_identity(r) for r in model.resources}
            and not closure.boundary_references, 'bundle_project_closure_incomplete')
    require(native.sha256 == model.manifest(artifacts, descriptor.data).sha256,
            'bundle_project_manifest_mismatch', code='SRV060')
    for key, actual in (('origin_model_root_sha256', native.sha256),
                        ('bundle_model_root_sha256', native.sha256),
                        ('configuration_sha256', native.data['configuration_sha256']),
                        ('profile_sha256', native.data['profile_sha256'])):
        require(manifest[key] == actual, 'bundle_model_binding_mismatch', code='SRV060')
    return {'format_version': 'bundle-verify-v1', 'manifest': manifest,
        'file': {'size': len(container.source_bytes), 'sha256': container.sha256},
        'validation_scope': 'closed_project_payload_model', 'container_verified': True,
        'model_root_verified': True, 'closure_verified': True,
        'external_hash_verified': externally_bound, 'creator_authenticated': False,
        'full_semantic_validation': False, 'approval_granted': False, 'write_authorized': False}


def verify_bundle(raw, *, expected_sha256=None):
    """Return byte-derived integrity/closure facts, never authenticity or approval.

    The external expectation binds the entire ZIP before model reconstruction.
    Successful verification concerns precisely the supplied closed inventory;
    it does not attest the original project's completeness or release readiness.
    """
    try:
        return _verify(BundleContainer(raw, expected_sha256=expected_sha256), expected_sha256 is not None)
    except SafetyViolation as error:
        raise BundleError('unsafe_bundle_model', code='SRV083', exit_code=7) from error
    except ModelError as error:
        raise BundleError(error.reason, exit_code=getattr(error, 'exit_code', 3)) from error
    except SrxError as error:
        raise BundleError(error.reason, code=error.code) from error
