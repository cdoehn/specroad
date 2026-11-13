"""Exact inner-plan reduction and one additive control revision; no authority."""
from base64 import b64encode
from dataclasses import dataclass
from hashlib import sha256

from ..changes._metadata_policy import bind_policy
from ..changes._patch_values import _snapshot
from ..changes._saved_plan_fold import fold_saved_plan
from ..changes._target_materialization import materialize_target
from ..changes.metadata_values import MetadataArtifact
from ..changes.values import ChangeOperation, ChangePlan
from ..model.audit_values import Actor, Revision, UtcTimestamp
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..storage.json_syntax import parse_json_object
from ..validation import ModelDocument
from .context import ProposalContext, reconstruct_proposal_target, specification_manifest
from .revisions import ProposalRevision
from .values import ProposalOriginal, require

COMMAND = 'proposal.apply'
GATE = 'extension:proposal-apply'
VERSION = 'proposal-apply-assessment-v1'


def apply_mode(operations):
    controls = [op for op in operations if op['op'] == 'proposal_control']
    selected = any('apply_check' in op for op in controls)
    if selected:
        require(len(controls) == 1 and controls[0] == operations[-1]
            and not any(k in controls[0] for k in ('review_start', 'review_decision')),
            'proposal_apply_final_control_required')
    return selected


def operation_proof(operation):
    proof = operation.get('apply_check')
    require(type(proof) is dict and set(proof) == {'format_version', 'assessment_bytes_base64'}
        and proof['format_version'] == 'proposal-apply-evidence-v1',
        'proposal_apply_evidence_required')
    from ._decision_evidence import decode
    raw, report = decode(proof['assessment_bytes_base64'], versions=(VERSION,))
    require(report['history']['observed_status'] == 'approved'
        and report['history']['current_approval'] is True, 'proposal_current_approval_required')
    return raw, report


def assessment(snapshot, original, services):
    from ._decision_evidence import assessment as observe
    from .validation import validate_proposal
    require(original.data['proposal_status'] == 'approved', 'proposal_apply_requires_approved')
    require(services.proposal_inputs is not None, 'proposal_original_provenance_unverified', exit_code=7)
    validate_proposal(ProposalContext(original, snapshot.model))
    return observe(snapshot, original, services, version=VERSION)


def operation(original, raw):
    value = dict(op='proposal_control', target=original.data['id'],
        expected_revision=original.data['revision'], expected_sha256=canonical_json_sha256(original.data),
        **{k: v for k, v in original.binding.data.items() if k != 'proposal_id'},
        events=[{'from': 'approved', 'to': 'applied', 'reason': 'proposal_apply',
                 'result_sha256': sha256(raw).hexdigest()}],
        apply_check=dict(format_version='proposal-apply-evidence-v1',
            assessment_bytes_base64=b64encode(raw).decode('ascii')))
    operation_proof(value)
    return value


def applied_original(original, control, *, context, actor, planned_at):
    raw, report = operation_proof(control)
    require(original.data['proposal_status'] == 'approved', 'proposal_apply_requires_approved')
    require(control == operation(original, raw)
        and report['binding'] == original.binding.data and report['proposal_sha256'] == original.sha256
        and report['context_sha256'] == context.sha256
        and report['history']['minimum_human_approvals'] == context.minimum_approvals,
        'proposal_apply_original_binding_changed', exit_code=6)
    row = dict(format_version='proposal-control-v1', binding=original.binding.data,
        actor=actor, occurred_at=planned_at, observed_revision=original.data['revision'],
        result_bytes_base64=b64encode(raw).decode('ascii'), **control['events'][0])
    value = original.data
    value.update(proposal_status='applied', maturity='applied',
                 control_history=[*value['control_history'], row])
    return ProposalRevision(original, value, expected_revision=Revision(original.data['revision']),
        actor=Actor(**actor), planned_at=UtcTimestamp(planned_at)).after


