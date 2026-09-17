"""Data-only distribution index validation, never resolution of project paths."""
import re
from .language_packages import LanguagePackageError, package_key, validate_ranges
from ..storage.json_syntax import parse_json_object

def decode_package_index(raw):
    value = parse_json_object(raw)
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


