"""Owned target source inventory and byte-derived manifest bindings.

No file discovery, I/O, authorization or target gate execution. The parent
pipeline deliberately rebuilds from these inputs instead of trusting caches.
"""
from dataclasses import dataclass
from hashlib import sha256
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.configuration import ProjectConfiguration
from ..model.model_manifest import ProjectReadBinding, ManifestResource, assemble_model_manifest
from ..model.manifest_resources import project_json_resource
from ..model.paths import artifact_path, classify_path, PathClass, project_path
from ..model.attachments import AttachmentDescriptor
from ..model.language_registry import LanguageRegistry
from ..model.language_package_values import LanguagePackage
from ..profiles.values import ProfileResource
from ..profiles.composition import compose_profiles
from ..profiles.composition_values import EffectiveProfile
from ..storage.json_syntax import parse_json_object
from ..validation import ModelDocument
from ..graph.relations import SourceRelations
from ..graph.scope_descriptors import ScopeDescriptor
from .target_values import TargetError

def _sequence(value, reason):
    if type(value) not in (tuple, list): raise TargetError(reason)
    return tuple(value)


def _project_scope(value):
    descriptor = ScopeDescriptor(value).data
    if (descriptor['scope_kind'] != 'project' or descriptor['boundary_policy'] != 'closed'
            or descriptor['configuration_id'] is not None):
        raise TargetError('target_complete_project_scope_required', pointer='/base/scope_descriptor')
    return descriptor


def _reservations(configuration, artifacts, relations, history):
    from ._common import _reference
    from ..model.relation_values import RelationIdentity
    result = {}
    for name, values in (('reserved_artifact_ids', artifacts),
                         ('reserved_relation_ids', relations), ('previously_approved_ids', history)):
        values = _sequence(values, 'target_reservation_sequence_required')
        for item in values:
            if name == 'reserved_relation_ids':
                RelationIdentity(item, 'random128-v1')
            else:
                ident = _reference(item, '/' + name)
                if ident.id_prefix != configuration.id_prefix:
                    raise TargetError('target_reservation_project_mismatch')
        if len(set(values)) != len(values):
            raise TargetError('target_duplicate_reservation', pointer='/' + name)
        result[name] = tuple(sorted(values))
    return result


def _source_digest(model):
    return canonical_json_sha256({'files': [{'path': p, 'sha256': sha256(b).hexdigest()}
                                           for p, b in sorted(model.source_files.items())],
        'profile': model.profile.binding(), 'reservations': model.reservations,
        'packages': [sha256(p.source_bytes).hexdigest() for p in model.language_packages],
        'attachments': [a.data for a in sorted(model.attachment_descriptors, key=lambda a: a.path)]})


def _default_scope():
    return {'scope_version':'scope-v1', 'scope_kind':'project', 'selector':{},
            'configuration_id':None, 'closure_profile':'core-closure-v1', 'boundary_policy':'closed'}


