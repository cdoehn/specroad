"""Presentation-only label lookup, never requirement parsing or translation."""
from ..model.language_labels import label_for as _label_for
from ..storage.language_packages import packages_for_language


def label_for(enum_value, *, domain, packages=()):
    return _label_for(enum_value, domain=domain, packages=packages)


def labels_for_locale(display_locale, *, activated=()):
    """Explicit display choice; never consult LANG or the content language."""
    return packages_for_language(display_locale, activated=activated).packages
