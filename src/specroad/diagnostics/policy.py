"""Fail thresholds and completeness decisions never alter observed severities."""
from dataclasses import dataclass
from ..result_contract import ResultContractError
from .values import Diagnostic, SEVERITIES, _text
from .ordering import diagnostic_key

@dataclass(frozen=True)
class FailPolicy:
    fail_on: str = "error"
    strict: bool = False

    def __post_init__(self):
        if type(self.fail_on) is not str or self.fail_on not in ("error", "warning"):
            raise ResultContractError("Unsupported fail threshold")
        if type(self.strict) is not bool:
            raise ResultContractError("Strict must be a boolean")

    @property
    def threshold(self):
        return "warning" if self.strict else self.fail_on

    def reached(self, diagnostics):
        if type(diagnostics) not in (tuple, list) or any(type(d) is not Diagnostic for d in diagnostics):
            raise ResultContractError("Expected complete typed diagnostic sequence")
        return any(d.severity == "error" or (self.threshold == "warning" and d.severity == "warning")
                   for d in diagnostics)


@dataclass(frozen=True)
class DiagnosticAssessment:
    diagnostics: tuple
    checked_ids: tuple
    complete: bool
    policy: FailPolicy
    operational_exit_code: int | None = None

    def __post_init__(self):
        if type(self.diagnostics) not in (tuple, list) or any(type(d) is not Diagnostic for d in self.diagnostics):
            raise ResultContractError("Expected typed diagnostic sequence")
        if type(self.checked_ids) not in (tuple, list):
            raise ResultContractError("Expected explicit checked IDs")
        for key in self.checked_ids:
            _text(key, "checked artifact ID")
        if type(self.complete) is not bool or type(self.policy) is not FailPolicy:
            raise ResultContractError("Explicit completion and policy required")
        if self.operational_exit_code is not None and (type(self.operational_exit_code) is not int or
                self.operational_exit_code not in range(2, 8)):
            raise ResultContractError("Invalid independent operation failure")
        object.__setattr__(self, "diagnostics", tuple(sorted(self.diagnostics, key=diagnostic_key)))
        object.__setattr__(self, "checked_ids", tuple(sorted(set(self.checked_ids))))

    def __bool__(self):
        raise TypeError("Use assessment.passed explicitly")

    @property
    def exit_code(self):
        if self.operational_exit_code is not None:
            return self.operational_exit_code
        if not self.complete:
            return 5  # unavailable check, NOT a fabricated resumable-work exit 8
        return 1 if self.policy.reached(self.diagnostics) else 0

    @property
    def passed(self):
        return self.exit_code == 0

    @property
    def summary(self):
        return {"checked_artifacts": len(self.checked_ids), "diagnostic_count": len(self.diagnostics),
                "diagnostics_by_severity": {s: sum(d.severity == s for d in self.diagnostics) for s in SEVERITIES}}

    def as_dict(self):
        return {"diagnostic_format_version": 1, "diagnostics": [d.as_dict() for d in self.diagnostics],
                "checked_ids": list(self.checked_ids), "summary": self.summary,
                "checks_complete": self.complete, "status": "success" if self.passed else "failed",
                "exit_code": self.exit_code, "fail_on": self.policy.threshold,
                "strict_requested": self.policy.strict, "approval_granted": False,
                "write_authorized": False}


def assess_diagnostics(diagnostics, *, checked_ids=(), complete=True, fail_on="error", strict=False,
                       operational_exit_code=None):
    return DiagnosticAssessment(diagnostics, checked_ids, complete, FailPolicy(fail_on, strict), operational_exit_code)

