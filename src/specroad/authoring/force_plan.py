"""Native Markdown target bytes, independent of a positive semantic verdict."""
from copy import deepcopy
from ..changes.write_guard_values import require
from ..changes.force_domain_gates import record_denial
from ..model.errors import ModelError


def target_plan(sources, intent, actor, time, decisions):
    from ..storage.plan_markdown import parse_plan
    from ..model.paths import classify_path, PathClass
    originals = tuple(parse_plan(raw, path=path, id_prefix=sources.configuration.id_prefix)
        for path, raw in sorted(sources.before.items())
        if classify_path(path, sources.configuration) is PathClass.PLAN)
    compiled = deepcopy(intent)
    require(not {'new_id', 'parent_relation_id'} & intent.keys(), 'plan_creation_ids_are_native', exit_code=2)
    if intent['command_id'] in ('plan.create', 'plan.entry.add'):
        kind = 'implementation_plan' if intent['command_id'] == 'plan.create' else 'plan_entry'
        compiled['new_id'] = sources.allocate(kind).id
        if kind == 'plan_entry': compiled['parent_relation_id'] = sources.relation().id
    from .plan_operations import reduce_plan_intent
    try:
        reduce_plan_intent(originals, compiled, actor=actor, planned_at=time,
            id_prefix=sources.configuration.id_prefix)
    except ModelError as error:
        record_denial(decisions, error, operation=intent['command_id'], subject=intent.get('target', 'plan'), requested=intent)
    rows, _ = reduce_plan_intent(originals, compiled, actor=actor, planned_at=time,
        id_prefix=sources.configuration.id_prefix, force_decisions=decisions)
    target = {p: b for p, b in sources.before.items() if p not in {s.path for s in originals}}
    target.update(rows)
    if sources.native is not None:
        try:
            from .native_plan import _prepared
            # Observe prerequisite/coverage/command policies on the same
            # actual plan target; no second allocator or alternate target.
            from ..changes._target_materialization import materialize_target
            from ..validation import ModelDocument
            from ..changes.plan_source_operation import prepare_operation
            from ._plan_checks import _check_command
            operation = prepare_operation(sources.model, compiled, actor=actor, planned_at=time)
            model = materialize_target(sources.model, tuple(ModelDocument(p, b) for p, b in rows), replace_plan_sources=True)
            _check_command(sources.model, model, operation)
        except ModelError as error:
            record_denial(decisions, error, operation=intent['command_id'], subject=intent.get('target', 'plan'), requested=intent)
    return target
