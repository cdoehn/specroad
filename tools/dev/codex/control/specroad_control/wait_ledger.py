"""Durable observation checkpoints, distinct from the bounded retry budget."""
import json
import math
from .config import digest
from .errors import ControlError
from .local import decode_object


class WaitHistory:
    def overload_wait(self):
        row = self.current()
        exists = self.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='overload_waits'").fetchone()
        retry = self.retry_info(row['sha'])
        number = retry['number'] if retry else 0
        found = self.db.execute('SELECT * FROM overload_waits WHERE source_sha=? AND number=?',
                                (row['sha'], number)).fetchone() if exists else None
        if found is None:
            if row['stage'] == 'overload_wait':
                raise ControlError('invalid_overload_wait', 'Waiting work has no durable evidence.')
            return None
        try:
            result = dict(found)
            result['evidence'] = evidence = decode_object(result['evidence'])
            result['progress'] = progress = decode_object(result['progress'])
            if set(evidence) != {'failure', 'attempt_sha256', 'dispatch_sha256', 'source_sha256',
                                 'number', 'workspace_sha256', 'pending', 'history_sha256'}:
                raise ValueError
            for key in ('attempt_sha256', 'dispatch_sha256', 'workspace_sha256', 'history_sha256'):
                digest(evidence[key])
            if (evidence['source_sha256'] != row['sha'] or type(evidence['number']) is not int
                    or evidence['number'] != number or not 0 <= number <= 8):
                raise ValueError
            pending = evidence['pending']
            if (not isinstance(pending, list) or not 1 <= len(pending) <= 4096
                    or any(not isinstance(item, str) or not item or len(item) > 256 for item in pending)
                    or len(set(pending)) != len(pending)):
                raise ValueError
            failure = evidence['failure']
            if (failure['turn_status'] != 'failed' or failure['codex_error'] != 'serverOverloaded'
                    or failure['codex_will_retry'] is not False
                    or not isinstance(failure['turn_id'], str) or not 1 <= len(failure['turn_id']) <= 160):
                raise ValueError
            if set(progress) != {'completed', 'terminals', 'history_sha256'} or not isinstance(progress['completed'], dict):
                raise ValueError
            digest(progress['history_sha256'])
            if (not set(progress['completed']) <= set(pending)
                    or not isinstance(progress['terminals'], list) or len(progress['terminals']) > 128
                    or any(not isinstance(value, str) for value in progress['terminals'])
                    or len(set(progress['terminals'])) != len(progress['terminals'])
                    or type(result['next_at']) not in (int, float)):
                raise ValueError
            for value in [*progress['completed'].values(), *progress['terminals']]:
                digest(value)
            for value in (result['next_at'], result['settle_since']):
                if value is not None and (type(value) not in (float, int) or not math.isfinite(value) or value < 0):
                    raise ValueError
            if result['settle_since'] is not None and (progress['terminals']
                    or not result['settle_since'] <= result['next_at'] <= result['settle_since'] + 120):
                raise ValueError
            return result
        except (ValueError, KeyError, TypeError, UnicodeError):
            raise ControlError('invalid_overload_wait', 'Waiting evidence is invalid; it is never reset.') from None

    def begin_overload_wait(self, evidence, progress, next_at, since, now):
        with self.transaction():
            row = self.current()
            if row['stage'] != 'running' or self.overload_wait() is not None:
                raise ControlError('invalid_transition', 'Only one failed dispatch may establish a wait checkpoint.')
            retry = self.retry_info(row['sha'])
            if evidence['source_sha256'] != row['sha'] or evidence['number'] != (retry['number'] if retry else 0):
                raise ControlError('invalid_overload_wait', 'Wait checkpoint belongs to different work.')
            self.db.execute('''CREATE TABLE IF NOT EXISTS overload_waits (
                source_sha TEXT NOT NULL, number INTEGER NOT NULL, evidence TEXT NOT NULL,
                progress TEXT NOT NULL, next_at REAL NOT NULL, settle_since REAL,
                PRIMARY KEY(source_sha,number))''')
            self.db.execute('INSERT INTO overload_waits VALUES(?,?,?,?,?,?)',
                            (row['sha'], evidence['number'], json.dumps(evidence), json.dumps(progress), next_at, since))
            self.db.execute("UPDATE jobs SET stage='overload_wait',error='serverOverloaded',updated=? WHERE run_id=?",
                            (now, row['run_id']))
            self.overload_wait()  # Validate before publishing the transaction.
        return self.overload_wait()

    def advance_overload_wait(self, saved, progress, next_at, since):
        with self.transaction():
            if self.current()['stage'] != 'overload_wait' or self.overload_wait() != saved:
                raise ControlError('overload_checkpoint_changed', 'Waiting checkpoint changed concurrently.')
            self.db.execute('UPDATE overload_waits SET progress=?,next_at=?,settle_since=? WHERE source_sha=? AND number=?',
                            (json.dumps(progress), next_at, since, saved['source_sha'], saved['number']))
            self.overload_wait()
