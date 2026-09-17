"""Deterministic manifest assembly over supplied, single-root observations.

The hash is real; completeness is NOT inferred from it. Scope closure, effective
profile composition, full artifact validation and locking remain caller duties.
This layer never issues a write, merge, baseline or release permission.
"""

from dataclasses import dataclass
import json
import re

from .canonical import canonical_json_bytes as canonical_json
from .configuration import ProjectConfiguration
from .errors import ModelError
from .hashes import canonical_json_sha256
from .paths import project_path
from .semantic_configuration import semantic_configuration


def _text(value):
    if type(value) is not str or not value.strip() or "\0" in value:
        raise ModelError("invalid_manifest_identity")
    try:
        value.encode("utf-8")
    except UnicodeError as error:
        raise ModelError("invalid_unicode") from error
    return value


def _hash(value):
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ModelError("invalid_manifest_hash")
    return value


@dataclass(frozen=True)
class ProjectReadBinding:
    """Ephemeral observation provenance. Never included in semantic hashes."""
    project_id: str
    source_root: str
    root_identity: tuple

    def __post_init__(self):
        _text(self.project_id)
        _text(self.source_root)
        if type(self.root_identity) is not tuple or not self.root_identity:
            raise ModelError("invalid_root_binding")


@dataclass(frozen=True, init=False)
class ManifestResource:
    """One owned resource record plus its non-semantic read provenance."""
    binding: ProjectReadBinding
    _encoded: bytes

    def __init__(self, binding, data):
        if not isinstance(binding, ProjectReadBinding) or type(data) is not dict:
            raise ModelError("manifest_resource_required")
        kind = data.get("kind")
        fields = {
            "artifact": {"kind", "id", "artifact_type", "revision", "sha256"},
            "profile": {"kind", "id", "version", "sha256"},
            "rule": {"kind", "id", "version", "sha256"},
            "mapping": {"kind", "id", "version", "sha256"},
            "language_registry": {"kind", "id", "version", "path", "size", "sha256"},
            "attachment": {"kind", "path", "size", "media_type", "sha256"},
        }
        if type(kind) is not str or kind not in fields or set(data) != fields[kind]:
            raise ModelError("invalid_manifest_resource")
        _hash(data["sha256"])
        if "id" in data:
            _text(data["id"])
        if "version" in data:
            _text(data["version"])
        if "revision" in data and (type(data["revision"]) is not int or data["revision"] < 1):
            raise ModelError("invalid_revision")
        if "artifact_type" in data:
            # Prefix is bound by the reader; pure assembly checks it against configuration.
            _text(data["artifact_type"])
        if "path" in data:
            project_path(data["path"])
        if "size" in data and (type(data["size"]) is not int or data["size"] < 0):
            raise ModelError("invalid_resource_size")
        if "media_type" in data:
            _text(data["media_type"])
        object.__setattr__(self, "binding", binding)
        object.__setattr__(self, "_encoded", canonical_json(data))

    @property
    def data(self):
        return json.loads(self._encoded)


def _descriptor(value):
    """Initial descriptor shapes only; resolving seeds/closure is a later service."""
    fields = {"scope_version", "scope_kind", "selector", "configuration_id",
              "closure_profile", "boundary_policy"}
    if (type(value) is not dict or set(value) != fields
            or value["scope_version"] != "scope-v1"
            or value["closure_profile"] != "core-closure-v1"
            or value["boundary_policy"] not in ("closed", "partial")):
        raise ModelError("invalid_scope_descriptor")
    kind, selector = value["scope_kind"], value["selector"]
    if value["configuration_id"] is not None:
        raise ModelError("configured_scope_not_supported")
    if type(selector) is not dict:
        raise ModelError("invalid_scope_selector")
    if kind in ("project", "specification"):
        if selector:
            raise ModelError("invalid_scope_selector")
    elif kind == "explicit":
        if set(selector) != {"artifact_ids", "resource_ids"}:
            raise ModelError("invalid_scope_selector")
        for values in selector.values():
            if type(values) is not list:
                raise ModelError("invalid_scope_selector")
            for name in values:
                _text(name)
            if values != sorted(set(values), key=lambda s: s.encode("utf-8")):
                raise ModelError("noncanonical_scope_selector")
    else:
        raise ModelError("scope_kind_not_supported")
    return json.loads(canonical_json(value))


