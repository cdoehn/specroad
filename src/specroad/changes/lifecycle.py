"""Pure standard-artifact lifecycle planning before hashes and metadata.

The existing field-only/metadata-only adapters keep their narrower contracts.
This adapter adds typed transition/retire operations, never storage effects.
Approvals require the complete dedicated gate and are not synthesized here.
"""
from ..model.canonical import canonical_json_sha256
from ..model.errors import ModelError
from ..model.identity_values import artifact_identity
from ._common import _artifact, _generic, _text
from ._fold_inputs import _inventory, _relation_inventory, _owned_sequence, _preflight, _files, _check_expected
from ._fold_reducers import _dispatch
from ._fold_results import _finish
from ._patch_values import _snapshot
from ._metadata_policy import bind_policy
from ._metadata_materialize import apply_policy
from .values import ChangeOperation
from .lifecycle_values import LifecycleError, LifecycleResult

LIFECYCLE_POLICY_VERSION = 'standard-lifecycle-v1'
# Exact table 9.6.1. Approval is a legal edge, not an automatic grant.
_TRANSITIONS = {
    'draft': frozenset(('proposed', 'rejected', 'retired')),
    'proposed': frozenset(('draft', 'in_review', 'rejected', 'retired')),
    'in_review': frozenset(('draft', 'proposed', 'approved', 'rejected')),
    'approved': frozenset(('proposed', 'superseded', 'retired')),
    'rejected': frozenset(('draft', 'retired')),
    'superseded': frozenset(('retired',)),
    'retired': frozenset(),
}
_CONTENT_EXCLUDED = frozenset(('revision', 'created_at', 'created_by', 'updated_at', 'updated_by', 'maturity'))


def lifecycle_content_sha256(artifact):
    """Only six TOP-LEVEL management fields are excluded; nested fields stay."""
    _artifact(artifact, '/artifact')
    return canonical_json_sha256({key: value for key, value in artifact.items() if key not in _CONTENT_EXCLUDED})


def _transition(state, operation, index, binding):
    target = operation['target']
    if target not in state:
        raise LifecycleError('missing_lifecycle_target', pointer='/target')
    before = state[target]
    _generic(artifact_identity(before), '/target')
    current = before['maturity']
    if operation['op'] == 'retire':
        _check_expected(before, operation)
        requested, metadata = 'retired', {'reason': operation['reason']}
    else:
        if current != operation['from']:
            raise LifecycleError('expected_maturity_mismatch', pointer='/from')
        requested, metadata = operation['to'], operation['metadata']
    if requested == current:
        # Only guarded repeated retire can reach this branch. Explicit equal
        # from/to transitions are rejected by the existing operation contract.
        return target, None
    if requested not in _TRANSITIONS[current]:
        raise LifecycleError('invalid_lifecycle_transition', pointer='/to')
    if requested in ('retired', 'rejected'):
        _text(metadata.get('reason'), '/reason' if operation['op'] == 'retire' else '/metadata/reason')
    if requested == 'approved':
        raise LifecycleError('approval_gate_required', pointer='/to')
    state[target] = {**before, 'maturity': requested}
    return target, {'operation_index': index, 'target': target, 'from': current,
        'to': requested, 'actor': binding['actor'], 'planned_at': binding['planned_at'],
        'metadata': metadata}


def _postconditions(base, state, touched, events, input_kind):
    decisions = []
    for target in sorted(touched):
        value, old = state[target], base.get(target)
        _generic(artifact_identity(value), '/artifacts/' + target)
        old_hash = None if old is None else lifecycle_content_sha256(old)
        new_hash = lifecycle_content_sha256(value)
        content_changed = old is not None and old_hash != new_hash
        requests = [event for event in events if event['target'] == target]
        withdrawn = old is not None and old['maturity'] == 'approved' and content_changed
        if withdrawn:
            conflict = next((event for event in requests if event['to'] != 'proposed'), None)
            if conflict is not None:
                raise LifecycleError('content_lifecycle_conflict',
                    pointer='/operations/' + str(conflict['operation_index']),
                    operation_index=conflict['operation_index'], input_kind=input_kind)
            value = {**value, 'maturity': 'proposed'}
            state[target] = value
        if old is not None and old['maturity'] == 'retired' and value['maturity'] != 'retired':
            raise LifecycleError('retired_is_final', pointer='/artifacts/' + target + '/maturity')
        if value['maturity'] == 'superseded' and (old is None or old['maturity'] != 'superseded'):
            successors = [a for a in state.values() if a['artifact_type'] == value['artifact_type']
                and a['id'] != target and any(edge['type'] == 'supersedes' and edge['target'] == target
                                            for edge in a['relations'])]
            if not successors:
                raise LifecycleError('successor_required_in_final_model', pointer='/artifacts/' + target + '/maturity')
        decisions.append({'artifact_id': target, 'base_maturity': None if old is None else old['maturity'],
            'final_maturity': value['maturity'], 'base_content_sha256': old_hash,
            'final_content_sha256': new_hash, 'content_changed': content_changed,
            'approval_withdrawn': withdrawn,
            'withdrawal_reason': 'approved_content_changed' if withdrawn else None,
            'operation_indices': list(touched[target])})
    return decisions


def prepare_change_lifecycle(artifacts, operations, *, metadata_policy_version, actor,
        planned_at, preconditions=(), source_files=None, reserved_artifact_ids=(),
        reserved_relation_ids=(), input_kind='authoring'):
    """Fold six operation kinds, decide final status, then stamp ONCE per ID.

    Legal approval transitions are deliberately refused until a full approval
    gate is integrated by target planning. No human/CI boolean bypass exists.
    Authoring conflicts use exit 2, contradictory saved plans use exit 3.
    """
    if type(input_kind) is not str or input_kind not in ('authoring', 'saved_plan'):
        raise LifecycleError('invalid_lifecycle_input_kind', pointer='/input_kind')
    binding = bind_policy(metadata_policy_version, actor, planned_at)
    state, seen, prefixes = _inventory(artifacts, reserved_artifact_ids)
    used = _relation_inventory(state, reserved_relation_ids)
    base = dict(state)
    ops = _owned_sequence(operations, '/operations')
    checked = _preflight(state, preconditions, _files(source_files))
    touched, events = {}, []
    for index, raw in enumerate(ops):
        try:
            value = ChangeOperation(raw).data
            if value['op'] in ('transition', 'retire'):
                target, event = _transition(state, value, index, binding)
                if event is not None: events.append(event)
            else:
                if value['op'] == 'create' and value['artifact']['maturity'] != 'draft':
                    raise LifecycleError('new_artifact_requires_draft', pointer='/artifact/maturity')
                target = _dispatch(state, seen, prefixes, used, value)
            touched.setdefault(target, []).append(index)
        except ModelError as error:
            raise LifecycleError(error.reason, pointer='/operations/' + str(index) + error.pointer,
                operation_index=index, input_kind=input_kind) from error
    decisions = _postconditions(base, state, touched, events, input_kind)
    folded = _finish(state, base, touched, len(ops), checked, hasher=canonical_json_sha256)
    prepared = apply_policy(base, folded, binding)
    return LifecycleResult(prepared, _snapshot(decisions), _snapshot(events))
