"""Deterministic plan intent reduction using original Markdown spans.

These candidates do not allocate identities or publish files. Creation IDs,
actor and time are explicit inputs, checked again by the native publisher.
"""
from copy import deepcopy
from string import Formatter

from ..model.audit import actor as parse_actor, new_artifact_audit
from ..model.audit_values import UtcTimestamp
from ..model.canonical import canonical_json_bytes as jcs
from ..model.plan_projection import PlanProjection
from ..model.plan_inventory import PlanProjectionInventory
from ..model.errors import ModelError
from ..storage.plan_authoring_edits import render_plan_sources
from ..changes.metadata_update import updated_audit_fields


from ..model.plan_command_ids import COMMANDS

CONTROLLED = frozenset(('id', 'id_scheme', 'schema_version', 'artifact_type',
    'revision', 'created_at', 'created_by', 'updated_at', 'updated_by', 'maturity',
    'parent_id', 'plan_id', 'children', 'parent_relation_id', 'implemented'))


def require(condition, reason):
    if not condition:
        raise ModelError(reason)


def commit_message(value):
    """A passive string, never a command, Git lookup or execution request."""
    template = value.get('commit_message_template', '{display_id} {title}')
    require(type(template) is str and '\0' not in template, 'invalid_plan_commit_template')
    try:
        parts = list(Formatter().parse(template))
    except ValueError as error:
        raise ModelError('invalid_plan_commit_template') from error
    fields = [field for _, field, _, _ in parts if field is not None]
    require('title' in fields and all(field in ('display_id', 'id', 'title', 'phase') for field in fields)
        and all(not spec and not conversion for _, _, spec, conversion in parts),
        'invalid_plan_commit_template')
    return template.format(**{name: value.get(name, '') for name in ('display_id', 'id', 'title', 'phase')})


def _resolve(values, identity, plan_id=None):
    require(type(identity) is str and bool(identity), 'plan_selector_required')
    if identity in values:
        selected = values[identity]
        require(plan_id is None or selected.get('plan_id', selected['id']) == plan_id,
                'plan_selector_owner_mismatch')
        return identity
    require(plan_id is not None, 'plan_display_selector_requires_owner')
    matches = [v['id'] for v in values.values()
               if v.get('plan_id', v['id']) == plan_id and v['display_id'] == identity]
    require(len(matches) == 1, 'plan_selector_missing_or_ambiguous')
    return matches[0]


def _subtree(values, identity):
    result, pending = [], [identity]
    while pending:
        item = pending.pop()
        require(item not in result and item in values, 'plan_target_cycle_or_missing')
        result.append(item)
        pending.extend(reversed(values[item]['children']))
    return result


def _groups(values, roots):
    return [[values[i] for i in _subtree(values, root)] for root in roots]


def _insert(values, identity, parent, position):
    children = values[parent]['children']
    require(type(position) is int and 0 <= position <= len(children), 'plan_position_out_of_bounds')
    children.insert(position, identity)


def _qualified_references(value):
    rows = list(value['prerequisites'])
    for claim in value.get('coverage_claims', []):
        rows.extend(claim['contributors'])
    return rows


