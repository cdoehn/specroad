"""Attempt evidence only; never an assertion of successful recovery."""
from functools import wraps
from ..model.errors import ModelError
from ..security import SafetyViolation
from .plans import _audit


def audited(function):
    @wraps(function)
    def run(root, intent, **options):
        attempt = {'plan': None, 'publication_started': False}
        try:
            return function(root, intent, _attempt=attempt, **options)
        except (ModelError, SafetyViolation, OSError) as error:
            diagnostic = error.diagnostic() if isinstance(error, ModelError) else {}
            state = diagnostic.get('write_state', 'unknown' if attempt['publication_started'] else 'not_committed')
            if state not in ('committed', 'not_committed', 'unknown'):
                state = 'unknown'
            plan = attempt['plan']
            command = intent.get('command_id') if type(intent) is dict else None
            audit = {} if plan is None else _audit(plan, command,
                dry_run=options.get('dry_run', False), write_state=state)
            planned_ids = audit.pop('created_ids', None)
            target = audit.pop('target_model_root_sha256', None)
            error.authoring_attempt = {**audit, 'format_version': 'authoring-audit-v1',
                'command_id': command, 'audit_scope': 'failed_plan_attempt',
                'write_state': state, 'planned_created_ids': planned_ids,
                'expected_model_root_sha256': target, 'outcome': 'failed',
                'current_target_verified': False, 'retry_safe': False,
                'recovery_required': diagnostic.get('recovery_required', state == 'unknown'),
                'automatic_retry': False, 'automatic_rollback': False, 'approval_granted': False}
            if 'force' in attempt:
                error.authoring_attempt.update(force=attempt['force'],
                    validation_status=attempt['validation_status'], force_report=attempt['force_report'])
            raise
    return run
