"""Typed command outcomes: human presentation is never an execution contract."""

from dataclasses import dataclass, field, replace
from enum import Enum, IntEnum
from types import MappingProxyType
from typing import Mapping
import json
import math
import re
from urllib.parse import quote

from .._metadata import __version__

FORMAT_VERSION = "2.0.0"


class ResultContractError(ValueError):
    """A trusted handler attempted to return an invalid or unsupported result."""


class ResultStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"


class FailureKind(IntEnum):
    POLICY = 1
    USAGE = 2
    MODEL = 3
    INTERNAL = 4
    ENVIRONMENT = 5
    CONFLICT = 6
    SECURITY = 7


def _text(value, name, *, optional=False):
    if value is None and optional:
        return
    if not isinstance(value, str) or not value or "\0" in value:
        raise ResultContractError("Invalid " + name)
    try:
        value.encode("utf-8")
    except UnicodeError as error:
        raise ResultContractError("Invalid Unicode in " + name) from error


def freeze(value):
    """Defensively snapshot finite JSON values; never stringify unknown objects."""
    if value is None or type(value) in (bool, int, str):
        if isinstance(value, str):
            try:
                value.encode("utf-8")
            except UnicodeError as error:
                raise ResultContractError("Invalid Unicode in JSON data") from error
        return value
    if type(value) is float and math.isfinite(value):
        return value
    if isinstance(value, Mapping):
        if not all(type(key) is str for key in value):
            raise ResultContractError("JSON object keys must be strings")
        return MappingProxyType({freeze(key): freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(freeze(item) for item in value)
    raise ResultContractError("Value is not finite JSON data")


def thaw(value):
    if isinstance(value, Mapping):
        return {key: thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [thaw(item) for item in value]
    return value


@dataclass(frozen=True)
class Diagnostic:
    code: str
    severity: str
    category: str
    message: str
    origin: str = "core"
    rule_id: str | None = None
    artifact_id: str | None = None
    path: str | None = None
    location: Mapping | None = None
    rationale: str | None = None
    remediation: str | None = None
    related_ids: tuple[str, ...] = ()

    def __post_init__(self):
        for name in ("code", "category", "message", "origin"):
            _text(getattr(self, name), name)
        if self.severity not in ("info", "warning", "error"):
            raise ResultContractError("Unknown diagnostic severity")
        for name in ("rule_id", "artifact_id", "path", "rationale", "remediation"):
            _text(getattr(self, name), name, optional=True)
        if self.location is not None and not isinstance(self.location, Mapping):
            raise ResultContractError("Diagnostic location must be an object")
        object.__setattr__(self, "location", freeze(self.location))
        if not isinstance(self.related_ids, (list, tuple)):
            raise ResultContractError("Related identities must be a sequence")
        for item in self.related_ids:
            _text(item, "related identity")
        object.__setattr__(self, "related_ids", tuple(sorted(set(self.related_ids))))

    def as_dict(self):
        return {name: thaw(getattr(self, name)) for name in self.__dataclass_fields__}


def _diagnostic_key(item):
    return (item.path or "", item.artifact_id or "", item.code,
            json.dumps(item.as_dict(), ensure_ascii=True, sort_keys=True, allow_nan=False))


@dataclass(frozen=True)
class CommandResult:
    command: str
    status: ResultStatus = ResultStatus.SUCCESS
    failure: FailureKind | None = None
    complete: bool = True
    result: object = None
    diagnostics: tuple[Diagnostic, ...] = ()
    project: Mapping | None = None
    details: Mapping = field(default_factory=dict)

    def __post_init__(self):
        if not isinstance(self.command, str) or not re.fullmatch(r"[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)*", self.command):
            raise ResultContractError("Invalid canonical result command")
        try:
            object.__setattr__(self, "status", ResultStatus(self.status))
        except (TypeError, ValueError) as error:
            raise ResultContractError("Unsupported result status") from error
        if type(self.complete) is not bool:
            raise ResultContractError("Completion must be a boolean")
        if self.status is ResultStatus.SUCCESS:
            if not self.complete or self.failure is not None:
                raise ResultContractError("Success requires completed work and no failed gate")
        else:
            if not isinstance(self.failure, FailureKind):
                raise ResultContractError("A failed result needs an explicit failure class")
        if not isinstance(self.diagnostics, (tuple, list)) or not all(isinstance(item, Diagnostic) for item in self.diagnostics):
            raise ResultContractError("Diagnostics must be typed records")
        object.__setattr__(self, "diagnostics", tuple(sorted(self.diagnostics, key=_diagnostic_key)))
        if self.project is not None and not isinstance(self.project, Mapping):
            raise ResultContractError("Project binding must be an object or null")
        if not isinstance(self.details, Mapping) or "complete" in self.details:
            raise ResultContractError("Summary cannot override completion")
        for name in ("result", "project", "details"):
            try:
                object.__setattr__(self, name, freeze(getattr(self, name)))
            except RecursionError as error:
                raise ResultContractError("Recursive or excessively nested result") from error

    @property
    def exit_code(self) -> int:
        return 0 if self.status is ResultStatus.SUCCESS else int(self.failure)

    @classmethod
    def failed(cls, command, kind, *, complete=False, diagnostics=(), **kwargs):
        return cls(command, ResultStatus.FAILED, kind, complete,
                   diagnostics=diagnostics, **kwargs)

    def as_dict(self):
        summary = thaw(self.details)
        summary["complete"] = self.complete
        return {"format_version": FORMAT_VERSION, "command": self.command,
                "status": self.status.value, "project": thaw(self.project),
                "result": thaw(self.result), "result_ref": None,
                "diagnostics": [item.as_dict() for item in self.diagnostics],
                "summary": summary}


def failed_result(command, kind, message):
    return CommandResult.failed(command, kind, diagnostics=(Diagnostic(
        "CORE_" + kind.name, "error", kind.name.lower(), message),))


def normalize_result(value, command):
    if isinstance(value, CommandResult):
        if value.command != command:
            raise ResultContractError("Handler returned a different command identity")
        return value
    if type(value) is not int or not 0 <= value <= 7:
        raise ResultContractError("Invalid handler outcome; bare continuation codes are forbidden")
    if value == 0:
        return CommandResult(command)
    return failed_result(command, FailureKind(value), "Command did not meet its execution contract.")


def sarif_document(outcome):
    """A closed diagnostic result in SARIF 2.1.0; other states use the envelope.

    Contract: OASIS SARIF 2.1.0, sections 3.13, 3.14, 3.19 and 3.27.
    No imports, analyzer execution, or external schema fetching occur here.
    """
    if not outcome.complete:
        return outcome.as_dict()
    results = []
    for item in outcome.diagnostics:
        record = {"ruleId": item.rule_id or item.code,
                  "level": {"info": "note", "warning": "warning", "error": "error"}[item.severity],
                  "message": {"text": item.message},
                  "properties": {"specroad": item.as_dict()}}
        if item.path:
            record["locations"] = [{"physicalLocation": {"artifactLocation": {
                "uri": quote(item.path.replace("\\", "/"), safe="/")}}}]
        results.append(record)
    return {"version": "2.1.0",
            "$schema": "https://docs.oasis-open.org/sarif/sarif/v2.1.0/cos02/schemas/sarif-schema-2.1.0.json",
            "runs": [{"tool": {"driver": {"name": "SpecRoad", "version": __version__}},
                      "invocations": [{"executionSuccessful": outcome.exit_code in (0, 1),
                                       "exitCode": outcome.exit_code}],
                      "results": results,
                      "properties": {"specroad": outcome.as_dict()}}]}


def serialize_result(outcome, output_format="json"):
    if output_format == "json":
        document = outcome.as_dict()
    elif output_format == "sarif":
        document = sarif_document(outcome)
    else:
        raise ResultContractError("Unknown machine format")
    return json.dumps(document, ensure_ascii=True, sort_keys=True, allow_nan=False)
