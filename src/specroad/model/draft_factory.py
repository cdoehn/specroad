"""Pure draft field construction shared by authoring adapters.

Inputs are explicit, already normalized fields and typed identity/audit values.
Requirements retain their existing M2 constructor. This assembly grants no
write authority and does not replace the caller's full artifact/target checks.
Historical records must never be reconstructed as new drafts through this API.
"""
from .audit import new_artifact_audit
from .requirement import prepare_requirement
from .versions import SCHEMA_VERSION


def prepare_draft_fields(kind, fields, *, identity, actor, planned_at, configuration):
    """Assemble the existing creation fields without clocks, allocation or I/O."""
    if kind == 'requirement':
        value = prepare_requirement(fields, identity=identity, actor=actor,
            planned_at=planned_at, configuration=configuration).data
    else:
        value = {**fields, 'schema_version': SCHEMA_VERSION, 'artifact_type': kind,
            'id': identity.id, 'id_scheme': identity.id_scheme, 'maturity': 'draft',
            **new_artifact_audit(actor=actor, planned_at=planned_at).as_fields()}
    return value
