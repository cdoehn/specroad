"""Explicit profile composition over supplied resources, never project discovery.

A composition is not a validated project, an authentic resource certificate, or
permission to write. Selection never reads CLI arguments or the environment.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from types import MappingProxyType

from ._contract import parse_profile_key
from .errors import ProfileError
from .values import ProfileResource
from .fields import observe_profile_fields
from ..model.artifact_schemas import MATURITIES
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.errors import ModelError
from ..storage.json_syntax import parse_json_object
from ..graph.relation_obligations import MinimumRelationRule
from ..model.language_registry import LanguageRegistry
from ..model.language_package_values import LanguagePackage
from ..model.language_tags import VALIDATOR_VERSION

COMPOSITION_VERSION = "profile-composition-v1"
# Chapter 13: structural, integrity, identity, recorded-evidence, transaction,
# execution-authority and path failures cannot be downgraded. Semantic review
# findings (e.g. SRV033/SRV050) remain configurable. SRV027 is protected because
# its code includes structural failures, not only review_outcome findings.
CORE_MINIMUM_SEVERITIES = MappingProxyType({key: "error" for key in (
    "SRV001", "SRV002", "SRV003", "SRV010", "SRV011", "SRV012", "SRV013",
    "SRV020", "SRV021", "SRV022", "SRV027", "SRV030", "SRV034", "SRV040", "SRV042",
    "SRV060", "SRV061", "SRV070", "SRV071", "SRV072", "SRV073", "SRV080", "SRV081",
    "SRV082", "SRV083", "SRV090", "SRV100", "SRV101", "SRV110", "SRV111", "SRV120",
    "SRV130", "SRV131", "SRV140", "SRV141", "SRV142", "SRV143", "SRV144", "SRV145",
    "SRV146", "SRV147", "SRV148", "SRV149", "SRV150", "SRV151", "SRV152", "SRV153",
    "SRV154", "SRV155", "SRV157", "SRV158", "SRV168", "SRV170", "SRV172", "SRV173",
    "SRV174", "SRV175", "SRV183", "SRV185", "SRV192", "SRV193", "SRV194", "SRV195",
    "core:requirement-origin", "core:requirement-verification",
)})


class ProfileCompositionError(ProfileError):
    """A failed composition has no effective model or hash to continue with."""
    code = "SRV142"
    exit_code = 3

    def __init__(self, reason, *, pointer="", profiles=(), rule_id=None):
        super().__init__(reason, pointer=pointer)
        self.profiles = tuple(profiles)
        self.rule_id = rule_id

    def diagnostic(self):
        return {**super().diagnostic(), "code": self.code, "exit_code": self.exit_code,
                "severity": "error", "profiles": list(self.profiles), "rule_id": self.rule_id,
                "effective_profile_available": False}


def _error(reason, pointer="", profiles=(), rule_id=None):
    raise ProfileCompositionError(reason, pointer=pointer, profiles=profiles, rule_id=rule_id)


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


def _cells(entry):
    for kind in sorted(entry["artifact_types"]):
        for maturity in sorted(entry["maturities"] or MATURITIES):
            yield kind, maturity


def _field_rows(values):
    return [{"artifact_types": [kind], "maturities": [maturity], "fields": sorted(fields)}
            for (kind, maturity), fields in sorted(values.items())]


def _merge(chain):
    required, forbidden, allowed = {}, {}, {}
    hard_limits, normative_policy = {}, {}
    rules = {"relation_rules": [], "lint_rules": []}
    seen_rules, rule_bindings, overrides = {}, [], {}
    minima = dict(CORE_MINIMUM_SEVERITIES)
    # Core-declared rule severity is a minimum; the built-in security floor is
    # never supplied by a user profile and cannot itself be overridden.
    core_data = chain[0].data
    levels = {"info": 0, "warning": 1, "error": 2}
    for family in rules:
        for rule in core_data[family]:
            minima[rule["rule_id"]] = max((minima.get(rule["rule_id"], "info"), rule["severity"]), key=levels.get)
    for profile in chain:
        data = profile.data
        for name, limit in data.get("hard_limits", {}).items():
            hard_limits[name] = min(hard_limits.get(name, limit), limit)
        for name, scalar in data.get("normative_policy", {}).items():
            if name in normative_policy and canonical_json_bytes(normative_policy[name]) != canonical_json_bytes(scalar):
                _error("profile_scalar_policy_conflict", "/normative_policy/" + name, (p.key for p in chain))
            normative_policy[name] = scalar
        for group, merged in (("required_fields", required), ("forbidden_fields", forbidden)):
            for entry in data[group]:
                for cell in _cells(entry):
                    merged.setdefault(cell, set()).update(entry["fields"])
        for entry in data["allowed_values"]:
            candidates = {canonical_json_bytes(v) for v in entry["values"]}
            for cell in _cells(entry):
                key = (*cell, entry["field"])
                allowed[key] = candidates if key not in allowed else allowed[key] & candidates
                if not allowed[key]:
                    _error("profile_empty_intersection", entry["field"], (p.key for p in chain))
        for family in rules:
            for rule in data[family]:
                identity = rule["rule_id"]
                binding = (family, rule["version"], canonical_json_sha256(rule))
                if identity in seen_rules:
                    if seen_rules[identity] != binding:
                        _error("profile_rule_conflict", "/" + family, (p.key for p in chain), identity)
                    continue
                seen_rules[identity] = binding
                rules[family].append(rule)
                rule_bindings.append({"family": family, "rule_id": identity, "version": binding[1], "sha256": binding[2]})
        for identity, severity in data["severity_overrides"].items():
            if identity in minima and levels[severity] < levels[minima[identity]]:
                _error("profile_core_severity_lowered", "/severity_overrides/" + identity, (profile.key,), identity)
            overrides[identity] = severity
    for cell, fields in required.items():
        for field in sorted(fields):
            for banned in sorted(forbidden.get(cell, ())):
                if field == banned or field.startswith(banned + "/"):
                    _error("profile_required_forbidden_conflict", field, (p.key for p in chain))
    for family in rules:
        for rule in rules[family]:
            rule["severity"] = overrides.get(rule["rule_id"], rule["severity"])
            floor = minima.get(rule["rule_id"])
            if floor is not None and levels[rule["severity"]] < levels[floor]:
                _error("profile_core_severity_lowered", "/" + family, (p.key for p in chain), rule["rule_id"])
    # A value is re-read from its canonical scalar/container form, not the first
    # profile's original number spelling. This keeps equivalent sets identical.
    return {"required_fields": _field_rows(required), "forbidden_fields": _field_rows(forbidden),
            "allowed_values": [{"artifact_types": [kind], "maturities": [maturity],
                                "field": field, "values": [json.loads(v) for v in sorted(values)]}
                               for (kind, maturity, field), values in sorted(allowed.items())],
            **rules, "rule_bindings": rule_bindings, "severity_overrides": overrides,
            "minimum_severities": minima, "hard_limits": hard_limits, "normative_policy": normative_policy}


@dataclass(frozen=True, init=False)
class EffectiveProfile:
    """Own the entire materialized composition; never certify a model or author."""
    _encoded: bytes
    selection_source: str

    def __init__(self, *args, **kwargs):
        raise TypeError("Use compose_profiles with explicit resources")

    @classmethod
    def _create(cls, value, source):
        result = object.__new__(cls)
        object.__setattr__(result, "_encoded", canonical_json_bytes(value))
        object.__setattr__(result, "selection_source", source)
        return result

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def canonical_bytes(self):
        return self._encoded

    @property
    def sha256(self):
        return sha256(self._encoded).hexdigest()

    @property
    def profile_chain(self):
        return tuple(p["profile_id"] + "@" + p["version"] for p in self.data["profiles"])

    def binding(self):
        return {"composition_version": COMPOSITION_VERSION, "sha256": self.sha256,
                "hash_algorithm": "jcs-sha256"}

    def minimum_relation_rules(self):
        return tuple(MinimumRelationRule(**{k: v for k, v in r.items() if k != "version"})
                     for r in self.data["merge"]["relation_rules"])

    def severity_for(self, rule_id, default):
        if type(rule_id) is not str or type(default) is not str or default not in ("error", "warning", "info"):
            _error("profile_severity_arguments_required")
        merged = self.data["merge"]
        chosen = merged["severity_overrides"].get(rule_id, default)
        levels = {"info": 0, "warning": 1, "error": 2}
        floor = merged["minimum_severities"].get(rule_id, "info")
        return max((chosen, floor), key=levels.get)



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
