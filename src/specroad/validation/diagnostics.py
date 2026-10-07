"""Projection of observed pipeline findings; no new checks, I/O or approval.

The original source report is retained alongside normalized diagnostics. Detailed
producer-specific fields are not lost or mistaken for verified provenance.
"""
from dataclasses import dataclass
from hashlib import sha256

from ..diagnostics import Diagnostic, assess_diagnostics, from_model_error
from ..model.errors import ModelError
from ..result_contract import ResultContractError
from .values import ModelDocument, ValidationReport

_REASON_CODES = {
    "invalid_json": "SRV001", "invalid_utf8": "SRV001", "duplicate_key": "SRV001",
    "invalid_unicode": "SRV001", "object_required": "SRV001",
    "unsupported_schema_version": "SRV003", "duplicate_artifact_id": "SRV010",
    "duplicate_relation_id": "SRV013", "missing_relation_target": "SRV020",
    "validation_field_target_missing": "SRV020", "relation_type_pair_forbidden": "SRV021",
    "self_relation_forbidden": "SRV021", "validation_field_target_type": "SRV021",
    "hierarchy_cycle": "SRV022", "relation_hierarchy_cycle": "SRV022", "duplicate_external_relation_identity": "SRV147",
    "validation_selected_id_missing": "SRV140",
    "validation_required_gate_unavailable": "VALIDATION_UNAVAILABLE",
    "validation_profile_unavailable": "VALIDATION_UNAVAILABLE",
}
_STRUCTURAL = {"parsing", "schema_types_identity_fields", "identities_references", "graph", "scope"}


@dataclass(frozen=True, init=False)
class ValidationAssessment:
    report: ValidationReport
    assessment: object

    def __init__(self, *args, **kwargs):
        raise TypeError("Use assess_validation to bind a real report")

    @classmethod
    def _create(cls, report, assessment):
        result = object.__new__(cls)
        object.__setattr__(result, "report", report)
        object.__setattr__(result, "assessment", assessment)
        return result

    @property
    def passed(self):
        return self.assessment.passed

    @property
    def exit_code(self):
        return self.assessment.exit_code

    @property
    def diagnostics(self):
        return self.assessment.diagnostics

    @property
    def summary(self):
        return self.assessment.summary

    def as_dict(self):
        return {**self.assessment.as_dict(), "input_sha256": self.report.data["input_sha256"],
                "validation_scope": self.report.data["validation_scope"],
                "source_report": self.report.data, "optional_lint_started": False}

    def __bool__(self):
        raise TypeError("Use assessment.passed explicitly")


def assess_validation(report, *, fail_on="error", strict=False, documents=None):
    """Normalize all emitted findings. Unavailable/blocked phases stay incomplete.

    This does not run optional lint or analyzers. Strict changes the fail threshold
    on supplied observations; callers must provide any required extra lint gate.
    Explicit source bytes, when provided, must match the report's source bindings.
    """
    if type(report) is not ValidationReport:
        raise ResultContractError("Expected an actual validation report")
    data = report.data
    sources = {}
    if documents is not None:
        if type(documents) not in (tuple, list) or any(type(d) is not ModelDocument for d in documents):
            raise ResultContractError("Expected model documents")
        if len({d.path for d in documents}) != len(documents):
            raise ResultContractError("Duplicate source label")
        bindings = sorted(({"path": d.path, "sha256": sha256(d.content).hexdigest()} for d in documents), key=lambda v:v["path"])
        if bindings != data["source_bindings"]:
            raise ResultContractError("Diagnostic source bytes do not match the checked model")
        sources = {d.path: d.content for d in documents}
    source_ids = {v["path"]: v["artifact_id"] for v in data["identified_sources"]}
    diagnostics = []
    for stage in data["stages"]:
        for item in stage["diagnostics"]:
            reason = item["reason"]
            code = item.get("code", _REASON_CODES.get(reason,
                "SRV002" if stage["stage"] == "schema_types_identity_fields" else "MODEL_VALIDATION"))
            origin = item.get("origin", "profile_rule" if stage["stage"] == "profiles" else "core_rule")
            path = item.get("path")
            location = item.get("location")
            if location is None:
                error = ModelError(reason, path=path, pointer=item.get("pointer"),
                    position=item.get("position"), line=item.get("line"), column=item.get("column"))
                location = from_model_error(error, source=sources.get(path), code=code).location
            diagnostics.append(Diagnostic(code, item.get("severity", "error"),
                item.get("category", "parse" if stage["stage"] == "parsing" else "model"),
                item.get("message", "Model validation reported a finding."), origin=origin,
                rule_id=item.get("rule_id"), artifact_id=item.get("artifact_id") or source_ids.get(path), path=path,
                location=location, rationale=item.get("rationale", reason),
                remediation=item.get("remediation"), related_ids=item.get("related_ids", (*item.get("artifact_ids", ()),
                    *item.get("relation_ids", ())))))
    failure = 3 if any(s["stage"] in _STRUCTURAL and s["status"] == "failed" for s in data["stages"]) else None
    if any(s["stage"] in ("profile_lint", "language_policy") and
           any(d.get("code") in ("SRV110", "SRV111", "SRV177", "SRV197") for d in s["diagnostics"])
           for s in data["stages"]):
        failure = 3  # Invalid executable data/structure is not a false policy predicate.
    if any(item["reason"] in ("validation_gate_check_failed", "validation_gate_discovery_failed")
           for stage in data["stages"] for item in stage["diagnostics"]):
        failure = 4
    assessment = assess_diagnostics(diagnostics, checked_ids=data["identified_ids"],
        complete=data["checks_complete"], fail_on=fail_on, strict=strict, operational_exit_code=failure)
    return ValidationAssessment._create(report, assessment)


# Preserve the earlier import path while keeping presentation separate.
from .result_adapter import validation_command_result