def reduce_plan_intent(sources, intent, *, actor, planned_at, id_prefix, force_decisions=None):
    """Return all resulting carriers and their changed projections.

    A removal with remaining incoming references fails with their complete
    source/target inventory. An explicit cross-plan move updates all qualified
    references in the same original-byte inventory.
    """
    require(type(intent) is dict and set(intent) <= {'command_id', 'target', 'plan_id',
        'fields', 'parent_id', 'position', 'target_plan_id', 'subtree', 'new_id', 'parent_relation_id'},
        'invalid_plan_authoring_intent')
    command = intent.get('command_id')
    require(type(command) is str and command in COMMANDS, 'unknown_plan_authoring_command')
    shared = {'command_id', 'target', 'plan_id'}
    selected = {
        'plan.create': {'fields', 'new_id'},
        'plan.update': {'fields'}, 'plan.remove': {'subtree'},
        'plan.entry.add': {'fields', 'parent_id', 'position', 'new_id', 'parent_relation_id'},
        'plan.entry.update': {'fields'}, 'plan.entry.remove': {'subtree'},
        'plan.entry.move': {'target_plan_id', 'parent_id', 'position'},
        'plan.entry.check': set(), 'plan.entry.uncheck': set(),
    }[command]
    require(set(intent) <= (shared | selected), 'unexpected_plan_authoring_option')
    if command == 'plan.create':
        require(not set(intent) & {'target', 'plan_id'}, 'unexpected_plan_authoring_option')
    actor = parse_actor(actor).as_fields()
    UtcTimestamp(planned_at)
    before = {p.data['id']: p.data for source in sources for p in source.projections}
    require(sum(len(s.projections) for s in sources) == len(before), 'duplicate_artifact_id')
    values = deepcopy(before)
    roots = [s.projections[0].data['id'] for s in sources]
    fields = intent.get('fields', {})
    require(type(fields) is dict, 'plan_fields_object_required')
    if set(fields) & CONTROLLED:
        if force_decisions is None:
            require(False, 'controlled_plan_authoring_field')
        else:
            force_decisions.decide(False, gate_id='schema:controlled_plan_authoring_field',
                diagnostic_code='CORE_MODEL', subject=intent.get('target', intent.get('new_id', 'plan')),
                operation=command, observed_binding=sorted(set(fields) & CONTROLLED),
                requested_binding=fields, effect='apply_explicit_plan_fields')
    target = None
    if command != 'plan.create':
        target = _resolve(values, intent.get('target'), intent.get('plan_id'))
        require((values[target]['artifact_type'] == 'implementation_plan') ==
                (command in ('plan.update', 'plan.remove', 'plan.entry.add')),
                'plan_authoring_target_type')
    created = set()
    if command in ('plan.create', 'plan.entry.add'):
        identity = intent.get('new_id')
        require(type(identity) is str and identity not in values, 'plan_creation_identity_collision')
        kind = 'implementation_plan' if command == 'plan.create' else 'plan_entry'
        value = {'schema_version': '0.3.0', 'id': identity, 'id_scheme': 'random128-v1',
            'artifact_type': kind, 'maturity': 'draft', 'relations': [], 'extensions': {},
            'description': '', 'prerequisites': [], 'children': [], **deepcopy(fields),
            **new_artifact_audit(actor=parse_actor(actor), planned_at=UtcTimestamp(planned_at)).as_fields()}
        if kind == 'implementation_plan':
            value.update(format='plan-markdown-v1', coverage_claims=fields.get('coverage_claims', []))
            roots.append(identity)
        else:
            parent = _resolve(values, intent.get('parent_id', target), target)
            value.update(plan_id=target, parent_id=parent, implemented=False,
                parent_relation_id=intent.get('parent_relation_id'),
                requirement_bindings=fields.get('requirement_bindings', []))
            _insert(values, identity, parent, intent.get('position', len(values[parent]['children'])))
        values[identity] = value
        created.add(identity)
    elif command in ('plan.update', 'plan.entry.update'):
        values[target].update(deepcopy(fields))
    elif command in ('plan.entry.check', 'plan.entry.uncheck'):
        require(not fields, 'unexpected_plan_authoring_fields')
        values[target]['implemented'] = command.endswith('.check')
    elif command in ('plan.remove', 'plan.entry.remove'):
        require(not fields and type(intent.get('subtree', False)) is bool, 'invalid_plan_remove_options')
        require(not values[target]['children'] or intent.get('subtree') is True, 'plan_subtree_selection_required')
        removed = set(_subtree(values, target))
        if target in roots:
            roots.remove(target)
        else:
            values[values[target]['parent_id']]['children'].remove(target)
        for identity in removed:
            del values[identity]

    else:
        require(not fields, 'unexpected_plan_authoring_fields')
        moved = _subtree(values, target)
        destination = intent.get('target_plan_id')
        require(type(destination) is str and destination in roots, 'plan_move_destination_required')
        require('position' in intent, 'plan_move_position_required')
        parent = _resolve(values, intent.get('parent_id'), destination)
        require(parent in values and parent not in moved, 'plan_move_parent_invalid')
        new_plan = values[parent].get('plan_id', parent)
        old_plan = values[target]['plan_id']
        values[values[target]['parent_id']]['children'].remove(target)
        _insert(values, target, parent, intent.get('position', len(values[parent]['children'])))
        values[target]['parent_id'] = parent
        for identity in moved:
            values[identity]['plan_id'] = new_plan
        if old_plan != new_plan:
            for value in values.values():
                for ref in _qualified_references(value):
                    if ref['entry_id'] in moved:
                        require(ref['plan_id'] == old_plan, 'plan_reference_owner_mismatch')
                        ref['plan_id'] = new_plan
    require(len({v['id'] for group in _groups(values, roots) for v in group}) == len(values),
            'plan_target_ownership_invalid')
    if force_decisions is not None:
        from ..force import ForceDecisions
        require(type(force_decisions) is ForceDecisions and force_decisions.request.requested,
                'explicit_force_required')
        from ..changes.force_domain_gates import record_denial
        checks = [lambda value=value: PlanProjection(value, id_prefix=id_prefix) for value in values.values()]
        checks.append(lambda: PlanProjectionInventory(list(values.values()), id_prefix=id_prefix))
        for check in checks:
            try:
                check()
            except ModelError as error:
                record_denial(force_decisions, error, operation=command, subject=target or intent['new_id'], requested=intent)
        for identity, value in values.items():
            if identity not in created and value != before[identity]:
                from ..changes._lifecycle_policy import _postconditions
                try:
                    _postconditions(before, {identity: deepcopy(value), **{k: v for k, v in values.items() if k != identity}},
                        {identity: [0]}, [], 'plan_edit')
                except ModelError as error:
                    record_denial(force_decisions, error, operation=command, subject=identity, requested=intent)
                value.update(updated_audit_fields(before[identity], actor=actor, planned_at=planned_at))
        return render_plan_sources(sources, _groups(values, roots), id_prefix=id_prefix, raw_targets=True), []
    for value in values.values():
        PlanProjection(value, id_prefix=id_prefix)
        if value.get('entry_kind') == 'commit' or 'commit_message_template' in value:
            commit_message(value)
    PlanProjectionInventory(list(values.values()), id_prefix=id_prefix)
    # Rendering may add the mandatory LF separating a former EOF body from
    # a new following section. Bind this actual projection, not a guessed one.
    first = render_plan_sources(sources, _groups(values, roots), id_prefix=id_prefix)
    actual = {p.data['id']: p.data for source in first for p in source.projections}
    require(set(actual) == set(values), 'plan_unrequested_projection_change')
    for identity, value in actual.items():
        expected = values[identity]
        different = {k for k in value.keys() | expected.keys() if value.get(k) != expected.get(k)}
        require(not different or (different == {'description'} and
            value['description'] == expected['description'] + '\n'), 'plan_unrequested_projection_change')
        if identity not in created and jcs(value) != jcs(before[identity]):
            from ..changes._lifecycle_policy import _postconditions
            _postconditions(before, actual, {identity: [0]}, [], 'plan_edit')
            value = actual[identity]
            value.update(updated_audit_fields(before[identity], actor=actor, planned_at=planned_at))
    final = render_plan_sources(first, _groups(actual, roots), id_prefix=id_prefix)
    require({p.data['id']: p.data for s in final for p in s.projections} == actual,
            'plan_unrequested_projection_change')
    changed = [v for identity, v in sorted(actual.items()) if identity not in before or jcs(v) != jcs(before[identity])]
    return final, changed
