"""Versioned operational lock data, not model identity or write permission."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from uuid import UUID
from ..model.audit_fields import _valid_utc
from ..storage.json_syntax import parse_json_object
from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError

LOCK_VERSION = 'project-lock-v1'
LOCK_PATH = '.specroad/locks/project.json'
MAX_LOCK_BYTES = 65536


class ProjectLockError(ModelError):
    code = 'SRV034'
    exit_code = 5

    def __init__(self, reason, *, exit_code=5, mutation_possible=False):
        super().__init__(reason, path=LOCK_PATH)
        self.exit_code = exit_code
        self.mutation_possible = mutation_possible

    def diagnostic(self):
        return {**super().diagnostic(), 'code': self.code, 'exit_code': self.exit_code,
                'mutation_possible': self.mutation_possible}


class LockKind(str, Enum):
    WRITER = 'writer'
    RECOVERY = 'recovery'
    OPERATIONAL = 'operational'


COMMANDS = {
    LockKind.WRITER: frozenset(('change apply', 'format', 'artifact create', 'artifact update',
        'relation add', 'relation remove', 'relation review', 'lifecycle transition',
        'document create', 'section add', 'section move', 'section remove',
        'block add', 'block update', 'block remove', 'view create', 'evidence record',
        'evidence import', 'baseline create', 'proposal create', 'proposal change',
        'proposal review start', 'proposal review', 'proposal apply', 'import apply',
        'migrate apply', 'merge apply')),
    LockKind.RECOVERY: frozenset(('recover run', 'recover discard', 'recover restore')),
    LockKind.OPERATIONAL: frozenset(('lock recover',)),
}


def text(value, *, optional=False):
    if value is None and optional:
        return
    if (type(value) is not str or not value or len(value) > 1024
            or value != value.strip() or any(ord(c) < 32 or ord(c) == 127 for c in value)):
        raise ProjectLockError('invalid_lock_text', exit_code=2)
    try:
        value.encode('utf-8')
    except UnicodeError as error:
        raise ProjectLockError('invalid_lock_text', exit_code=2) from error


def kind_and_command(kind, command):
    if type(kind) is str:
        try:
            kind = LockKind(kind)
        except ValueError as error:
            raise ProjectLockError('unknown_lock_kind', exit_code=2) from error
    if type(kind) is not LockKind or type(command) is not str or command not in COMMANDS[kind]:
        raise ProjectLockError('lock_command_class_mismatch', exit_code=2)
    return kind


@dataclass(frozen=True)
class OwnerIdentity:
    host_id: str | None
    process_id: int
    process_start_id: str | None

    def __post_init__(self):
        text(self.host_id, optional=True)
        text(self.process_start_id, optional=True)
        if type(self.process_id) is not int or not 0 < self.process_id < 2**31:
            raise ProjectLockError('invalid_owner_pid', exit_code=2)

    def as_dict(self):
        return {'host_id': self.host_id, 'process_id': self.process_id,
                'process_start_id': self.process_start_id}


@dataclass(frozen=True, init=False)
class LockRecord:
    _raw: bytes

    def __init__(self, raw):
        if type(raw) is not bytes or not 0 < len(raw) <= MAX_LOCK_BYTES:
            raise ProjectLockError('invalid_lock_record', exit_code=3)
        try:
            v = parse_json_object(raw, path=LOCK_PATH)
            fields = {'format_version', 'kind', 'lock_id', 'project_id', 'root_identity',
                      'host_id', 'process_id', 'process_start_id', 'created_at',
                      'command', 'request_id', 'transaction_id'}
            if set(v) != fields or v['format_version'] != LOCK_VERSION:
                raise ValueError('shape')
            selected = kind_and_command(v['kind'], v['command'])
            lock_id = UUID(v['lock_id'])
            if lock_id.version != 4 or str(lock_id) != v['lock_id']:
                raise ValueError('lock id')
            text(v['project_id'])
            for k in ('request_id', 'transaction_id'):
                text(v[k], optional=True)
            if v['request_id'] is not None:
                from .authoring import normalize_request_id
                normalize_request_id(v['request_id'])
            if selected in (LockKind.WRITER, LockKind.RECOVERY) and v['transaction_id'] is None:
                raise ValueError('transaction id')
            if not _valid_utc(v['created_at']):
                raise ValueError('timestamp')
            ident = v['root_identity']
            if (type(ident) is not dict or set(ident) != {'device', 'inode'}
                    or any(type(x) is not str or not x.isascii() or not x.isdecimal()
                           or len(x) > 30 for x in ident.values())):
                raise ValueError('root identity')
            OwnerIdentity(v['host_id'], v['process_id'], v['process_start_id'])
        except (ModelError, ValueError, TypeError, AttributeError, OverflowError) as error:
            raise ProjectLockError('invalid_lock_record', exit_code=3) from error
        object.__setattr__(self, '_raw', raw)

    @property
    def data(self):
        return parse_json_object(self._raw)

    @property
    def source_bytes(self):
        return self._raw

    @property
    def sha256(self):
        return sha256(self._raw).hexdigest()

    @property
    def owner(self):
        v = self.data
        return OwnerIdentity(v['host_id'], v['process_id'], v['process_start_id'])

    def __bool__(self):
        raise TypeError('Inspect lock record explicitly')


@dataclass(frozen=True, init=False)
class LockStatus:
    _raw: bytes

    @classmethod
    def create(cls, value):
        obj = object.__new__(cls)
        object.__setattr__(obj, '_raw', canonical_json_bytes(value))
        return obj

    @property
    def data(self):
        return parse_json_object(self._raw)

    def __bool__(self):
        raise TypeError('Inspect lock status explicitly')
