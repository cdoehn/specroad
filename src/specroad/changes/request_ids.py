"""Normative-write request values; no analyzer conversion or receipt effects."""
from dataclasses import dataclass
import re
from .errors import ChangePlanError

REQUEST_PATTERN = r'[A-Za-z0-9][A-Za-z0-9._:-]{0,127}'


class AuthoringError(ChangePlanError):
    """Usage or policy rejection before invoking a normative writer."""
    def __init__(self, reason, *, pointer='', exit_code=2):
        super().__init__(reason, pointer=pointer, code='SRV146')
        self.exit_code = exit_code

    def diagnostic(self):
        return {**super().diagnostic(), 'write_state': 'not_committed',
                'authorization_granted': False}


@dataclass(frozen=True)
class NormativeRequestId:
    """Caller-assigned write namespace. No strip/casefold/UUID substitution."""
    value: str

    def __post_init__(self):
        if type(self.value) is not str or re.fullmatch(REQUEST_PATTERN, self.value) is None:
            raise AuthoringError('invalid_normative_request_id', pointer='/request_id')

    @property
    def namespace(self):
        return 'normative_write'


def normalize_request_id(value):
    if value is None:
        return None
    if type(value) is NormativeRequestId:
        return NormativeRequestId(value.value)
    # Foreign typed IDs, including analyzer request objects, are never coerced.
    return NormativeRequestId(value)


def request_id_schema():
    # Explicit null represents an absent optional caller Request-ID, not a
    # generated ID. AI/CI actual-write policy is enforced at the write boundary.
    return {'anyOf': [{'type': 'null'}, {'type': 'string',
        'pattern': '^' + REQUEST_PATTERN + r'(?![\s\S])'}]}
