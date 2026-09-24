"""Owned finding values and exact observed-location contracts; no I/O."""
from dataclasses import dataclass
from types import MappingProxyType
from ..result_contract import ResultContractError
from .catalog import CORE_MINIMUM_SEVERITIES

ORIGINS = ("core_rule", "profile_rule", "import_rule", "migration_rule", "merge_rule",
           "analyzer_observation", "ai_suggestion")
SEVERITIES = ("error", "warning", "info")
LOCATION_KEYS = ("pointer", "line", "column", "end_line", "end_column", "byte_offset",
                 "character_offset")
FIELDS = ("code", "severity", "category", "message", "origin", "rule_id", "artifact_id",
          "path", "location", "rationale", "remediation", "related_ids")


def _text(value, name, optional=False):
    if value is None and optional:
        return
    if type(value) is not str or not value or "\0" in value:
        raise ResultContractError("Invalid " + name)
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise ResultContractError("Invalid Unicode in " + name) from exc


def _pointer(value):
    if type(value) is not str or (value and not value.startswith("/")):
        raise ResultContractError("Invalid JSON pointer")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise ResultContractError("Invalid pointer Unicode") from exc
    index = 0
    while index < len(value):
        if value[index] == "~":
            if index + 1 >= len(value) or value[index + 1] not in "01":
                raise ResultContractError("Invalid pointer escape")
            index += 1
        index += 1


def _location(value):
    if value is None:
        return None
    if type(value) not in (dict, MappingProxyType):
        raise ResultContractError("Diagnostic location must be an object")
    if any(type(k) is not str or k not in LOCATION_KEYS for k in value):
        raise ResultContractError("Unknown diagnostic location field")
    copy = dict(value)
    for key, item in copy.items():
        if item is None:
            continue
        if key == "pointer":
            _pointer(item)
        elif type(item) is not int or item < (0 if key.endswith("offset") else 1):
            raise ResultContractError("Invalid location coordinate")
    start = (copy.get("line"), copy.get("column"))
    end = (copy.get("end_line"), copy.get("end_column"))
    if start[0] is not None and end[0] is not None and end[0] < start[0]:
        raise ResultContractError("Reversed location lines")
    if all(x is not None for x in (*start, *end)) and end < start:
        raise ResultContractError("Reversed location range")
    return MappingProxyType(copy)


@dataclass(frozen=True)
class Diagnostic:
    code: str
    severity: str
    category: str
    message: str
    origin: str = "core_rule"
    rule_id: str | None = None
    artifact_id: str | None = None
    path: str | None = None
    location: object = None
    rationale: str | None = None
    remediation: str | None = None
    related_ids: tuple = ()

    def __post_init__(self):
        for key in ("code", "category", "message"):
            _text(getattr(self, key), key)
        if type(self.origin) is not str or self.origin not in ORIGINS:
            raise ResultContractError("Unknown diagnostic origin")
        if type(self.severity) is not str or self.severity not in SEVERITIES:
            raise ResultContractError("Unknown diagnostic severity")
        for key in ("rule_id", "artifact_id", "path", "rationale", "remediation"):
            _text(getattr(self, key), key, optional=True)
        if self.severity != "error" and any(key in CORE_MINIMUM_SEVERITIES for key in (self.code, self.rule_id)):
            raise ResultContractError("Protected diagnostic cannot be downgraded")
        object.__setattr__(self, "location", _location(self.location))
        if type(self.related_ids) not in (tuple, list):
            raise ResultContractError("Related IDs must be a sequence")
        for item in self.related_ids:
            _text(item, "related ID")
        object.__setattr__(self, "related_ids", tuple(sorted(set(self.related_ids))))

    def as_dict(self):
        value = {key: getattr(self, key) for key in FIELDS}
        value["location"] = None if self.location is None else dict(self.location)
        value["related_ids"] = list(self.related_ids)
        return value

    @classmethod
    def from_dict(cls, value):
        if type(value) is not dict or set(value) != set(FIELDS):
            raise ResultContractError("Incomplete or unknown diagnostic fields")
        return cls(**value)

