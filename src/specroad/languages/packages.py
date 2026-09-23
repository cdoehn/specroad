"""Ordered, hash-bound language package composition on explicit resources.

No resource is discovered or fetched here. Package rules remain unexecuted.
Missing capabilities never become a passed language/semantics assessment.
"""
from dataclasses import dataclass
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.language_packages import LanguagePackage, LanguagePackageError, parse_package_key, range_matches
from ..model.language_literal_rules import parse_literal_rules
from ..model.language_tags import parse_language_tag
from ..storage.json_syntax import parse_json_object


@dataclass(frozen=True, init=False)
class LanguageComposition:
    _encoded: bytes

    def __init__(self):
        raise TypeError("Use compose_language_packages with explicit resources")

    @classmethod
    def _create(cls, value):
        obj = object.__new__(cls)
        object.__setattr__(obj, "_encoded", canonical_json_bytes(value))
        return obj

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def sha256(self):
        return canonical_json_sha256(self.data)

    def binding(self):
        return {"composition_version": "language-packages-v1", "sha256": self.sha256}


def compose_language_packages(language, *, activated, resources):
    """All Basic-Filtering matches in activation order, never first-match lookup."""
    tag = parse_language_tag(language)
    if type(activated) not in (list, tuple) or type(resources) not in (list, tuple):
        raise LanguagePackageError("package_sequence_required")
    for key in activated:
        parse_package_key(key)
    keys = tuple(dict.fromkeys(activated))
    index = {}
    for package in resources:
        if type(package) is not LanguagePackage:
            raise LanguagePackageError("typed_packages_required")
        checked = LanguagePackage(package.source_bytes)
        if checked.binding() != package.binding() or checked.capabilities != package.capabilities:
            raise LanguagePackageError("package_binding_mismatch")
        if checked.key in index and index[checked.key].sha256 != checked.sha256:
            raise LanguagePackageError("package_identity_conflict")
        index.setdefault(checked.key, checked)
    selected, absent, rules = [], [], {}
    for key in keys:
        if key not in index:
            absent.append(key)
            continue
        package = index[key]
        if not any(range_matches(r, language) for r in package.language_ranges):
            continue
        selected.append(package)
        for rule in parse_literal_rules(package.data["literal_rules"]):
            data = rule.data
            identity = data["policy_id"]
            prior = rules.get(identity)
            if prior is not None and (prior["version"], prior["sha256"]) != (data["version"], rule.sha256):
                raise LanguagePackageError("literal_rule_identity_conflict", pointer="/literal_rules")
            if prior is None:
                rules[identity] = {"rule_id": identity, "version": data["version"], "sha256": rule.sha256,
                    "definition": data, "packages": [package.key]}
            elif package.key not in prior["packages"]:
                prior["packages"].append(package.key)
    lint = "available" if rules else "not_available"
    diagnostics = []
    if absent or lint == "not_available":
        diagnostics.append({"code": "SRV182", "severity": "info", "reason": "language_checks_not_available",
                            "missing_packages": absent, "lint": lint})
    return LanguageComposition._create({"composition_version": "language-packages-v1",
        "language": tag.canonical, "activated": list(keys), "packages": [p.binding() for p in selected],
        "unavailable": absent, "literal_rules": list(rules.values()), "diagnostics": diagnostics,
        "capabilities": {"metadata": "available" if any("metadata" in p.capabilities for p in selected) else "not_available",
                         "labels": "available" if any("labels" in p.capabilities for p in selected) else "not_available",
                         "literal_lint": lint, "language_detection": "not_available", "modality": "not_available",
                         "contradiction": "not_available", "translation": "not_available"},
        "rules_executed": False, "lint_passed": None, "approval_granted": False,
        "validation_scope": "supplied_language_resources_only"})
