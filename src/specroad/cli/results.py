"""Typed command outcomes: human presentation is never an execution contract."""

from dataclasses import dataclass, field
from enum import Enum, IntEnum
from types import MappingProxyType
from typing import Mapping
import json
import hashlib
import os
from pathlib import Path
import stat
import math
import re


FORMAT_VERSION = "2.0.0"


from ..result_contract import ResultContractError
from ..diagnostics import Diagnostic, diagnostic_key as _diagnostic_key


class ResultStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"
    CONTINUATION_REQUIRED = "continuation_required"


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


class OperationFailure(Exception):
    """A known Core failure, unlike an unexpected Python exception."""

    def __init__(self, kind: FailureKind, message: str, *, complete=False, details=None):
        if not isinstance(kind, FailureKind):
            raise ResultContractError("Failure class must be explicit")
        _text(message, "failure message")
        super().__init__(message)
        self.kind = kind
        if type(complete) is not bool:
            raise ResultContractError("Completion must be a boolean")
        reserved = {"complete", "failure_kind", "partial_scope", "delivery", "work_id",
                    "completed_units", "total_units", "remaining_manifest_sha256", "checkpoint", "next_action"}
        details = {} if details is None else details
        if not isinstance(details, Mapping) or reserved.intersection(details):
            raise ResultContractError("Failure details cannot override control fields")
        self.complete = complete
        try:
            self.details = freeze(details)
        except RecursionError as error:
            raise ResultContractError("Recursive failure details") from error


