"""Distribution-only package loading, never a project-register fallback.

The small index may be read without reading each package. Only explicitly
activated and matching packages are loaded. Project-bound profile composition
and its hashes will be implemented by the later profile workflow.
"""
from importlib.resources import files

from ..model.language_packages import (LanguagePackage, LanguagePackageError, package_key,
                                       parse_package_key, validate_ranges, range_matches, coalesce_packages)
from ..model.language_tags import parse_language_tag
from ..model.language_package_index import decode_package_index
from ..model.language_package_values import PackageSelection
from .json_syntax import parse_json_object


def _read(filename):
    try:
        return files("specroad.language_data").joinpath(filename).read_bytes()
    except (OSError, ValueError) as error:
        raise LanguagePackageError("distribution_package_unavailable") from error


def bundled_package_index():
    return decode_package_index(_read("packages.json"))


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


def packages_for_language(language, *, activated=()):
    parse_language_tag(language)
    if type(activated) not in (tuple, list):
        raise LanguagePackageError("package_sequence_required")
    for key in activated: parse_package_key(key)
    activated = tuple(dict.fromkeys(activated))
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
