"""Exact UTC comparison and one-microsecond advancement without a clock.

Fractional seconds are digit strings: no binary floats, Decimal context,
locale conversion, or truncation to Python datetime's six fractional digits.
Explicit leap-second spellings follow the existing UtcTimestamp contract;
this module does not certify them against an external leap-second register.
"""
from datetime import date, timedelta
from ..model.audit_values import UtcTimestamp
from ..model.errors import ModelError
from .metadata_values import MetadataError


def _parts(value, pointer):
    try:
        UtcTimestamp(value)
    except ModelError as error:
        raise MetadataError(error.reason, pointer=pointer) from None
    year, month, day = (int(part) for part in value[:10].split("-"))
    h, m, s = (int(part) for part in value[11:19].split(":"))
    fraction = value[20:-1] if value[19:20] == "." else ""
    return (date(year, month, day), h, m, s), fraction


def _successor(value):
    whole, fraction = _parts(value, "/updated_at")
    width = max(6, len(fraction))
    digits = list(fraction.ljust(width, "0"))
    # A microsecond increments digit 6, retaining all less significant digits.
    carry = True
    for index in range(5, -1, -1):
        if digits[index] == "9":
            digits[index] = "0"
        else:
            digits[index] = chr(ord(digits[index]) + 1)
            carry = False
            break
    d, h, m, s = whole
    if carry:
        if s >= 59:
            s = 0
            m += 1
            if m == 60:
                m = 0
                h += 1
                if h == 24:
                    h = 0
                    try:
                        d += timedelta(days=1)
                    except OverflowError:
                        raise MetadataError("timestamp_overflow", pointer="/updated_at") from None
        else:
            s += 1
    tail = "".join(digits).rstrip("0")
    return (f"{d.year:04d}-{d.month:02d}-{d.day:02d}T{h:02d}:{m:02d}:{s:02d}"
            + ("." + tail if tail else "") + "Z")


def next_update_time(planned_at, base_updated_at):
    """K.2: max(bound planned_at, base.updated_at + exactly one microsecond)."""
    planned, pf = _parts(planned_at, "/planned_at")
    successor = _successor(base_updated_at)
    previous, sf = _parts(successor, "/updated_at")
    width = max(len(pf), len(sf))
    return planned_at if (planned, pf.ljust(width, "0")) >= (previous, sf.ljust(width, "0")) else successor
