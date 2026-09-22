"""Disjoint numeric diagnostics shared by SRX parsing and evaluation."""
from .errors import SrxError


class SrxNumericError(SrxError):
    def __init__(self, reason, *, rule_id, pointer="/expression", subject="expression", position=None, line=None, column=None):
        if reason not in ("division_by_zero", "non_finite", "precision_exceeded", "non_terminating", "jcs_roundtrip_loss"):
            raise ValueError("Unknown SRX numeric reason")
        super().__init__(reason, rule_id=rule_id, pointer=pointer,
                         expected="exact finite JCS number", actual="number", subject=subject,
                         position=position, line=line, column=column)
        self.code = "SRV197"


