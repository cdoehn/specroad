"""Read project configuration/defaults and resolved option provenance only.

Profile selectors remain selectors: this observation does not load the model,
validate a profile composition or treat it as release/authoring authority.
"""
from hashlib import sha256
from .contracts import CommandClass, CommandSpec, EffectScope, PreflightProfile, CommandProtocol, WorkContract
from .options import global_options
from .parameters import OptionSpec
from .results import CommandResult, OperationFailure, FailureKind


from .config_values import configuration_view


def config_show(invocation):
    from ..model.configuration import ProjectConfiguration
    from ..model.errors import ModelError
    from ..security import ProjectBoundary, SafetyViolation
    from ..storage.json_syntax import parse_json_object
    from ..query._read_errors import read_failure, read_details
    try:
        boundary = ProjectBoundary(invocation.resolved.project_root)
        raw = boundary.read_bytes('specroad.json')
        configuration = ProjectConfiguration(parse_json_object(raw))
        result = configuration_view(configuration, invocation.resolved)
        result['source_sha256'] = sha256(raw).hexdigest()
        if boundary.read_bytes('specroad.json') != raw:
            raise OperationFailure(FailureKind.CONFLICT, 'Configuration changed during observation.')
        boundary._check_root()
        from .result_schemas import validate_result_document
        validate_result_document('config-show-v1', result)
        return CommandResult('config.show', result=result, details=read_details(),
            project={'project_root': str(boundary.root), 'project_id': configuration.project_id})
    except (OperationFailure, ModelError, SafetyViolation, OSError) as error:
        return read_failure('config.show', error, None, read_details())


def commands():
    return (CommandSpec('config.show', ('config', 'show'), CommandClass.READ_ONLY,
        PreflightProfile.PROJECT_METADATA, EffectScope.NONE, handler=config_show,
        requires_project=True, configuration_schema_required=True,
        options=global_options('--project', '--profile', '--fail-on', '--strict', '--quiet', '--no-color') + (
            OptionSpec(
                '--format', takes_value=True, choices=('pretty', 'json')),),
        protocol=CommandProtocol('config-show-v1', {'command_id': 'config.show'},
            handler_exit_codes=(0, 2, 3, 4, 5, 6, 7),
            diagnostic_codes=('CORE_USAGE', 'CORE_MODEL', 'CORE_ENVIRONMENT', 'CORE_CONFLICT', 'CORE_SECURITY'),
            work=WorkContract('configuration_observation', ('project_configuration', 'resolved_options')))),)
