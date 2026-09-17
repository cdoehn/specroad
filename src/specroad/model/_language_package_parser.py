"""Closed passive package syntax; no I/O, imports or callbacks from data."""
import re
from .errors import ModelError
from .language_tags import parse_language_tag

_PACKAGE_ID = re.compile(r"[A-Za-z][A-Za-z0-9_-]*", re.ASCII)
_SEMVER = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)(?:-(?:0|[1-9][0-9]*|[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*)(?:\.(?:0|[1-9][0-9]*|[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*))*)?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?", re.ASCII)
_RANGE = re.compile(r"[A-Za-z]{1,8}(?:-[A-Za-z0-9]{1,8})*|\*", re.ASCII)
_LABEL_KEY = re.compile(r"[a-z][a-z0-9_]*", re.ASCII)
_FIELDS = frozenset({"package_id", "version", "language_ranges", "labels", "literal_rules", "capabilities"})


class LanguagePackageError(ModelError):
    """A malformed or unsupported declaration, never a lint result."""
    exit_code = 3


def package_key(package_id, version):
    if type(package_id) is not str or not _PACKAGE_ID.fullmatch(package_id):
        raise LanguagePackageError("invalid_package_id")
    if type(version) is not str or not _SEMVER.fullmatch(version):
        raise LanguagePackageError("invalid_package_version")
    return package_id + "@" + version


def parse_package_key(value):
    if type(value) is not str or value.count("@") != 1:
        raise LanguagePackageError("invalid_package_key")
    package_id, version = value.split("@")
    package_key(package_id, version)
    return package_id, version


def validate_ranges(values):
    if type(values) not in (list, tuple) or not values:
        raise LanguagePackageError("language_ranges_required")
    if any(type(v) is not str or not _RANGE.fullmatch(v) for v in values):
        raise LanguagePackageError("invalid_language_range")
    if len({v.lower() for v in values}) != len(values):
        raise LanguagePackageError("duplicate_language_range")
    return tuple(values)


def range_matches(language_range, language):
    """RFC 4647 basic matching only; no alias lookup or script inference."""
    validate_ranges([language_range])
    tag = parse_language_tag(language).canonical.lower()
    value = language_range.lower()
    return value == "*" or tag == value or tag.startswith(value + "-")


def _validate_package(value):
    if set(value) != _FIELDS:
        raise LanguagePackageError("invalid_package_fields")
    package_key(value["package_id"], value["version"])
    validate_ranges(value["language_ranges"])
    labels = value["labels"]
    if type(labels) is not dict:
        raise LanguagePackageError("invalid_labels")
    for domain, entries in labels.items():
        if not _LABEL_KEY.fullmatch(domain) or type(entries) is not dict:
            raise LanguagePackageError("invalid_label_domain")
        for key, text in entries.items():
            if not _LABEL_KEY.fullmatch(key) or type(text) is not str or not text:
                raise LanguagePackageError("invalid_label_entry")
    if value["literal_rules"] != [] or type(value["literal_rules"]) is not list:
        raise LanguagePackageError("literal_rules_not_supported")
    caps = value["capabilities"]
    if (type(caps) is not list or any(type(v) is not str or v not in {"metadata", "labels"} for v in caps)
            or len(set(caps)) != len(caps)):
        raise LanguagePackageError("unsupported_package_capability")
    if labels and "labels" not in caps:
        raise LanguagePackageError("labels_capability_required")


