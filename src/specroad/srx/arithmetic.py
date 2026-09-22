"""Exact operations with an explicitly scoped numeric policy and error boundary."""
from decimal import Context, ROUND_HALF_EVEN, localcontext
from fractions import Fraction
from .errors import SrxError
from .numeric_errors import SrxNumericError
from .numeric_policy import NumericPolicy, SrxPolicyError
from .numeric_boundary import operand_decimal, result_number
from ._exact_decimal import finite_decimal

ARITHMETIC_OPERATORS = ("add", "subtract", "multiply", "divide")


def arithmetic_operation(op, left, right, *, policy, rule_id, pointer="/expression"):
    if type(op) is not str or op not in ARITHMETIC_OPERATORS:
        raise SrxError("unsupported_operator", rule_id=rule_id, pointer=pointer+"/op")
    if type(policy) is not NumericPolicy:
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
