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
    return _content_hash(artifact)


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


def _ordinary(state, base, seen, prefixes, used, value):
    """Keep ordered guards on real intermediate values, not a status projection.

    Approved-only field obligations must not prevent editing a candidate that
    will become proposed. Reuse the existing patch/safety contracts and validate
    those fields against the derived status, without changing stored from/hash
    guards or installing the final status before the fold has finished.
    """
    from .json_patch import apply_json_patch
    kind = value['op']
    owner = value.get('target') if kind == 'update' else value.get('source')
    original = state.get(owner)
    base_approved = owner in base and base[owner]['maturity'] == 'approved'
    if original is None or not base_approved:
        return _dispatch(state, seen, prefixes, used, value)
    _generic(artifact_identity(original), '/target' if kind == 'update' else '/source')
    if kind == 'update':
        _check_expected(original, value)
        candidate = apply_json_patch(original, value['patch']).data
        projected = candidate
        if _content_hash(candidate) != _content_hash(base[owner]):
            projected = {**candidate, 'maturity': 'proposed'}
        _artifact(projected, '/candidate', expected_type=original['artifact_type'])
        state[owner] = candidate
        return owner
    # The relation reducers guard relation identity/hash, not a source artifact
    # hash. A private view lets them validate their final source fields under
    # the pending downgrade while retaining the real intermediate maturity.
    shadow = dict(state)
    shadow[owner] = {**original, 'maturity': 'proposed'}
    target = _dispatch(shadow, seen, prefixes, used, value)
    state[target] = {**shadow[target], 'maturity': original['maturity']}
    return target


def prepare_change_lifecycle(artifacts, operations, *, metadata_policy_version, actor,
        planned_at, preconditions=(), source_files=None, reserved_artifact_ids=(),
        reserved_relation_ids=(), previously_approved_ids=(), input_kind='authoring'):
    """Fold six operation kinds, decide final status, then stamp ONCE per ID.

    Legal approval transitions are deliberately refused until a full approval
    gate is integrated by target planning. No human/CI boolean bypass exists.
    Authoring conflicts use exit 2, contradictory saved plans use exit 3.
    """
    if type(input_kind) is not str or input_kind not in ('authoring', 'saved_plan'):
        raise LifecycleError('invalid_lifecycle_input_kind', pointer='/input_kind')
    binding = bind_policy(metadata_policy_version, actor, planned_at)
    history = _history(previously_approved_ids)
    reserved = _owned_sequence(reserved_artifact_ids, '/reserved_artifact_ids')
    state, seen, prefixes = _inventory(artifacts, [*reserved, *history])
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
                target = _ordinary(state, base, seen, prefixes, used, value)
            touched.setdefault(target, []).append(index)
        except ModelError as error:
            raise LifecycleError(error.reason, pointer='/operations/' + str(index) + error.pointer,
                operation_index=index, input_kind=input_kind) from error
    decisions = _postconditions(base, state, touched, events, input_kind)
    folded = _finish(state, base, touched, len(ops), checked, hasher=canonical_json_sha256)
    prepared = apply_policy(base, folded, binding)
    observed_history = sorted(set(history) | {k for k,v in base.items() if v['maturity'] == 'approved'})
    return LifecycleResult(prepared, _snapshot(decisions), _snapshot(events),
                           _history=_snapshot(observed_history))


def _history(values):
    from ._common import _reference
    owned = _owned_sequence(values, '/previously_approved_ids')
    for index, value in enumerate(owned):
        _reference(value, '/previously_approved_ids/' + str(index))
    if len(owned) != len(set(owned)):
        raise LifecycleError('duplicate_history_identity', pointer='/previously_approved_ids')
    return owned


def prepare_plan_lifecycle(plan, artifacts, *, observed_base_root, observed_scope,
                           source_files=None, reserved_artifact_ids=(),
                           reserved_relation_ids=(), previously_approved_ids=()):
    """Recompute lifecycle BEFORE verifying declared final artifact hashes.

    Exact root/scope observations must come from the trusted caller. This API
    does not attest a live filesystem, authenticate history or check target root.
    """
    import re
    from dataclasses import replace
    from .values import ChangePlan
    from ..graph.scope_descriptors import ScopeDescriptor
    if type(plan) is not ChangePlan:
        raise LifecycleError('change_plan_required', pointer='/plan')
    value = plan.data
    if (type(observed_base_root) is not str or re.fullmatch('[0-9a-f]{64}', observed_base_root) is None
            or observed_base_root != value['base']['model_root_sha256']):
        raise LifecycleError('base_root_mismatch', pointer='/base/model_root_sha256')
    if ScopeDescriptor(observed_scope).data != value['base']['scope_descriptor']:
        raise LifecycleError('base_scope_mismatch', pointer='/base/scope_descriptor')
    result = prepare_change_lifecycle(artifacts, value['operations'],
        metadata_policy_version=value['metadata_policy_version'], actor=value['actor'],
        planned_at=value['planned_at'], preconditions=value['preconditions'], source_files=source_files,
        reserved_artifact_ids=reserved_artifact_ids, reserved_relation_ids=reserved_relation_ids,
        previously_approved_ids=previously_approved_ids, input_kind='saved_plan')
    expected = {entry['artifact']['id']: entry['sha256'] for entry in value['result_artifacts']}
    actual = {item.id: item.candidate_sha256 for item in result.candidates}
    if set(expected) != set(actual):
        raise LifecycleError('declared_result_set_mismatch', pointer='/result_artifacts')
    for index, entry in enumerate(value['result_artifacts']):
        if actual[entry['artifact']['id']] != entry['sha256']:
            raise LifecycleError('declared_lifecycle_result_mismatch', pointer='/result_artifacts/' + str(index))
    return replace(result, plan_sha256=plan.sha256, declared_artifacts_verified=True)


def prepare_change_lifecycle_bytes(sources, operations, **inputs):
    """Actual UTF-8 source bytes, never paths. Original bytes remain unchanged."""
    from dataclasses import replace
    from ..storage.json_syntax import parse_json_object
    if type(sources) not in (tuple, list):
        raise LifecycleError('source_bytes_sequence_required', pointer='/sources')
    values, original = [], {}
    for index, raw in enumerate(sources):
        at = '/sources/' + str(index)
        if type(raw) is not bytes:
            raise LifecycleError('bytes_required', pointer=at)
        value = parse_json_object(raw)
        identity = _artifact(value, at)
        if identity.id in original:
            raise LifecycleError('duplicate_source_identity', pointer=at)
        values.append(value)
        original[identity.id] = raw
    result = prepare_change_lifecycle(values, operations, **inputs)
    candidates = tuple(replace(item, original_bytes=original.get(item.id)) for item in result.candidates)
    return replace(result, _metadata=replace(result._metadata, candidates=candidates))
