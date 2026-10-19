"""Versioned passive waiver fields; legacy bytes are never migrated on read."""
from .audit_fields import audit_definitions
from ._schema import validate_builtin
from .audit_values import UtcTimestamp
from .errors import ModelError
import re

WAIVER_VERSION = '1.0.0'
CONTENT_HASH_ALGORITHM = 'waiver-content-hash-v1'
DEADLINE_PATTERN = (r'^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:'
                    r'[0-5][0-9](?:\.[0-9]{1,9})?Z(?![\s\S])')


def waiver_schema():
    text = {'$ref': '#/$defs/text'}
    digest = {'type': 'string', 'pattern': r'^[0-9a-f]{64}(?![\s\S])'}
    fields = {'reason': text, 'scope_descriptor': {'type': 'object'},
        'expiry_condition': text, 'human_review_id': text, 'artifact_sha256': digest,
        'configuration_sha256': {'anyOf': [{'type': 'null'}, digest]}}
    legacy = {'type': 'object', 'required': [key for key in fields if key != 'configuration_sha256'],
              'properties': fields, 'additionalProperties': False}
    current = {**fields, 'format_version': {'const': WAIVER_VERSION},
        'content_hash_algorithm': {'const': CONTENT_HASH_ALGORITHM},
        'expiry_condition': {'type': 'object', 'required': ['kind', 'expires_at'],
            'properties': {'kind': {'const': 'utc_deadline'},
                'expires_at': {'type': 'string', 'format': 'date-time', 'pattern': DEADLINE_PATTERN}},
            'additionalProperties': False}}
    return {'anyOf': [legacy, {'type': 'object', 'required': list(current),
        'properties': current, 'additionalProperties': False}]}


def validate_waiver_fields(value):
    validate_builtin(value, {**waiver_schema(), '$defs': audit_definitions()})


def waiver_time(value):
    """Lossless ordering at nanosecond precision; never consult a clock."""
    if type(value) is not str or re.fullmatch(DEADLINE_PATTERN, value) is None:
        raise ModelError('invalid_waiver_utc_time')
    UtcTimestamp(value)
    fraction = value[20:-1] if value[19] == '.' else ''
    return value[:19], fraction.ljust(9, '0')
