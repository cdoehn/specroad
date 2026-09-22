"""Exact rational operations on JCS decimal spellings, not binary expansions."""
from decimal import Context, Decimal, ROUND_HALF_EVEN, localcontext
from fractions import Fraction
import math
from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from .errors import SrxError
from .numeric_policy import NumericPolicy
from ._json_values import json_type

ARITHMETIC_OPERATORS = ("add", "subtract", "multiply", "divide")


class SrxNumericError(SrxError):
    def __init__(self, reason, *, rule_id, pointer="/expression", subject="expression"):
        if reason not in ("division_by_zero", "non_finite", "precision_exceeded", "non_terminating", "jcs_roundtrip_loss"):
            raise ValueError("Unknown SRX numeric reason")
        super().__init__(reason, rule_id=rule_id, pointer=pointer,
                         expected="exact finite JCS number", actual="number", subject=subject)
        self.code = "SRV197"


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


def finite_decimal(value, *, rule_id, pointer):
    """Reduce denominator first; an exact decimal has only factors 2 and 5."""
    denominator = value.denominator
    twos = fives = 0
    while denominator % 2 == 0:
        denominator //= 2
        twos += 1
    while denominator % 5 == 0:
        denominator //= 5
        fives += 1
    if denominator != 1:
        raise SrxNumericError("non_terminating", rule_id=rule_id, pointer=pointer)
    if value.numerator == 0:
        return Decimal(0), 1
    scale = max(twos, fives)
    coefficient = abs(value.numerator) * 2 ** (scale-twos) * 5 ** (scale-fives)
    exponent = -scale
    while coefficient % 10 == 0:
        coefficient //= 10
        exponent += 1
    digits = tuple(int(c) for c in str(coefficient))
    return Decimal((int(value.numerator < 0), digits, exponent)), len(digits)


def result_number(value, decimal, *, rule_id, pointer):
    candidate = float(decimal)
    if not math.isfinite(candidate):
        raise SrxNumericError("jcs_roundtrip_loss", rule_id=rule_id, pointer=pointer)
    if Decimal(canonical_json_bytes(candidate).decode("ascii")) != decimal:
        raise SrxNumericError("jcs_roundtrip_loss", rule_id=rule_id, pointer=pointer)
    return value.numerator if value.denominator == 1 else candidate


def arithmetic_operation(op, left, right, *, policy, rule_id, pointer="/expression"):
    if type(op) is not str or op not in ARITHMETIC_OPERATORS:
        raise SrxError("unsupported_operator", rule_id=rule_id, pointer=pointer+"/op")
    if type(policy) is not NumericPolicy:
        from .numeric_policy import SrxPolicyError
        raise SrxPolicyError(rule_id=rule_id, pointer="/project/srx_policy")
    # Explicit local context; even DefaultContext/flags/traps changed by callers
    # cannot affect a result. Exact Fraction arithmetic never rounds to this prec.
    context = Context(prec=policy.decimal_precision, rounding=ROUND_HALF_EVEN,
                      Emin=-999999, Emax=999999, capitals=1, clamp=0, flags=[], traps=[])
    with localcontext(context):
        a = Fraction(operand_decimal(left, rule_id=rule_id, pointer=pointer+"/args/0"))
        b = Fraction(operand_decimal(right, rule_id=rule_id, pointer=pointer+"/args/1"))
        if op == "add":
            value = a + b
        elif op == "subtract":
            value = a - b
        elif op == "multiply":
            value = a * b
        else:
            if b == 0:
                raise SrxNumericError("division_by_zero", rule_id=rule_id, pointer=pointer)
            value = a / b
        decimal, digits = finite_decimal(value, rule_id=rule_id, pointer=pointer)
        if digits > policy.decimal_precision:
            raise SrxNumericError("precision_exceeded", rule_id=rule_id, pointer=pointer)
        return result_number(value, decimal, rule_id=rule_id, pointer=pointer)
