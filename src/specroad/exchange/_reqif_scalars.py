"""Exact ReqIF lexical checks; independent of native number representation."""
import re

from ._reqif_values import _error

_INTEGER = re.compile(r"[+-]?[0-9]+\Z")
_REAL = re.compile(r"(?:[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?|INF|-INF|NaN)\Z")
_DATE = re.compile(r"(-?(?:[0-9]{4}|[1-9][0-9]{4,}))-([0-9]{2})-([0-9]{2})T"
                   r"([0-9]{2}):([0-9]{2}):([0-9]{2})(\.[0-9]+)?(Z|[+-][0-9]{2}:[0-9]{2})?\Z")
_START = "A-Za-z_\u00c0-\u00d6\u00d8-\u00f6\u00f8-\u02ff\u0370-\u037d\u037f-\u1fff\u200c-\u200d\u2070-\u218f\u2c00-\u2fef\u3001-\ud7ff\uf900-\ufdcf\ufdf0-\ufffd\U00010000-\U000effff"
_ID = re.compile("[" + _START + "][" + _START + "0-9.\u00b7\u0300-\u036f\u203f-\u2040-]*\\Z")


def _identifier(value):
    return type(value) is str and _ID.fullmatch(value) is not None


def _date(value, node):
    match = _DATE.fullmatch(value.strip(" \t\r\n"))
    if match is None:
        raise _error("reqif_invalid_datetime", node)
    # Gregorian leap years depend only on year modulo 400. No host integer
    # digit limit or datetime year range may truncate a valid XML year.
    year_text = match.group(1).lstrip("-")
    year = int(year_text[-4:])
    month, day, hour, minute, second = (int(v) for v in match.groups()[1:6])
    fraction, zone = match.groups()[6:]
    leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
    days = (31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
    if (not year_text.strip("0") or not 1 <= month <= 12 or not 1 <= day <= days[month - 1]
            or hour > 24 or minute > 59 or second > 59
            or (hour == 24 and (minute or second or (fraction and set(fraction[1:]) != {"0"})))):
        raise _error("reqif_invalid_datetime", node)
    if zone and zone != "Z":
        hours, minutes = int(zone[1:3]), int(zone[4:6])
        if hours > 14 or minutes > 59 or (hours == 14 and minutes):
            raise _error("reqif_invalid_datetime", node)
    return value


def _boolean(value, node):
    token = value.strip(" \t\r\n")
    if token not in ("true", "false", "1", "0"):
        raise _error("reqif_invalid_boolean", node)
    return token in ("true", "1")


def _number(value, family, node):
    token = value.strip(" \t\r\n")
    if not (_INTEGER if family == "INTEGER" else _REAL).fullmatch(token):
        raise _error("reqif_invalid_number", node)
    return token


def _shift_exponent(text, offset):
    """Add a small digit-count offset to an unbounded signed decimal exponent."""
    negative = text.startswith("-")
    digits = text.lstrip("+-").lstrip("0") or "0"
    if len(digits) <= 18:
        return str((-1 if negative else 1) * int(digits) + offset)
    # With longer exponents the sign cannot be changed by an input-size offset.
    carry = -offset if negative else offset
    result = []
    for digit in reversed(digits):
        carry, remainder = divmod(int(digit) + carry, 10)
        result.append(str(remainder))
    while carry:
        carry, remainder = divmod(carry, 10)
        result.append(str(remainder))
    return ("-" if negative else "") + ("".join(reversed(result)).lstrip("0") or "0")


def _signed_integer_compare(left, right):
    a, b = left.lstrip("-"), right.lstrip("-")
    if left.startswith("-") != right.startswith("-"):
        return -1 if left.startswith("-") else 1
    comparison = ((len(a), a) > (len(b), b)) - ((len(a), a) < (len(b), b))
    return -comparison if left.startswith("-") else comparison


def _numeric_parts(token):
    negative = token.startswith("-")
    mantissa, _, exponent = token.lstrip("+-").lower().partition("e")
    whole, _, fraction = mantissa.partition(".")
    digits = (whole + fraction).lstrip("0")
    if not digits:
        return 0, "0", "0"
    magnitude = _shift_exponent(exponent or "0", len(digits) - len(fraction))
    return -1 if negative else 1, magnitude, digits.rstrip("0")


def _compare_numbers(left, right):
    """Exact lexical range comparison without binary64/Decimal context limits."""
    if "NaN" in (left, right):
        return None
    if left == right:
        return 0
    if left == "-INF" or right == "INF":
        return -1
    if left == "INF" or right == "-INF":
        return 1
    ls, le, ld = _numeric_parts(left)
    rs, re, rd = _numeric_parts(right)
    if ls != rs:
        return (ls > rs) - (ls < rs)
    comparison = _signed_integer_compare(le, re)
    if not comparison:
        length = max(len(ld), len(rd))
        a, b = ld.ljust(length, "0"), rd.ljust(length, "0")
        comparison = (a > b) - (a < b)
    return ls * comparison
