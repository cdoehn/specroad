"""Shared native authoring checks; original behavior preserved."""
from ..model.errors import ModelError
from ..model.canonical import canonical_json_bytes


def _check_command(before, after, operation):
    old = {v['id']: v for v in before.artifacts}
    new = {v['id']: v for v in after.artifacts}
    removed = old.keys() - new.keys()
    # The complete shared reference validator checks all target types. Preserve
    # a complete incoming inventory for callers of a destructive command too.
    impact = []
    from ..migration.model_inputs import records
    for record in records(after):
        if record.identity.id in removed:
            continue
        for edge in record.relations:
            if edge.target in removed:
                impact.append({'source_id': record.identity.id, 'target_id': edge.target,
                               'relation_id': edge.identity.id})
    if impact:
        error = ModelError('plan_remove_open_impact')
        error.impact = sorted(impact, key=canonical_json_bytes)
        raise error
    if operation['intent']['command_id'] != 'plan.entry.check':
        return
    from .plan_operations import _resolve
    selected = _resolve({i:v for i,v in old.items() if v['artifact_type'] in ('implementation_plan','plan_entry')},
        operation['intent']['target'], operation['intent'].get('plan_id'))
    # All explicit prerequisites, including the owning plan, are AND inputs.
    # Optional subtrees are excluded only when computing a parent's mandatory
    # leaves, never when the optional node is explicitly referenced.
    def leaves(identity, active):
        if identity in active or identity not in old:
            raise ModelError('plan_prerequisite_cycle_or_missing')
        value = old[identity]
        if value['children']:
            result = []
            for child in value['children']:
                if old[child].get('required', True):
                    result.extend(leaves(child, active | {identity}))
            return result
        if value.get('entry_kind') == 'stage' or value['artifact_type'] == 'implementation_plan':
            return []
        return [value['implemented']]
    def ready(identity, active):
        if identity in active or identity not in old:
            raise ModelError('plan_prerequisite_cycle_or_missing')
        value = old[identity]
        refs = list(value['prerequisites'])
        if value['artifact_type'] == 'plan_entry':
            refs += old[value['plan_id']]['prerequisites']
        for child in value['children']:
            if old[child].get('required', True):
                ready(child, active | {identity})
        for ref in refs:
            target = ref['entry_id']
            ready(target, active | {identity})
            completed = leaves(target, set())
            if not completed or not all(completed):
                raise ModelError('plan_prerequisite_unmet')
    ready(selected, set())
