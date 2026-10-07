"""Owned project bytes for the built-in validation adapters; no resource lookup."""
from dataclasses import dataclass
from hashlib import sha256

from ..model.canonical import canonical_json_sha256
from ..model.configuration import ProjectConfiguration
from ..model.errors import ModelError
from ..model.language_registry import LanguageRegistry
from ..model.language_package_values import LanguagePackage
from ..profiles import ProfileResource, compose_profiles
from ..storage.json_syntax import parse_json_object


@dataclass(frozen=True, init=False)
class ValidationResources:
    """Actual configuration and optional explicitly bound offline registry.

    Absence of a registry leaves the language gate unavailable. These inputs
    carry no human review, history, evidence, disk freshness or write authority.
    """
    configuration_bytes: bytes
    registry: LanguageRegistry | None
    profile_resources: tuple
    core_key: str | None
    cli_profiles: tuple
    language_packages: tuple
    _input_sha256: str

    def __init__(self, configuration_bytes, *, registry=None, profile_resources=(),
                 core_key=None, cli_profiles=(), language_packages=()):
        if type(configuration_bytes) is not bytes:
            raise ModelError("validation_configuration_bytes_required")
        configuration = ProjectConfiguration(parse_json_object(configuration_bytes))
        if registry is not None:
            if type(registry) is not LanguageRegistry:
                raise ModelError("validation_language_registry_required")
            binding = configuration.data.get("language_registry")
            if binding is None:
                raise ModelError("validation_registry_binding_required")
            registry = LanguageRegistry(registry.source_bytes,
                expected_sha256=binding["sha256"], expected_version=binding["registry_version"])
        if (type(profile_resources) not in (tuple, list)
                or any(type(p) is not ProfileResource for p in profile_resources)):
            raise ModelError("validation_profile_resources_required")
        profiles = tuple(ProfileResource(p.source_bytes) for p in profile_resources)
        if any(p.binding() != original.binding() or p.source_sha256 != original.source_sha256
               for p, original in zip(profiles, profile_resources)):
            raise ModelError("validation_profile_resource_mismatch")
        if core_key is not None and (type(core_key) is not str or not core_key):
            raise ModelError("validation_core_profile_key_required")
        if type(cli_profiles) not in (tuple, list) or any(type(p) is not str for p in cli_profiles):
            raise ModelError("validation_profile_selection_required")
        if (type(language_packages) not in (tuple, list)
                or any(type(p) is not LanguagePackage for p in language_packages)):
            raise ModelError("validation_language_packages_required")
        packages = tuple(LanguagePackage(p.source_bytes) for p in language_packages)
        if any(p.binding() != original.binding() for p, original in zip(packages, language_packages)):
            raise ModelError("validation_language_package_mismatch")
        object.__setattr__(self, "configuration_bytes", configuration_bytes)
        object.__setattr__(self, "registry", registry)
        object.__setattr__(self, "profile_resources", profiles)
        object.__setattr__(self, "core_key", core_key)
        object.__setattr__(self, "cli_profiles", tuple(cli_profiles))
        object.__setattr__(self, "language_packages", packages)
        object.__setattr__(self, "_input_sha256", self.sha256)

    @property
    def configuration(self):
        return ProjectConfiguration(parse_json_object(self.configuration_bytes))

    @property
    def sha256(self):
        return canonical_json_sha256({"configuration": sha256(self.configuration_bytes).hexdigest(),
            "registry": None if self.registry is None else sha256(self.registry.source_bytes).hexdigest(),
            "profiles": sorted(sha256(p.source_bytes).hexdigest() for p in self.profile_resources),
            "core_key": self.core_key, "cli_profiles": list(self.cli_profiles),
            "language_packages": [sha256(p.source_bytes).hexdigest() for p in self.language_packages]})

    def snapshot(self):
        if self.sha256 != self._input_sha256:
            raise ModelError("validation_resource_inputs_changed")
        return ValidationResources(self.configuration_bytes, registry=self.registry,
            profile_resources=self.profile_resources, core_key=self.core_key,
            cli_profiles=self.cli_profiles, language_packages=self.language_packages)

    def checked_profile(self, profile):
        """Recompose from actual resource bytes and the explicit selection."""
        if profile is None:
            return None
        if self.core_key is None or not self.profile_resources:
            raise ModelError("validation_profile_resource_bytes_required")
        rebuilt = compose_profiles(self.profile_resources, core_key=self.core_key,
            project_profiles=self.configuration.data["profiles"], cli_profiles=self.cli_profiles,
            language_registry=self.registry, language_packages=self.language_packages)
        if rebuilt.canonical_bytes != profile.canonical_bytes:
            raise ModelError("validation_profile_context_mismatch")
        return rebuilt
