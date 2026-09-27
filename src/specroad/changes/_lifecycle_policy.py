"""Fixed lifecycle projection and postconditions, independent of file writers.

No dynamic policy/provider registration is read from plan data. This policy
runs inside the planner before the existing metadata and result hash stages.
"""
from ..model.canonical import canonical_json_sha256
from ..model.errors import ModelError
from ..model.identity_values import artifact_identity
from ._common import _generic, _text
from ._fold_inputs import _check_expected
from .lifecycle_values import LifecycleError

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

def _content_hash(artifact):
    # Internal owned candidate: maturity can still require a dedicated gate.
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
    # Gate approval only after final content comparison. A contradictory
    # reapproval of base-approved content must remain a 9.6.3 conflict.
    state[target] = {**before, 'maturity': requested}
    return target, {'operation_index': index, 'target': target, 'from': current,
        'to': requested, 'actor': binding['actor'], 'planned_at': binding['planned_at'],
        'metadata': metadata}

def _postconditions(base, state, touched, events, input_kind):
    decisions = []
    for target in sorted(touched):
        value, old = state[target], base.get(target)
        _generic(artifact_identity(value), '/artifacts/' + target)
        old_hash = None if old is None else _content_hash(old)
        new_hash = _content_hash(value)
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
        approval = next((event for event in requests if event['to'] == 'approved'), None)
        if approval is not None:
            raise LifecycleError('approval_gate_required',
                pointer='/operations/' + str(approval['operation_index']) + '/to',
                operation_index=approval['operation_index'])
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
    if any(event['to'] == 'superseded' for event in events):
        # A cycle is not a legitimate successor proof. Reuse the stored-graph
        # checker rather than create a second traversal policy.
        from ..graph.hierarchies import validate_hierarchies
        from ..graph.references import RelationReferences
        from ..graph.relations import SourceRelations
        from ..model.canonical import canonical_json_bytes
        try:
            validate_hierarchies(RelationReferences(tuple(
                SourceRelations(canonical_json_bytes(v)) for v in state.values())))
        except ModelError as error:
            raise LifecycleError(error.reason, pointer=error.pointer) from error
    return decisions
