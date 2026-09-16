"""RFC-8785 JSON bytes and SHA-256, not human-readable serialization.

The public value boundary accepts only JSON's built-in Python counterparts.
Raw object input additionally uses SpecRoad's lossless decimal-token reader.
No Unicode normalization, default fields, implicit coercion or field exclusion.
"""

from decimal import Decimal
from hashlib import sha256
import json
import math

from .errors import ModelError

__all__ = ("canonical_json_bytes", "canonical_json_sha256",
           "canonical_object_bytes", "canonical_object_sha256")


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
        return value.encode("utf-16-be")
    except UnicodeError as error:
        raise ModelError("invalid_unicode", pointer=pointer) from error


def _child(pointer, name):
    return pointer + "/" + str(name).replace("~", "~0").replace("/", "~1")


def canonical_json_bytes(value):
    """Return JCS UTF-8 for one value, without changing it or writing files.

Numbers already represented by float are binary64 values, not their lost
source token. To reject precision loss in an external JSON object, use
canonical_object_bytes on the original bytes instead of a permissive parser.
    """
    output = bytearray()
    active = set()

    def visit(item, pointer):
        kind = type(item)
        if item is None:
            output.extend(b"null")
        elif kind is bool:
            output.extend(b"true" if item else b"false")
        elif kind in (int, float):
            output.extend(_number(item, pointer).encode("ascii"))
        elif kind is str:
            output.extend(_string(item, pointer))
        elif kind in (list, dict):
            identity = id(item)
            if identity in active:
                raise ModelError("cyclic_json", pointer=pointer)
            active.add(identity)
            try:
                if kind is list:
                    output.extend(b"[")
                    for index, element in enumerate(item):
                        if index:
                            output.extend(b",")
                        visit(element, _child(pointer, index))
                    output.extend(b"]")
                else:
                    keys = sorted(item, key=lambda key: _key(key, pointer))
                    output.extend(b"{")
                    for index, key in enumerate(keys):
                        if index:
                            output.extend(b",")
                        output.extend(_string(key, pointer))
                        output.extend(b":")
                        visit(item[key], _child(pointer, key))
                    output.extend(b"}")
            finally:
                active.remove(identity)
        else:
            raise ModelError("unsupported_json_type", pointer=pointer)

    try:
        visit(value, "")
    except RecursionError as error:
        raise ModelError("json_nesting_limit") from error
    return bytes(output)


def canonical_json_sha256(value):
    """Full-value JCS/SHA-256; callers must explicitly form other hash domains.

This is not a signature, review, verification result, or write authorization.
No audit field or application-defined self-hash is implicitly excluded.
    """
    return sha256(canonical_json_bytes(value)).hexdigest()


def canonical_object_bytes(raw, *, path=None):
    """Validate one original JSON object before canonicalization; no disk I/O."""
    from ..storage.json_syntax import parse_json_object
    return canonical_json_bytes(parse_json_object(raw, path=path))


def canonical_object_sha256(raw, *, path=None):
    """Hash an object's canonical values, not its original file bytes."""
    return sha256(canonical_object_bytes(raw, path=path)).hexdigest()
