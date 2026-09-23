"""Explicit Core-first selection and composition, with no implicit I/O.

Merge strategies and immutable output values live in their own modules. This
facade does not select project language resources, run lint, or authorize writes.
"""
from ._contract import parse_profile_key
from .values import ProfileResource
from .fields import observe_profile_fields
from .composition_values import (COMPOSITION_VERSION, EffectiveProfile,
    ProfileCompositionError, _error)
from ._composition_merge import _merge
from ..model.errors import ModelError
from ..model.language_registry import LanguageRegistry
from ..model.language_package_values import LanguagePackage
from ..model.language_tags import VALIDATOR_VERSION

def _selection(resources, core_key, project_profiles, cli_profiles):
    if type(resources) not in (tuple, list):
        _error("profile_resources_required")
    index = {}
    for resource in resources:
        if type(resource) is not ProfileResource:
            _error("profile_resource_required")
        # Reparse the owned bytes. Detached/fabricated metadata cannot alter the
        # actual profile used for either execution contracts or hash formation.
        checked = ProfileResource(resource.source_bytes)
        if checked.binding() != resource.binding() or checked.source_sha256 != resource.source_sha256:
            _error("profile_binding_mismatch")
        if checked.key in index:
            _error("profile_duplicate_resource", profiles=(checked.key,))
        index[checked.key] = checked
    if parse_profile_key(core_key)[0] != "core":
        _error("profile_exact_core_required", "/core_key")
    for value, at in ((project_profiles, "/project_profiles"), (cli_profiles, "/cli_profiles")):
        if type(value) not in (tuple, list) or any(type(key) is not str for key in value):
            _error("profile_selection_required", at)
    source = "cli" if cli_profiles else "project"
    keys = (core_key, *(cli_profiles if cli_profiles else project_profiles))
    identities = set()
    selected = []
    for position, key in enumerate(keys):
        name, _ = parse_profile_key(key)
        if name in identities:
            _error("profile_duplicate_identity", "/profiles/" + str(position), profiles=(key,))
        identities.add(name)
        if key not in index:
            _error("profile_not_available", "/profiles/" + str(position), profiles=(key,))
        selected.append(index[key])
    return tuple(selected), source


def _language_bindings(registry, packages):
    if registry is not None:
        if type(registry) is not LanguageRegistry:
            _error("profile_registry_required", "/language_registry")
        # Verify the bound bytes, not just copied labels or a mutable metadata dict.
        checked = LanguageRegistry(registry.source_bytes, expected_sha256=registry.sha256,
                                   expected_version=registry.version)
        binding = {"registry_id": "iana-language-subtags", "registry_version": checked.version,
                   "sha256": checked.sha256, "validator_version": VALIDATOR_VERSION}
    else:
        binding = None  # Explicitly no supplied registry; not a project default.
    if type(packages) not in (tuple, list):
        _error("profile_language_packages_required", "/language_packages")
    unique = {}
    for package in packages:
        if type(package) is not LanguagePackage:
            _error("profile_language_package_required", "/language_packages")
        checked = LanguagePackage(package.source_bytes)
        if checked.binding() != package.binding():
            _error("profile_package_binding_mismatch", "/language_packages")
        if checked.key in unique:
            if unique[checked.key] != checked.binding():
                _error("profile_language_package_conflict", "/language_packages")
            continue
        unique[checked.key] = checked.binding()
    # Keep the explicit activation order: later literal-rule composition must
    # not silently reorder packages. No content-language equality is imposed.
    return binding, list(unique.values())


def compose_profiles(resources, *, core_key, project_profiles=(), cli_profiles=(),
                     language_registry=None, language_packages=()):
    """Core first, nonempty explicit CLI selection replaces the project selection.

    Language resources are explicit typed byte-bound values, not selected from
    the host. A conflict returns no EffectiveProfile. No partial success.
    """
    try:
        registry_binding, package_bindings = _language_bindings(language_registry, language_packages)
        chain, source = _selection(resources, core_key, project_profiles, cli_profiles)
        merged = _merge(chain)
        value = {"composition_version": COMPOSITION_VERSION,
                 "profiles": [{k: p.binding()[k] for k in ("profile_id", "version", "sha256")} for p in chain],
                 "language_registry": registry_binding, "language_packages": package_bindings, "merge": merged}
        return EffectiveProfile._create(value, source)
    except ProfileCompositionError:
        raise
    except ModelError as error:
        raise ProfileCompositionError(error.reason, pointer=error.pointer) from error


def check_composed_fields(profile, artifact):
    """Only local field effects, not relation/lint execution or model approval."""
    if type(profile) is not EffectiveProfile:
        _error("effective_profile_required")
    checked, diagnostics = observe_profile_fields(profile.data["merge"], artifact)
    return {"profile": profile.binding(), "validation_scope": "profile_fields_only",
            "profile_composition_checked": True, "checked_fields": checked,
            "field_checks_passed": not diagnostics, "diagnostics": diagnostics,
            "relation_rules_checked": False, "lint_rules_checked": False, "approval_granted": False}
