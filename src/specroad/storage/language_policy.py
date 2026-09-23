"""Read-only declaration checks using explicit project-bound language resources.

References are caller-supplied observations, not a new persisted project index.
Only matching activated payloads are opened. All bindings are rechecked before
return; this is not an atomic snapshot, authorization, or registry updater.
"""
from dataclasses import dataclass
import re

from ..languages import compose_language_packages, evaluate_language
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.configuration import ProjectConfiguration
from ..model.language_packages import (LanguagePackage, LanguagePackageError,
    package_key, parse_package_key, validate_ranges, range_matches)
from ..model.language_policy import LanguagePolicy, LanguagePolicyError
from ..model.language_tags import parse_language_tag
from ..model.paths import PathClass, project_path
from .json_syntax import parse_json_object
from .language_registry import read_language_registry, require_registry_current
from .project import ProjectSource
from .requirement import read_requirement


def effective_language_configuration(configuration):
    """Materialize defaults in a fresh projection, never change saved metadata."""
    if type(configuration) is not ProjectConfiguration:
        raise LanguagePolicyError("language_project_configuration_required")
    data = configuration.data
    return {"language_policy": LanguagePolicy(data.get("language_policy", {})).data,
            "language_registry": data.get("language_registry"),
            "language_packages": data.get("language_packages", [])}


def _references(source, references):
    if type(references) not in (tuple, list):
        raise LanguagePackageError("package_references_required")
    index, paths = {}, {}
    for item in references:
        if type(item) is not dict or set(item) != {"package_id", "version", "path", "sha256", "language_ranges"}:
            raise LanguagePackageError("package_reference_fields")
        key = package_key(item["package_id"], item["version"])
        if type(item["path"]) is not str:
            raise LanguagePackageError("package_reference_path_required")
        path = project_path(item["path"])
        if source.classify(path) is not PathClass.PROFILE:
            raise LanguagePackageError("package_reference_path_class", path=path)
        validate_ranges(item["language_ranges"])
        if type(item["sha256"]) is not str or not re.fullmatch(r"[0-9a-f]{64}", item["sha256"]):
            raise LanguagePackageError("package_reference_hash_required", path=path)
        # Owned JSON values only; do not hold a mutable caller-owned dictionary.
        owned = parse_json_object(canonical_json_bytes(item))
        if key in index and index[key] != owned:
            raise LanguagePackageError("package_reference_conflict", path=path)
        if path in paths and paths[path] != key:
            raise LanguagePackageError("package_reference_path_conflict", path=path)
        index.setdefault(key, owned)
        paths[path] = key
    return index


@dataclass(frozen=True, init=False)
class ProjectLanguagePackages:
    _encoded: bytes
    packages: tuple

    def __init__(self):
        raise TypeError("Use read_project_language_packages")

    @classmethod
    def _create(cls, value, packages):
        obj = object.__new__(cls)
        object.__setattr__(obj, "_encoded", canonical_json_bytes(value))
        object.__setattr__(obj, "packages", tuple(packages))
        return obj

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def sha256(self):
        return canonical_json_sha256(self.data)


def read_project_language_packages(source, language, *, references):
    """Use only activation from this exact project and explicit reference data.

A missing reference reports not_available. A selected known reference whose
file is missing, corrupt or differs from the supplied binding is a hard error.
Nonmatching reference metadata is only a declared selection input; its unopened
payload is explicitly not verified. It is never evidence for a language check.
"""
    if type(source) is not ProjectSource:
        raise LanguagePackageError("package_project_source_required")
    parse_language_tag(language)
    source.check_current()
    activated = source.configuration.data.get("language_packages", [])
    for key in activated:
        parse_package_key(key)
    index = _references(source, references)
    selected, excluded, relevant, reads = [], [], [], []
    for key in activated:
        reference = index.get(key)
        if reference is None:
            relevant.append(key)
            continue
        if not any(range_matches(r, language) for r in reference["language_ranges"]):
            excluded.append(reference)
            continue
        relevant.append(key)
        raw = source.read_normative(reference["path"])
        package = LanguagePackage(raw)
        expected = {k: v for k, v in reference.items() if k != "path"}
        if package.binding() != expected:
            raise LanguagePackageError("package_binding_mismatch", path=reference["path"])
        selected.append(package)
        reads.append((reference, raw))
    composition = compose_language_packages(language, activated=relevant, resources=selected)
    for reference, raw in reads:
        if source.read_normative(reference["path"]) != raw:
            raise LanguagePackageError("package_changed_during_read", path=reference["path"])
    source.check_current()
    return ProjectLanguagePackages._create({
        "observation_version": "project-language-packages-v1",
        "requested_activation": activated,
        "verified_references": [ref for ref, _ in reads],
        "nonmatching_references": excluded, "nonmatching_payloads_verified": False,
        "composition": composition.data, "composition_sha256": composition.sha256,
        "atomic_snapshot": False, "approval_granted": False,
        "validation_scope": "explicit_project_language_resources_only"}, selected)


def inspect_requirement_language(source, path, *, package_references, fail_on=None, strict=False):
    """Check one stored requirement without defaults for its declared language.

The caller supplies complete expected package-reference metadata for its purpose;
no directory inventory or resource discovery is claimed. A semantic configuration
projection binds the exact language policy, register and loaded package bytes.
"""
    if type(source) is not ProjectSource:
        raise LanguagePolicyError("language_project_source_required")
    source.check_current()
    configuration = effective_language_configuration(source.configuration)
    registry = read_language_registry(source)
    requirement = read_requirement(source, path)
    language = requirement.data["language"]
    threshold = (source.configuration.data["validation_policy"].get("fail_on", "error")
                 if fail_on is None else fail_on)
    policy = evaluate_language(language, policy=LanguagePolicy(configuration["language_policy"]),
                               registry=registry, fail_on=threshold, strict=strict)
    packages = read_project_language_packages(source, language, references=package_references)
    # Recheck the full selected observation, not just the latest file read.
    for reference in packages.data["verified_references"]:
        raw = source.read_normative(reference["path"])
        expected = {k: v for k, v in reference.items() if k != "path"}
        if LanguagePackage(raw).binding() != expected:
            raise LanguagePackageError("package_observation_changed", path=reference["path"])
    require_registry_current(source, registry)
    if source.read_normative(path) != requirement.source_bytes:
        raise LanguagePolicyError("language_requirement_changed", path=path)
    source.check_current()
    semantic = {**configuration, "loaded_packages": [p.binding() for p in packages.packages]}
    from hashlib import sha256
    return {"format_version": 1, "requirement_id": requirement.data["id"],
        "source_sha256": sha256(requirement.source_bytes).hexdigest(),
        "language": language, "metadata": policy, "packages": packages.data,
        "effective_language_configuration": semantic,
        "language_configuration_sha256": canonical_json_sha256(semantic),
        "exit_code": policy["exit_code"], "atomic_snapshot": False,
        "project_complete": False, "approval_granted": False,
        "validation_scope": "selected_requirement_language_only"}
