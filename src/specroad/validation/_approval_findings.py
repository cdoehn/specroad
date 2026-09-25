"""Common structured finding projection, independent of gate execution."""
from ..diagnostics import Diagnostic

def _finding(context, reason, *, pointer='', code='SRV030', path=None, origin='core_rule'):
    return {'reason':reason, 'diagnostic':Diagnostic(code,'error','approval',
        'Requirement approval prerequisite not satisfied.', artifact_id=context.requirement_id,
        path=path, location={'pointer':pointer}, rationale=reason, origin=origin).as_dict()}
