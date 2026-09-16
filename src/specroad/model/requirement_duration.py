"""Explicit duration values for structured requirement semantics.

A deliberately bounded value contract, not text recognition or a general UCUM
engine. It accepts ISO designator durations and known UCUM time-unit atoms.
Unknown unit expressions fail as unsupported, not as proved invalid UCUM.
No arithmetic conversion of calendar years/months to fixed seconds is done.
"""
from dataclasses import dataclass
import json
import re

from .canonical import canonical_json_bytes
from .errors import ModelError

# ISO designator representation, including weeks and decimal fractions on the
# lowest-order component only. A comma is preserved, not normalized to a dot.
_NUMBER = r"[0-9]+(?:[.,][0-9]+)?"
_DESIGNATORS = re.compile(r"P(?:(" + _NUMBER + r")W|(?:([0-9]+(?:[.,][0-9]+)?)Y)?"
                         r"(?:([0-9]+(?:[.,][0-9]+)?)M)?(?:([0-9]+(?:[.,][0-9]+)?)D)?"
                         r"(?:T(?:([0-9]+(?:[.,][0-9]+)?)H)?(?:([0-9]+(?:[.,][0-9]+)?)M)?"
                         r"(?:([0-9]+(?:[.,][0-9]+)?)S)?)?)")
_PREFIXES = ("Y", "Z", "E", "P", "T", "G", "M", "k", "h", "da", "d", "c", "m", "u", "n", "p", "f", "a", "z", "y")
# Case-sensitive UCUM symbols. Some calendar-related units are fixed UCUM
# quantities; no conversion to/from an ISO calendar duration is implied.
_TIME_UNITS = frozenset({"s", "min", "h", "d", "wk", "a", "a_j", "a_g", "a_t", "mo", "mo_j", "mo_g", "mo_s"}
                        | {prefix + "s" for prefix in _PREFIXES})


def _iso(value):
    match = _DESIGNATORS.fullmatch(value)
    if match is None:
        return False
    components = [part for part in match.groups() if part is not None]
    if not components or ("T" in value and value.endswith("T")):
        return False
    # Fractions are only meaningful on the smallest unit actually present.
    return not any("." in part or "," in part for part in components[:-1])


@dataclass(frozen=True, init=False)
class RequirementDuration:
    """Validated explicit duration, with detached JSON data and no conversions."""
    _encoded: bytes
    representation: str

    def __init__(self, value):
        canonical_json_bytes(value)  # Exact JSON types, finite numeric values.
        if type(value) is str:
            if not _iso(value):
                raise ModelError("unsupported_duration_representation")
            representation = "iso8601_designator"
        elif type(value) is dict:
            if value.keys() != {"value", "unit"}:
                raise ModelError("duration_value_and_unit_required")
            if type(value["value"]) not in (int, float):
                raise ModelError("duration_number_required", pointer="/value")
            if value["value"] < 0:
                raise ModelError("negative_duration", pointer="/value")
            if type(value["unit"]) is not str or value["unit"] not in _TIME_UNITS:
                raise ModelError("unsupported_duration_unit", pointer="/unit")
            representation = "ucum_time_quantity"
        else:
            raise ModelError("duration_value_and_unit_required")
        object.__setattr__(self, "_encoded", json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8"))
        object.__setattr__(self, "representation", representation)

    @property
    def data(self):
        return json.loads(self._encoded)
