"""Pure label lookup over supplied passive resources, independent of the CLI.

This module accepts enum keys and packages, never requirement statements or
locale defaults. Resource loading and package selection remain with callers.
"""
from .language_packages import coalesce_packages


def label_for(enum_value, *, domain, packages=()):
    if type(enum_value) is not str or type(domain) is not str:
        raise TypeError("Labels require string data keys")
    packages = coalesce_packages(packages)
    label = enum_value
    for package in packages:
        label = package.data["labels"].get(domain, {}).get(enum_value, label)
    return label
