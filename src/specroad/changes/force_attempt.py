"""Preserve an actual failed Force attempt without claiming completion."""
from functools import wraps
from ..model.errors import ModelError
from ..bundles.errors import BundleError
from ..security import SafetyViolation
from .values import ChangePlan


def audited(function):
    @wraps(function)
    def run(root, value, **options):
        attempt = options.pop('_attempt', None)
        if attempt is None:
            attempt = {'plan': None, 'publication_started': False}
        if type(value) is ChangePlan:
            attempt['plan'] = value
        attempt.setdefault('validation_status', 'unknown')
        attempt.setdefault('force_report', None)
        command = options.get('_command_id', options.get('command'))
        if command is None and type(value) is dict:
            command = value.get('command_id')
        try:
            return function(root, value, _attempt=attempt, **options)
        except (ModelError, BundleError, SafetyViolation, OSError) as error:
            diagnostic = error.diagnostic() if isinstance(error, ModelError) else {}
            state = diagnostic.get('write_state',
                'unknown' if attempt['publication_started'] else 'not_committed')
            if state not in ('not_committed', 'committed', 'unknown'):
                state = 'unknown'
            plan = attempt['plan']
            facts = dict(format_version='force-failed-attempt-v1', command_id=command,
                plan=None if plan is None else plan.data,
                plan_sha256=None if plan is None else plan.sha256,
                write_state=state, outcome='failed', current_target_verified=False,
                retry_safe=False, automatic_retry=False, automatic_rollback=False,
                recovery_required=diagnostic.get('recovery_required', state == 'unknown'),
                approval_granted=False)
            if 'decisions' in attempt:
                attempt['force'] = attempt['decisions'].summary
            if 'force' in attempt:
                facts.update(force=attempt['force'], validation_status=attempt['validation_status'],
                    force_report=attempt['force_report'])
            error.authoring_attempt = facts
            raise
    return run
