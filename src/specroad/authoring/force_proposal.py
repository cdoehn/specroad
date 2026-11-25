"""Force Proposal redirection retains the complete passive inner intention."""
from ..model.audit import new_artifact_audit, actor as read_actor
from ..model.audit_values import UtcTimestamp
from ..model.versions import SCHEMA_VERSION
from ..model.canonical import canonical_json_bytes as jcs
from ..changes.write_guard_values import require
from ..proposals.values import content_sha256
from ..proposals.change_ids import allocate_change_id


def redirect(sources, plan, fields, actor, time):
    require(type(fields) is dict and {'title', 'rationale', 'changes'} <= fields.keys()
        and not fields.keys() - {'title', 'rationale', 'changes', 'model_provenance'}
        and type(fields['changes']) is list and len(fields['changes']) == 1,
        'proposal_explicit_metadata_required', exit_code=2)
    explanation = fields['changes'][0]
    require(type(explanation) is dict and set(explanation) == {
        'rationale', 'requirement_or_issue_ids', 'sources', 'assumptions', 'confidence'},
        'proposal_explicit_explanation_required', exit_code=2)
    identity = sources.allocate('proposal')
    changes = []
    for operation in plan.data['operations']:
        # Raw paths stay explicit; no nonexistent artifact identities are invented.
        changes.append({**explanation, 'change_id': allocate_change_id(tuple(r['change_id'] for r in changes)),
            'targets': [operation['path']]})
    value = dict(schema_version=SCHEMA_VERSION, artifact_type='proposal', id=identity.id,
        id_scheme=identity.id_scheme, title=fields['title'], rationale=fields['rationale'],
        maturity='draft', proposal_status='draft', content_revision=1, relations=[], extensions={},
        reviews=[], control_history=[], base=plan.data['base'], change_plan=plan.data, changes=changes,
        **new_artifact_audit(actor=read_actor(actor), planned_at=UtcTimestamp(time)).as_fields())
    provenance = fields.get('model_provenance')
    if provenance is not None:
        from ..model.proposal_fields import MODEL_FIELDS
        require(type(provenance) is dict and set(provenance) == set(MODEL_FIELDS) | {'unknown_reasons'},
            'proposal_model_fields_required', exit_code=2)
        value.update(provenance)
    value['content_sha256'] = content_sha256(value)
    return {**sources.before, identity.path: jcs(value)}