@dataclass(frozen=True)
class ApplyCandidates:
    target_model: object
    candidates: tuple
    _history: tuple

    @property
    def artifacts(self): return self.target_model.artifacts
    @property
    def metadata_applied(self): return True
    @property
    def decisions(self): return []
    @property
    def previously_approved_ids(self): return list(self._history)


def prepare_apply_candidates(model, operations, *, metadata_policy_version, actor,
                             planned_at, preconditions=()):
    require(apply_mode(operations), 'proposal_apply_evidence_required')
    control = ChangeOperation(operations[-1]).data
    metadata = bind_policy(metadata_policy_version, actor, planned_at)
    originals = {parse_json_object(d.content)['id']: d for d in model.documents}
    require(control['target'] in originals, 'proposal_control_target_missing')
    document = originals[control['target']]
    original = ProposalOriginal(document.content, path=document.path)
    inner = ChangePlan(canonical_json_bytes(original.data['change_plan']))
    value = inner.data
    require(operations[:-1] == value['operations'] and list(preconditions) == value['preconditions']
        and metadata_policy_version == value['metadata_policy_version'],
        'proposal_apply_inner_plan_changed', exit_code=6)
    context = ProposalContext(original, model)
    # The inner plan retains its own actor, time, IDs and metadata. Its native
    # reducer checks every precondition and result; Apply never replans it.
    folded, _, _ = fold_saved_plan(inner, model, observed_base_root=specification_manifest(model).sha256,
                                  observed_scope=value['base']['scope_descriptor'])
    target = reconstruct_proposal_target(context)
    after = applied_original(original, control, context=context,
        actor=metadata['actor'], planned_at=metadata['planned_at'])
    target = materialize_target(target, (ModelDocument(after.path, after.source_bytes),))
    candidate = MetadataArtifact(after.data['id'], _snapshot(after.data),
        canonical_json_sha256(original.data), canonical_json_sha256(after.data),
        (len(operations) - 1,), 'updated', original.source_bytes)
    return ApplyCandidates(target, (*folded.candidates, candidate), tuple(folded.previously_approved_ids))


def bind_apply_authoring(plan):
    from ..changes.authoring import prepare_authoring_request
    from ..changes.authoring_values import AuthoringRequest
    value = plan.data
    require(apply_mode(value['operations']), 'proposal_apply_evidence_required')
    operation_proof(value['operations'][-1])
    request = prepare_authoring_request(command_id='proposal apply', actor=value['actor'],
        operations=value['operations'], request_id=value['request_id'])
    return AuthoringRequest._create({**request.data, 'plan_sha256': plan.sha256,
        'base_model_root_sha256': value['base']['model_root_sha256'],
        'scope_descriptor': value['base']['scope_descriptor']})


def read_apply_observation(original, context):
    """Exact row decoding still requires host provenance and real receipts."""
    from .observations import ProposalControlObservation
    before = context.original
    rows = original.data['control_history']
    require(len(rows) == len(before.data['control_history']) + 1, 'proposal_apply_control_count')
    row = rows[-1]
    require(set(row) == {'format_version', 'binding', 'actor', 'occurred_at', 'observed_revision',
        'result_bytes_base64', 'from', 'to', 'reason', 'result_sha256'}, 'proposal_apply_row_invalid')
    raw, _ = operation_proof({'apply_check': dict(format_version='proposal-apply-evidence-v1',
                                               assessment_bytes_base64=row['result_bytes_base64'])})
    expected = applied_original(before, operation(before, raw), context=context,
                               actor=row['actor'], planned_at=row['occurred_at'])
    require(original.source_bytes == expected.source_bytes, 'proposal_apply_original_binding_changed', exit_code=6)
    return ProposalControlObservation(original, len(rows) - 1, context, Actor(**row['actor']),
        UtcTimestamp(row['occurred_at']), 'approved', 'applied', 'proposal_apply', raw)
