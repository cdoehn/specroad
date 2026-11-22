"""Read project configuration/defaults and resolved option provenance only.

Profile selectors remain selectors: this observation does not load the model,
validate a profile composition or treat it as release/authoring authority.
"""
from hashlib import sha256
from .contracts import CommandClass, CommandSpec, EffectScope, PreflightProfile, CommandProtocol, WorkContract
from .options import global_options
from .parameters import OptionSpec
from .results import CommandResult, OperationFailure, FailureKind, thaw


def configuration_view(configuration, resolved):
    from ..model.canonical import canonical_json_bytes
    from ..model.configuration_schema import configuration_json_schema
    from ..model.language_policy import resolve_language_policy
    from ..storage.json_syntax import parse_json_object
    data = configuration.data
    schema = configuration_json_schema(data['schema_version'])
    origins = {}

    def materialize(stored, fields, pointer=''):
        result = dict(stored)
        for name in sorted(set(stored) | set(fields)):
            field, path = fields.get(name, {}), pointer + '/' + name.replace('~', '~0').replace('/', '~1')
            if name not in stored and 'default' in field:
                result[name] = field['default']
            if name in result:
                origins[path] = [{'source': 'default', 'value': field['default']}] if 'default' in field else []
                if name in stored:
                    origins[path].append({'source': 'project', 'value': stored[name]})
            if isinstance(stored.get(name), dict) or (field.get('type') == 'object' and 'properties' in field):
                nested = materialize(stored.get(name, {}), field.get('properties', {}), path)
                if nested:
                    result[name] = nested
        return result

    effective = materialize(data, schema['properties'])
    effective['validation_policy'].setdefault('required_relation_review', 'current')
    if 'required_relation_review' not in data['validation_policy']:
        origins['/validation_policy/required_relation_review'] = [{'source': 'default', 'value': 'current'}]
    effective['language_policy'] = resolve_language_policy(data.get('language_policy', {}))
    for key, default in (('query_default_limit', 100), ('query_result_count', 10000)):
        effective.setdefault('resource_limits', {}).setdefault(key, default)
        if key not in data.get('resource_limits', {}):
            origins['/resource_limits/' + key] = [{'source': 'default', 'value': default}]
    from ..analyzers.language_policy import materialize_policy
    configured = data.get('analyzer_policy', {}).get('language_detection', {})
    analyzer_defaults = materialize_policy()
    language_detection = materialize_policy(configured)
    effective.setdefault('analyzer_policy', {})['language_detection'] = language_detection
    for key, default in analyzer_defaults.items():
        origins['/analyzer_policy/language_detection/' + key] = [{'source': 'default', 'value': default}]
        if key in configured:
            origins['/analyzer_policy/language_detection/' + key].append({'source': 'project', 'value': configured[key]})
    options = thaw(dict(resolved.values))
    histories = {k: [{'source': h.source, 'value': thaw(h.value)} for h in rows]
                 for k, rows in resolved.history.items()}
    # Verify that the preflight project values still describe this observation.
    for key, project_value in (('profiles', data.get('profiles')),
                               ('fail_on', data.get('validation_policy', {}).get('fail_on'))):
        project_rows = [row for row in histories[key] if row['source'] == 'project']
        if key == 'profiles' and project_value is not None:
            from .option_values import _profiles
            project_value = list(_profiles(project_value))
        if project_rows != ([] if project_value is None else [{'source': 'project', 'value': project_value}]):
            raise OperationFailure(FailureKind.CONFLICT, 'Configuration changed after preflight.')
    effective['profiles'] = options['profiles']
    effective.setdefault('validation_policy', {})['fail_on'] = options['fail_on']
    origins['/profiles'] = histories['profiles']
    origins['/validation_policy/fail_on'] = histories['fail_on']
    # Detach defaults and provenance values as a single owned JSON observation.
    return parse_json_object(canonical_json_bytes({'format_version': '1.0.0',
        'effective_configuration': effective, 'origins': origins,
        'resolved_options': options, 'option_origins': histories,
        'scope': 'project_configuration_and_resolved_options',
        'profile_composition_verified': False, 'model_loaded': False,
        'full_validation_passed': False, 'write_authorized': False, 'approval_granted': False}))


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
