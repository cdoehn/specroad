"""Presentation-only label lookup, never requirement parsing or translation."""
from ..model.language_packages import coalesce_packages
from ..storage.language_packages import packages_for_language


def label_for(enum_value, *, domain, packages=()):
    if type(enum_value) is not str or type(domain) is not str:
        raise TypeError("Labels require string data keys")
    packages = coalesce_packages(packages)
    label = enum_value
    for package in packages:
        label = package.data["labels"].get(domain, {}).get(enum_value, label)
    return label


def labels_for_locale(display_locale, *, activated=()):
    """Explicit display choice; never consult LANG or the content language."""
    return packages_for_language(display_locale, activated=activated).packages
