"""Read and recheck the actual configured inventory; never initialize or write."""
from ..changes.target_model import TargetModel
from ..model.attachments import AttachmentDescriptor
from ..model.errors import ModelError
from ..model.language_package_values import LanguagePackage
from ..model.model_manifest import ProjectReadBinding
from ..model.paths import PathClass
from ..profiles.composition import compose_profiles
from ..profiles.values import ProfileResource
from ..storage.json_syntax import parse_json_object
from ..storage.language_registry import read_language_registry
from ..storage.project import ProjectSource
from ..storage.resource_discovery import current_json_paths
from ..validation import ModelDocument


class InspectionChanged(ModelError):
    exit_code = 6


class InspectionSnapshot:
    """An observation with a final reread, not an atomic snapshot or write grant."""
    def __init__(self, root, profiles):
        self.source = source = ProjectSource(root)
        self.paths = current_json_paths(source)
        self.raw = {p: source.read_normative(p) for p in self.paths}
        configuration = source.configuration
        registry_binding = configuration.data.get('language_registry')
        self.registry_path = None if registry_binding is None else registry_binding['path']
        registry = None
        if registry_binding is not None:
            registry = read_language_registry(source)
            self.raw[self.registry_path] = registry.source_bytes
        documents, resources, profile_sources, packages, attachments = [], [], [], {}, {}
        for path, raw in self.raw.items():
            if path == 'specroad.json':
                continue
            document = ModelDocument(path, raw)
            kind = source.classify(path)
            if kind is PathClass.ARTIFACT:
                documents.append(document)
                for value in parse_json_object(raw, path=path).get('attachments', []):
                    descriptor = AttachmentDescriptor.from_data(value)
                    previous = attachments.get(descriptor.path)
                    if previous is not None and previous.data != descriptor.data:
                        raise ModelError('inspection_attachment_conflict', path=descriptor.path)
                    attachments[descriptor.path] = descriptor
            elif registry_binding is not None and path == registry_binding['path']:
                resources.append(document)
            elif kind is PathClass.PROFILE and 'package_id' in parse_json_object(raw, path=path):
                package = LanguagePackage(raw)
                if package.key in packages:
                    raise ModelError('inspection_duplicate_language_package', path=path)
                packages[package.key] = package
            else:
                resources.append(document)
                if kind is PathClass.PROFILE:
                    profile_sources.append(ProfileResource(raw))
        selected_packages = []
        for key in configuration.data.get('language_packages', []):
            if key not in packages:
                raise ModelError('inspection_language_package_missing')
            selected_packages.append(packages[key])
        # The public API and CLI both resolve one explicit Core-first selection.
        keys = configuration.data.get('profiles', []) if profiles is None else profiles
        keys = tuple(key for key in keys if key not in ('core', 'core@0.2.0'))
        profile = compose_profiles(profile_sources, core_key='core@0.2.0',
            cli_profiles=keys, language_registry=registry, language_packages=selected_packages)
        self.payload_paths = tuple(sorted(attachments))
        for path in self.payload_paths:
            raw = source.read_normative(path, referenced_payloads=self.payload_paths)
            self.raw[path] = raw
            resources.append(ModelDocument(path, raw))
        binding = ProjectReadBinding(configuration.project_id, str(source.boundary.root),
                                     source.boundary._root_identity)
        self.model = TargetModel(self.raw['specroad.json'], binding, documents,
            profile=profile, resource_files=resources, attachments=tuple(attachments.values()),
            language_packages=selected_packages)

    def verify_current(self):
        source = self.source
        source.check_current()
        if current_json_paths(source) != self.paths:
            raise InspectionChanged('inspection_inventory_changed')
        for path, raw in self.raw.items():
            current = (source.boundary.read_bytes(path) if path == self.registry_path else
                       source.read_normative(path, referenced_payloads=self.payload_paths))
            if current != raw:
                raise InspectionChanged('inspection_source_changed', path=path)
        if current_json_paths(source) != self.paths:
            raise InspectionChanged('inspection_inventory_changed')
        source.check_current()
