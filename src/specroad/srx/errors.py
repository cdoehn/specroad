"""Structured SRX failures, separate from human-readable presentation."""


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
        return {"code": self.code, "reason": self.reason,
                "rule_id": self.rule_id,
                "expression_pointer": self.pointer if self.subject == "expression" else "/expression",
                "input_pointer": self.pointer, "subject": self.subject,
                "position": self.position, "line": self.line, "column": self.column,
                "expected_type": self.expected, "actual_type": self.actual,
                "diagnostic_version": 1,
                "repair_action": _repair(self.code, self.reason)[0],
                "recommendation": _repair(self.code, self.reason)[1]}


# Hints are static data: no operand values, automatic repair, I/O or conversion.
_REPAIRS = {
    "invalid_pointer_escape": ("correct_json_pointer", "Use a static RFC-6901 pointer with only ~0 and ~1 escape sequences."),
    "invalid_array_index": ("correct_array_index", "Use an explicitly valid array index; an invalid address is not a missing field."),
    "duplicate_key": ("remove_duplicate_key", "Provide unambiguous JSON object keys without duplicate entries."),
    "invalid_json": ("correct_json_document", "Provide one strict UTF-8 JSON object without comments or trailing data."),
    "trailing_data": ("correct_json_document", "Provide exactly one JSON document; remove trailing data without altering intended values."),
    "unsupported_version": ("select_supported_version", "Use an explicitly supported SRX language version; do not reinterpret an incompatible program."),
    "unsupported_language": ("select_supported_language", "Declare the supported SRX language explicitly."),
    "unsupported_operator": ("replace_unsupported_operator", "Replace the operator with a supported declarative operation; do not execute code from data."),
    "operand_type": ("supply_declared_type", "Supply an operand of the declared type; missing and null are distinct and no implicit conversion is performed."),
    "operand_types": ("supply_compatible_types", "Compare compatible SRX types without implicit Boolean, numeric or string conversion."),
    "invalid_fields": ("correct_expression_fields", "Provide exactly the fields required by this expression or context contract."),
    "binary_arity": ("correct_operand_count", "Provide exactly two expression operands in their declared order."),
    "division_by_zero": ("supply_nonzero_divisor", "Supply a nonzero divisor or explicitly guard this operation; do not substitute a fabricated result."),
    "non_finite": ("supply_finite_number", "Supply a finite numeric operand; NaN and infinities are not SRX JSON values."),
    "precision_exceeded": ("review_project_precision", "Review the exact result and the explicit project precision policy; never silently round or change the policy."),
    "non_terminating": ("use_exact_numeric_contract", "Use an exact supported representation or an explicitly string-based contract; increasing precision cannot make this quotient terminate."),
    "jcs_roundtrip_loss": ("use_exact_numeric_contract", "Use a representation permitted by the numeric contract; never silently round at the JCS boundary."),
    "invalid_numeric_policy": ("correct_project_policy", "Supply the supported numeric policy version and an integer precision from 1 through 1000."),
}


def _repair(code, reason):
    if reason in _REPAIRS:
        return _REPAIRS[reason]
    if code == "SRV111":
        return ("review_structure_policy", "Reduce expression structure or explicitly review its hard policy; increasing a soft work target is not a repair.")
    return ("check_explicit_input", "Check the indicated input against the explicit SRX 1.0 contract; no automatic repair is performed.")
