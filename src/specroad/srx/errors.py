"""Structured SRX failures, separate from diagnostic projection and presentation."""
from .diagnostics import diagnostic_record


class SrxError(ValueError):
    """A rejected expression/context is not a Boolean false result."""

    def __init__(self, reason, *, rule_id, pointer="/expression",
                 expected="JSON", actual="invalid", subject="expression",
                 position=None, line=None, column=None):
        super().__init__("SRX input rejected: " + reason)
        self.reason = reason
        self.rule_id = rule_id
        self.pointer = pointer
        self.expected = expected
        self.actual = actual
        self.subject = subject
        self.code = "SRV110"
        self.position = position
        self.line = line
        self.column = column
        # Optional immutable observation of failed work, never a Boolean result.
        self.resource_usage = None

    def diagnostic(self):
        return diagnostic_record(code=self.code, reason=self.reason, rule_id=self.rule_id,
                                 pointer=self.pointer, expected=self.expected, actual=self.actual,
                                 subject=self.subject, position=self.position,
                                 line=self.line, column=self.column)
