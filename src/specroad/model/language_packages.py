"""Passive language label/metadata contracts, not language policy or analysis.

Only metadata/label packages with empty literal_rules are currently executable
as resources. A future rule interpreter must explicitly add its own contract;
no arbitrary project declaration can turn itself into a Python callback.
"""
from dataclasses import dataclass
from hashlib import sha256
import re

from .errors import ModelError
from .language_tags import parse_language_tag
from ..storage.json_syntax import parse_json_object

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


@dataclass(frozen=True, init=False)
class LanguagePackage:
    source_bytes: bytes
    package_id: str
    version: str
    language_ranges: tuple
    capabilities: tuple
    sha256: str

    def __init__(self, raw):
        if type(raw) is not bytes:
            raise LanguagePackageError("package_bytes_required")
        value = parse_json_object(raw)
        _validate_package(value)
        object.__setattr__(self, "source_bytes", raw)
        for key in ("package_id", "version"):
            object.__setattr__(self, key, value[key])
        for key in ("language_ranges", "capabilities"):
            object.__setattr__(self, key, tuple(value[key]))
        object.__setattr__(self, "sha256", sha256(raw).hexdigest())

    @property
    def key(self):
        return package_key(self.package_id, self.version)

    @property
    def data(self):
        return parse_json_object(self.source_bytes)

    def binding(self):
        return {"package_id": self.package_id, "version": self.version,
                "language_ranges": list(self.language_ranges), "sha256": self.sha256}


def coalesce_packages(packages):
    """Collapse identical identity/version/bytes only; conflicts are not merges."""
    if type(packages) not in (tuple, list) or any(type(p) is not LanguagePackage for p in packages):
        raise LanguagePackageError("typed_packages_required")
    unique = {}
    for package in packages:
        prior = unique.get(package.key)
        if prior is not None and prior.sha256 != package.sha256:
            raise LanguagePackageError("package_identity_conflict")
        unique.setdefault(package.key, package)
    return tuple(unique.values())


def select_language_packages(language, packages):
    """Select from an explicitly supplied, already validated set; no defaults."""
    parse_language_tag(language)
    packages = coalesce_packages(packages)
    return tuple(p for p in packages if any(range_matches(r, language) for r in p.language_ranges))