@dataclass(frozen=True, init=False)
class TargetModel:
    """Owned complete supplied inventory. Completeness on disk is not attested.

    Sources are real bytes, not paths to open. Resource and profile identities
    are recomputed from those bytes. Semantic resource editing remains
    unsupported; the normalization planner can rebuild value-identical bytes.
    """
    configuration_bytes: bytes
    configuration: ProjectConfiguration
    binding: ProjectReadBinding
    documents: tuple
    resource_files: tuple
    resources: tuple
    profile: EffectiveProfile
    profile_resources: tuple
    language_packages: tuple
    language_registry: LanguageRegistry | None
    attachment_descriptors: tuple
    reserved_artifact_ids: tuple
    reserved_relation_ids: tuple
    previously_approved_ids: tuple
    _sources_sha256: str

    def __init__(self, configuration_bytes, binding, documents, *, profile,
                 resource_files=(), attachments=(), language_packages=(),
                 reserved_artifact_ids=(), reserved_relation_ids=(), previously_approved_ids=()):
        if type(configuration_bytes) is not bytes or type(binding) is not ProjectReadBinding:
            raise TargetError('target_configuration_bytes_and_binding_required')
        configuration = ProjectConfiguration(parse_json_object(configuration_bytes))
        if configuration.project_id != binding.project_id:
            raise TargetError('target_project_binding_mismatch')
        documents = _sequence(documents, 'target_documents_required')
        files = _sequence(resource_files, 'target_resource_files_required')
        if any(type(d) is not ModelDocument for d in documents + files):
            raise TargetError('target_document_required')
        documents = tuple(ModelDocument(d.path, d.content) for d in documents)
        files = tuple(ModelDocument(d.path, d.content) for d in files)
        paths = ['specroad.json', *(d.path for d in documents + files)]
        if len(set(p.casefold() for p in paths)) != len(paths):
            raise TargetError('target_duplicate_path')
        records, seen = [], set()
        for document in documents:
            r = SourceRelations(document.content, path=document.path)
            identity = r.identity
            if identity.id in seen: raise TargetError('target_duplicate_artifact_id')
            seen.add(identity.id)
            expected = artifact_path(identity.artifact_type, identity.id, configuration.id_prefix)
            if document.path != expected:
                raise TargetError('target_artifact_path_mismatch')
            records.append(r)
        descriptions = _sequence(attachments, 'target_attachments_required')
        if any(type(a) is not AttachmentDescriptor for a in descriptions):
            raise TargetError('target_attachment_descriptor_required')
        descriptions = tuple(AttachmentDescriptor.from_data(a.data) for a in descriptions)
        by_path = {a.path: a for a in descriptions}
        if len(by_path) != len(descriptions): raise TargetError('target_duplicate_attachment')
        registry_data = configuration.data.get('language_registry')
        registry, resources, profile_sources = None, [], []
        for document in files:
            path = project_path(document.path)
            if registry_data is not None and path == registry_data['path']:
                registry = LanguageRegistry(document.content, expected_sha256=registry_data['sha256'],
                                            expected_version=registry_data['registry_version'])
                resource = ManifestResource(binding, {'kind': 'language_registry', 'path': path,
                    'id': registry_data['registry_id'], 'version': registry.version,
                    'size': len(document.content), 'sha256': registry.sha256})
            elif path in by_path:
                a = by_path[path]
                if len(document.content) != a.size or sha256(document.content).hexdigest() != a.sha256:
                    raise TargetError('target_attachment_bytes_mismatch')
                resource = ManifestResource(binding, {'kind': 'attachment', **a.data})
            else:
                kind = classify_path(path, configuration)
                if kind not in (PathClass.PROFILE, PathClass.RULE, PathClass.MAPPING):
                    raise TargetError('target_unsupported_resource')
                resource = project_json_resource(configuration, path, document.content, binding)
                if kind is PathClass.PROFILE: profile_sources.append(ProfileResource(document.content))
            resources.append(resource)
        if not set(by_path) <= {d.path for d in files}:
            raise TargetError('target_attachment_bytes_missing')
        if registry_data is not None and registry is None:
            raise TargetError('target_registry_bytes_missing')
        if type(profile) is not EffectiveProfile or not profile.profile_chain:
            raise TargetError('target_effective_profile_required')
        packages = _sequence(language_packages, 'target_language_packages_required')
        if any(type(p) is not LanguagePackage for p in packages):
            raise TargetError('target_language_package_required')
        owned_packages = tuple(LanguagePackage(p.source_bytes) for p in packages)
        if any(a.binding() != b.binding() for a, b in zip(owned_packages, packages)):
            raise TargetError('target_language_package_binding_mismatch')
        packages = owned_packages
        # Recomposition binds actual resource bytes, not a fabricated hash label.
        rebuilt = compose_profiles(profile_sources, core_key=profile.profile_chain[0],
            cli_profiles=profile.profile_chain[1:], language_registry=registry,
            language_packages=packages)
        if rebuilt.canonical_bytes != profile.canonical_bytes:
            raise TargetError('target_profile_resource_mismatch')
        reservations = _reservations(configuration, reserved_artifact_ids,
                                     reserved_relation_ids, previously_approved_ids)
        for name, value in (('configuration_bytes', configuration_bytes), ('configuration', configuration),
                ('binding', binding), ('documents', tuple(sorted(documents, key=lambda d:d.path))),
                ('resource_files', tuple(sorted(files, key=lambda d:d.path))), ('resources', tuple(resources)),
                ('profile', rebuilt), ('profile_resources', tuple(profile_sources)),
                ('language_packages', packages), ('language_registry', registry),
                ('attachment_descriptors', descriptions), *reservations.items()):
            object.__setattr__(self, name, value)
        # Reuse the canonical manifest's cross-resource identity checks now.
        self.manifest([r.data for r in records], _default_scope())
        object.__setattr__(self, '_sources_sha256', _source_digest(self))

    def snapshot(self):
        """Rebuild from original bytes; cached derived metadata is never authority."""
        if _source_digest(self) != self._sources_sha256:
            raise TargetError('target_sources_changed')
        return TargetModel(self.configuration_bytes, self.binding, self.documents,
            profile=self.profile, resource_files=self.resource_files,
            attachments=self.attachment_descriptors, language_packages=self.language_packages,
            **self.reservations)

    @property
    def reservations(self):
        return {name: list(getattr(self, name)) for name in
                ('reserved_artifact_ids', 'reserved_relation_ids', 'previously_approved_ids')}

    @property
    def source_files(self):
        return {'specroad.json': self.configuration_bytes,
                **{d.path:d.content for d in self.documents + self.resource_files}}

    @property
    def artifacts(self): return [parse_json_object(d.content) for d in self.documents]

    @property
    def resources_sha256(self):
        return canonical_json_sha256({'reservations': self.reservations, 'configuration_bytes': sha256(self.configuration_bytes).hexdigest(),
            'files': [{'path':d.path, 'sha256':sha256(d.content).hexdigest()} for d in self.resource_files],
            'language_packages': [p.binding() for p in self.language_packages],
            'profile': self.profile.binding()})

    def manifest(self, artifacts, descriptor):
        descriptor = _project_scope(descriptor)
        resources = list(self.resources)
        attachments = {r.data['path']:r.data for r in resources if r.data['kind'] == 'attachment'}
        for artifact in artifacts:
            for declared in artifact.get('attachments', []):
                a = AttachmentDescriptor.from_data(declared)
                if attachments.get(a.path) != {'kind':'attachment', **a.data}:
                    raise TargetError('target_referenced_attachment_unbound')
            resources.append(ManifestResource(self.binding, {'kind':'artifact', 'id':artifact['id'],
                'artifact_type':artifact['artifact_type'], 'revision':artifact['revision'],
                'sha256':canonical_json_sha256(artifact)}))
        return assemble_model_manifest(self.configuration, self.binding, resources,
            scope_descriptor=descriptor, effective_profile=self.profile.data)
