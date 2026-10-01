"""Detached recovery observations; a parsed journal never grants permission."""
from dataclasses import dataclass
from hashlib import sha256
from uuid import UUID
from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..storage.json_syntax import parse_json_object
from .execution_values import ChangeExecutionError
from .journal_values import BuildingJournal, JournalError
from ._journal_codec import _hash, _text, journal_path

AUDIT_ROOT = '.specroad/recovery/transaction-audit'


class RecoveryError(JournalError):
    """A failed operational action preserves evidence; never infer a rollback."""
    def __init__(self, reason, *, path=None, exit_code=3, mutation_possible=False,
                 normative_writes_by_recovery=0):
        super().__init__(reason, path=path, exit_code=exit_code, mutation_possible=mutation_possible)
        self.normative_writes_by_recovery = normative_writes_by_recovery

    def diagnostic(self):
        return {**super().diagnostic(),
                'normative_writes_by_recovery': self.normative_writes_by_recovery,
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
        except (ValueError, TypeError, KeyError, ModelError, ChangeExecutionError) as error:
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


@dataclass(frozen=True, init=False)
class RollingBackJournal:
    """Durable reverse cursor. ``published_count`` means entries still to restore."""
    _raw: bytes

    def __init__(self, raw):
        try:
            if type(raw) is not bytes:
                raise ValueError('bytes required')
            value = parse_json_object(raw)
            if value.get('state') != 'rolling_back':
                raise ValueError('rolling_back required')
            rollback = value.pop('rollback')
            if (type(rollback) is not dict or set(rollback) != {
                    'started_from_sha256', 'started_from_published_count'}
                    or not _hash(rollback['started_from_sha256'])
                    or type(rollback['started_from_published_count']) is not int):
                raise ValueError('invalid rollback binding')
            count = value.get('published_count')
            entries = value.get('files')
            if (type(count) is not int or type(entries) is not list
                    or not 0 <= count <= len(entries)
                    or not 0 <= rollback['started_from_published_count'] <= len(entries)):
                raise ValueError('invalid rollback cursor')
            for index, entry in enumerate(entries):
                if type(entry) is not dict or entry.get('published') is not (index < count):
                    raise ValueError('invalid rollback prefix')
            value['state'] = 'committing'
            from .committing_values import CommittingJournal
            CommittingJournal(canonical_json_bytes(value))
        except (ValueError, TypeError, KeyError, ModelError, ChangeExecutionError) as error:
            raise RecoveryError('invalid_rolling_back_journal') from error
        object.__setattr__(self, '_raw', raw)

    @property
    def data(self): return parse_json_object(self._raw)
    @property
    def source_bytes(self): return self._raw
    @property
    def sha256(self): return sha256(self._raw).hexdigest()
    @property
    def path(self): return journal_path(self.data['transaction_id'])
    def __bool__(self): raise TypeError('Rollback progress is not a completed recovery')


@dataclass(frozen=True, init=False)
class RolledBackJournal:
    """Terminal deterministic rollback record retaining the original binding."""
    _raw: bytes

    def __init__(self, raw):
        try:
            if type(raw) is not bytes:
                raise ValueError('bytes required')
            value = parse_json_object(raw)
            if value.get('state') != 'rolled_back' or 'discard' in value:
                raise ValueError('rolled_back transaction required')
            if value.get('published_count') != 0 or any(
                    type(entry) is not dict or entry.get('published') is not False
                    for entry in value.get('files', ())):
                raise ValueError('rollback not complete')
            value['state'] = 'rolling_back'
            RollingBackJournal(canonical_json_bytes(value))
        except (ValueError, TypeError, KeyError, ModelError, ChangeExecutionError) as error:
            raise RecoveryError('invalid_rolled_back_journal') from error
        object.__setattr__(self, '_raw', raw)

    @property
    def data(self): return parse_json_object(self._raw)
    @property
    def source_bytes(self): return self._raw
    @property
    def sha256(self): return sha256(self._raw).hexdigest()
    @property
    def path(self): return journal_path(self.data['transaction_id'])
    def __bool__(self): raise TypeError('Inspect the rollback completion explicitly')
