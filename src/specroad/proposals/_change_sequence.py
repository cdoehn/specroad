"""Pure exact sequence reconstruction; no entropy, host callbacks or writes."""
from ..changes import ChangePlan
from ..model.canonical import canonical_json_bytes
from .change_order import ProposalChanges
from .values import require


def changed_sequence(before, operation):
    from ._change_control import change_record
    after = change_record(operation)
    changes = ProposalChanges(before)
    plan = ChangePlan(canonical_json_bytes(after.data['change_plan']))
    ids = operation['changed_change_ids']
    if not ids:
        require(operation['action'] in ('update', 'move') and bool(changes.changes)
            and canonical_json_bytes(after.data) == canonical_json_bytes(before.data), 'proposal_noop_record_changed')
        return changes
    identity = ids[0]
    action = operation['action']
    rows = after.data['changes']
    if action == 'remove':
        result = changes.remove(identity, change_plan=plan)
    else:
        positions = [index for index, row in enumerate(rows) if row['change_id'] == identity]
        require(len(positions) == 1, 'proposal_changed_ids_invalid')
        index = positions[0]
        if action == 'move':
            result = changes.move(identity, index, change_plan=plan)
        elif action == 'update':
            result = changes.update(identity, change_plan=plan, explanation={
                key: value for key, value in rows[index].items() if key not in ('change_id', 'targets')})
        else:
            require(identity not in changes.change_ids
                and len(rows) == len(changes.changes) + 1,
                'proposal_change_order_mismatch')
            expected_rows = changes.changes
            expected_ops = changes.change_plan.data['operations']
            require(len(plan.operations) == len(expected_ops) + 1,
                    'proposal_change_order_mismatch')
            expected_rows.insert(index, rows[index])
            expected_ops.insert(index, plan.operations[index].data)
            # _replace checks the complete order, target IDs, explanations and
            # unchanged basis. Unlike add(), it does not draw fresh entropy.
            result = changes._replace(plan, expected_rows, expected_ops, (identity,))
    require(canonical_json_bytes(result.changes) == canonical_json_bytes(rows) and result.changed_change_ids == tuple(ids),
            'proposal_change_order_mismatch')
    return result