def _sha256(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ResultContractError("A complete SHA-256 is required")


def _count(value, name):
    if type(value) is not int or value < 0:
        raise ResultContractError(name + " must be a nonnegative integer")


def _verify_file(path, expected_size, expected_sha256):
    """Confirm a currently readable regular file without following its leaf link.

    This verifies publication bytes only. It does not interpret checkpoints or
    replace a work-engine verifier for schemas, scopes, journals or part hashes.
    """
    try:
        target = Path(path)
        before = target.lstat()
        if not stat.S_ISREG(before.st_mode):
            raise OperationFailure(FailureKind.SECURITY, "Result reference is not a regular file.")
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        descriptor = os.open(target, flags)
        with os.fdopen(descriptor, "rb") as stream:
            opened = os.fstat(stream.fileno())
            if not stat.S_ISREG(opened.st_mode) or (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino):
                raise OperationFailure(FailureKind.SECURITY, "Result reference changed while opening.")
            digest = hashlib.sha256()
            size = 0
            while True:
                chunk = stream.read(65536)
                if not chunk:
                    break
                size += len(chunk)
                if size > expected_size:
                    raise OperationFailure(FailureKind.CONFLICT, "Published result size changed.")
                digest.update(chunk)
            after = target.lstat()
            if (not stat.S_ISREG(after.st_mode)
                    or (after.st_dev, after.st_ino) != (opened.st_dev, opened.st_ino)
                    or size != expected_size or digest.hexdigest() != expected_sha256):
                raise OperationFailure(FailureKind.CONFLICT, "Published result bytes changed.")
    except OSError as error:
        raise OperationFailure(FailureKind.ENVIRONMENT, "Published result is unavailable.") from error


@dataclass(frozen=True)
class ResultReference:
    """A reference to an already published complete external result, not a writer."""

    path: str
    media_type: str
    size: int
    sha256: str
    result_schema: str

    def __post_init__(self):
        for name in ("path", "media_type", "result_schema"):
            _text(getattr(self, name), name)
        if "/" not in self.media_type:
            raise ResultContractError("A media type is required")
        _count(self.size, "size")
        _sha256(self.sha256)

    def verify(self):
        _verify_file(self.path, self.size, self.sha256)

    def as_dict(self):
        return {name: getattr(self, name) for name in self.__dataclass_fields__}


@dataclass(frozen=True)
class ContinuationClaim:
    """Required control data supplied by the future trusted work engine."""

    work_id: str
    completed_units: int
    total_units: int | None
    remaining_manifest_sha256: str
    checkpoint: str
    work_dir: str

    def __post_init__(self):
        if not isinstance(self.work_id, str) or not re.fullmatch(r"WORK-[0-9A-HJKMNP-TV-Z]{26}", self.work_id):
            raise ResultContractError("Invalid work identity")
        _count(self.completed_units, "completed_units")
        if self.total_units is not None:
            _count(self.total_units, "total_units")
            if self.completed_units > self.total_units:
                raise ResultContractError("Completed units exceed total units")
        _sha256(self.remaining_manifest_sha256)
        _text(self.checkpoint, "checkpoint")
        _text(self.work_dir, "work_dir")

    def summary(self):
        return {"work_id": self.work_id, "completed_units": self.completed_units,
                "total_units": self.total_units,
                "remaining_manifest_sha256": self.remaining_manifest_sha256,
                "checkpoint": self.checkpoint,
                "next_action": {"command_id": "work.resume", "arguments": {"work_dir": self.work_dir}}}


@dataclass(frozen=True)
class CheckpointValidation:
    """A verifier's full semantic approval bound to exact durable file bytes.

    The injected trusted Core verifier must check the entire checkpoint contract,
    including scope, tool/schema compatibility and all referenced work parts.
    A successful existence check or boolean is not this approval. This type does
    not itself implement the later milestone-6 work engine.
    """

    claim: ContinuationClaim
    checkpoint_size: int
    checkpoint_sha256: str

    def __post_init__(self):
        if not isinstance(self.claim, ContinuationClaim):
            raise ResultContractError("Typed continuation claim required")
        _count(self.checkpoint_size, "checkpoint_size")
        _sha256(self.checkpoint_sha256)


def _verify_checkpoint(claim, verifier):
    if not isinstance(claim, ContinuationClaim) or not callable(verifier):
        raise ResultContractError("No trusted checkpoint verifier is available")
    try:
        if not stat.S_ISREG(Path(claim.checkpoint).lstat().st_mode):
            raise OperationFailure(FailureKind.SECURITY, "Checkpoint is not a regular file.")
    except OSError as error:
        raise OperationFailure(FailureKind.ENVIRONMENT, "Checkpoint is unavailable.") from error
    validation = verifier(claim)
    if not isinstance(validation, CheckpointValidation) or validation.claim != claim:
        raise ResultContractError("Checkpoint verifier did not confirm this continuation")
    _verify_file(claim.checkpoint, validation.checkpoint_size, validation.checkpoint_sha256)
    return validation


@dataclass(frozen=True, init=False)
class VerifiedContinuation:
    """Freshly checked in-process handoff; not constructible from CLI/JSON data."""

    claim: ContinuationClaim
    validation: CheckpointValidation
    _verifier: object = field(repr=False, compare=False)

    def __init__(self, *args, **kwargs):
        raise ResultContractError("Use confirm_continuation with a trusted verifier")

    def verify(self):
        fresh = _verify_checkpoint(self.claim, self._verifier)
        if fresh != self.validation:
            raise OperationFailure(FailureKind.CONFLICT, "Checkpoint changed after confirmation.")


def confirm_continuation(claim, verifier):
    """Validate the full work checkpoint through an explicitly injected adapter.

    There is deliberately no default verifier, schema guess or work.resume stub.
    The later work engine is responsible for providing the real implementation.
    """
    validation = _verify_checkpoint(claim, verifier)
    proof = object.__new__(VerifiedContinuation)
    object.__setattr__(proof, "claim", claim)
    object.__setattr__(proof, "validation", validation)
    object.__setattr__(proof, "_verifier", verifier)
    return proof


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
    result_ref: ResultReference | None = None
    partial_scope: str | None = None
    continuation: VerifiedContinuation | None = None

    def __post_init__(self):
        if not isinstance(self.command, str) or not re.fullmatch(r"[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)*", self.command):
            raise ResultContractError("Invalid canonical result command")
        try:
            object.__setattr__(self, "status", ResultStatus(self.status))
        except (TypeError, ValueError) as error:
            raise ResultContractError("Unsupported result status") from error
        if type(self.complete) is not bool:
            raise ResultContractError("Completion must be a boolean")
        if self.status is ResultStatus.FAILED:
            if not isinstance(self.failure, FailureKind):
                raise ResultContractError("A failed result needs an explicit failure class")
        elif self.failure is not None:
            raise ResultContractError("Only a failed result can have a failure class")
        if self.status in (ResultStatus.SUCCESS, ResultStatus.PARTIAL) and not self.complete:
            raise ResultContractError("Success requires all work in its explicit scope")
        if self.status is ResultStatus.PARTIAL:
            _text(self.partial_scope, "explicit partial scope")
        elif self.partial_scope is not None:
            raise ResultContractError("Partial scope requires the partial status")
        if self.status is ResultStatus.CONTINUATION_REQUIRED:
            if self.complete or not isinstance(self.continuation, VerifiedContinuation):
                raise ResultContractError("Continuation requires an actual confirmed checkpoint")
            if self.result is not None or self.result_ref is not None:
                raise ResultContractError("Unfinished work cannot claim a completed result delivery")
        elif self.continuation is not None:
            raise ResultContractError("Checkpoint continuation requires continuation status")
        if self.result_ref is not None:
            if not isinstance(self.result_ref, ResultReference) or self.result is not None:
                raise ResultContractError("Inline and external result delivery are exclusive")
        if not isinstance(self.diagnostics, (tuple, list)) or not all(isinstance(item, Diagnostic) for item in self.diagnostics):
            raise ResultContractError("Diagnostics must be typed records")
        object.__setattr__(self, "diagnostics", tuple(sorted(self.diagnostics, key=_diagnostic_key)))
        if self.project is not None and not isinstance(self.project, Mapping):
            raise ResultContractError("Project binding must be an object or null")
        reserved = {"complete", "failure_kind", "partial_scope", "delivery", "work_id",
                    "completed_units", "total_units", "remaining_manifest_sha256", "checkpoint", "next_action"}
        if not isinstance(self.details, Mapping) or reserved.intersection(self.details):
            raise ResultContractError("Summary cannot override result-control fields")
        for name in ("result", "project", "details"):
            try:
                object.__setattr__(self, name, freeze(getattr(self, name)))
            except RecursionError as error:
                raise ResultContractError("Recursive or excessively nested result") from error

    @property
    def exit_code(self) -> int:
        self.verify_delivery()
        if self.status is ResultStatus.FAILED:
            return int(self.failure)
        return 8 if self.status is ResultStatus.CONTINUATION_REQUIRED else 0

    def verify_delivery(self):
        if self.continuation is not None:
            self.continuation.verify()
        if self.result_ref is not None:
            self.result_ref.verify()

    @classmethod
    def failed(cls, command, kind, *, complete=False, diagnostics=(), **kwargs):
        return cls(command, ResultStatus.FAILED, kind, complete,
                   diagnostics=diagnostics, **kwargs)

    def as_dict(self):
        from .serialization import envelope_document
        return envelope_document(self)


def failed_result(command, kind, message, *, complete=False, details=None):
    return CommandResult.failed(command, kind, complete=complete,
        details={} if details is None else details,
        diagnostics=(Diagnostic("CORE_" + kind.name, "error", kind.name.lower(), message),))


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
    from .serialization import sarif_document as project_sarif
    return project_sarif(outcome)


def serialize_result(outcome, output_format="json"):
    from .serialization import serialize_result as encode
    return encode(outcome, output_format)
