"""Explicit immutable SRX numeric policy, independent of process defaults."""
from dataclasses import dataclass
from .errors import SrxError


class SrxPolicyError(SrxError):
    def __init__(self, *, rule_id, pointer):
        super().__init__("invalid_numeric_policy", rule_id=rule_id, pointer=pointer,
                         expected="srx-decimal-v1, precision 1..1000", actual="invalid_policy", subject="context")
        self.exit_code = 2

    def diagnostic(self):
        return {**super().diagnostic(), "exit_code": self.exit_code}


@dataclass(frozen=True)
class NumericPolicy:
    decimal_precision: int = 34
    numeric_policy_version: str = "srx-decimal-v1"

    def __post_init__(self):
        if (type(self.decimal_precision) is not int or not 1 <= self.decimal_precision <= 1000
                or type(self.numeric_policy_version) is not str or self.numeric_policy_version != "srx-decimal-v1"):
            raise SrxPolicyError(rule_id=None, pointer="/project/srx_policy")

    @property
    def data(self):
        return {"numeric_policy_version": self.numeric_policy_version,
                "decimal_precision": self.decimal_precision}

    @classmethod
    def from_project(cls, project, *, rule_id):
        if type(project) is not dict:
            raise SrxPolicyError(rule_id=rule_id, pointer="/project")
        raw = project.get("srx_policy", {})
        if type(raw) is not dict or set(raw) - {"decimal_precision", "numeric_policy_version"}:
            raise SrxPolicyError(rule_id=rule_id, pointer="/project/srx_policy")
        digits = raw.get("decimal_precision", 34)
        version = raw.get("numeric_policy_version", "srx-decimal-v1")
        if type(digits) is not int or not 1 <= digits <= 1000:
            raise SrxPolicyError(rule_id=rule_id, pointer="/project/srx_policy/decimal_precision")
        if type(version) is not str or version != "srx-decimal-v1":
            raise SrxPolicyError(rule_id=rule_id, pointer="/project/srx_policy/numeric_policy_version")
        return cls(digits, version)
