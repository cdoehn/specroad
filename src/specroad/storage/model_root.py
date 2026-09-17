"""Read bindings for explicitly selected model inputs under exactly one root.

No scope closure, profile composition, writes, cache or external process. Callers
must resolve a complete scope in the later scope engine; this is not a full
project loader merely because a project descriptor was supplied.
"""

from dataclasses import dataclass
from hashlib import sha256

from ..model.artifact_schemas import validate_common_fields
from ..model.canonical import canonical_json_sha256
from ..model.errors import ModelError
from ..model.model_manifest import ProjectReadBinding, ManifestResource, assemble_model_manifest
from ..model.paths import PathClass, artifact_path
from ..model.versions import SCHEMA_VERSION
from .attachments import fingerprint_file, verify_attachments
from .json_syntax import parse_json_object
from .project import ProjectSource


def _binding(source):
    if not isinstance(source, ProjectSource):
        raise ModelError("project_source_required")
    source.check_current()
    return ProjectReadBinding(source.configuration.project_id, str(source.boundary.root),
                              source.boundary._root_identity)


@dataclass(frozen=True)
class CapturedModelInputs:
    """Byte freshness belongs to this read only; no durable write capability."""
    binding: ProjectReadBinding
    configuration_bytes: bytes
    resources: tuple[ManifestResource, ...]
    byte_bindings: tuple[tuple[str, int, str], ...]


def _json_resource(source, path, raw, binding):
    value = parse_json_object(raw, path=path)
    if value.get("schema_version") != SCHEMA_VERSION:
        raise ModelError("unsupported_schema_version", path=path, highest_supported=SCHEMA_VERSION)
    if "project_id" in value and value["project_id"] != binding.project_id:
        raise ModelError("manifest_project_mismatch", path=path)
    kind = source.classify(path)
    common = {"kind": kind.value, "sha256": canonical_json_sha256(value)}
    if kind is PathClass.ARTIFACT:
        validate_common_fields(value)
        if artifact_path(value["artifact_type"], value["id"], source.configuration.id_prefix) != path:
            raise ModelError("artifact_path_identity_mismatch", path=path)
        common.update(id=value["id"], artifact_type=value["artifact_type"], revision=value["revision"])
    elif kind in (PathClass.PROFILE, PathClass.RULE, PathClass.MAPPING):
        id_key = kind.value + "_id"
        version_key = kind.value + "_version"
        # Resource metadata must be explicit, never inferred from a filename.
        if id_key not in value or version_key not in value:
            raise ModelError("missing_resource_identity", path=path)
        common.update(id=value[id_key], version=value[version_key])
    else:
        raise ModelError("not_manifest_input", path=path)
    return ManifestResource(binding, common)


def capture_model_inputs(source, resource_paths, *, attachments=()):
    """Capture only explicit members; always bind semantic project configuration.

    The list is not a declaration of complete closure. No implicit inclusion of
    archive objects, baseline payloads or strings that look like references.
    """
    binding = _binding(source)
    names = source._paths(resource_paths)
    if len({name.casefold() for name in names}) != len(names):
        raise ModelError("resource_path_collision")
    resources, observed = [], []
    for path in sorted(names, key=lambda s: s.encode("utf-8")):
        raw = source.read_normative(path)
        if path != "specroad.json":
            resources.append(_json_resource(source, path, raw, binding))
        observed.append((path, len(raw), sha256(raw).hexdigest()))
    registry = source.configuration.data.get("language_registry")
    if registry is not None:
        path = registry["path"]
        if path in names:
            raise ModelError("conflicting_resource_roles", path=path)
        item = fingerprint_file(source.boundary, path)
        if item.sha256 != registry["sha256"]:
            raise ModelError("registry_hash_mismatch", path=path)
        resources.append(ManifestResource(binding, {"kind": "language_registry",
            "id": registry["registry_id"], "version": registry["registry_version"],
            "path": path, "size": item.size, "sha256": item.sha256}))
        observed.append((path, item.size, item.sha256))
    for item in verify_attachments(source, attachments):
        resources.append(ManifestResource(binding, {"kind": "attachment", **item.data}))
        observed.append((item.path, item.size, item.sha256))
    if len({path.casefold() for path, _, _ in observed}) != len(observed):
        raise ModelError("resource_path_collision")
    result = CapturedModelInputs(binding, source.configuration_bytes, tuple(resources), tuple(observed))
    check_model_inputs_current(source, result)
    return result


def check_model_inputs_current(source, captured):
    """Recheck selected bytes and root. Still not an atomic multi-file snapshot."""
    if not isinstance(captured, CapturedModelInputs) or _binding(source) != captured.binding:
        raise ModelError("manifest_project_mismatch")
    if source.configuration_bytes != captured.configuration_bytes:
        raise ModelError("configuration_changed")
    for path, size, expected_hash in captured.byte_bindings:
        current = fingerprint_file(source.boundary, path)
        if current.size != size or current.sha256 != expected_hash:
            raise ModelError("model_input_changed", path=path)
    source.check_current()


def prepare_model_root(source, resource_paths, *, scope_descriptor, effective_profile,
                       attachments=(), boundary_references=()):
    """Compose a real hash with explicitly limited verification scope."""
    captured = capture_model_inputs(source, resource_paths, attachments=attachments)
    result = assemble_model_manifest(source.configuration, captured.binding, captured.resources,
                                    scope_descriptor=scope_descriptor, effective_profile=effective_profile,
                                    boundary_references=boundary_references)
    check_model_inputs_current(source, captured)
    return result
