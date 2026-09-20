"""Structured SRX failures, separate from human-readable presentation."""


class SrxError(ValueError):
    """A rejected expression/context is not a Boolean false result."""

    def __init__(self, reason, *, rule_id, pointer="/expression",
                 expected="JSON", actual="invalid", subject="expression"):
        super().__init__("SRX input rejected: " + reason)
        self.reason = reason
        self.rule_id = rule_id
        self.pointer = pointer
        self.expected = expected
        self.actual = actual
        self.subject = subject
        self.code = "SRV110"

    def diagnostic(self):
        return {"code": self.code, "reason": self.reason,
                "rule_id": self.rule_id,
                "expression_pointer": self.pointer if self.subject == "expression" else "/expression",
                "input_pointer": self.pointer, "subject": self.subject,
                "expected_type": self.expected, "actual_type": self.actual,
                "recommendation": "Supply an explicit supported SRX 1.0 expression and JSON-only context."}
