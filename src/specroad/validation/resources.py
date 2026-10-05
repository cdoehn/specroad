"""Owned project bytes for the built-in validation adapters; no resource lookup."""
from dataclasses import dataclass
from hashlib import sha256

from ..model.canonical import canonical_json_sha256
from ..model.configuration import ProjectConfiguration
from ..model.errors import ModelError
from ..model.language_registry import LanguageRegistry
from ..storage.json_syntax import parse_json_object


@dataclass(frozen=True, init=False)
class ValidationResources:
    """Actual configuration and optional explicitly bound offline registry.

    Absence of a registry leaves the language gate unavailable. These inputs
    carry no human review, history, evidence, disk freshness or write authority.
    """
    configuration_bytes: bytes
    registry: LanguageRegistry | None

    def __init__(self, configuration_bytes, *, registry=None):
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
        object.__setattr__(self, "configuration_bytes", configuration_bytes)
        object.__setattr__(self, "registry", registry)

    @property
    def configuration(self):
        return ProjectConfiguration(parse_json_object(self.configuration_bytes))

    @property
    def sha256(self):
        return canonical_json_sha256({"configuration": sha256(self.configuration_bytes).hexdigest(),
            "registry": None if self.registry is None else self.registry.sha256})

    def snapshot(self):
        return ValidationResources(self.configuration_bytes, registry=self.registry)
