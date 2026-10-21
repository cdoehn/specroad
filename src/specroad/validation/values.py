"""Immutable, bound contracts for explicitly supplied model validation."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import re
from typing import Callable

from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.errors import ModelError
from ..storage.json_syntax import parse_json_object

VALIDATION_VERSION = "model-validation-v1"
# These semantic services have their own planned implementations. Field schemas
# do not certify sealed baselines, current evidence or legitimate approvals.
HOOK_NAMES = (
    "lifecycle", "baseline_integrity", "evidence_currentness", "review_currentness",
    "profile_lint", "language_policy", "document_model", "external_resources", "configuration",
    "task_done",
)


def _text(value, reason):
    if type(value) is not str or not value.strip():
        raise ModelError(reason)
    return value


def _sequence(value, reason):
    if type(value) not in (tuple, list):
        raise ModelError(reason)
    return tuple(value)


def _ids(values):
    values = _sequence(values, "validation_ids_required")
    for value in values:
        _text(value, "validation_id_required")
    if len(set(values)) != len(values):
        raise ModelError("duplicate_validation_id")
    return tuple(sorted(values))


@dataclass(frozen=True)
class ModelDocument:
    """A logical source label and exact already-loaded bytes, never a file opener."""
    path: str
    content: bytes

    def __post_init__(self):
        _text(self.path, "validation_source_label_required")
        if type(self.content) is not bytes:
            raise ModelError("validation_source_bytes_required", path=self.path)


def _document_bindings(documents):
    """Bind exact observed bytes, preserving the caller's established order."""
    return [{"path": document.path, "sha256": sha256(document.content).hexdigest()}
            for document in documents]


def _diagnostics(value):
    items = _sequence(value, "validation_diagnostics_required")
    for item in items:
        if type(item) is not dict:
            raise ModelError("validation_diagnostic_required")
        _text(item.get("reason"), "validation_diagnostic_reason_required")
        if item.get("severity", "error") not in ("info", "warning", "error"):
            raise ModelError("validation_diagnostic_severity_invalid")
        for key in ("artifact_id", "path"):
            if key in item and item[key] is not None and type(item[key]) is not str:
                raise ModelError("validation_diagnostic_location_invalid")
        if "pointer" in item and (type(item["pointer"]) is not str or
                                   (item["pointer"] and not item["pointer"].startswith("/"))):
            raise ModelError("validation_diagnostic_pointer_invalid")
    return canonical_json_bytes(list(items))


@dataclass(frozen=True, init=False)
class GateResult:
    """A result bound to one gate, exact sources, selection and complete subjects."""
    input_sha256: str
    checked_ids: tuple
    _diagnostics: bytes

    def __init__(self, input_sha256, checked_ids, diagnostics=()):
        _text(input_sha256, "validation_binding_required")
        object.__setattr__(self, "input_sha256", input_sha256)
        object.__setattr__(self, "checked_ids", _ids(checked_ids))
        object.__setattr__(self, "_diagnostics", _diagnostics(diagnostics))

    @property
    def diagnostics(self):
        return parse_json_object(b'{"items":' + self._diagnostics + b'}')["items"]


@dataclass(frozen=True, init=False)
class GateDependencies:
    """Explicit empty lists count; omitted sources do not. No resources are fetched."""
    input_sha256: str
    _encoded: bytes

    def __init__(self, input_sha256, by_artifact):
        _text(input_sha256, "validation_binding_required")
        if type(by_artifact) is not dict:
            raise ModelError("validation_dependency_mapping_required")
        owned = {}
        for source, targets in by_artifact.items():
            _text(source, "validation_dependency_source_required")
            owned[source] = list(_ids(targets))
        object.__setattr__(self, "input_sha256", input_sha256)
        object.__setattr__(self, "_encoded", canonical_json_bytes(owned))

    @property
    def by_artifact(self):
        return parse_json_object(self._encoded)


