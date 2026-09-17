"""Stable passive-package API: no executable rule or translated label logic."""
from ._language_package_parser import (LanguagePackageError, package_key,
    parse_package_key, validate_ranges, range_matches)
from .language_package_values import LanguagePackage, PackageSelection, coalesce_packages
from .language_tags import parse_language_tag

__all__ = ("LanguagePackage", "PackageSelection", "LanguagePackageError", "package_key",
           "parse_package_key", "validate_ranges", "range_matches", "coalesce_packages",
           "select_language_packages")

def select_language_packages(language, packages):
    """Select from an explicitly supplied, already validated set; no defaults."""
    parse_language_tag(language)
    packages = coalesce_packages(packages)
    return tuple(p for p in packages if any(range_matches(r, language) for r in p.language_ranges))
