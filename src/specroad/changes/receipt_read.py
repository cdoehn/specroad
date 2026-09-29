"""Read durable completion proof; never infer commit from output or receipts alone.

Hashes establish local consistency, not signatures. A committed marker and all
its linked receipts are mandatory. Live target checks require original inputs.
"""
from contextlib import contextmanager
import os
from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..security import SafetyViolation
from ..security import paths as guards
from ..storage.project import ProjectSource
from ._journal_codec import journal_path, _transaction
from ._journal_io import _read
from ._lock_files import LockFiles
from ._publication_observation import _root
from .publication_values import PublicationPreflight
from .execution_values import ChangeExecutionError
from .receipt_values import (ReceiptError, CommittedJournal, TransactionReceipt,
    RequestReceipt, TransactionCompletion, completion_marker_path)
from .receipt_projection import prepare_completion_receipts, request_for_transaction
from .receipt_finalization import _target_snapshot


def _expected_target(preflight):
    return {**preflight._model.source_files,
            **{d.path: d.content for d in preflight.request.documents},
            **{d.path: d.content for d in preflight._package_files}}


class _CompletionProof:
    def __init__(self, files, source, transaction_id, *, preflight=None):
        self.files, self.source = files, source
        self.records, self.parents = {}, {}
        self.archive_path = completion_marker_path(transaction_id)
        self.active_path = journal_path(transaction_id)
        self.active_raw = self.read(self.active_path, optional=True)
        self.archived_raw = self.read(self.archive_path, optional=True)
        if self.active_raw is None and self.archived_raw is None:
            raise ReceiptError('committed_proof_missing', path=self.active_path)
        if (self.active_raw is not None and self.archived_raw is not None
                and self.active_raw != self.archived_raw):
            raise ReceiptError('committed_markers_disagree', exit_code=6)
        raw = self.active_raw if self.active_raw is not None else self.archived_raw
        self.journal = CommittedJournal(raw)
        value = self.journal.data
        if (value['transaction_id'] != transaction_id
                or value['project_id'] != source.configuration.project_id
                or value['root_identity'] != list(source.boundary._root_identity)):
            raise ReceiptError('completion_project_binding_mismatch', exit_code=6)
        refs = value['receipts']
        transaction = TransactionReceipt(self.read(refs['transaction']['path']))
        if (transaction.sha256 != refs['transaction']['sha256']
                or canonical_json_bytes(transaction.data['journal']) != self.journal.predecessor.source_bytes):
            raise ReceiptError('transaction_receipt_link_mismatch', exit_code=6)
        self.receipt_paths = [transaction.path]
        request = None
        if refs['request'] is not None:
            request = RequestReceipt(self.read(refs['request']['path']))
            if (request.sha256 != refs['request']['sha256']
                    or canonical_json_bytes(request.data) != canonical_json_bytes(request_for_transaction(transaction).data)):
                raise ReceiptError('request_receipt_link_mismatch', exit_code=6)
            self.receipt_paths.append(request.path)
        if preflight is not None:
            if type(preflight) is not PublicationPreflight:
                raise ReceiptError('publication_preflight_required', exit_code=2)
            expected = prepare_completion_receipts(preflight, self.journal.predecessor)
            if (expected[0].source_bytes != transaction.source_bytes
                    or expected[2].source_bytes != self.journal.source_bytes
                    or (None if request is None else request.source_bytes) !=
                       (None if expected[1] is None else expected[1].source_bytes)):
                raise ReceiptError('completion_request_binding_mismatch', exit_code=6)
            self.live_snapshot = _target_snapshot(source, _expected_target(preflight))
        else:
            self.live_snapshot = None
        self.check()
        if preflight is not None and self.live_snapshot != _target_snapshot(source, _expected_target(preflight)):
            raise ReceiptError('completion_target_identity_changed', exit_code=6)

    def read(self, path, *, optional=False):
        parts, name = tuple(path.split('/')[:-1]), path.rsplit('/', 1)[-1]
        with self.files.directory(parts) as directory:
            if directory is None:
                if not optional: raise ReceiptError('completion_receipt_missing', path=path)
                result = None
            else:
                self.parents[parts] = guards._identity(os.fstat(directory))
                try:
                    info = os.stat(name, dir_fd=directory, follow_symlinks=False)
                except FileNotFoundError:
                    if not optional: raise ReceiptError('completion_receipt_missing', path=path)
                    result = None
                else:
                    identity = guards._identity(info)
                    result = (_read(directory, name, expected_identity=identity), identity)
        self.records[path] = result
        return None if result is None else result[0]

    def check(self):
        self.source.check_current()
        for parts, identity in self.parents.items():
            with self.files.directory(parts) as directory:
                if directory is None or guards._identity(os.fstat(directory)) != identity:
                    raise ReceiptError('receipt_directory_changed', exit_code=6)
        for path, result in self.records.items():
            parts, name = tuple(path.split('/')[:-1]), path.rsplit('/', 1)[-1]
            with self.files.directory(parts) as directory:
                if result is None:
                    if directory is None: continue
                    try: os.stat(name, dir_fd=directory, follow_symlinks=False)
                    except FileNotFoundError: continue
                    raise ReceiptError('completion_proof_changed', path=path, exit_code=6)
                if directory is None or _read(directory, name, expected_identity=result[1]) != result[0]:
                    raise ReceiptError('completion_proof_changed', path=path, exit_code=6)
        self.source.check_current()

    def durable_tokens(self):
        """Exclude work-journal existence; cleanup may remove it, never these files."""
        paths = self.receipt_paths + [self.archive_path]
        return {p: (self.records[p], self.parents.get(tuple(p.split('/')[:-1]))) for p in paths}

    def work_present(self):
        with self.files.directory(tuple(self.active_path.split('/')[:-1])) as directory:
            return directory is not None


def read_transaction_completion(source, transaction_id, *, preflight=None):
    """Observe committed + linked receipts. No writes, locks or retry dispatch.

    Without preflight this verifies historical local records, not the current
    model. Original source identity is required; a copied tree is not its owner.
    """
    if type(source) is not ProjectSource:
        raise ReceiptError('project_source_required', exit_code=2)
    try:
        _transaction(transaction_id)
        with LockFiles(source.boundary.root) as files:
            proof = _CompletionProof(files, source, transaction_id, preflight=preflight)
            work = proof.work_present()
            proof.check()
            return TransactionCompletion._create(proof.journal, live=preflight is not None,
                                                  cleanup=not work)
    except (OSError, ModelError, SafetyViolation, ChangeExecutionError) as error:
        if isinstance(error, ReceiptError): raise
        raise ReceiptError(getattr(error, 'reason', 'completion_read_failed'),
            path=getattr(error, 'path', None),
            exit_code=getattr(error, 'exit_code', 7 if isinstance(error, SafetyViolation) else 5)) from error
