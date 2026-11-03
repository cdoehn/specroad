"""Additive runtime-only retry history. Existing claims are never reset or erased."""
import json
import math
from .errors import ControlError
from .local import decode_object
from .config import digest


def validate_mode(evidence, source_sha):
    mode = evidence.get('mode', 'readonly')
    if mode not in ('readonly', 'continuation'):
        raise ValueError('Unknown continuation mode')
    if mode == 'continuation':
        for key in ('history_sha256', 'attempt_sha256', 'dispatch_sha256'):
            digest(evidence[key])
        if (evidence.get('legacy') is not False or evidence.get('source_sha256') != source_sha
                or evidence.get('turn_status') != 'failed' or evidence.get('codex_error') != 'serverOverloaded'
                or evidence.get('codex_will_retry') is not False):
            raise ValueError('Unbound continuation')
    elif any(key in evidence for key in ('history_sha256', 'attempt_sha256', 'dispatch_sha256', 'source_sha256')):
        raise ValueError('Continuation cannot be downgraded to a replay')


class RetryHistory:
    def retry_info(self, source_sha):
        exists = self.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='retry_attempts'").fetchone()
        if not exists:
            return None
        row = self.db.execute("SELECT * FROM retry_attempts WHERE source_sha=? ORDER BY number DESC LIMIT 1", (source_sha,)).fetchone()
        if row is None:
            return None
        result = dict(row)
        try:
            result['evidence'] = decode_object(result['failure'])
            digest(result['evidence']['workspace_sha256'])
            validate_mode(result['evidence'], source_sha)
        except (ValueError, KeyError, TypeError, UnicodeError):
            raise ControlError('invalid_retry_history', 'A complete persisted retry proof is required.') from None
        if (type(result['number']) is not int or not 1 <= result['number'] <= 8
                or type(result['due']) not in (int, float) or not math.isfinite(result['due'])
                or result['due'] < 0 or not isinstance(result['failed_turn'], str) or not result['failed_turn']
                or len(result['failed_turn']) > 160 or result['evidence'].get('turn_id') != result['failed_turn']
                or type(result['evidence'].get('legacy')) is not bool):
            raise ControlError('invalid_retry_history', 'Retry history cannot be guessed or reset.')
        count = self.db.execute('SELECT COUNT(*) FROM retry_attempts WHERE source_sha=?', (source_sha,)).fetchone()[0]
        if count != result['number']:
            raise ControlError('invalid_retry_history', 'Retry attempt history has gaps; no reset is inferred.')
        return result

    def schedule_retry(self, failure, delays, now):
        try:
            digest(failure['workspace_sha256'])
            if (failure.get('turn_status') != 'failed' or failure.get('codex_error') != 'serverOverloaded'
                    or failure.get('codex_will_retry') is not False or type(failure.get('legacy')) is not bool
                    or not isinstance(failure.get('turn_id'), str) or not failure['turn_id']
                    or len(failure['turn_id']) > 160 or type(now) not in (int, float)
                    or not math.isfinite(now) or now < 0):
                raise ValueError
        except (ValueError, TypeError, KeyError):
            raise ControlError('retry_evidence_invalid', 'Invalid failure proof cannot mutate retry history.') from None
        with self.transaction():
            row = self.current()
            try:
                validate_mode(failure, row['sha'])
            except (ValueError, KeyError, TypeError):
                raise ControlError('retry_evidence_invalid', 'Continuation proof belongs to different work.') from None
            if row['stage'] not in ('running', 'uncertain', 'overload_wait'):
                raise ControlError('invalid_transition', 'Only a proved failed attempt can schedule a replacement.')
            previous = self.retry_info(row['sha'])
            number = previous['number'] + 1 if previous else 1
            if number > len(delays):
                raise ControlError('retry_exhausted', 'The bounded overload retry budget is exhausted.')
            if previous and previous['failed_turn'] == failure['turn_id']:
                raise ControlError('retry_evidence_reused', 'A failed turn cannot authorize multiple attempts.')
            self.db.execute('''CREATE TABLE IF NOT EXISTS retry_attempts (
                source_sha TEXT NOT NULL, number INTEGER NOT NULL, failed_turn TEXT NOT NULL,
                due REAL NOT NULL, failure TEXT NOT NULL,
                PRIMARY KEY(source_sha,number), UNIQUE(source_sha,failed_turn))''')
            due = now + delays[number - 1]
            if self.db.execute('SELECT 1 FROM retry_attempts WHERE source_sha=? AND failed_turn=?', (row['sha'], failure['turn_id'])).fetchone():
                raise ControlError('retry_evidence_reused', 'No turn may fund a second replacement.')
            self.db.execute('INSERT INTO retry_attempts VALUES(?,?,?,?,?)',
                            (row['sha'], number, failure['turn_id'], due, json.dumps(failure)))
            self.db.execute("UPDATE jobs SET stage='retry_wait',error='serverOverloaded',updated=? WHERE run_id=?",
                            (now, row['run_id']))
        return self.retry_info(row['sha'])


def attempt_directory(paths, source_sha, number):
    root = paths.state / 'jobs' / source_sha
    return root if number == 0 else root / 'attempts' / f'{number:04d}'
