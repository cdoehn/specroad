"""Read-only adapters preserving the native lock/recovery observation schemas."""
from .registry import CommandClass, CommandSpec, EffectScope, OptionSpec, PreflightProfile
from .contracts import CommandProtocol, WorkContract
from .results import CommandResult, OperationFailure, FailureKind


def metadata_command(invocation):
    from ..model.errors import ModelError
    from ..security import ProjectBoundary, SafetyViolation
    from ..storage.json_syntax import parse_json_object
    from ..changes.locking import inspect_project_lock
    from ..changes.recovery_read import inspect_recovery
    from ..query._read_errors import read_failure, read_details
    command = invocation.command.command_id
    try:
        boundary = ProjectBoundary(invocation.resolved.project_root)
        configuration = boundary.read_bytes('specroad.json')
        project_id = parse_json_object(configuration).get('project_id')
        project_id = project_id if type(project_id) is str and project_id else None
        reader = inspect_project_lock if command == 'lock.status' else inspect_recovery
        result = reader(boundary.root, expected_project_id=project_id).data
        if boundary.read_bytes('specroad.json') != configuration:
            raise OperationFailure(FailureKind.CONFLICT, 'Project metadata changed during observation.')
        boundary._check_root()
        from .result_schemas import validate_result_document
        validate_result_document(invocation.command.protocol.result_schema, result)
        return CommandResult(command, result=result, details=read_details(),
            project={'project_root': str(boundary.root), 'project_id': project_id})
    except (OperationFailure, ModelError, SafetyViolation, OSError) as error:
        return read_failure(command, error, None, read_details())


def metadata_commands():
    return tuple(CommandSpec(command_id=family + '.status', words=(family, 'status'),
        command_class=CommandClass.READ_ONLY, preflight_profile=PreflightProfile.PROJECT_METADATA,
        effect_scope=EffectScope.NONE, requires_project=True, handler=metadata_command,
        options=(OptionSpec('--project', takes_value=True),
            OptionSpec('--format', takes_value=True, choices=('pretty', 'json')),
            OptionSpec('--quiet'), OptionSpec('--no-color')),
        protocol=CommandProtocol(schema, {'command_id': family + '.status'},
            handler_exit_codes=(0, 2, 3, 4, 5, 6, 7),
            diagnostic_codes=('CORE_ENVIRONMENT', 'CORE_SECURITY', 'CORE_CONFLICT', 'CORE_MODEL'),
            work=WorkContract('operational_metadata', ('runtime_metadata',))))
        for family, schema in (('lock', 'project-lock-v1'), ('recover', 'recovery-status-v1')))
