"""Owned effective configuration values and provenance; no project I/O."""
from .results import OperationFailure, FailureKind, thaw


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
