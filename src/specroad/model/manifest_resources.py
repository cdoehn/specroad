"""Project a selected JSON resource to a manifest record, without any I/O."""

from .artifact_schemas import validate_common_fields
from .canonical import canonical_json_sha256
from .errors import ModelError
from .model_manifest import ManifestResource
from .paths import PathClass, artifact_path, classify_path
from .versions import SCHEMA_VERSION
from ..storage.json_syntax import parse_json_object


def project_json_resource(configuration, path, raw, binding):
    value = parse_json_object(raw, path=path)
    if value.get("schema_version") != SCHEMA_VERSION:
        raise ModelError("unsupported_schema_version", path=path, highest_supported=SCHEMA_VERSION)
    if "project_id" in value and value["project_id"] != binding.project_id:
        raise ModelError("manifest_project_mismatch", path=path)
    kind = classify_path(path, configuration)
    common = {"kind": kind.value, "sha256": canonical_json_sha256(value)}
    if kind is PathClass.ARTIFACT:
        validate_common_fields(value)
        if artifact_path(value["artifact_type"], value["id"], configuration.id_prefix) != path:
            raise ModelError("artifact_path_identity_mismatch", path=path)
        common.update(id=value["id"], artifact_type=value["artifact_type"], revision=value["revision"])
    elif kind in (PathClass.PROFILE, PathClass.RULE, PathClass.MAPPING):
        id_key = kind.value + "_id"
        version_key = kind.value + "_version"
        # Resource metadata must be explicit, never inferred from a filename.
        if id_key not in value or not ({version_key, "version"} & value.keys()):
            raise ModelError("missing_resource_identity", path=path)
        if version_key in value and "version" in value and value["version"] != value[version_key]:
            raise ModelError("conflicting_resource_version", path=path)
        common.update(id=value[id_key], version=value.get(version_key, value.get("version")))
    else:
        raise ModelError("not_manifest_input", path=path)
    return ManifestResource(binding, common)