@dataclass(frozen=True, init=False)
class ModelManifest:
    """A manifest-input hash, not proof of a fully resolved or locked project."""
    _encoded: bytes

    def __init__(self, value):
        object.__setattr__(self, "_encoded", canonical_json(value))

    @property
    def data(self):
        return json.loads(self._encoded)

    @property
    def canonical_bytes(self):
        return self._encoded

    @property
    def sha256(self):
        from hashlib import sha256
        return sha256(self._encoded).hexdigest()

    @property
    def scope_sha256(self):
        return self.data["scope_sha256"]

    @property
    def validation_scope(self):
        return "manifest_inputs_only"

    @property
    def closure_verified(self):
        return False

    @property
    def profile_composition_verified(self):
        return False

    @property
    def atomic_snapshot(self):
        return False


def assemble_model_manifest(configuration, binding, resources, *, scope_descriptor,
                            effective_profile, boundary_references=()):
    """Hash precisely the supplied scope, full resources and semantic policies.

    effective_profile must be an explicitly supplied semantic projection from a
    caller. This function binds its bytes, not a claim that composition succeeded.
    Local source provenance is checked but never mixed into the portable hash.
    """
    if not isinstance(configuration, ProjectConfiguration) or not isinstance(binding, ProjectReadBinding):
        raise ModelError("project_binding_required")
    if configuration.project_id != binding.project_id:
        raise ModelError("manifest_project_mismatch")
    if isinstance(resources, (str, bytes, dict)):
        raise ModelError("manifest_resource_sequence_required")
    try:
        resources = tuple(resources)
    except TypeError as error:
        raise ModelError("manifest_resource_sequence_required") from error
    records = []
    from .paths import artifact_path
    for resource in resources:
        if not isinstance(resource, ManifestResource):
            raise ModelError("manifest_resource_required")
        if resource.binding != binding:
            raise ModelError("manifest_project_mismatch")
        record = resource.data
        if record["kind"] == "artifact":
            artifact_path(record["artifact_type"], record["id"], configuration.id_prefix)
        records.append(record)
    identities = [(r["kind"], r.get("id", r.get("path")), r.get("version")) for r in records]
    if len(identities) != len(set(identities)):
        raise ModelError("duplicate_manifest_resource")
    descriptor = _descriptor(scope_descriptor)
    artifacts = sorted((r for r in records if r["kind"] == "artifact"), key=lambda r: r["id"].encode("utf-8"))
    attachments = sorted((r for r in records if r["kind"] == "attachment"), key=lambda r: r["path"].encode("utf-8"))
    others = sorted((r for r in records if r["kind"] not in ("artifact", "attachment")),
                    key=lambda r: (r["id"].encode("utf-8"), r["version"].encode("utf-8"), r["kind"]))
    if descriptor["scope_kind"] == "specification" and any(r["artifact_type"] in ("proposal", "baseline") for r in artifacts):
        raise ModelError("scope_control_dependency")
    if descriptor["scope_kind"] == "explicit":
        if not set(descriptor["selector"]["artifact_ids"]) <= {r["id"] for r in artifacts}:
            raise ModelError("missing_scope_seed")
        if not set(descriptor["selector"]["resource_ids"]) <= {r["id"] + "@" + r["version"] for r in others}:
            raise ModelError("missing_scope_seed")
    if type(effective_profile) is not dict:
        raise ModelError("effective_profile_projection_required")
    profile_hash = canonical_json_sha256(effective_profile)
    config_hash = canonical_json_sha256(semantic_configuration(configuration))
    # W supports closed observations; partial boundaries are implemented in R.
    if boundary_references:
        raise ModelError("boundary_references_not_supported")
    scope = {"project_id": binding.project_id, "scope_descriptor": descriptor,
             "artifacts": artifacts, "resources": others, "attachments": attachments,
             "boundary_references": [], "configuration_sha256": config_hash,
             "profile_sha256": profile_hash}
    return ModelManifest({"model_manifest_version": "model-manifest-v1", **scope,
                          "scope_sha256": canonical_json_sha256(scope)})
