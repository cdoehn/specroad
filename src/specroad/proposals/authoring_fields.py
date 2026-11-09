"""Pure correspondence between explanations and the single native Change Plan."""
from .values import require


def validate_explanations(value, plan):
    if 'changes' not in value:
        return  # Historical passive originals do not become authoring inputs.
    changes = value['changes']
    require(len(changes) == len(plan.operations), 'proposal_explanation_count', pointer='/changes')
    identities = [row['change_id'] for row in changes]
    require(len(set(identities)) == len(identities), 'duplicate_proposal_change_id', pointer='/changes')
    for index, (row, operation) in enumerate(zip(changes, plan.operations)):
        pointer = '/changes/' + str(index)
        targets = list(operation.result_ids)
        if operation.op == 'representation_normalize':
            targets = [operation.data['path']]
        require(row['targets'] == targets, 'proposal_explanation_targets', pointer=pointer + '/targets')
        refs = row['requirement_or_issue_ids']
        require(len(set(refs)) == len(refs), 'duplicate_proposal_requirement',
                pointer=pointer + '/requirement_or_issue_ids')
        if value['created_by']['actor_type'] == 'ai':
            require(type(row['confidence']) in (int, float), 'proposal_confidence_required',
                    pointer=pointer + '/confidence')
