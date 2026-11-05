"""Explicit audited single-conflict decisions over current native sources.

Targets are declarative field/value bindings. Neither parsing nor resolution
publishes project files, stamps resource metadata or validates the final target.
"""
from dataclasses import dataclass
from hashlib import sha256
import re

from ..model.canonical import canonical_json_bytes as jcs, canonical_json_sha256 as digest
from ..model.errors import ModelError
from ..model._schema import validate_builtin
from ..model.audit import actor as read_actor
from ..model.audit_values import UtcTimestamp
from ..storage.json_syntax import parse_json_object as parsed
from .field_values import FieldValue, _MISSING
from .conflict_schema import ROLES
from .conflicts import parse_merge_conflicts, read_merge_conflicts
from .resolution_schema import FORMAT, schema


@dataclass(frozen=True, init=False)
class MergeResolutions:
    _encoded: bytes

    @classmethod
    def _create(cls, value):
        result = object.__new__(cls)
        object.__setattr__(result, '_encoded', jcs(value))
        return result

    @property
    def data(self):
        return parsed(self._encoded)

    @property
    def canonical_bytes(self):
        return self._encoded

    @property
    def sha256(self):
        return sha256(self._encoded).hexdigest()

    @property
    def ready(self):
        return False

    @property
    def write_authorized(self):
        return False

    def __bool__(self):
        raise TypeError('Resolution is not target validation or write authority')


def parse_resolution_value(raw):
    """Decode one complete JSON value through the native strict number parser."""
    if type(raw) is not bytes:
        raise ModelError('merge_resolution_value_bytes_required')
    wrapped = parsed(b'{"value":' + raw + b'}')
    if set(wrapped) != {'value'}:
        raise ModelError('invalid_merge_resolution_value')
    return FieldValue._create(wrapped['value']).value


def _selected(row, choice):
    if choice['kind'] == 'take':
        option = 'take_' + choice['role']
        value = row['values'][choice['role']]
    else:
        option = 'value'
        value = {'state': 'present', 'domain': 'json-v1',
                 'value': FieldValue._create(choice['value']).value}
    if option not in row['allowed_resolutions']:
        raise ModelError('merge_resolution_not_allowed')
    return value


def _event(row, choice, actor, resolved_at, previous):
    value = {'previous_sha256': previous, 'conflict_id': row['conflict_id'],
        'choice': choice, 'value': _selected(row, choice),
        'actor': read_actor(actor).as_fields(), 'resolved_at': UtcTimestamp(resolved_at).value}
    return {'resolution_id': 'MR-' + digest(value), **value}


def _document(catalogue, events):
    rows = {row['conflict_id']: row for row in catalogue.conflicts}
    targets = [{**{name: rows[event['conflict_id']][name] for name in ('conflict_id', 'identity', 'pointer')},
                'value': event['value']} for event in events]
    targets.sort(key=lambda item: item['conflict_id'])
    unresolved = sorted(set(rows) - {event['conflict_id'] for event in events})
    return {'resolution_format_version': FORMAT, 'catalogue': catalogue.data,
        'catalogue_sha256': catalogue.sha256, 'resolutions': events,
        'resolutions_sha256': digest(events), 'targets': targets,
        'unresolved_conflict_ids': unresolved,
        'pending_gates': (['audited_resolution'] if unresolved else [])
                         + ['merge_metadata', 'target_validation', 'publication'],
        'ready': False, 'write_authorized': False, 'approval_granted': False}


def parse_merge_resolutions(raw):
    """Check every stored binding without opening embedded source paths."""
    if type(raw) is not bytes:
        raise ModelError('merge_resolutions_bytes_required')
    document = parsed(raw)
    validate_builtin(document, schema())
    catalogue = parse_merge_conflicts(jcs(document['catalogue']))
    events, seen = [], set()
    previous = catalogue.sha256
    for event in document['resolutions']:
        identifier = event['conflict_id']
        if identifier in seen:
            raise ModelError('merge_conflict_already_resolved')
        seen.add(identifier)
        expected = _event(catalogue.conflict(identifier), event['choice'], event['actor'],
                          event['resolved_at'], previous)
        if jcs(event) != jcs(expected):
            raise ModelError('merge_resolution_event_binding')
        events.append(expected)
        previous = digest(expected)
    expected = _document(catalogue, events)
    if jcs(document) != jcs(expected):
        raise ModelError('merge_resolution_plan_binding')
    return MergeResolutions._create(expected)


def parse_resolution_plan(raw):
    """Accept the original catalogue or its audited declarative successor."""
    document = parsed(raw)
    if 'resolution_format_version' in document:
        return parse_merge_resolutions(raw)
    return parse_merge_conflicts(raw)


def read_merge_resolutions(raw, sources, *, history, expected_plan_sha256):
    """Revalidate the entire selected plan and all three native original sources."""
    if (type(expected_plan_sha256) is not str
            or re.fullmatch(r'[0-9a-f]{64}', expected_plan_sha256) is None):
        raise ModelError('merge_expected_plan_hash_required')
    plan = parse_resolution_plan(raw)
    if plan.sha256 != expected_plan_sha256:
        raise ModelError('merge_resolution_input_hash')
    data = plan.data
    catalogue = data['catalogue'] if type(plan) is MergeResolutions else data
    read_merge_conflicts(jcs(catalogue), sources, history=history)
    return plan


def resolve_merge_conflict(raw, sources, *, history, expected_plan_sha256,
                          conflict_id, actor, resolved_at, take=None, value=_MISSING):
    """Append exactly one decision; never change an existing plan or project."""
    if (take is None) == (value is _MISSING):
        raise ModelError('merge_resolution_choice_required')
    if take is not None and (type(take) is not str or take not in ROLES):
        raise ModelError('invalid_merge_resolution_take')
    choice = ({'kind': 'take', 'role': take} if take is not None else
              {'kind': 'value', 'value': FieldValue._create(value).value})
    # Detach explicit audit data before any caller-owned source callbacks.
    actor = read_actor(actor).as_fields()
    resolved_at = UtcTimestamp(resolved_at).value
    plan = read_merge_resolutions(raw, sources, history=history,
                                  expected_plan_sha256=expected_plan_sha256)
    data = plan.data
    catalogue = parse_merge_conflicts(jcs(data['catalogue'])) if type(plan) is MergeResolutions else plan
    events = data['resolutions'] if type(plan) is MergeResolutions else []
    row = catalogue.conflict(conflict_id)
    if any(event['conflict_id'] == conflict_id for event in events):
        raise ModelError('merge_conflict_already_resolved')
    previous = digest(events[-1]) if events else catalogue.sha256
    events.append(_event(row, choice, actor, resolved_at, previous))
    result = parse_merge_resolutions(jcs(_document(catalogue, events)))
    for role in ROLES:
        getattr(sources, role).verify_current()
    return result
