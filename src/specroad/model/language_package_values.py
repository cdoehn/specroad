"""Immutable metadata bindings and results, separate from presentation labels."""
from dataclasses import dataclass
from hashlib import sha256
from ._language_package_parser import (_validate_package, package_key, parse_package_key,
    LanguagePackageError, range_matches)
from .language_tags import parse_language_tag
from ..storage.json_syntax import parse_json_object

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


@dataclass(frozen=True)
class PackageSelection:
    language: str
    packages: tuple
    unavailable: tuple

    def __post_init__(self):
        parse_language_tag(self.language)
        packages = coalesce_packages(self.packages)
        if any(not any(range_matches(r, self.language) for r in p.language_ranges) for p in packages):
            raise LanguagePackageError("selection_language_mismatch")
        if type(self.unavailable) not in (tuple, list):
            raise LanguagePackageError("package_sequence_required")
        for key in self.unavailable: parse_package_key(key)
        missing = tuple(dict.fromkeys(self.unavailable))
        if set(missing) & {p.key for p in packages}:
            raise LanguagePackageError("contradictory_package_availability")
        object.__setattr__(self, "packages", packages)
        object.__setattr__(self, "unavailable", missing)

    def as_dict(self):
        return {"language": self.language, "packages": [p.binding() for p in self.packages],
                "unavailable": list(self.unavailable),
                "content_support": "utf8", "metadata_policy": "not_evaluated",
                "labels": "available" if any("labels" in p.capabilities for p in self.packages) else "not_available",
                "lint": "not_available", "detector": "not_available"}


