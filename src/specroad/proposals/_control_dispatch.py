"""Closed selection of existing control adapters; no generic control writer."""
from .values import require


def control_mode(operations):
    selected = any(op['op'] == 'proposal_control' for op in operations)
    if selected:
        require(len(operations) == 1 and
            ('review_start' in operations[0]) != ('review_decision' in operations[0]),
            'proposal_control_isolated_operation_required')
    return selected


def adapter(operations):
    require(control_mode(operations), 'proposal_control_operation_required')
    if 'review_decision' in operations[0]:
        from . import _decision_control as module
        return module.COMMAND, module.GATE, module.prepare_review_candidates, module.bind_review_authoring
    from . import _review_control as module
    return module.COMMAND, module.GATE, module.prepare_control_candidates, module.bind_control_authoring


def prepare_candidates(model, operations, **options):
    return adapter(operations)[2](model, operations, **options)


def bind_authoring(plan):
    return adapter(plan.data['operations'])[3](plan)
