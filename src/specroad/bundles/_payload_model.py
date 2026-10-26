"""Reconstruct native inputs from owned bundle bytes, without a filesystem root."""
from ..changes.target_model import TargetModel
from ..model.attachments import AttachmentDescriptor
from ..model.configuration import ProjectConfiguration
from ..model.domain_schemas import DOMAIN_TYPES, validate_domain_fields
from ..model.language_package_values import LanguagePackage
from ..model.language_registry import LanguageRegistry
from ..model.model_manifest import ProjectReadBinding, ManifestResource
from ..model.manifest_resources import project_json_resource
from ..model.canonical import canonical_json_sha256
from ..model.paths import artifact_path
from ..graph.relations import SourceRelations
from hashlib import sha256
from dataclasses import dataclass
from ..model.paths import PathClass, classify_path
from ..model.record_schemas import validate_record_fields
from ..profiles.composition import compose_profiles
from ..profiles.values import ProfileResource
from ..storage.json_syntax import parse_json_object
from ..validation import ModelDocument
from .errors import BundleError
from .manifest import require


def payload_model(container, *, partial=False):
    files = container.files
    from ._receipts import verify_payload_receipts
    receipts = verify_payload_receipts(container)
    # Keep transport receipt hashes out of the native model-resource pipeline.
    model_files = {path: raw for path, raw in files.items() if path not in receipts}
    configuration = ProjectConfiguration(parse_json_object(files['specroad.json']))
    registry_binding = configuration.data.get('language_registry')
    registry_path = None if registry_binding is None else registry_binding['path']
    registry = None
    if registry_binding is not None:
        require(registry_path in files, 'bundle_language_registry_missing')
        registry = LanguageRegistry(files[registry_path], expected_sha256=registry_binding['sha256'],
                                    expected_version=registry_binding['registry_version'])
    documents, resources, profiles, packages, attachments = [], [], [], {}, {}
    for path, raw in model_files.items():
        if path == 'specroad.json' or (partial and path.startswith('bundle-context/')):
            continue
        kind = classify_path(path, configuration)
        document = ModelDocument(path, raw)
        if kind is PathClass.ARTIFACT:
            value = parse_json_object(raw, path=path)
            require(type(value.get('artifact_type')) is str, 'bundle_artifact_type')
            (validate_domain_fields if value.get('artifact_type') in DOMAIN_TYPES
             else validate_record_fields)(value)
            documents.append(document)
            for item in value.get('attachments', []):
                attachment = AttachmentDescriptor.from_data(item)
                if partial and attachment.path not in files:
                    continue
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
    constructor = PartialPayloadModel if partial else TargetModel
    return constructor(files['specroad.json'], binding, documents, profile=profile,
        resource_files=resources, attachments=tuple(attachments.values()), language_packages=selected)


@dataclass(frozen=True, init=False, eq=False)
class PartialPayloadModel:
    """Native byte observations, never a writable or complete TargetModel."""
    def __init__(self, configuration_bytes, binding, documents, *, profile,
                 resource_files, attachments, language_packages):
        configuration = ProjectConfiguration(parse_json_object(configuration_bytes))
        seen = set()
        for document in documents:
            record = SourceRelations(document.content, path=document.path)
            require(record.identity.id not in seen, 'bundle_duplicate_artifact')
            seen.add(record.identity.id)
            require(artifact_path(record.identity.artifact_type, record.identity.id,
                                  configuration.id_prefix) == document.path, 'bundle_artifact_path')
            canonical_json_sha256(record.data)
        descriptions = {a.path: a for a in attachments}
        resources = []
        registry_binding = configuration.data.get('language_registry')
        registry_path = None if registry_binding is None else registry_binding['path']
        for document in resource_files:
            path, raw = document.path, document.content
            kind = classify_path(path, configuration)
            if path == registry_path:
                registry = LanguageRegistry(raw, expected_sha256=registry_binding['sha256'],
                                             expected_version=registry_binding['registry_version'])
                value = {'kind': 'language_registry', 'path': path, 'id': registry_binding['registry_id'],
                         'version': registry.version, 'size': len(raw), 'sha256': registry.sha256}
            elif kind is PathClass.ATTACHMENT:
                descriptor = descriptions.get(path)
                require(descriptor is not None, 'bundle_attachment_unbound')
                require(descriptor.size == len(raw) and descriptor.sha256 == sha256(raw).hexdigest(),
                        'bundle_attachment_bytes_mismatch', code='SRV060')
                value = {'kind': 'attachment', **descriptor.data}
            elif kind is PathClass.ARCHIVE_OBJECT:
                from ..archive.objects import SnapshotObject
                reference = SnapshotObject(raw).reference
                require(path == reference.path, 'bundle_archive_path', code='SRV060')
                value = {'kind': 'archive', 'path': path, 'sha256': reference.sha256, 'size': reference.size}
            else:
                resources.append(project_json_resource(configuration, path, raw, binding))
                continue
            resources.append(ManifestResource(binding, value))
        profiles = tuple(ProfileResource(d.content) for d in resource_files
                         if classify_path(d.path, configuration) is PathClass.PROFILE)
        for name, value in (('configuration', configuration), ('binding', binding),
                ('documents', tuple(documents)), ('resource_files', tuple(resource_files)),
                ('resources', tuple(resources)), ('profile', profile), ('profile_resources', profiles),
                ('attachment_descriptors', tuple(attachments)), ('language_packages', tuple(language_packages)),
                ('source_files', {'specroad.json': configuration_bytes,
                                 **{d.path: d.content for d in (*documents, *resource_files)}})):
            object.__setattr__(self, name, value)
