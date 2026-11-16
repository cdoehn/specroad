"""Descriptor-bound observation shared by historical and normal receipts.

This reader captures bytes and directory/file identities. It grants no writer
capability and has no journal, replay, cleanup or repair operation.
"""
import os
from ..security import paths as guards
from ._journal_io import _read
from .receipt_values import ReceiptError


class CompletionRecords:
    def __init__(self, files, source, *, read_record=_read):
        self.files, self.source = files, source
        self.records, self.parents = {}, {}
        self._read_record = read_record

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
                    result = (self._read_record(directory, name, expected_identity=identity), identity)
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
                if directory is None or self._read_record(directory, name, expected_identity=result[1]) != result[0]:
                    raise ReceiptError('completion_proof_changed', path=path, exit_code=6)
        self.source.check_current()

    def durable_tokens(self):
        """Exclude work-journal existence; cleanup may remove it, never these files."""
        paths = self.receipt_paths + [self.archive_path]
        return {p: (self.records[p], self.parents.get(tuple(p.split('/')[:-1]))) for p in paths}
