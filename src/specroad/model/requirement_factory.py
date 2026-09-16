"""One pure new-requirement constructor for future CLI/import adapters.

Historical migration reads use RequirementArtifact; they must not be rewritten
as fresh drafts. No caller is authorized to publish by this preparation alone.
"""
from .audit import new_artifact_audit
from .configuration import ProjectConfiguration
from .domain_fields import NormativeForce
from .errors import ModelError
from .identity_values import ArtifactIdentity, RANDOM_SCHEME
from .requirement_values import RequirementDraft, _owned, _explicit_text
from .versions import SCHEMA_VERSION

_MISSING = object()
_RESERVED = frozenset({"schema_version", "artifact_type", "id", "id_scheme", "maturity",
                       "revision", "created_at", "updated_at", "created_by", "updated_by"})


def _resolve(data, field, argument, default=_MISSING):
    """Reject conflicting supplied values; absence, null and empty are distinct."""
    if argument is not _MISSING:
        if field in data and (type(data[field]) is not type(argument) or data[field] != argument):
            raise ModelError("requirement_input_conflict", pointer="/" + field)
        data[field] = argument
        return "argument"
    if field in data:
        return "input"
    if default is not _MISSING:
        data[field] = default
        return "project_default"
    raise ModelError("missing_field", pointer="/" + field)


def prepare_requirement(fields, *, identity, actor, planned_at, configuration=None,
                        language=_MISSING, normative_force=_MISSING):
    """Materialize an explicitly described new requirement, always as a draft.

    fields is the input object's content (without identity/audit/maturity).
    language/normative_force are independent explicitly supplied command inputs.
    Only configuration.language_policy.default_language can fill absent language.
    A later writer must still bind configuration, reserve the ID and authorize.
    """
    if type(fields) is not dict:
        raise ModelError("object_required")
    data = _owned(fields)
    forbidden = sorted(data.keys() & _RESERVED)
    if forbidden:
        raise ModelError("reserved_requirement_field", pointer="/" + forbidden[0])
    if type(identity) is not ArtifactIdentity or identity.artifact_type != "requirement" or identity.id_scheme != RANDOM_SCHEME:
        raise ModelError("new_requirement_identity_required")
    if configuration is not None and type(configuration) is not ProjectConfiguration:
        raise ModelError("typed_project_configuration_required")
    default = _MISSING
    if configuration is not None:
        if identity.id_prefix != configuration.id_prefix:
            raise ModelError("requirement_project_prefix_mismatch")
        default = configuration.data.get("language_policy", {}).get("default_language", _MISSING)
    language_source = _resolve(data, "language", language, default)
    force_source = _resolve(data, "normative_force", normative_force)
    _explicit_text(data["language"], "language")
    NormativeForce.from_value(data["normative_force"])
    data.update(schema_version=SCHEMA_VERSION, artifact_type="requirement", id=identity.id,
                id_scheme=identity.id_scheme, maturity="draft")
    data.update(new_artifact_audit(actor=actor, planned_at=planned_at).as_fields())
    data.setdefault("relations", [])
    data.setdefault("extensions", {})
    data.setdefault("implementation_status", "not_started")
    data.setdefault("verification_plan_status", "not_planned")
    return RequirementDraft(data, language_source=language_source, force_source=force_source)
