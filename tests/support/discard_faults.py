"""Interrupt real discard writes and publication boundaries in owned projects."""
import json
import os
from unittest.mock import patch

from .publication import TRANSACTION
from .recovery_writes import RecoveryWriteFault, fd_path


class DiscardFault(RecoveryWriteFault):
    def selected_path(self, parent, raw):
        value = json.loads(raw)
        if self.site == 'marker' and value.get('state') == 'rolled_back' and 'discard' in value:
            return parent / 'journal.discard'
        if self.site == 'original' and value.get('state') in ('building', 'prepared'):
            return parent / 'journal.before.json'
        if self.site == 'intent' and value.get('phase') == 'intent' and value.get('action') == 'discard':
            return parent / 'intent.json'
        if self.site == 'receipt' and value.get('format_version') == 'recovery-transaction-receipt-v1':
            return parent / 'transaction.json'
        if self.site == 'completed' and value.get('phase') == 'completed' and value.get('action') == 'discard':
            return parent / 'completed.json'
        if self.site == 'barrier' and value.get('format_version') == 'terminal-recovery-pending-v1':
            from specroad.changes._recovery_barrier import barrier_path
            return self.root / barrier_path(TRANSACTION, 'discard')
        return None

    def interrupt(self):
        if self.process_stop:
            print(json.dumps({'pid': os.getpid(), 'interrupted': self.site, 'mode': self.mode}), flush=True)
        return super().interrupt()

    def __enter__(self):
        super().__enter__()
        for name, selected in (('replace', lambda src: src == 'journal.discard'),
                               ('rename', lambda src: src == TRANSACTION),
                               ('unlink', lambda src: str(src).startswith('pending-discard-'))):
            native = getattr(os, name)
            def operation(src, *args, _name=name, _selected=selected, _native=native, **kwargs):
                chosen = not self.fired and self.site == _name and _selected(src)
                if chosen and self.mode == 'before':
                    self.interrupt()
                result = _native(src, *args, **kwargs)
                if chosen and self.mode == 'after':
                    self.interrupt()
                return result
            self.stack.enter_context(patch.object(os, name, side_effect=operation))
        if self.site == 'archive_sync':
            native = os.fsync
            def sync(fd):
                result = native(fd)
                if (not self.fired and fd_path(fd) == self.root / '.specroad/transactions'
                        and not (self.root / '.specroad/transactions' / TRANSACTION).exists()):
                    self.interrupt()
                return result
            self.stack.enter_context(patch.object(os, 'fsync', side_effect=sync))
        return self
