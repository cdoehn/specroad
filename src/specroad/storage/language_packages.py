"""Distribution-only package loading, never a project-register fallback.

The small index may be read without reading each package. Only explicitly
activated and matching packages are loaded. Project-bound profile composition
and its hashes will be implemented by the later profile workflow.
"""
from dataclasses import dataclass
from importlib.resources import files
import re

from ..model.language_packages import (LanguagePackage, LanguagePackageError, package_key,
                                       parse_package_key, validate_ranges, range_matches)
from ..model.language_tags import parse_language_tag
from .json_syntax import parse_json_object


def _read(filename):
    try:
        return files("specroad.language_data").joinpath(filename).read_bytes()
    except (OSError, ValueError) as error:
        raise LanguagePackageError("distribution_package_unavailable") from error


def bundled_package_index():
    value = parse_json_object(_read("packages.json"))
    if set(value) != {"format_version", "packages"} or type(value["format_version"]) is not int or value["format_version"] != 1:
        raise LanguagePackageError("invalid_package_index")
    entries = value["packages"]
    if type(entries) is not list:
        raise LanguagePackageError("invalid_package_index")
    keys, filenames = set(), set()
    for item in entries:
        if type(item) is not dict or set(item) != {"package_id", "version", "language_ranges", "sha256", "filename"}:
            raise LanguagePackageError("invalid_package_reference")
        key = package_key(item["package_id"], item["version"])
        validate_ranges(item["language_ranges"])
        if type(item["sha256"]) is not str or not re.fullmatch(r"[0-9a-f]{64}", item["sha256"]):
            raise LanguagePackageError("invalid_package_hash")
        name = item["filename"]
        if type(name) is not str or not re.fullmatch(r"packages/[A-Za-z][A-Za-z0-9_-]*\.json", name, re.ASCII):
            raise LanguagePackageError("invalid_package_filename")
        if key in keys or name.casefold() in filenames:
            raise LanguagePackageError("duplicate_package_reference")
        keys.add(key); filenames.add(name.casefold())
    return tuple(entries)


def _load_reference(item):
    package = LanguagePackage(_read(item["filename"]))
    if package.binding() != {key: item[key] for key in ("package_id", "version", "language_ranges", "sha256")}:
        raise LanguagePackageError("package_binding_mismatch")
    return package


def load_bundled_package(key):
    parse_package_key(key)
    for item in bundled_package_index():
        if package_key(item["package_id"], item["version"]) == key:
            return _load_reference(item)
    raise LanguagePackageError("package_not_available")


@dataclass(frozen=True)
class PackageSelection:
    language: str
    packages: tuple
    unavailable: tuple

    def as_dict(self):
        return {"language": self.language, "packages": [p.binding() for p in self.packages],
                "unavailable": list(self.unavailable),
                "content_support": "utf8", "metadata_policy": "not_evaluated",
                "labels": "available" if any("labels" in p.capabilities for p in self.packages) else "not_available",
                "lint": "not_available", "detector": "not_available"}


def packages_for_language(language, *, activated=()):
    parse_language_tag(language)
    if type(activated) not in (tuple, list):
        raise LanguagePackageError("package_sequence_required")
    for key in activated: parse_package_key(key)
    # No requested packages means no index or resource IO at all.
    index = {package_key(v["package_id"], v["version"]): v for v in bundled_package_index()} if activated else {}
    selected, unavailable = [], []
    for key in activated:
        item = index.get(key)
        if item is None:
            unavailable.append(key)
        elif any(range_matches(r, language) for r in item["language_ranges"]):
            selected.append(_load_reference(item))
    return PackageSelection(language, tuple(selected), tuple(unavailable))


def minimum_language_corpus():
    value = parse_json_object(_read("minimum_corpus.json"))
    if set(value) != {"format_version", "minimum_tags", "additional_tags"} or type(value["format_version"]) is not int or value["format_version"] != 1:
        raise LanguagePackageError("invalid_minimum_language_corpus")
    for key in ("minimum_tags", "additional_tags"):
        if type(value[key]) is not list or not value[key]:
            raise LanguagePackageError("invalid_minimum_language_corpus")
        for tag in value[key]: parse_language_tag(tag)
        if len({parse_language_tag(t).canonical.lower() for t in value[key]}) != len(value[key]):
            raise LanguagePackageError("duplicate_corpus_tag")
    return value
