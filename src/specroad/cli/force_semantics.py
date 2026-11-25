"""Complete negative read observations may overrule exit policy, not evidence."""
from dataclasses import replace
from ..force import ForceDecisions
from .results import ResultStatus, thaw


def completed_policy(invocation, outcome, decisions):
    # Semantic fail-on is evaluated after the real reader finished. Interrupted
    # work, missing inputs, I/O and unavailable engines are never made complete.
    if (not decisions.request.requested or not outcome.complete or outcome.exit_code != 1
            or not (invocation.command.command_class.value == 'read_only' or
                invocation.command.command_id.startswith('analyzer.') and
                invocation.command.command_class.value == 'generated_output')):
        return outcome
    command = invocation.command.command_id
    payload = thaw(outcome.result)
    decisions.decide(False, gate_id=('analyzer_policy' if command.startswith('analyzer.') else 'schema') + ':fail_on',
        diagnostic_code='CORE_MODEL', subject=command, operation=command,
        observed_binding={'exit_code': outcome.exit_code, 'diagnostics': [d.as_dict() for d in outcome.diagnostics],
            'result': payload}, requested_binding=decisions.request.data,
        effect='return_completed_negative_observation_without_passing_check')
    return replace(outcome, status=ResultStatus.FORCED, failure=None,
        force=decisions.summary, validation_status='invalid')
