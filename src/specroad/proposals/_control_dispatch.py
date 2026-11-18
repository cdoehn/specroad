"""Closed selection of existing control adapters; no generic control writer."""
from .values import require


def control_mode(operations):
    from ._change_control import change_mode
    if change_mode(operations):
        return True
    from ._create_control import creation_mode
    if creation_mode(operations):
        return True
    selected = any(op['op'] == 'proposal_control' for op in operations)
    if selected:
        from ._apply_control import apply_mode
        if apply_mode(operations):
            return True
        require(len(operations) == 1 and
            ('review_start' in operations[0]) != ('review_decision' in operations[0]),
            'proposal_control_isolated_operation_required')
    return selected


def adapter(operations):
    require(control_mode(operations), 'proposal_control_operation_required')
    from . import _change_control
    if _change_control.change_mode(operations):
        return ('proposal.change.' + operations[0]['action'], _change_control.GATE,
                _change_control.prepare_change_candidates, _change_control.bind_change_authoring)
    from . import _create_control
    if _create_control.creation_mode(operations):
        return (_create_control.COMMAND, _create_control.GATE,
                _create_control.prepare_create_candidates, _create_control.bind_create_authoring)
    from . import _apply_control
    if _apply_control.apply_mode(operations):
        return (_apply_control.COMMAND, _apply_control.GATE,
                _apply_control.prepare_apply_candidates, _apply_control.bind_apply_authoring)
    if 'review_decision' in operations[0]:
        from . import _decision_control as module
        return module.COMMAND, module.GATE, module.prepare_review_candidates, module.bind_review_authoring
    from . import _review_control as module
    return module.COMMAND, module.GATE, module.prepare_control_candidates, module.bind_control_authoring


def prepare_candidates(model, operations, **options):
    return adapter(operations)[2](model, operations, **options)


def bind_authoring(plan):
    return adapter(plan.data['operations'])[3](plan)
