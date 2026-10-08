"""Pure current-resource eligibility shared by readers, plans and recovery.

The caller supplies configuration, classified path and original bytes. This
check neither reads a project nor grants write authority or full target approval.
"""
from .artifact_schemas import validate_common_fields
from .configuration import ProjectConfiguration
from .errors import ModelError
from .paths import PathClass, artifact_path
from .record_contracts import SPECIAL_STATES
from .record_schemas import validate_record_fields
from .versions import SCHEMA_VERSION
from ..storage.json_syntax import parse_json_object


def _validate_format_input(configuration, path, raw, kind):
    value = parse_json_object(raw, path=path)
    if value.get("schema_version") != SCHEMA_VERSION:
        raise ModelError("unsupported_schema_version", path=path,
                         pointer="/schema_version", highest_supported=SCHEMA_VERSION)
    if kind is PathClass.CONFIGURATION:
        ProjectConfiguration(value)
    elif kind is PathClass.ARTIFACT:
        validate_common_fields(value)
        expected = artifact_path(value["artifact_type"], value["id"], configuration.id_prefix)
        if path != expected:
            raise ModelError("artifact_path_identity_mismatch", path=path)
        artifact_type = value["artifact_type"]
        if artifact_type in SPECIAL_STATES:
            # Validate the stored status, including its maturity coupling, before
            # deciding mutability. Missing or unknown statuses fail closed.
            validate_record_fields(value)
            status_field, _ = SPECIAL_STATES[artifact_type]
            terminal = {"applied", "rejected", "stale"}
            if artifact_type != "proposal" or value[status_field] in terminal:
                raise ModelError("protected_original_resource", path=path)
    # Profile/rule/mapping schemas are later layers. Syntax/version validation
    # here is not a claim of full schema, graph or profile validation.
