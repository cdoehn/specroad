"""Shared native authoring checks; original behavior preserved."""
from ..changes import AuthoringError
from ..model.canonical import canonical_json_sha256 as digest
from ..model.relation_identity import allocate_relation_identity, relation_identity


def _remove_section(data,sources,actor,time,old):
    from ..changes.lifecycle_inputs import normalize_retire_input
    from ._document_mutations import _removal_inventory, _section_removal
    from ._document_operations import _reparent
    cascade=data.get('cascade',False);destination=data.get('move_children_to')
    if (type(cascade) is not bool or cascade and destination is not None
            or ('position' in data) != (destination is not None)):
        raise AuthoringError('document_removal_strategy_conflict')
    guards={k:data[k] for k in ('expected_revision','expected_sha256') if k in data}
    if old is not None:
        first={'op':'retire','target':data['target'],'reason':data['reason'],**guards}
        if cascade:
            if any(op['op']!='retire' for op in old):raise AuthoringError('request_operations_conflict',exit_code=6)
            return [first,*({**op,'reason':data['reason']} for op in old[1:])]
        if destination is None:
            if len(old)!=1:raise AuthoringError('request_operations_conflict',exit_code=6)
            return [first]
        result=[first]
        for index in range(1,len(old),2):
            removal,addition=old[index:index+2]
            result.extend(_reparent(data['target'],removal['relation_id'],addition['relation']['target'],
                parent_id=destination,relation_identity=relation_identity(addition['relation']),
                position=data['position']+(index-1)//2,expected_relation_sha256=removal['expected_sha256'],
                reason=data['reason'],actor=actor,planned_at=time))
        return result
    index,children,descendants=_removal_inventory(sources.model,data['target'])
    first=normalize_retire_input(index[data['target']],reason=data['reason'],**guards)
    retirements=[normalize_retire_input(index[i],expected_revision=index[i]['revision'],
        expected_sha256=digest(index[i]),reason=data['reason']) for i in descendants[1:]] if cascade else []
    moves=[];inventory=sources.relations
    if destination is not None:
        for position,edge in enumerate(children[data['target']]):
            allocation=allocate_relation_identity(inventory);inventory=allocation.inventory
            moves.append(dict(target=edge['target'],relation_identity=allocation.identity,
                position=data['position']+position,expected_relation_sha256=digest(edge)))
    return _section_removal(sources.model,first,cascade=cascade,move_children_to=destination,
        child_retirements=retirements,child_moves=moves,actor=actor,planned_at=time)[1]
