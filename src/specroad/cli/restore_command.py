"""Public Restore boundary with fresh host authority and native error contracts."""
from ._restore_adapter import run_restore
from ._restore_options import RESTORE_OPTIONS, restore_request
from .requests import CommandRequest
from .results import CommandResult, FailureKind, OperationFailure
from .result_schemas import validate_result_document
from ..recovery.values import RestoreError, RestorePlan
from ..recovery._owned_checks import owned_checks


@owned_checks
def restore_command(invocation):
    # Display/runtime options never enter the saved recovery order or authority.
    flags = {option.flag for option in RESTORE_OPTIONS}
    request = CommandRequest('recover.restore',
        {key: value for key, value in invocation.options.items() if key in flags})
    try:
        request = restore_request(request)
        if ('--work-dir' in invocation.options or any(key in invocation.options for key in
            ('--step-cpu-ms', '--step-wall-ms', '--cpu-budget-ms', '--wall-budget-ms'))
                or invocation.options.get('--resource-profile') == 'constrained'):
            from .work_handler import start_restore_work
            return start_restore_work(invocation, request)
        result = run_restore(request, authority=invocation.recovery_authority,
                             services=invocation.restore_services)
        if type(result) is RestorePlan:
            value = {'format_version': 'restore-command-v1', 'mode': 'plan',
                'restore_plan': result.data, 'execution': None,
                'plan_file': {'root': request.options['--output-root'],
                    'path': request.options['--output'], 'size': len(result.source_bytes),
                    'sha256': result.sha256},
                'history_assessments': list(result.history_assessments)}
        else:
            native = result.data
            if native['result'] != 'restored' or native['recovery_required']:
                raise OperationFailure(FailureKind.ENVIRONMENT,
                    'Restore recovery did not restore the project.',
                    details={'restore': native, 'recovery_required': True})
            value = {'format_version': 'restore-command-v1', 'mode': 'execute',
                'restore_plan': None, 'execution': native, 'plan_file': None,
                'history_assessments': native['historical_findings']}
        validate_result_document('restore-command-v1', value)
        return CommandResult('recover.restore', result=value)
    except RestoreError as error:
        raise OperationFailure(FailureKind(error.exit_code), error.reason,
                               details=error.diagnostic()) from error
