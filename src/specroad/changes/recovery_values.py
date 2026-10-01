"""Detached recovery observations; a parsed journal never grants permission."""
from dataclasses import dataclass
from hashlib import sha256
from uuid import UUID
from ..model.canonical import canonical_json_bytes
from ..storage.json_syntax import parse_json_object
from .execution_values import ChangeExecutionError
from .journal_values import BuildingJournal, JournalError
from ._journal_codec import _hash, _text, journal_path

AUDIT_ROOT = '.specroad/recovery/transaction-audit'


class RecoveryError(JournalError):
    """A failed operational action preserves evidence; never infer a rollback."""
    def diagnostic(self):
        return {**super().diagnostic(), 'normative_writes_by_recovery': 0,
                'discard_completed': False, 'recovery_required': True}


@dataclass(frozen=True)
class RecoveryAuthority:
    """Host-registered authorization, not a capability read from project data.

    The callback receives detached JSON and must return an actual bool. The host
    must authenticate the caller; an actor label alone is not authentication.
    """
    authority_id: str
    version: str
    check: object

    def __post_init__(self):
        if (not _text(self.authority_id) or not _text(self.version)
                or not callable(self.check)):
            raise RecoveryError('recovery_authority_required', exit_code=2)


@dataclass(frozen=True, init=False)
class RecoveryObservation:
    _raw: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError('Use the recovery observation or discard API')

    @classmethod
    def _create(cls, data):
        obj = object.__new__(cls)
        object.__setattr__(obj, '_raw', canonical_json_bytes(data))
        return obj

    @property
    def data(self): return parse_json_object(self._raw)
    def __bool__(self): raise TypeError('Inspect the recovery outcome explicitly')


@dataclass(frozen=True, init=False)
class DiscardedJournal:
    """Terminal unpublished journal, with links to durable original audit bytes."""
    _raw: bytes

    def __init__(self, raw):
        try:
            if type(raw) is not bytes:
                raise ValueError('bytes required')
            value = parse_json_object(raw)
            if value.get('state') != 'rolled_back':
                raise ValueError('rolled_back required')
            recovery = value.pop('discard')
            if (type(recovery) is not dict or set(recovery) != {
                    'event_id', 'previous_state', 'journal_before_sha256',
                    'intent_sha256', 'audit_path'}
                    or recovery['previous_state'] not in ('building', 'prepared')
                    or not _hash(recovery['journal_before_sha256'])
                    or not _hash(recovery['intent_sha256'])):
                raise ValueError('invalid discard binding')
            token = recovery['event_id']
            if str(UUID(token)) != token or recovery['audit_path'] != AUDIT_ROOT + '/' + token:
                raise ValueError('invalid audit path')
            value['state'] = 'building'
            BuildingJournal(canonical_json_bytes(value))
        except (ValueError, TypeError, KeyError, ChangeExecutionError) as error:
            raise RecoveryError('invalid_discarded_journal') from error
        object.__setattr__(self, '_raw', raw)

    @property
    def data(self): return parse_json_object(self._raw)
    @property
    def source_bytes(self): return self._raw
    @property
    def sha256(self): return sha256(self._raw).hexdigest()
    @property
    def path(self): return journal_path(self.data['transaction_id'])
    def __bool__(self): raise TypeError('A terminal record still needs audit verification')
