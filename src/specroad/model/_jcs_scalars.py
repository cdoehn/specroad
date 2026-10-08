"""RFC-8785 scalar encoding; independent of human formatting and storage."""

from decimal import Decimal
from codecs import utf_16_be_encode
import json
import math

from .errors import ModelError


def _number(value, pointer):
    """Shortest binary64 significand with ECMAScript decimal placement.

CPython repr supplies shortest, nearest, ties-to-even roundtrip digits. RFC
8785 section 3.2.2.3 requires ECMAScript's notation thresholds instead of
Python's; no float formatting precision or Decimal arithmetic is applied.
Python integers must preserve their mathematical decimal value on that
roundtrip, exactly as required by SpecRoad's JSON input contract.
    """
    try:
        number = float(value)
    except (OverflowError, ValueError) as error:
        raise ModelError("nonfinite_number", pointer=pointer) from error
    if not math.isfinite(number):
        raise ModelError("nonfinite_number", pointer=pointer)
    if type(value) is int and Decimal(str(number)) != Decimal(value):
        raise ModelError("number_roundtrip_loss", pointer=pointer)
    if number == 0:
        return "0"
    negative = number < 0
    mantissa, _, exponent = repr(abs(number)).partition("e")
    whole, _, fraction = mantissa.partition(".")
    digits = whole + fraction
    point = len(whole) + (int(exponent) if exponent else 0)
    leading = len(digits) - len(digits.lstrip("0"))
    digits = digits.lstrip("0").rstrip("0")
    point -= leading
    if 0 < point <= 21:
        if point >= len(digits):
            result = digits + "0" * (point - len(digits))
        else:
            result = digits[:point] + "." + digits[point:]
    elif -6 < point <= 0:
        result = "0." + "0" * (-point) + digits
    else:
        result = digits[0] + (("." + digits[1:]) if len(digits) > 1 else "")
        result += "e" + ("+" if point - 1 >= 0 else "-") + str(abs(point - 1))
    return ("-" if negative else "") + result


def _string(value, pointer):
    try:
        # Only string primitives use json.dumps, never numbers or containers.
        # It implements the required lowercase control escapes and preserves
        # every other scalar, including U+2028/U+2029 and combining marks.
        return json.dumps(value, ensure_ascii=False).encode("utf-8")
    except UnicodeError as error:
        raise ModelError("invalid_unicode", pointer=pointer) from error


def _key(value, pointer):
    if type(value) is not str:
        raise ModelError("string_key_required", pointer=pointer)
    try:
        # Calling the built-in encoder directly avoids a first-use registry
        # lookup/import while an otherwise pure operation is already running.
        return utf_16_be_encode(value)[0]
    except UnicodeError as error:
        raise ModelError("invalid_unicode", pointer=pointer) from error

