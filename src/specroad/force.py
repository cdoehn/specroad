"""Explicit, invocation-owned Force decisions; never ambient authorization.

An override records a refused check. It does not change that check's result,
provide missing operation inputs, or authorize an external runtime.
"""
from dataclasses import dataclass
from .model.canonical import canonical_json_bytes as jcs, canonical_json_sha256 as digest
from json import loads as json_value
from .model.errors import ModelError


GATE_CLASSES = (
    'structure', 'schema', 'references', 'cycles', 'profiles', 'language',
    'lifecycle', 'task', 'readiness', 'actor', 'review', 'approval',
    'immutable', 'partial', 'stale', 'hash', 'merge_conflict', 'import_conflict',
    'work_marker', 'write_marker', 'lock', 'safety', 'path', 'format',
    'resource_limit', 'analyzer_policy',
)
OVERRIDE_FIELDS = frozenset(('gate_id', 'diagnostic_code', 'subject',
    'original_decision', 'operation', 'observed_binding', 'requested_binding', 'effect'))


class ForceContractError(ModelError):
    def __init__(self, reason, *, exit_code=2):
        super().__init__(reason)
        self.exit_code = exit_code


def _text(value):
    if type(value) is not str or not value.strip() or '\0' in value:
        raise ForceContractError('force_nonempty_text_required')
    try:
        value.encode('utf-8')
    except UnicodeError as error:
        raise ForceContractError('force_valid_unicode_required') from error
    return value


@dataclass(frozen=True)
class ForceRequest:
    requested: bool = False
    reason: str | None = None

    def __post_init__(self):
        if type(self.requested) is not bool:
            raise ForceContractError('force_boolean_required')
        if self.reason is not None:
            _text(self.reason)
            if not self.requested:
                raise ForceContractError('force_reason_requires_force')

    @property
    def data(self):
        return {'requested': self.requested, 'reason': self.reason}

    @classmethod
    def from_mapping(cls, value):
        if type(value) is not dict or set(value) != {'requested', 'reason'}:
            raise ForceContractError('force_request_fields')
        return cls(value['requested'], value['reason'])


def validate_override(value):
    if type(value) is not dict or set(value) != OVERRIDE_FIELDS:
        raise ForceContractError('force_override_fields')
    for key in OVERRIDE_FIELDS - {'observed_binding', 'requested_binding'}:
        _text(value[key])
    if value['gate_id'].split(':', 1)[0] not in GATE_CLASSES:
        raise ForceContractError('force_unknown_gate_class')
    if value['original_decision'] not in ('denied', 'unknown'):
        raise ForceContractError('force_override_requires_negative_decision')
    # Own the complete JSON, including the binding objects; no live references.
    return json_value(jcs(value))


def override_key(value):
    return (value['gate_id'], value['subject'], jcs(value))


def validate_summary(value):
    if type(value) is not dict or set(value) != {'requested', 'used', 'reason', 'overrides'}:
        raise ForceContractError('force_summary_fields')
    request = ForceRequest(value['requested'], value['reason'])
    if type(value['used']) is not bool or type(value['overrides']) is not list:
        raise ForceContractError('force_summary_types')
    rows = [validate_override(v) for v in value['overrides']]
    if (value['used'] != bool(rows) or (rows and not request.requested)
            or rows != sorted(rows, key=override_key) or len({jcs(r) for r in rows}) != len(rows)):
        raise ForceContractError('force_summary_binding')
    return json_value(jcs(value))


class ForceDecisions:
    """One execution's findings. Calling a gate never turns unknown into valid."""
    def __init__(self, request=ForceRequest()):
        if type(request) is not ForceRequest:
            raise ForceContractError('force_request_required')
        self.request = request
        self._overrides = {}
        self._invalid = False
        self._unknown = False
        self._checked = False

    def observe_validation(self, status):
        if status not in ('valid', 'invalid', 'unknown'):
            raise ForceContractError('force_validation_status')
        self._checked = True
        self._invalid |= status == 'invalid'
        self._unknown |= status == 'unknown'

    def decide(self, allowed, *, gate_id, diagnostic_code, subject, operation,
               observed_binding, requested_binding, effect):
        if allowed is not True and allowed is not False and allowed is not None:
            raise ForceContractError('force_gate_decision_type')
        if allowed is True:
            return True
        self.observe_validation('invalid' if allowed is False else 'unknown')
        row = validate_override(dict(gate_id=gate_id, diagnostic_code=diagnostic_code,
            subject=subject, original_decision='denied' if allowed is False else 'unknown',
            operation=operation, observed_binding=observed_binding,
            requested_binding=requested_binding, effect=effect))
        if self.request.requested:
            self._overrides[jcs(row)] = row
            return True
        return False

    @property
    def validation_status(self):
        return ('invalid' if self._invalid else 'unknown' if self._unknown or not self._checked else 'valid')

    @property
    def summary(self):
        return validate_summary({**self.request.data, 'used': bool(self._overrides),
            'overrides': sorted(self._overrides.values(), key=override_key)})


def operations_hash(plan):
    """Historical ordinary operation hashes remain unchanged."""
    if 'force' not in plan:
        return digest(plan['operations'])
    ForceRequest.from_mapping(plan['force'])
    keys = ('operations', 'force', 'base', 'expected_result', 'preconditions')
    if plan['format_version'] == '1.5.0':
        keys += ('operational_binding',)
    if plan['format_version'] in ('1.4.0', '1.5.0'):
        keys += ('native_intent',)
    return digest({key: plan[key] for key in keys})
