"""Load the explicitly bound project snapshot, never a fallback or online copy."""

from hashlib import sha256
from importlib.resources import files
import json

from ..model.language_registry import LanguageRegistry, LanguageRegistryError
from ..model.language_tags import VALIDATOR_VERSION


def bundled_language_registry():
    """Distribution data for future init; never used as a project fallback."""
    resource = files("specroad.language_data")
    try:
        manifest = json.loads(resource.joinpath("snapshot.json").read_bytes())
        if (manifest["format_version"] != 1 or manifest["registry_id"] != "iana-language-subtags"
                or manifest["filename"] != "registry.txt" or manifest["validator_version"] != VALIDATOR_VERSION):
            raise LanguageRegistryError("invalid_distribution_registry_manifest")
        raw = resource.joinpath("registry.txt").read_bytes()
        registry = LanguageRegistry(raw, expected_sha256=manifest["sha256"], expected_version=manifest["registry_version"])
        if len(registry.records) != manifest["record_count"]:
            raise LanguageRegistryError("registry_record_count_mismatch")
        return registry
    except (OSError, KeyError, TypeError, UnicodeError, json.JSONDecodeError) as error:
        raise LanguageRegistryError("distribution_registry_unavailable") from error


def read_language_registry(source):
    """An immutable read observation, not a live cache or write authorization."""
    source.check_current()
    binding = source.configuration.data.get("language_registry")
    if binding is None:
        raise LanguageRegistryError("language_registry_required")
    path = binding["path"]
    try:
        # The registry is not JSON. Its only allowed path is the configured,
        # managed profiles/language-data resource; boundary reads reject links.
        raw = source.boundary.read_bytes(path)
        registry = LanguageRegistry(raw, expected_sha256=binding["sha256"],
                                    expected_version=binding["registry_version"])
        source.check_current()
        if source.boundary.read_bytes(path) != raw:
            raise LanguageRegistryError("registry_changed", path=path)
        source.check_current()
        return registry
    except OSError as error:
        raise LanguageRegistryError("registry_unavailable", path=path) from error


def registry_binding(registry, *, path="profiles/language-data/registry.txt"):
    """Propose init metadata only; callers still need the planned-write engine."""
    from ..model.paths import project_path
    if not isinstance(registry, LanguageRegistry): raise TypeError("A validated registry is required")
    path = project_path(path)
    if not path.startswith("profiles/language-data/"):
        raise LanguageRegistryError("invalid_registry_binding", path=path)
    return {"registry_id": "iana-language-subtags", "registry_version": registry.version,
            "path": path, "sha256": registry.sha256}
