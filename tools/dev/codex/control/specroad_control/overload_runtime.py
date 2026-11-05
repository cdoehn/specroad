"""Worker waiting policy; evidence and SQLite checkpoints have separate owners."""
from . import overload_wait
from .errors import ControlError
from .telemetry import record


class OverloadWaiting:
    """Read-only completion observation before the Engine's existing dispatch path."""
    def begin_wait(self, ledger, source, directory, number):
        evidence, progress, ready = overload_wait.observe(self.config, self.codex, directory, source, number)
        self.exchange.source(source)
        self.exchange.assert_current(source, ledger.known_runs())
        if ready:
            checkpoint = {'workspace_sha256': evidence['workspace_sha256'],
                          'history_sha256': progress['history_sha256']}
            if self.adopt_failed_output(ledger, source, directory, checkpoint=checkpoint):
                return {'halted': False, 'again': True}
            try:
                pending = self.schedule_retry(ledger, source, directory, checkpoint=checkpoint)
            except ControlError as exc:
                if exc.code == 'retry_patch_present' and self.adopt_failed_output(ledger, source, directory, checkpoint=checkpoint):
                    return {'halted': False, 'again': True}
                raise
            return {'halted': False, 'again': False, 'retry_after': max(0, pending['due'] - self.clock())}
        now = self.clock()
        next_at, since = overload_wait.next_observation(progress, ready, now, None)
        saved = ledger.begin_overload_wait(evidence, progress, next_at, since, now)
        self.update(stage='overload_wait', error='serverOverloaded', retry_at=None,
                    retry_attempt=number, retry_mode='continuation', retry_blocked_reason=None,
                    overload_check_at=saved['next_at'])
        record('retry_decision', source_sha256=source['sha256'], decision='observe_background',
               retry_attempt=number, wait_seconds=next_at-now, overload_check_at=next_at)
        return {'halted': False, 'again': False, 'retry_after': next_at-now}

    def observe_wait(self, ledger, source):
        try:
            saved = ledger.overload_wait()
            now = self.clock()
            self.update(retry_attempt=saved['number'], retry_at=None, retry_mode='continuation',
                        overload_check_at=saved['next_at'])
            if not self.gate.allowed:
                return {'halted': False, 'again': False}
            if saved['next_at'] > now:
                return {'halted': False, 'again': False, 'retry_after': saved['next_at']-now}
            directory = ledger.attempt_directory(self.paths, source['sha256'], saved['number'])
            evidence, progress, ready = overload_wait.observe(
                self.config, self.codex, directory, source, saved['number'], saved=saved)
            self.exchange.source(source)
            self.exchange.assert_current(source, ledger.known_runs())
            if ready:
                # Re-read strict terminal evidence. Never replace the waiting
                # workspace baseline with a fresh one when promoting to retry.
                checkpoint = {'workspace_sha256': evidence['workspace_sha256'],
                              'history_sha256': progress['history_sha256']}
                if self.adopt_failed_output(ledger, source, directory, checkpoint=checkpoint):
                    return {'halted': False, 'again': True}
                try:
                    pending = self.schedule_retry(ledger, source, directory, checkpoint=checkpoint)
                except ControlError as exc:
                    if exc.code == 'retry_patch_present' and self.adopt_failed_output(ledger, source, directory, checkpoint=checkpoint):
                        return {'halted': False, 'again': True}
                    raise
                self.update(overload_check_at=None)
                return {'halted': False, 'again': False, 'retry_after': max(0, pending['due']-self.clock())}
            next_at, since = overload_wait.next_observation(progress, ready, now, saved['settle_since'])
            ledger.advance_overload_wait(saved, progress, next_at, since)
            self.update(overload_check_at=next_at)
            return {'halted': False, 'again': False, 'retry_after': next_at-now}
        except ControlError as exc:
            ledger.change('uncertain', error=exc.code)
            self.update(stage='uncertain', error=exc.code, retry_blocked_reason=exc.code)
            record('retry_decision', source_sha256=source['sha256'], decision='blocked', reason=exc.code)
            return {'halted': True, 'again': False}