@dataclass(frozen=True)
class ModelGate:
    """Explicit trusted code only. Version identifies a gate, not proof of trust.

    Built-in checks cannot be replaced. Reserved semantic hooks apply according
    to Core policy; an extra ``extension:...`` gate applies to all selected IDs.
    Both discovery and checking must return the bound, complete result contract.
    """
    gate_id: str
    version: str
    dependencies: Callable
    check: Callable
    resources_sha256: str | None = None

    def __post_init__(self):
        _text(self.gate_id, "validation_gate_id_required")
        _text(self.version, "validation_gate_version_required")
        if self.gate_id not in HOOK_NAMES and not self.gate_id.startswith("extension:"):
            raise ModelError("validation_gate_id_reserved_or_unknown")
        if self.gate_id == "extension:":
            raise ModelError("validation_gate_id_required")
        if self.resources_sha256 is not None and (type(self.resources_sha256) is not str or
                re.fullmatch(r"[0-9a-f]{64}", self.resources_sha256) is None):
            raise ModelError("validation_gate_resource_binding_invalid")
        if not callable(self.dependencies) or not callable(self.check):
            raise ModelError("validation_trusted_gate_callable_required")


@dataclass(frozen=True, init=False)
class GateContext:
    """Owned bytes and immutable IDs; reads return detached JSON values."""
    documents: tuple
    subjects: tuple
    gate_id: str
    version: str
    phase: str
    input_sha256: str
    _profile_bytes: bytes | None
    _configuration_bytes: bytes | None
    _records: tuple
    resources_sha256: str | None

    def __init__(self, *args, **kwargs):
        raise TypeError("Gate contexts are created by the validation pipeline")

    @classmethod
    def _create(cls, records, documents, profile, subjects, gate, phase, basis, *, configuration=None):
        obj = object.__new__(cls)
        subjects = _ids(subjects)
        binding = canonical_json_sha256({"model": basis, "gate": gate.gate_id,
            "version": gate.version, "phase": phase, "subjects": list(subjects)})
        for name, value in (("documents", documents), ("subjects", subjects),
                            ("gate_id", gate.gate_id), ("version", gate.version),
                            ("phase", phase), ("input_sha256", binding),
                            ("_profile_bytes", profile.canonical_bytes if profile is not None else None),
                            ('_configuration_bytes', None if configuration is None else canonical_json_bytes(configuration)),
                            ("_records", tuple((r.identity.id, r.source_bytes) for r in records)),
                            ("resources_sha256", gate.resources_sha256)):
            object.__setattr__(obj, name, value)
        return obj

    @property
    def all_ids(self):
        return tuple(identity for identity, _ in self._records)

    def artifact(self, identity):
        for key, raw in self._records:
            if key == identity:
                return parse_json_object(raw)
        raise ModelError("validation_context_artifact_missing")

    @property
    def profile_data(self):
        return None if self._profile_bytes is None else parse_json_object(self._profile_bytes)

    @property
    def configuration_data(self):
        return None if self._configuration_bytes is None else parse_json_object(self._configuration_bytes)

    def result(self, diagnostics=()):
        return GateResult(self.input_sha256, self.subjects, diagnostics)

    def dependency_result(self, by_artifact):
        return GateDependencies(self.input_sha256, by_artifact)


@dataclass(frozen=True, init=False)
class ValidationReport:
    """Pipeline observation, not permission, inventory authentication or a snapshot."""
    _encoded: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError("Use validate_model to obtain a report")

    def __bool__(self):
        raise TypeError("Use report.passed explicitly; an incomplete report is not success")

    @classmethod
    def _create(cls, data):
        obj = object.__new__(cls)
        object.__setattr__(obj, "_encoded", canonical_json_bytes(data))
        return obj

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def passed(self):
        return self.data["model_valid"] is True

    @property
    def complete(self):
        return self.data["checks_complete"]

    @property
    def diagnostics(self):
        return tuple(item for stage in self.data["stages"] for item in stage["diagnostics"])

