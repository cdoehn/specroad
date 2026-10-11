"""Closed, ordered merge strategy table for the versioned profile contract.

Each invocation owns all state. Strategy names are fixed trusted code, never
callbacks or attribute names supplied by a profile document.
"""
import json
from types import MappingProxyType
from ..model.artifact_schemas import MATURITIES
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from .composition_values import _error

# Chapter 13: structural, integrity, identity, recorded-evidence, transaction,
# execution-authority and path failures cannot be downgraded. Semantic review
# findings (e.g. SRV033/SRV050) remain configurable. SRV027 is protected because
# its code includes structural failures, not only review_outcome findings.
from ..diagnostics.catalog import CORE_MINIMUM_SEVERITIES



# Order also fixes which conflict is reported first, preserving the W/R contract.
MERGE_STRATEGIES = (
    ("hard_limits", "minimum"),
    ("normative_policy", "equal"),
    ("required_fields", "scoped_union"),
    ("forbidden_fields", "scoped_union"),
    ("allowed_values", "scoped_intersection"),
    ("relation_rules", "ordered_rule_identity"),
    ("lint_rules", "ordered_rule_identity"),
    ("severity_overrides", "later_wins_with_floor"),
    ("relation_review_policy", "scoped_review_severity"),
)
SEVERITY_RANK = {"info": 0, "warning": 1, "error": 2}

def _cells(entry):
    for kind in sorted(entry["artifact_types"]):
        for maturity in sorted(entry["maturities"] or MATURITIES):
            yield kind, maturity


def _field_rows(values):
    return [{"artifact_types": [kind], "maturities": [maturity], "fields": sorted(fields)}
            for (kind, maturity), fields in sorted(values.items())]



class _MergeProjection:
    """One composition's accumulator, never a global or reusable mutable cache."""
    def __init__(self, chain):
        self.chain = chain
        self.unions = {"required_fields": {}, "forbidden_fields": {}}
        self.allowed = {}
        self.rules = {"relation_rules": [], "lint_rules": []}
        self.seen_rules, self.rule_bindings, self.overrides = {}, [], {}
        self.hard_limits, self.normative_policy = {}, {}
        self.review_severities = {}
        self.minima = dict(CORE_MINIMUM_SEVERITIES)
        core_data = chain[0].data
        for family in self.rules:
            for rule in core_data[family]:
                self.minima[rule["rule_id"]] = max((self.minima.get(rule["rule_id"], "info"),
                                                   rule["severity"]), key=SEVERITY_RANK.get)

    def apply(self, profile):
        data = profile.data
        handlers = {
            "minimum": self._minimum, "equal": self._equal,
            "scoped_union": self._union, "scoped_intersection": self._intersection,
            "ordered_rule_identity": self._rules,
            "later_wins_with_floor": self._overrides,
            "scoped_review_severity": self._review_policy,
        }
        for group, strategy in MERGE_STRATEGIES:
            handlers[strategy](group, data.get(group, {}), profile.key)

    def _minimum(self, group, entries, profile):
        for name, limit in entries.items():
            self.hard_limits[name] = min(self.hard_limits.get(name, limit), limit)

    def _equal(self, group, entries, profile):
        for name, scalar in entries.items():
            if name in self.normative_policy and canonical_json_bytes(self.normative_policy[name]) != canonical_json_bytes(scalar):
                _error("profile_scalar_policy_conflict", "/normative_policy/" + name,
                       (p.key for p in self.chain))
            self.normative_policy[name] = scalar

    def _union(self, group, entries, profile):
        merged = self.unions[group]
        for entry in entries:
            for cell in _cells(entry):
                merged.setdefault(cell, set()).update(entry["fields"])

    def _intersection(self, group, entries, profile):
        for entry in entries:
            candidates = {canonical_json_bytes(v) for v in entry["values"]}
            for cell in _cells(entry):
                key = (*cell, entry["field"])
                self.allowed[key] = candidates if key not in self.allowed else self.allowed[key] & candidates
                if not self.allowed[key]:
                    _error("profile_empty_intersection", entry["field"], (p.key for p in self.chain))

    def _rules(self, family, entries, profile):
        for rule in entries:
            identity = rule["rule_id"]
            binding = (family, rule["version"], canonical_json_sha256(rule))
            if identity in self.seen_rules:
                if self.seen_rules[identity] != binding:
                    _error("profile_rule_conflict", "/" + family, (p.key for p in self.chain), identity)
                continue
            self.seen_rules[identity] = binding
            self.rules[family].append(rule)
            self.rule_bindings.append({"family": family, "rule_id": identity,
                                       "version": binding[1], "sha256": binding[2]})

    def _overrides(self, group, entries, profile):
        for identity, severity in entries.items():
            if identity in self.minima and SEVERITY_RANK[severity] < SEVERITY_RANK[self.minima[identity]]:
                _error("profile_core_severity_lowered", "/severity_overrides/" + identity, (profile,), identity)
            self.overrides[identity] = severity
            status = {"SRV025": "unreviewed", "SRV026": "suspect"}.get(identity)
            for cell in self.review_severities:
                if cell[2] == status:
                    self.review_severities[cell] = severity

    def _review_policy(self, group, entries, profile):
        # Later profiles win. In the same profile scoped cells are more specific
        # than its global code override, which has already been applied.
        for entry in entries:
            for kind in entry["relation_types"]:
                for maturity in entry["maturities"] or MATURITIES:
                    self.review_severities[(kind, maturity, entry["status"])] = entry["severity"]

    def finish(self):
        for cell, fields in self.unions["required_fields"].items():
            for field in sorted(fields):
                for banned in sorted(self.unions["forbidden_fields"].get(cell, ())):
                    if field == banned or field.startswith(banned + "/"):
                        _error("profile_required_forbidden_conflict", field, (p.key for p in self.chain))
        for family in self.rules:
            for rule in self.rules[family]:
                rule["severity"] = self.overrides.get(rule["rule_id"], rule["severity"])
                floor = self.minima.get(rule["rule_id"])
                if floor is not None and SEVERITY_RANK[rule["severity"]] < SEVERITY_RANK[floor]:
                    _error("profile_core_severity_lowered", "/" + family, (p.key for p in self.chain), rule["rule_id"])
        result = {
            **{group: _field_rows(fields) for group, fields in self.unions.items()},
            "allowed_values": [{"artifact_types": [kind], "maturities": [maturity],
                                "field": field, "values": [json.loads(v) for v in sorted(values)]}
                               for (kind, maturity, field), values in sorted(self.allowed.items())],
            **self.rules, "rule_bindings": self.rule_bindings,
            "severity_overrides": self.overrides, "minimum_severities": self.minima,
            "hard_limits": self.hard_limits, "normative_policy": self.normative_policy,
        }
        if self.review_severities:
            result["relation_review_policy"] = [
                {"relation_type": kind, "maturity": maturity, "status": status, "severity": severity}
                for (kind, maturity, status), severity in sorted(self.review_severities.items())]
        return result


def _merge(chain):
    accumulator = _MergeProjection(chain)
    for profile in chain:
        accumulator.apply(profile)
    return accumulator.finish()
