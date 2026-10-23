"""Passive import execution reports, separate from planning and publication.

These projections perform no I/O, authorization or recovery. Only the shared
native writer supplies execution evidence; an assessed plan remains passive.
"""
from ..model.errors import ModelError
from ..security import SafetyViolation


def _submitted_plan(report):
    return {'submitted_import_plan': None if report is None else report.data,
        'submitted_import_plan_sha256': None if report is None else report.sha256}


def execution_result(report, execution):
    return {'format_version': 'artifact-import-execution-v1',
        **_submitted_plan(report), 'execution': execution,
        'input_parsed': False, 'approval_granted': False}


def failed_execution(report, error, *, entered_writer):
    if isinstance(error, ModelError):
        diagnostic = error.diagnostic()
        exit_code = getattr(error, 'exit_code', 3)
    elif isinstance(error, SafetyViolation):
        diagnostic = {'reason': 'unsafe_import_execution'}
        exit_code = 7
    else:
        # OS messages may contain submitted paths or source contents.
        diagnostic = {'reason': 'import_execution_io_failure'}
        exit_code = 5
    state = diagnostic.get('write_state', 'unknown') if entered_writer else 'not_committed'
    if state not in ('not_committed', 'committed', 'unknown'):
        state = 'unknown'
    return {'format_version': 'artifact-import-execution-v1',
        'status': 'failed', 'exit_code': exit_code, **_submitted_plan(report),
        'execution': None, 'failure_phase': 'native_execution' if entered_writer else 'import_planning',
        'write_state': state, 'diagnostics': [diagnostic],
        'current_target_verified': False,
        'recovery_required': (diagnostic.get('recovery_required', state == 'unknown')
                              if entered_writer else False),
        'retry_safe': False, 'automatic_retry': False, 'automatic_rollback': False,
        'input_parsed': False, 'approval_granted': False}
