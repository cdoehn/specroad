"""Explicit distribution profile resolution; never a project fallback or update."""
from importlib.resources import files
import re
from ..profiles.core import ProfileResource, ProfileError, parse_profile_key
from .json_syntax import parse_json_object

_BUNDLED = {"core@0.2.0": "core.json", "software-de@0.2.0": "software-de.json",
            "software-en@0.2.0": "software-en.json"}

def _read(filename):
    try:
        return files("specroad.profile_data").joinpath(filename).read_bytes()
    except (OSError, ValueError) as error:
        raise ProfileError("profile_resource_unavailable") from error


def bundled_profile_index():
    value = parse_json_object(_read("profiles.json"))
    if (set(value) != {"format_version", "profiles"} or type(value["format_version"]) is not int
            or value["format_version"] != 1 or type(value["profiles"]) is not list):
        raise ProfileError("profile_invalid_index")
    seen = set()
    for item in value["profiles"]:
        if type(item) is not dict or set(item) != {"profile_id", "version", "filename", "sha256", "source_sha256"}:
            raise ProfileError("profile_invalid_index")
        # Validate parts before combining; non-string values never invoke hooks.
        if type(item["profile_id"]) is not str or type(item["version"]) is not str:
            raise ProfileError("profile_invalid_index")
        key = item["profile_id"] + "@" + item["version"]
        parse_profile_key(key)
        if key in seen or key not in _BUNDLED or item["filename"] != _BUNDLED[key]:
            raise ProfileError("profile_invalid_index")
        seen.add(key)
        if any(type(item[k]) is not str or re.fullmatch(r"[0-9a-f]{64}", item[k]) is None
               for k in ("sha256", "source_sha256")):
            raise ProfileError("profile_invalid_index")
    if seen != set(_BUNDLED):
        raise ProfileError("profile_incomplete_index")
    return tuple(value["profiles"])


def load_bundled_profile(key):
    parse_profile_key(key)
    if key not in _BUNDLED:
        raise ProfileError("profile_not_available")
    reference = next(r for r in bundled_profile_index() if r["profile_id"] + "@" + r["version"] == key)
    resource = ProfileResource(_read(_BUNDLED[key]))
    if (resource.key != key or resource.sha256 != reference["sha256"]
            or resource.source_sha256 != reference["source_sha256"]):
        raise ProfileError("profile_binding_mismatch")
    return resource


def read_profile(source, path, *, expected_key, expected_sha256):
    """Read one explicit hash-bound normative profile; never use distribution fallback.

The final read detects observed byte changes, not arbitrary concurrent changes
between filesystem observations. This is no atomic multi-file snapshot and no
reusable permission to write. A profile's canonical identity does not prove who
created the supplied file or selected its expected digest.
"""
    from .project import ProjectSource
    from ..model.paths import PathClass
    if type(source) is not ProjectSource:
        raise ProfileError("profile_project_source_required")
    parse_profile_key(expected_key)
    if type(expected_sha256) is not str or re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is None:
        raise ProfileError("profile_expected_hash_required")
    source.check_current()
    if source.classify(path) is not PathClass.PROFILE:
        raise ProfileError("profile_path_class_mismatch", path=path)
    raw = source.read_normative(path)
    profile = ProfileResource(raw)
    if profile.key != expected_key or profile.sha256 != expected_sha256:
        raise ProfileError("profile_binding_mismatch", path=path)
    source.check_current()
    if source.read_normative(path) != raw:
        raise ProfileError("profile_changed_during_read", path=path)
    source.check_current()
    return profile
