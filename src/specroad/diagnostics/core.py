"""Owned diagnostics, semantic ordering and explicit completion/fail decisions.

A finding does not execute its rule, authenticate its origin or grant approval.
Locations are observations. Missing locations remain null, not guessed.
"""
from dataclasses import dataclass
from types import MappingProxyType
import json

from ..result_contract import ResultContractError
from ..model.errors import ModelError
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


def _optional_key(value):
    return (0, "") if value is None else (1, value)


def diagnostic_key(item):
    if type(item) is not Diagnostic:
        raise ResultContractError("Expected a typed diagnostic")
    pointer = None if item.location is None else item.location.get("pointer")
    return (SEVERITIES.index(item.severity), _optional_key(item.path),
            _optional_key(item.artifact_id), _optional_key(pointer), item.code,
            tuple(-1 if item.location is None or item.location.get(k) is None else item.location[k]
                  for k in ("line", "column", "end_line", "end_column", "byte_offset", "character_offset")),
            item.origin, _optional_key(item.rule_id),
            json.dumps(item.as_dict(), ensure_ascii=True, sort_keys=True, separators=(",", ":")))


def from_model_error(error, *, artifact_id=None, source=None, code=None, origin="core_rule", rule_id=None):
    """Preserve observed pointers and coordinates, never recover IDs from broken JSON.

    JSON syntax offsets count codepoints; UTF-8 decoding offsets count bytes.
    Supplying the exact original source permits converting the other coordinate.
    No source bytes or excerpts are copied into the human message.
    """
    if not isinstance(error, ModelError):
        raise ResultContractError("Expected a model error")
    if source is not None and type(source) is not bytes:
        raise ResultContractError("Source must be bytes")
    location = {"pointer": error.pointer, "line": error.line, "column": error.column,
                "byte_offset": None, "character_offset": None}
    position = error.position
    if position is not None:
        if type(position) is not int or position < 0:
            raise ResultContractError("Invalid observed source offset")
        if error.reason == "invalid_utf8":
            location["byte_offset"] = position
            if source is not None:
                if position > len(source):
                    raise ResultContractError("Source does not contain observed position")
                try:
                    prefix = source[:position].decode("utf-8")
                except UnicodeError as exc:
                    raise ResultContractError("Invalid source prefix") from exc
                location["character_offset"] = len(prefix)
                location["line"] = prefix.count("\n") + 1
                location["column"] = len(prefix.rsplit("\n", 1)[-1]) + 1
        elif error.reason == "invalid_json":
            location["character_offset"] = position
            if source is not None:
                try:
                    text = source.decode("utf-8")
                except UnicodeError as exc:
                    raise ResultContractError("Source is not UTF-8") from exc
                if position > len(text):
                    raise ResultContractError("Source does not contain observed position")
                prefix = text[:position]
                observed_line = prefix.count("\n") + 1
                observed_column = len(prefix.rsplit("\n", 1)[-1]) + 1
                if ((error.line is not None and error.line != observed_line) or
                        (error.column is not None and error.column != observed_column)):
                    raise ResultContractError("Source coordinates contradict the observed position")
                location["line"] = observed_line
                location["column"] = observed_column
                location["byte_offset"] = len(prefix.encode("utf-8"))
    if code is None:
        code = "SRV001" if error.reason in ("invalid_json", "invalid_utf8", "duplicate_key", "invalid_unicode", "object_required") else "SRV002"
    return Diagnostic(code, "error", "parse" if code == "SRV001" else "model",
        "Project data does not satisfy its declared contract.", origin=origin,
        rule_id=rule_id, artifact_id=artifact_id, path=error.path, location=location,
        rationale=error.reason, remediation="Inspect the indicated source without changing unrelated data.")


