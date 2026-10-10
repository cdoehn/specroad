"""Native draft field schemas and CLI value conversion before transport reads."""
from ..changes.request_ids import AuthoringError
from ..cli._arguments import bind_values
from ..cli.parameters import OptionSpec
from ..model.artifact_types import artifact_type
from ..model.domain_schemas import DOMAIN_TYPES, domain_schema
from ..model.errors import ModelError
from ..model.record_schemas import record_schema, require_generic_mutation
from ..storage.json_syntax import parse_json_object

_GENERATED = frozenset(('schema_version', 'artifact_type', 'id', 'id_scheme', 'maturity',
    'revision', 'created_at', 'updated_at', 'created_by', 'updated_by'))


def _schema(kind):
    artifact_type(kind)
    if kind in DOMAIN_TYPES:
        stored = domain_schema(kind)
    else:
        require_generic_mutation(kind, 'create')
        stored = record_schema(kind)
    # Keep field definitions/conditional obligations, but do not fabricate an
    # identity or audit record just to validate pre-planning input fields.
    return {'type': 'object', '$defs': stored['$defs'],
        'properties': {k: v for k, v in stored['properties'].items() if k not in _GENERATED},
        'required': [k for k in stored['required'] if k not in _GENERATED],
        'allOf': stored.get('allOf', []), 'additionalProperties': False}


def _text_option(node, definitions):
    if '$ref' in node:
        node = definitions[node['$ref'].removeprefix('#/$defs/')]
    return node.get('type') == 'string' or ('enum' in node and
        all(type(value) is str for value in node['enum']))


def _options(schema):
    return tuple(OptionSpec('--' + name.replace('_', '-'), takes_value=True)
                 for name in sorted(schema['properties']))


def _option_fields(kind, options):
    schema = _schema(kind)
    bound = bind_values({} if options is None else options, _options(schema))
    option_fields = {}
    for flag, value in bound.items():
        field = flag[2:].replace('-', '_')
        if _text_option(schema['properties'][field], schema['$defs']):
            option_fields[field] = value
        else:
            try:
                decoded = parse_json_object(('{"value":' + value + '}').encode())
                if set(decoded) != {'value'}:
                    raise ModelError('single_json_value_required')
                option_fields[field] = decoded['value']
            except ModelError as error:
                pointer = '/' + field + error.pointer.removeprefix('/value')
                raise AuthoringError(error.reason, pointer=pointer, exit_code=3) from error
    return option_fields
