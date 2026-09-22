"""Strict JCS input/output boundaries; never binary float expansions."""
from decimal import Decimal
import math
from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from .errors import SrxError
from .numeric_errors import SrxNumericError
from ._json_values import json_type


def operand_decimal(value, *, rule_id, pointer):
    # Check the exact built-in type before any conversion hooks may execute.
    if type(value) not in (int, float):
        from .types import MISSING
        raise SrxError("operand_type", rule_id=rule_id, pointer=pointer,
                       expected="number", actual="missing" if value is MISSING else json_type(value))
    if type(value) is float and not math.isfinite(value):
        raise SrxNumericError("non_finite", rule_id=rule_id, pointer=pointer)
    try:
        return Decimal(canonical_json_bytes(value).decode("ascii"))
    except ModelError:
        raise SrxNumericError("jcs_roundtrip_loss", rule_id=rule_id, pointer=pointer) from None


def result_number(value, decimal, *, rule_id, pointer):
    candidate = float(decimal)
    if not math.isfinite(candidate):
        raise SrxNumericError("jcs_roundtrip_loss", rule_id=rule_id, pointer=pointer)
    if Decimal(canonical_json_bytes(candidate).decode("ascii")) != decimal:
        raise SrxNumericError("jcs_roundtrip_loss", rule_id=rule_id, pointer=pointer)
    return value.numerator if value.denominator == 1 else candidate