@dataclass(frozen=True)
class FailPolicy:
    fail_on: str = "error"
    strict: bool = False

    def __post_init__(self):
        if type(self.fail_on) is not str or self.fail_on not in ("error", "warning"):
            raise ResultContractError("Unsupported fail threshold")
        if type(self.strict) is not bool:
            raise ResultContractError("Strict must be a boolean")

    @property
    def threshold(self):
        return "warning" if self.strict else self.fail_on

    def reached(self, diagnostics):
        if type(diagnostics) not in (tuple, list) or any(type(d) is not Diagnostic for d in diagnostics):
            raise ResultContractError("Expected complete typed diagnostic sequence")
        return any(d.severity == "error" or (self.threshold == "warning" and d.severity == "warning")
                   for d in diagnostics)


@dataclass(frozen=True)
class DiagnosticAssessment:
    diagnostics: tuple
    checked_ids: tuple
    complete: bool
    policy: FailPolicy
    operational_exit_code: int | None = None

    def __post_init__(self):
        if type(self.diagnostics) not in (tuple, list) or any(type(d) is not Diagnostic for d in self.diagnostics):
            raise ResultContractError("Expected typed diagnostic sequence")
        if type(self.checked_ids) not in (tuple, list):
            raise ResultContractError("Expected explicit checked IDs")
        for key in self.checked_ids:
            _text(key, "checked artifact ID")
        if type(self.complete) is not bool or type(self.policy) is not FailPolicy:
            raise ResultContractError("Explicit completion and policy required")
        if self.operational_exit_code is not None and (type(self.operational_exit_code) is not int or
                self.operational_exit_code not in range(2, 8)):
            raise ResultContractError("Invalid independent operation failure")
        object.__setattr__(self, "diagnostics", tuple(sorted(self.diagnostics, key=diagnostic_key)))
        object.__setattr__(self, "checked_ids", tuple(sorted(set(self.checked_ids))))

    def __bool__(self):
        raise TypeError("Use assessment.passed explicitly")

    @property
    def exit_code(self):
        if self.operational_exit_code is not None:
            return self.operational_exit_code
        if not self.complete:
            return 5  # unavailable check, NOT a fabricated resumable-work exit 8
        return 1 if self.policy.reached(self.diagnostics) else 0

    @property
    def passed(self):
        return self.exit_code == 0

    @property
    def summary(self):
        return {"checked_artifacts": len(self.checked_ids), "diagnostic_count": len(self.diagnostics),
                "diagnostics_by_severity": {s: sum(d.severity == s for d in self.diagnostics) for s in SEVERITIES}}

    def as_dict(self):
        return {"diagnostic_format_version": 1, "diagnostics": [d.as_dict() for d in self.diagnostics],
                "checked_ids": list(self.checked_ids), "summary": self.summary,
                "checks_complete": self.complete, "status": "success" if self.passed else "failed",
                "exit_code": self.exit_code, "fail_on": self.policy.threshold,
                "strict_requested": self.policy.strict, "approval_granted": False,
                "write_authorized": False}


def assess_diagnostics(diagnostics, *, checked_ids=(), complete=True, fail_on="error", strict=False,
                       operational_exit_code=None):
    return DiagnosticAssessment(diagnostics, checked_ids, complete, FailPolicy(fail_on, strict), operational_exit_code)


def diagnostic_schema():
    """Shared serialized field contract, no external resolution or injected defaults."""
    nonempty = {"type": "string", "minLength": 1}
    nullable = lambda s: {"anyOf": [{"type": "null"}, s]}
    location = {"type": "object", "properties": {
        k: nullable({"type": "string", "pattern": r"^(?:$|/(?:[^~]|~[01])*$)"} if k == "pointer" else
                    {"type": "integer", "minimum": 0 if k.endswith("offset") else 1}) for k in LOCATION_KEYS},
        "additionalProperties": False}
    return {"type": "object", "properties": {
        **{k: dict(nonempty) for k in ("code", "category", "message")},
        "origin": {"enum": list(ORIGINS)}, "severity": {"enum": list(SEVERITIES)},
        **{k: nullable(dict(nonempty)) for k in ("rule_id", "artifact_id", "path", "rationale", "remediation")},
        "location": nullable(location), "related_ids": {"type": "array", "items": dict(nonempty)}},
        "required": sorted(FIELDS), "additionalProperties": False}
