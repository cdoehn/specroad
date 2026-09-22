"""Exact reduced rational to decimal conversion; independent of JCS transport."""
from decimal import Decimal
from .numeric_errors import SrxNumericError


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


