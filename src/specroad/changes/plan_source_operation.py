"""Closed original-byte plan authoring operation in the common ChangePlan.

Stored operations are passive. Only the native plan authoring adapter may
publish them, after recompilation, complete current-source and writer checks.
"""
from ..model.canonical import canonical_json_bytes as jcs, canonical_json_sha256 as digest
from ..model.errors import ModelError
from ..storage.plan_markdown import parse_plan
from ._schema_fields import obj, arr, text
from .errors import ChangePlanError


def operation_schema():
    nullable_text = {'anyOf': [{'type': 'string'}, {'type': 'null'}]}
    return obj({'op': {'const': 'plan_edit'}, 'intent': {'type': 'object'},
        'sources': arr(obj({'path': text(), 'before': nullable_text, 'after': nullable_text})),
        'result_ids': arr(text())})


def sources(value, side):
    return tuple(parse_plan(row[side].encode('utf-8'), path=row['path'])
                 for row in value['sources'] if row[side] is not None)


def validate_operation(value, pointer=''):
    from ..model._schema import validate_builtin
    validate_builtin(value, operation_schema())
    paths = [row['path'] for row in value['sources']]
    if paths != sorted(set(paths)) or value['result_ids'] != sorted(set(value['result_ids'])):
        raise ChangePlanError('plan_source_operation_order', pointer=pointer)
    before, after = sources(value, 'before'), sources(value, 'after')
    old = {p.data['id']: p.data for s in before for p in s.projections}
    new = {p.data['id']: p.data for s in after for p in s.projections}
    changed = sorted(identity for identity, v in new.items() if old.get(identity) != v)
    if changed != value['result_ids']:
        raise ChangePlanError('plan_source_result_owners', pointer=pointer)
    if any(row['before'] is None and row['after'] is None for row in value['sources']):
        raise ChangePlanError('plan_source_empty_record', pointer=pointer)


def result_owners(value):
    return tuple(value['result_ids'])


def deleted_paths(operations):
    return sorted(row['path'] for op in operations if op['op'] == 'plan_edit'
                  for row in op['sources'] if row['after'] is None)


def preconditions(value):
    from hashlib import sha256
    return [({'kind': 'absent', 'path': row['path']} if row['before'] is None else
        {'kind': 'file', 'path': row['path'], 'expected_byte_sha256': sha256(row['before'].encode('utf-8')).hexdigest()})
        for row in value['sources']]


def prepare_operation(model, intent, *, actor, planned_at):
    from ..authoring.plan_operations import reduce_plan_intent
    target, changed = reduce_plan_intent(model.plan_sources, intent, actor=actor,
        planned_at=planned_at, id_prefix=model.configuration.id_prefix)
    before = {s.path: s.source_bytes for s in model.plan_sources}
    after = {s.path: s.source_bytes for s in target}
    operation = {'op': 'plan_edit', 'intent': intent, 'result_ids': sorted(v['id'] for v in changed),
        'sources': [{'path': p, 'before': None if p not in before else before[p].decode('utf-8'),
                    'after': None if p not in after else after[p].decode('utf-8')}
                    for p in sorted(before.keys() | after.keys())]}
    validate_operation(operation)
    return operation


def created_ids(value):
    from ..graph.plan_sources import records
    def identities(side):
        records_ = records(sources(value, side))
        return {r.identity.id for r in records_} | {e.identity.id for r in records_ for e in r.relations}
    return sorted(identities('after') - identities('before'))


def recompile(value, *, actor, planned_at, id_prefix):
    from ..authoring.plan_operations import reduce_plan_intent
    validate_operation(value)
    before = sources(value, 'before')
    target, changed = reduce_plan_intent(before, value['intent'], actor=actor,
        planned_at=planned_at, id_prefix=id_prefix)
    if {s.path: s.source_bytes for s in target} != {
            s.path: s.source_bytes for s in sources(value, 'after')}:
        raise ChangePlanError('plan_source_recompilation_mismatch')
    return target, changed


def check_envelope(value):
    operations = value['operations']
    if not any(op['op'] == 'plan_edit' for op in operations):
        return
    if len(operations) != 1:
        raise ChangePlanError('plan_source_specialist_sequence_required')
    op = operations[0]
    all_sources = sources(op, 'before') + sources(op, 'after')
    if not all_sources:
        raise ChangePlanError('plan_source_inventory_required')
    prefix = all_sources[0].projections[0].data['id'].split('-')[0]
    _, changed = recompile(op, actor=value['actor'], planned_at=value['planned_at'], id_prefix=prefix)
    if value['result_artifacts'] != [{'artifact': v, 'sha256': digest(v)} for v in changed]:
        raise ChangePlanError('plan_source_envelope_results')
    from hashlib import sha256
    preconditions = [({'kind': 'absent', 'path': row['path']} if row['before'] is None else
        {'kind': 'file', 'path': row['path'], 'expected_byte_sha256': sha256(row['before'].encode('utf-8')).hexdigest()})
        for row in op['sources']]
    if value['preconditions'] != preconditions:
        raise ChangePlanError('plan_source_precondition_binding')


def explanation_targets(value):
    before = {p.data['id']: p.data for source in sources(value, 'before') for p in source.projections}
    after = {p.data['id'] for source in sources(value, 'after') for p in source.projections}
    targets = set(value['result_ids']) | (before.keys() - after)
    if not targets:
        from ..authoring.plan_operations import _resolve
        targets.add(_resolve(before, value['intent']['target'], value['intent'].get('plan_id')))
    return sorted(targets)
