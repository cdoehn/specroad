"""Native I/O interruptions selected by bound recovery content and destination."""
from contextlib import ExitStack
import json
import os
from pathlib import Path
from unittest.mock import patch

from specroad.changes import (CommittingJournal, CommittedJournal, RollingBackJournal,
    RolledBackJournal, RecoveryAuthority, project_lock, complete_published_transaction,
    rollback_interrupted_transaction)
from specroad.changes.receipt_values import request_receipt_path
from support.publication import TRANSACTION

SITES = ('rollback_copy', 'rollback_cursor', 'rollback_terminal', 'rollback_audit',
         'rollback_receipt', 'completion_transaction', 'completion_request',
         'completion_marker', 'completion_audit')
AUTHORITY = RecoveryAuthority('recovery-write-test', '1', lambda request: True)


def journal_at(root, path):
    raw = (root / path).read_bytes()
    cls = {'committing': CommittingJournal, 'committed': CommittedJournal,
           'rolling_back': RollingBackJournal, 'rolled_back': RolledBackJournal}
    return cls[json.loads(raw)['state']](raw)


def invoke(root, path, site, *, authority=AUTHORITY):
    from test_transaction_recovery_completion import recovery_options
    journal = journal_at(root, path)
    operation = (rollback_interrupted_transaction if site.startswith('rollback_')
                 else complete_published_transaction)
    with project_lock(root, **recovery_options(journal)) as held:
        return operation(TRANSACTION, held_lock=held, authority=authority,
                         expected_journal_sha256=journal.sha256)


def scenario(root, site):
    from test_transaction_recovery_rollback import partial_commit
    from test_transaction_recovery_completion import crash_after_last_target
    from test_recovery_inventory import expected_basis, expected_target
    if site.startswith('rollback_'):
        model, plan, journal = partial_commit(root)
        expected, digest = expected_basis(model, plan)
    else:
        model, plan, preflight, journal, _ = crash_after_last_target(root)
        expected, digest = expected_target(model, plan, preflight)
    return journal, expected, digest


def snapshot(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob('*')
            if p.is_file() and p.relative_to(root).as_posix() != '.specroad/locks/project.json'}


def fd_path(fd):
    return Path(os.readlink('/proc/self/fd/' + str(fd)))


class RecoveryWriteFault:
    """Keep real native writes, links and syncs; interrupt one selected boundary."""
    def __init__(self, root, site, mode, *, process_stop=False, on_stage=None, on_link=None):
        self.root, self.site, self.mode = root, site, mode
        self.process_stop, self.on_stage, self.on_link = process_stop, on_stage, on_link
        self.open, self.write, self.fsync, self.link = os.open, os.write, os.fsync, os.link
        self.parents, self.fd, self.path, self.expected = {}, None, None, None
        self.partial = self.fired = self.linked = self.staged = False
        self.parent_fd = None

    def selected_path(self, parent, raw):
        relative = parent.relative_to(self.root).as_posix()
        if self.site == 'rollback_copy':
            return parent / '0.bin' if parent.name == 'rollback' else None
        data = json.loads(raw)
        state, count = data.get('state'), data.get('published_count')
        if relative == '.specroad/transactions/' + TRANSACTION:
            if ((self.site == 'rollback_cursor' and state == 'rolling_back' and count == 0)
                    or (self.site == 'rollback_terminal' and state == 'rolled_back')):
                return parent / 'journal.rollback'
            if self.site == 'completion_marker' and state == 'committed':
                return parent / 'journal.complete'
        if (self.site in ('rollback_receipt', 'completion_transaction')
                and relative.startswith('.specroad/transactions/receipts/')):
            return parent / 'transaction.json'
        if self.site == 'completion_request' and relative == '.specroad/requests':
            return self.root / request_receipt_path(data['request_id'])
        if (self.site in ('rollback_audit', 'completion_audit')
                and data.get('format_version') == 'terminal-recovery-audit-v1'):
            return parent / (data['action'] + '.json')
        return None

    def opening(self, name, flags, *args, **kwargs):
        fd = self.open(name, flags, *args, **kwargs)
        self.parents.pop(fd, None)
        if kwargs.get('dir_fd') is not None and (
                flags & os.O_TMPFILE == os.O_TMPFILE or flags & os.O_CREAT):
            self.parents[fd] = fd_path(kwargs['dir_fd'])
        return fd

    def interrupt(self):
        self.fired = True
        if self.process_stop:
            os._exit(23)
        raise OSError(5, 'interrupted recovery derivative')

    def writing(self, fd, raw):
        if not self.fired and self.fd is None and fd in self.parents:
            parent = self.parents[fd]
            if parent.is_relative_to(self.root):
                path = self.selected_path(parent, bytes(raw))
                if path is not None:
                    self.fd, self.path, self.expected = fd, path, bytes(raw)
        if fd == self.fd and not self.fired:
            if self.mode == 'empty':
                self.interrupt()
            if self.mode == 'prefix':
                if not self.partial:
                    self.partial = True
                    assert self.write(fd, raw[:17]) == 17
                    return 17
                self.interrupt()
        return self.write(fd, raw)

    def syncing(self, fd):
        result = self.fsync(fd)
        if not self.fired and fd == self.fd and not self.staged:
            self.staged = True
            if self.on_stage is not None:
                self.on_stage(fd, self)
            if self.mode == 'file_sync':
                self.interrupt()
        if not self.fired and self.linked and fd == self.parent_fd and self.mode == 'parent_sync':
            self.interrupt()
        return result

    def linking(self, source, target, **kwargs):
        selected = source == '/proc/self/fd/' + str(self.fd)
        if selected:
            if self.on_link is not None:
                self.on_link(self)
            if self.mode == 'link_before':
                self.interrupt()
        result = self.link(source, target, **kwargs)
        if selected:
            self.linked, self.parent_fd = True, kwargs['dst_dir_fd']
            if self.mode == 'link_after':
                self.interrupt()
        return result

    def __enter__(self):
        self.stack = ExitStack()
        for name, function in (('open', self.opening), ('write', self.writing),
                               ('fsync', self.syncing), ('link', self.linking)):
            self.stack.enter_context(patch.object(os, name, side_effect=function))
        return self

    def __exit__(self, *exception):
        return self.stack.__exit__(*exception)
