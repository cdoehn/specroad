"""One renderer-independent result projection for native Force writers."""
from ..diagnostics import Diagnostic
from .results import CommandResult


def result(command, value, *, payload=None):
    diagnostics = tuple(Diagnostic(d.get('code') or 'CORE_MODEL', d.get('severity', 'error'),
        d.get('reason') or 'force_target_diagnostic', d.get('reason') or 'Target validation finding',
        path=d.get('path')) for d in value['diagnostics'])
    from .results import ResultStatus
    return CommandResult(command, status=ResultStatus(value['status']), result=value if payload is None else payload, force=value['force'],
        validation_status=value['validation_status'], diagnostics=diagnostics)


def proposal_command(invocation):
    from ..proposals.force import author
    options = invocation.options
    revision = options['--expected-revision']
    from ..changes.write_guard_values import require
    require(type(revision) is str and revision.isascii() and revision.isdecimal(),
        'proposal_expected_revision_required', exit_code=2)
    value = _invoke(author, invocation.resolved.project_root, invocation.arguments['proposal'],
        command=invocation.command.command_id, expected_revision=int(revision),
        actor=dict(actor_type=options['--actor-type'], actor_id=options['--actor-id']),
        request_id=options.get('--request-id'), decision=options.get('--decision'), comment=options.get('--comment'),
        dry_run=options.get('--dry-run', False), authority=invocation.publication_authority,
        services=invocation.restore_services, force=True, force_reason=options.get('--force-reason'),
        cwd=invocation.resolved.working_directory, checked_work=options.get('--checked-work'))
    return result(invocation.command.command_id, value)


def schema():
    from .result_schemas import _object, _nullable, _array
    sha = {'type': 'string', 'pattern': r'^[0-9a-f]{64}(?![\s\S])'}
    text = {'type': 'string', 'minLength': 1}
    flag = {'type': 'boolean'}
    return _object({'format_version': {'const': 'force-authoring-execution-v1'},
        'command_id': text, 'status': {'enum': ['success', 'forced']}, 'exit_code': {'const': 0},
        'dry_run': flag, 'replayed': flag, 'complete': {'const': True},
        'write_state': {'enum': ['not_committed', 'committed']}, 'plan_sha256': sha,
        'operations_sha256': sha, 'target_model_root_sha256': _nullable(sha),
        'validation_status': {'enum': ['valid', 'invalid', 'unknown']},
        'force': _object({'requested': {'const': True}, 'used': flag, 'reason': _nullable(text),
            'overrides': _array(_object({'gate_id': text, 'diagnostic_code': text, 'subject': text,
                'original_decision': {'enum': ['denied', 'unknown']}, 'operation': text,
                'observed_binding': True, 'requested_binding': True, 'effect': text}))}),
        'report': {'type': 'object'}, 'diagnostics': _array({'type': 'object'}),
        'completion': _nullable({'type': 'object'}), 'approval_granted': {'const': False},
        'audit': {'type': 'object'}})


def _invoke(callback, *args, **options):
    from ..model.errors import ModelError
    from ..bundles.errors import BundleError
    from ..security import SafetyViolation
    from .results import OperationFailure, FailureKind
    try:
        return callback(*args, **options)
    except (ModelError, BundleError, SafetyViolation, OSError) as error:
        code = 7 if isinstance(error, SafetyViolation) else 5 if isinstance(error, OSError) else error.exit_code
        raise OperationFailure(FailureKind(code), getattr(error, 'reason', 'force_io_failure'),
            details={'authoring_attempt': getattr(error, 'authoring_attempt', None)}) from error
