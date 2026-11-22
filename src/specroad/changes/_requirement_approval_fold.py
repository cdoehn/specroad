"""Pure exact Requirement transform and passive context/review references."""
from dataclasses import dataclass, replace
import re

from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.errors import ModelError
from ..model.paths import artifact_path
from ..storage.json_syntax import parse_json_object
from ..validation import (ApprovalContext, HumanRequirementReview, ReviewVerifier,
    ModelGate, assess_requirement_approval)
from .values import ChangeOperation
from .lifecycle_values import LifecycleError, LifecycleResult
from .request_ids import AuthoringError
from ._metadata_policy import bind_policy
from ._metadata_materialize import apply_policy
from ._fold_inputs import _inventory, _preflight, _files
from ._fold_results import _finish
from ._patch_values import _snapshot
from .lifecycle import _history, lifecycle_content_sha256

APPROVAL_GATE = 'extension:requirement-approval'
APPROVAL_BINDING = 'requirement-approval-v1'


def approval_mode(operations):
    return any(op['op'] == 'transition' and op['to'] == 'approved'
        and 'requirement_approval' in op['metadata'] for op in operations)


def bind_requirement_approval(operation, context, review):
    """Bind observations as passive plan data; this does not evaluate a gate."""
    if (type(operation) is not ChangeOperation or type(context) is not ApprovalContext
            or type(review) is not HumanRequirementReview):
        raise LifecycleError('approval_typed_inputs_required')
    value = operation.data
    if (value['op'] != 'transition' or value['from'] != 'in_review'
            or value['to'] != 'approved' or value['target'] != context.requirement_id):
        raise LifecycleError('approval_isolated_requirement_transition_required')
    value['metadata'] = {**value['metadata'], 'requirement_approval': {
        'version': APPROVAL_BINDING, 'input_sha256': context.input_sha256,
        'review_sha256': review.sha256}}
    return ChangeOperation(value)


def _operation(model, operations, actor):
    if len(operations) != 1:
        raise LifecycleError('approval_isolated_requirement_transition_required')
    operation = ChangeOperation(operations[0]).data
    before = next((a for a in model.artifacts if a['id'] == operation.get('target')), None)
    if (operation['op'] != 'transition' or operation['from'] != 'in_review'
            or operation['to'] != 'approved' or before is None
            or before['artifact_type'] != 'requirement' or before['maturity'] != 'in_review'):
        raise LifecycleError('approval_isolated_requirement_transition_required')
    binding = operation['metadata'].get('requirement_approval')
    if (type(binding) is not dict or set(binding) != {'version', 'input_sha256', 'review_sha256'}
            or binding['version'] != APPROVAL_BINDING
            or any(type(binding[k]) is not str or re.fullmatch('[0-9a-f]{64}', binding[k]) is None
                   for k in ('input_sha256', 'review_sha256'))):
        raise LifecycleError('approval_metadata_binding_required')
    if actor['actor_type'] != 'human':
        raise AuthoringError('approval_human_actor_required', exit_code=7)
    return operation, before


def prepare_requirement_candidates(model, operations, *, metadata_policy_version,
        actor, planned_at, preconditions=()):
    """Pure exact transform, selected only for an isolated bound approval intent.

    Current review eligibility is checked by the mandatory native target gate.
    Historical readers can reconstruct the declared transform without claiming
    that the old review is still valid. No ordinary lifecycle fold is relaxed.
    """
    metadata = bind_policy(metadata_policy_version, actor, planned_at)
    operation, before = _operation(model, operations, metadata['actor'])
    history = _history(model.previously_approved_ids)
    base, _, _ = _inventory(model.artifacts, [*model.reserved_artifact_ids, *history])
    checked = _preflight(base, preconditions, _files(model.source_files))
    identity = before['id']
    state = {**base, identity: {**before, 'maturity': 'approved'}}
    folded = _finish(state, base, {identity: [0]}, 1, checked, hasher=canonical_json_sha256)
    prepared = apply_policy(base, folded, metadata)
    content_hash = lifecycle_content_sha256(before)
    decisions = [{'artifact_id': identity, 'base_maturity': 'in_review',
        'final_maturity': 'approved', 'base_content_sha256': content_hash,
        'final_content_sha256': content_hash, 'content_changed': False,
        'approval_withdrawn': False, 'withdrawal_reason': None, 'operation_indices': [0]}]
    events = [{'operation_index': 0, 'target': identity, 'from': 'in_review',
        'to': 'approved', 'actor': metadata['actor'], 'planned_at': metadata['planned_at'],
        'metadata': operation['metadata']}]
    return LifecycleResult(prepared, _snapshot(decisions), _snapshot(events),
        _history=_snapshot(sorted(set(history) | {a['id'] for a in base.values()
                                                if a['maturity'] == 'approved'})))


def prepare_plan_requirement(plan, model, *, observed_base_root, observed_scope):
    value = plan.data
    if (value['base']['model_root_sha256'] != observed_base_root
            or value['base']['scope_descriptor'] != observed_scope):
        raise LifecycleError('approval_plan_basis_mismatch')
    folded = prepare_requirement_candidates(model, value['operations'],
        metadata_policy_version=value['metadata_policy_version'], actor=value['actor'],
        planned_at=value['planned_at'], preconditions=value['preconditions'])
    if {c.id: c.candidate_sha256 for c in folded.candidates} != {
            r['artifact']['id']: r['sha256'] for r in value['result_artifacts']}:
        raise LifecycleError('declared_approval_result_mismatch')
    return replace(folded, plan_sha256=plan.sha256, declared_artifacts_verified=True)
