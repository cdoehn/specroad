"""Shared primitive audit contracts, not operation-specific metadata policy."""

from datetime import date
import re

ACTOR_TYPES = ("human", "ai", "ci", "tool")
AUDIT_FIELDS = ("revision", "created_at", "created_by", "updated_at", "updated_by")
UTC_PATTERN = r"^[0-9]{4}-[0-9]{2}-[0-9]{2}[Tt][0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?Z(?![\s\S])"


def _valid_utc(value):
    if type(value) is not str or re.fullmatch(UTC_PATTERN, value) is None:
        return False
    year, month, day = map(int, value[:10].split("-"))
    hour, minute, second = map(int, value[11:19].split(":"))
    try:
        date(year, month, day)
    except ValueError:
        return False
    if hour > 23 or minute > 59 or second > 60:
        return False
    # Candidate syntax only; no online leap-second registry is consulted.
    return second != 60 or (hour == 23 and minute == 59 and (month, day) in ((6, 30), (12, 31)))



def audit_definitions():
    text = {"type": "string", "minLength": 1, "pattern": "\\S",
            "not": {"pattern": "\\u0000"}}
    actor = {"type": "object", "required": ["actor_type", "actor_id"],
             "properties": {"actor_type": {"enum": list(ACTOR_TYPES)},
                            "actor_id": dict(text)}, "additionalProperties": False}
    utc = {"type": "string", "format": "date-time",
           "pattern": UTC_PATTERN}
    return {"text": text, "actor": actor, "utc": utc}

