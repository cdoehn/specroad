"""Closed, additive handover receipts; ordinary ledger opens verify the chain."""
from hashlib import sha256
import json
import math
from pathlib import Path
import sqlite3

from .config import digest, identity
from .errors import ControlError
from .local import decode_object


FIELDS = {'id', 'created_at', 'old_scope', 'new_scope', 'from_thread_id', 'to_thread_id',
          'thread_cwd', 'old_config_sha256', 'new_config_sha256', 'history_sha256',
          'lifecycle_sha256', 'current_run_id', 'source_sha256', 'previous_sha256'}


def conflict(message):
    raise ControlError('handover_conflict', message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def receipt(value):
    try:
        if not isinstance(value, dict):
            raise ValueError
        if set(value) == FIELDS | {'version', 'from_thread_cwd', 'request_sha256'}:
            if type(value['version']) is not int or value['version'] != 2:
                raise ValueError
            old_cwd = value['from_thread_cwd']
            if old_cwd is not None and (not isinstance(old_cwd, str) or not Path(old_cwd).is_absolute()
                    or str(Path(old_cwd)) != old_cwd or '..' in Path(old_cwd).parts
                    or any(ord(c) < 32 or ord(c) == 127 for c in old_cwd)):
                raise ValueError
            if value['request_sha256'] is not None:
                digest(value['request_sha256'])
            if value['from_thread_cwd'] is None and value['request_sha256'] is None:
                raise ValueError
        elif set(value) != FIELDS:
            raise ValueError
        for name in ('id', 'from_thread_id', 'to_thread_id', 'current_run_id'):
            identity(value[name])
        for name in ('old_scope', 'new_scope', 'old_config_sha256', 'new_config_sha256',
                     'history_sha256', 'lifecycle_sha256', 'source_sha256'):
            digest(value[name])
        if value['previous_sha256'] is not None:
            digest(value['previous_sha256'])
        if (value['old_scope'] == value['new_scope'] or value['from_thread_id'] == value['to_thread_id']
                or type(value['created_at']) not in (int, float)
                or not math.isfinite(value['created_at']) or value['created_at'] < 0):
            raise ValueError
        cwd = value['thread_cwd']
        if (not isinstance(cwd, str) or not Path(cwd).is_absolute() or str(Path(cwd)) != cwd
                or '..' in Path(cwd).parts or any(ord(c) < 32 or ord(c) == 127 for c in cwd)):
            raise ValueError
        return value
    except (ValueError, TypeError, KeyError, AttributeError):
        raise ControlError('invalid_handover_receipt', 'Damaged handover evidence is preserved; no inferred transfer.') from None


def validate_chain(db, expected_scope):
    try:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='thread_handovers'").fetchone():
            return
        previous, previous_raw = None, None
        for record_id, raw in db.execute('SELECT id,receipt FROM thread_handovers ORDER BY rowid'):
            if not isinstance(raw, str) or len(raw.encode()) > 65536:
                raise ValueError
            current = receipt(decode_object(raw))
            if current['id'] != record_id or canonical(current).decode() != raw:
                raise ValueError
            expected_previous = sha256(previous_raw.encode()).hexdigest() if previous_raw else None
            if current['previous_sha256'] != expected_previous:
                raise ValueError
            if previous and (current['old_scope'] != previous['new_scope']
                             or current['from_thread_id'] != previous['to_thread_id']):
                raise ValueError
            previous, previous_raw = current, raw
        if previous is None or previous['new_scope'] != expected_scope:
            raise ValueError
    except (sqlite3.Error, ValueError, TypeError, KeyError, UnicodeError, ControlError):
        raise ControlError('invalid_handover_history', 'Handover history is incomplete or inconsistent; preserve it.') from None
