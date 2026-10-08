"""Checked disposable work storage, never the durable receipt namespace.

The caller must establish and archive the committed proof before discard.
No normative publishing or recovery decisions are implemented by this worker.
"""
import os
from ..model.errors import ModelError
from ..security import SafetyViolation
from ..security import paths as guards
from ._publication_observation import _root
from ._target_materialization import publication_target
from ._journal_io import _read
from ._staging_files import _write_new, _image
from .publication_check import _same_request
from .publication_values import PublicationPreflight, PublicationAuthority
from .locking import HeldProjectLock
from .execution_values import ChangeExecutionError
from .receipt_values import ReceiptError, TransactionCompletion
from .receipt_read import _CompletionProof, _expected_target
from .receipt_finalization import _target_snapshot


class _CleanupSession:
    def __init__(self, preflight, transaction_id, held, authority):
        self.preflight, self.transaction_id, self.held = preflight, transaction_id, held
        self.files, self.source = held._files, _root(publication_target(preflight))
        self.proof = _CompletionProof(self.files, self.source, transaction_id, preflight=preflight)
        self.journal = self.proof.journal
        self.prefix = tuple(self.journal.path.split('/')[:-1])
        self.target_snapshot = self.proof.live_snapshot
        self.tokens = None
        self.check_lock()
        detached = preflight.request.detached()
        try: allowed = authority.check(detached)
        except Exception as error:
            raise ReceiptError('cleanup_authority_failed', exit_code=7, committed_possible=True) from error
        _same_request(detached, preflight.request)
        if type(allowed) is not bool or not allowed:
            raise ReceiptError('cleanup_authorization_denied', exit_code=7, committed_possible=True)
        self.proof.check()
        self.check_target()
        self.remaining = self.work_state()

    def check_lock(self):
        self.held.check()
        value, journal = self.held.record.data, self.journal.data
        if (value['kind'] != 'writer' or value['command'] != 'change apply'
                or value['project_id'] != journal['project_id']
                or value['request_id'] != journal['request_id']
                or value['transaction_id'] != journal['transaction_id']
                or self.source.boundary.root != self.files.boundary.root
                or list(self.files.boundary._root_identity) != journal['root_identity']):
            raise ReceiptError('cleanup_lock_binding_mismatch', exit_code=6)
        active = self.files.journal_entries()
        if active not in ((), ('/'.join(self.prefix),)):
            raise ReceiptError('cleanup_foreign_recovery_entries', exit_code=5)
        self.source.check_current()

    def check_target(self):
        if _target_snapshot(self.source, _expected_target(self.preflight)) != self.target_snapshot:
            raise ReceiptError('cleanup_target_changed', exit_code=6)

    def work_state(self):
        """Inventory of only expendable work, with strict subset matching on resume."""
        result = {}
        with self.files.directory(self.prefix) as directory:
            if directory is None: return result
            result['/'.join(self.prefix)] = ('directory', guards._identity(os.fstat(directory)))
            names = set(os.listdir(directory))
            if not names <= {'journal.json', 'before', 'staging'}:
                raise ReceiptError('cleanup_unknown_work_entries', exit_code=6)
            if 'journal.json' in names:
                raw = _read(directory, 'journal.json')
                if raw != self.journal.source_bytes:
                    raise ReceiptError('cleanup_journal_changed', exit_code=6)
                result[self.journal.path] = ('file', guards._identity(os.stat('journal.json', dir_fd=directory, follow_symlinks=False)), self.journal.sha256)
            elif self.proof.archived_raw is None:
                raise ReceiptError('cleanup_missing_committed_marker', exit_code=6)
        expected_before = {e['before_image_path'].rsplit('/',1)[-1]: e
                           for e in self.journal.data['files'] if e['existed_before']}
        for kind in ('before', 'staging'):
            parts = (*self.prefix, kind)
            with self.files.directory(parts) as directory:
                if directory is None: continue
                result['/'.join(parts)] = ('directory', guards._identity(os.fstat(directory)))
                names = set(os.listdir(directory))
                allowed = expected_before if kind == 'before' else {}
                if not names <= set(allowed):
                    raise ReceiptError('cleanup_unknown_work_images', exit_code=6)
                for name in sorted(names):
                    entry = allowed[name]
                    identity = _image(directory, name, entry['before_size'], entry['before_sha256'])
                    result['/'.join((*parts,name))] = ('file', identity, entry['before_sha256'])
        return result

    def guard(self):
        self.check_lock()
        current = _CompletionProof(self.files, self.source, self.transaction_id)
        if current.journal.source_bytes != self.journal.source_bytes:
            raise ReceiptError('cleanup_committed_proof_changed', exit_code=6)
        if self.tokens is not None and current.durable_tokens() != self.tokens:
            raise ReceiptError('cleanup_receipts_replaced', exit_code=6)
        self.check_target()
        if self.work_state() != self.remaining:
            raise ReceiptError('cleanup_work_changed', exit_code=6)

    def archive(self):
        self.guard()
        path = self.proof.archive_path
        with self.files.directory(tuple(path.split('/')[:-1])) as directory:
            if directory is None:
                raise ReceiptError('cleanup_receipt_directory_missing', exit_code=6)
            if self.proof.archived_raw is None:
                _write_new(directory, 'committed.json', self.journal.source_bytes)
            else:
                # Resume cleanup only; resynchronize the existing, exact marker.
                fd = os.open('committed.json', os.O_RDONLY | os.O_NOFOLLOW | getattr(os,'O_NONBLOCK',0), dir_fd=directory)
                try:
                    identity = guards._identity(os.fstat(fd))
                    if _read(directory, 'committed.json', expected_identity=identity) != self.journal.source_bytes:
                        raise ReceiptError('cleanup_archive_changed', exit_code=6)
                    os.fsync(fd); os.fsync(directory)
                finally: os.close(fd)
        self.proof = _CompletionProof(self.files, self.source, self.transaction_id)
        if self.proof.journal.source_bytes != self.journal.source_bytes:
            raise ReceiptError('cleanup_archive_changed', exit_code=6)
        self.tokens = self.proof.durable_tokens()
        self.guard()

    def discard(self):
        # Children before parents, and journal last: no recursive deletion and
        # no wildcard. The immutable committed marker remains in receipts/.
        prefix = '/'.join(self.prefix)
        paths = [p for p,v in self.remaining.items() if v[0]=='file' and p != self.journal.path]
        paths += [prefix+'/before', prefix+'/staging', self.journal.path, prefix]
        for path in paths:
            if path not in self.remaining: continue
            self.guard()
            parts, name = tuple(path.split('/')[:-1]), path.rsplit('/',1)[-1]
            expected = self.remaining[path]
            with self.files.directory(parts) as parent:
                if parent is None: raise ReceiptError('cleanup_parent_missing', exit_code=6)
                info = os.stat(name, dir_fd=parent, follow_symlinks=False)
                if guards._identity(info) != expected[1]:
                    raise ReceiptError('cleanup_entry_replaced', exit_code=6)
                if expected[0] == 'directory': os.rmdir(name, dir_fd=parent)
                else: os.unlink(name, dir_fd=parent)
                del self.remaining[path]
                os.fsync(parent)
            self.guard()
