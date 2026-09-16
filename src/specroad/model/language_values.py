"""Immutable language registry values, independent of storage and policy."""

from dataclasses import dataclass

from .errors import ModelError
from .language_tags import VALIDATOR_VERSION


class LanguageRegistryError(ModelError):
    exit_code = 3


@dataclass(frozen=True)
class RegistryRecord:
    kind: str
    value: str
    fields: tuple

    def values(self, name):
        return tuple(value for key, value in self.fields if key == name)


@dataclass(frozen=True)
class LanguageAssessment:
    original: str
    canonical: str | None
    registry_state: str
    syntax_valid: bool
    reasons: tuple
    unknown_subtags: tuple
    deprecated: tuple
    preferred_values: tuple
    unspecified: bool
    registry_version: str
    registry_sha256: str
    validator_version: str = VALIDATOR_VERSION
    registration_scope: str = "language_subtags_only"
    linguistic_validation: bool = False

    def as_dict(self):
        return {"original": self.original, "canonical": self.canonical,
                "syntax_valid": self.syntax_valid, "registry_state": self.registry_state,
                "reasons": list(self.reasons), "unknown_subtags": list(self.unknown_subtags),
                "deprecated": list(self.deprecated),
                "preferred_values": [{"subtag": key, "value": value} for key, value in self.preferred_values],
                "unspecified": self.unspecified, "registry_id": "iana-language-subtags",
                "registry_version": self.registry_version, "registry_sha256": self.registry_sha256,
                "validator_version": self.validator_version, "registration_scope": self.registration_scope,
                "linguistic_validation": False}


