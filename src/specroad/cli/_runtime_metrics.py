"""Attach requested operational metrics without changing the command payload."""
from dataclasses import replace
from typing import Mapping

from .results import thaw


def attach_runtime_summary(outcome, command, consumption_call):
    report = consumption_call.finish()
    if command == 'environment.check' and isinstance(outcome.result, Mapping):
        policy = outcome.result.get('resource_policy')
        if isinstance(policy, Mapping) and isinstance(policy.get('effective_budgets'), Mapping):
            # The completed diagnosis also knows stable selected-project targets.
            report['effective_budgets'] = thaw(policy['effective_budgets'])
    report['observation_scope'] = 'parsed_command_through_result_assembly'
    report['includes_interpreter_start'] = False
    report['includes_result_delivery'] = False
    outcome = replace(outcome, details={**outcome.details, 'runtime': report})
    return outcome
