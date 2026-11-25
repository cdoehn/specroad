"""Concrete section retirement/reparenting, preserving explicit selection."""
from ..changes.write_guard_values import require
from ..model.canonical import canonical_json_sha256 as digest


def remove(sources, data, actor, time):
    root = data['target']; sources.artifact(root)
    cascade = data.get('cascade', False); destination = data.get('move_children_to')
    require(type(cascade) is bool and not (cascade and destination is not None),
        'section_removal_selection_required', exit_code=2)
    selected = []; pending = [root]
    operations = []
    while pending:
        identity = pending.pop()
        if identity in selected: continue
        selected.append(identity)
        _, value = sources.artifact(identity)
        children = [r for r in value.get('relations', []) if r.get('type') == 'contains']
        if children and not cascade:
            require(destination is not None, 'section_removal_children_selection_required', exit_code=2)
            sources.artifact(destination)
            require(destination != identity, 'section_removal_destination_required', exit_code=2)
            for offset, child in enumerate(sorted(children, key=lambda e: (e.get('position', 0), e['relation_id']))):
                operations.append(dict(op='relation_remove', source=identity, relation_id=child['relation_id'],
                    expected_sha256=digest(child), reason=data['reason']))
                edge = {**child, **sources.relation().as_fields(), 'created_at': time, 'created_by': actor,
                    'position': data.get('position', 0) + offset}
                operations.append(dict(op='relation_add', source=destination, relation=edge))
        if cascade: pending.extend(r['target'] for r in reversed(children))
        operations.append(dict(op='retire', target=identity, reason=data['reason'],
            **({k: data[k] for k in ('expected_revision', 'expected_sha256') if k in data} if identity == root else {})))
    return operations
