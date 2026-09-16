"""Load the explicitly bound project snapshot, never a fallback or online copy."""

from hashlib import sha256
from importlib.resources import files
import json
from .json_syntax import parse_json_object
from ..model.errors import ModelError
from ..security import SafetyViolation

from ..model.language_registry import LanguageRegistry, LanguageRegistryError
from ..model.language_tags import VALIDATOR_VERSION


def bundled_language_registry():
    """Distribution data for future init; never used as a project fallback."""
    resource = files("specroad.language_data")
    try:
        manifest = parse_json_object(resource.joinpath("snapshot.json").read_bytes())
        if set(manifest) != {"format_version", "registry_id", "registry_version", "filename", "sha256",
                             "validator_version", "record_count", "source"}:
            raise LanguageRegistryError("invalid_distribution_registry_manifest")
        if (type(manifest["format_version"]) is not int or manifest["format_version"] != 1
                or type(manifest["record_count"]) is not int or manifest["record_count"] < 1 or manifest["registry_id"] != "iana-language-subtags"
                or manifest["filename"] != "registry.txt" or manifest["validator_version"] != VALIDATOR_VERSION):
            raise LanguageRegistryError("invalid_distribution_registry_manifest")
        raw = resource.joinpath("registry.txt").read_bytes()
        registry = LanguageRegistry(raw, expected_sha256=manifest["sha256"], expected_version=manifest["registry_version"])
        if len(registry.records) != manifest["record_count"]:
            raise LanguageRegistryError("registry_record_count_mismatch")
        return registry
    except LanguageRegistryError:
        raise
    except (OSError, KeyError, TypeError, UnicodeError, ModelError, json.JSONDecodeError) as error:
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
    except SafetyViolation as error:
        raise LanguageRegistryError("unsafe_registry_resource", path=path) from error
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


def require_registry_current(source, registry):
    """Revalidate an observation; still not a transactional write permission."""
    if not isinstance(registry, LanguageRegistry):
        raise TypeError("A validated registry is required")
    current = read_language_registry(source)
    if (current.version, current.sha256, current.source_bytes) != (registry.version, registry.sha256, registry.source_bytes):
        raise LanguageRegistryError("registry_observation_changed")
    return current
