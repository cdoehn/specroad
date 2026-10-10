"""Shared artifact-create inputs, before identity allocation, planning or writes.

These are executable input adapters for the following authoring service, not a
registered artifact writer. File paths and transport spelling are absent from
the canonical intent. Only an explicit input='-' may consume a binary stdin.
"""
from dataclasses import dataclass
from hashlib import sha256
import os
from pathlib import Path
import sys

from ..changes.request_ids import AuthoringError
from ..cli._arguments import bind_options, bind_values
from ..cli.command_errors import CommandUsageError
from ..cli.parameters import OptionSpec
from ..model._schema import validate_builtin
from ..model.artifact_types import artifact_type
from ..model.canonical import canonical_json_bytes
from ..model.domain_schemas import DOMAIN_TYPES, domain_schema
from ..model.errors import ModelError
from ..model.language_tags import parse_language_tag
from ..model.record_schemas import record_schema, require_generic_mutation
from ..security import ProjectBoundary, SafetyViolation
from ..security.resource_access import opened_resource
from ..storage.json_syntax import parse_json_object

INPUT_VERSION = '1.0.0'
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


@dataclass(frozen=True, init=False)
class ArtifactCreateInput:
    """Owned normalized intent, never a saved Change Plan or write permission."""
    source_bytes: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError('Use normalize_artifact_create_input or read_artifact_create_input')

    @classmethod
    def _create(cls, kind, fields):
        value = object.__new__(cls)
        object.__setattr__(value, 'source_bytes', canonical_json_bytes({
            'format_version': INPUT_VERSION, 'command_id': 'artifact.create',
            'artifact_type': kind, 'fields': fields}))
        return value

    @property
    def data(self):
        return parse_json_object(self.source_bytes)

    @property
    def fields(self):
        return self.data['fields']

    @property
    def sha256(self):
        return sha256(self.source_bytes).hexdigest()

    def __bool__(self):
        raise TypeError('Prepared input is not publication authority')


def normalize_artifact_create_input(kind, fields):
    """Use native draft field schemas without consuming entropy or wall time."""
    try:
        schema = _schema(kind)
        if type(fields) is not dict:
            raise ModelError('object_required')
        owned = parse_json_object(canonical_json_bytes(fields))
        owned.setdefault('relations', [])
        owned.setdefault('extensions', {})
        validate_builtin(owned, schema)
        if 'language' in owned:
            owned['language'] = parse_language_tag(owned['language']).canonical
        return ArtifactCreateInput._create(kind, owned)
    except ModelError as error:
        raise AuthoringError(error.reason, pointer=error.pointer, exit_code=3) from error


def _read_stream(read, expected_size=None):
    raw = bytearray()
    while True:
        requested = 65536 if expected_size is None else min(65536, expected_size + 1 - len(raw))
        if requested <= 0: raise SafetyViolation('Authoring input grew while reading')
        try:
            block = read(requested)
        except SafetyViolation:
            raise
        except (OSError, ValueError) as error:
            # A closed binary stream raises ValueError, not OSError. Do not
            # retry a read that may already have consumed part of the input.
            raise AuthoringError('authoring_input_io', exit_code=5) from error
        if type(block) is not bytes or len(block) > requested:
            raise SafetyViolation('Authoring input reader violated its byte contract')
        if not block: break
        raw.extend(block)
    if expected_size is not None and len(raw) != expected_size:
        raise SafetyViolation('Authoring input changed while reading')
    return bytes(raw)


def _read_input(path, cwd, stdin):
    if type(path) is not str or not path or '\0' in path:
        raise AuthoringError('authoring_input_path_required', pointer='/input')
    if path == '-':
        stream = getattr(sys.stdin, 'buffer', None) if stdin is None else stdin
        read = getattr(stream, 'read', None)
        if not callable(read):
            raise AuthoringError('binary_stdin_unavailable', exit_code=5)
        return _read_stream(read)
    target = Path(path)
    if not target.is_absolute(): target = (Path.cwd() if cwd is None else Path(cwd)) / target
    boundary = ProjectBoundary(target.parent)
    with opened_resource(boundary, target.name) as (fd, info):
        return _read_stream(lambda size: os.read(fd, size), info.st_size)


def read_artifact_create_input(kind, *, options=None, input=None, cwd=None, stdin=None):
    """Merge supplied field options with an explicit flat JSON field object.

    Text/enum fields use literal CLI text. Composite, numeric and union-valued
    fields use one JSON value (including quotes for a string in a union).
    Distinct sources can complement each other; conflicting fields are rejected.
    No implicit stdin read, output, project discovery or executable data loading.
    """
    try:
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
        fields = {} if input is None else parse_json_object(_read_input(input, cwd, stdin))
        for field, value in option_fields.items():
            if field in fields and canonical_json_bytes(fields[field]) != canonical_json_bytes(value):
                raise AuthoringError('authoring_input_conflict', pointer='/' + field)
            fields[field] = value
        return normalize_artifact_create_input(kind, fields)
    except AuthoringError:
        raise
    except SafetyViolation as error:
        raise AuthoringError('unsafe_authoring_input', exit_code=7) from error
    except CommandUsageError as error:
        raise AuthoringError('invalid_authoring_options') from error
    except ModelError as error:
        raise AuthoringError(error.reason, pointer=error.pointer, exit_code=3) from error
    except OSError as error:
        raise AuthoringError('authoring_input_io', exit_code=5) from error


def parse_artifact_create_input(argv, *, cwd=None, stdin=None):
    """Bind a create tail, TYPE [field options] [--input FILE|-], without writes.

    This adapter is intended for the subsequent artifact-create handler. It
    does not register a writer or claim a completed authoring command result.
    """
    if type(argv) not in (list, tuple) or not argv or any(type(v) is not str for v in argv):
        raise AuthoringError('artifact_create_arguments_required')
    kind = argv[0]
    try:
        options = (*_options(_schema(kind)), OptionSpec('--input', takes_value=True))
        bound, arguments = bind_options(argv, (kind,), options)
    except CommandUsageError as error:
        raise AuthoringError('invalid_authoring_options') from error
    except ModelError as error:
        raise AuthoringError(error.reason, pointer=error.pointer, exit_code=3) from error
    return read_artifact_create_input(kind, options={k: v for k, v in bound.items() if k != '--input'},
        input=bound.get('--input'), cwd=cwd, stdin=stdin)
