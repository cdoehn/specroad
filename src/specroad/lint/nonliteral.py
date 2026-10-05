"""Read-only rationale and minimum-relation observations over supplied sources.

This is a Core lint scope, not full schema/model, review or language validation.
Complete source membership and profile selection belong to the caller.
"""
from hashlib import sha256

from ..graph.relations import SourceRelations
from ..graph.relation_obligations import RelationObligations
from ..model._schema import validate_builtin
from ..model.domain_fields import approved_required_fields
from ..model.domain_schemas import DOMAIN_TYPES, domain_schema
from ..model.record_schemas import record_schema
from ..model.errors import ModelError
from ..profiles.composition_values import EffectiveProfile


def lint_core(sources, *, selected_ids=None, profile=None, fail_on="error", strict=False):
    """Reuse current maturity/field and minimum rules without granting approval.

    All supplied references must resolve before their minima can be counted.
    A profile is an explicit composed value, never discovered executable code.
    Literal checks remain in lint_literals; neither API claims semantic language
    understanding or evidence/review freshness.
    """
    if type(sources) not in (tuple, list) or any(type(s) is not SourceRelations for s in sources):
        raise ModelError("core_lint_sources_required")
    if profile is not None and type(profile) is not EffectiveProfile:
        raise ModelError("core_lint_effective_profile_required")
    if type(fail_on) is not str or fail_on not in ("error", "warning") or type(strict) is not bool:
        raise ModelError("core_lint_fail_policy_invalid")
    if any(s.path is not None and (type(s.path) is not str or not s.path) for s in sources):
        raise ModelError("core_lint_source_path_required")
    paths = [s.path for s in sources if s.path is not None]
    if len(paths) != len(set(paths)):
        raise ModelError("core_lint_duplicate_source_path")
    records = tuple(SourceRelations(s.source_bytes, path=s.path) for s in sources)
    rules = () if profile is None else profile.minimum_relation_rules()
    obligations = RelationObligations(records, profile_rules=rules)
    index = {r.identity.id: r for r in records}
    if selected_ids is None:
        selected = tuple(sorted(index))
    else:
        if (type(selected_ids) not in (tuple, list) or not selected_ids
                or any(type(i) is not str or not i for i in selected_ids)
                or len(set(selected_ids)) != len(selected_ids)):
            raise ModelError("core_lint_selection_required")
        selected = tuple(sorted(selected_ids))
        if any(i not in index for i in selected):
            raise ModelError("core_lint_selected_id_missing")
    diagnostics = []
    for identity in selected:
        source = index[identity]
        value = source.data
        kind = value["artifact_type"]
        schema = (domain_schema if kind in DOMAIN_TYPES else record_schema)(kind, value["schema_version"])
        if "rationale" not in schema["properties"]:
            continue
        reason = None
        required = ("rationale" in schema["required"] or
                    (value["maturity"] == "approved" and "rationale" in approved_required_fields(kind)))
        if "rationale" not in value:
            if required:
                reason = "missing_rationale"
        else:
            try:
                validate_builtin(value["rationale"],
                    {"$defs": schema["$defs"], **schema["properties"]["rationale"]})
            except ModelError:
                reason = "invalid_rationale"
        if reason is not None:
            diagnostics.append({"code": "SRV002", "severity": "error", "reason": reason,
                "origin": "core_rule", "rule_id": "core:" + kind + "-rationale",
                "artifact_id": identity, "path": source.path, "pointer": "/rationale"})
    for check in obligations.checks:
        if check.artifact_id not in selected or check.satisfied:
            continue
        code = {"core:requirement-origin": "SRV031",
                "core:requirement-verification": "SRV032"}.get(check.rule_id, "SRV023")
        severity = check.severity
        if profile is not None and not check.rule_id.startswith("core:"):
            severity = profile.severity_for(check.rule_id, severity)
        diagnostics.append({**check.diagnostic(), "code": code, "severity": severity,
            "origin": "core_rule" if check.rule_id.startswith("core:") else "profile_rule",
            "path": index[check.artifact_id].path, "pointer": "/relations"})
    diagnostics.sort(key=lambda d: ({"error": 0, "warning": 1, "info": 2}[d["severity"]],
        d["path"] or "", d["artifact_id"], d["pointer"], d["code"], d["rule_id"]))
    threshold = "warning" if strict else fail_on
    failed = any(d["severity"] == "error" or
                 (d["severity"] == "warning" and threshold == "warning") for d in diagnostics)
    return {"format_version": 1, "validation_scope": "selected_core_lint_over_supplied_records",
        "checked_ids": list(selected), "checks_complete": True,
        "core_checks_passed": not failed, "diagnostics": diagnostics,
        "failure_threshold": threshold,
        "source_bindings": [{"artifact_id": r.identity.id, "path": r.path,
                             "sha256": sha256(r.source_bytes).hexdigest()}
                            for r in sorted(records, key=lambda r: r.identity.id)],
        "profile_binding": None if profile is None else profile.binding(),
        "profile_minima_checked": profile is not None, "full_profile_checked": False,
        "minimum_relations_input_sha256": obligations.input_sha256,
        "minimum_relations_policy_sha256": obligations.policy_sha256,
        "full_schema_checked": False, "review_status_checked": False,
        "language_detection_performed": False, "project_complete": False,
        "approval_granted": False, "write_authorized": False}
