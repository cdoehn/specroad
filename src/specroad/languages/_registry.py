"""Bound registry observation, separate from permission and severity policy."""
from ..model.language_policy import LanguagePolicyError
from ..model.language_registry import LanguageRegistry


def assess_declaration(registry, language):
    if type(registry) is not LanguageRegistry:
        raise LanguagePolicyError("language_registry_required")
    # Reparse captured bytes rather than trusting detached metadata/cache fields.
    checked = LanguageRegistry(registry.source_bytes, expected_sha256=registry.sha256,
                               expected_version=registry.version)
    return checked.inspect(language)
