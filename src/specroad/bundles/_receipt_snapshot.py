"""Observe completed receipt bytes and retain native filesystem proof.

Pure payload checks live in _receipts; these inode and directory observations
are local freshness guards and never inputs to the normative model hash.
"""
import re

from ..changes.receipt_read import read_transaction_completion
from ..changes.receipt_values import ReceiptError
from ..model.operational_paths import REQUESTS_ROOT, RECEIPTS_ROOT
from ..security.resource_access import opened_resource, directory_entries
from .errors import BundleError
from .manifest import require
from ._receipts import _path_kind, completed_receipts, verify_imported_receipts


def _observe(source):
    records, directories = {}, {}

    def names(path, optional=False):
        with opened_resource(source.boundary, path, directory=True, missing_ok=optional) as (fd, info):
            if fd is None:
                directories[path] = None
                return ()
            entries = directory_entries(source.boundary, path)
            directories[path] = ((info.st_dev, info.st_ino), entries)
            return entries

    paths = []
    for name, directory in names(REQUESTS_ROOT, True):
        path = REQUESTS_ROOT + '/' + name
        require(not directory and _path_kind(path) == 'request', 'bundle_receipt_path_invalid')
        paths.append(path)
    for name, directory in names(RECEIPTS_ROOT, True):
        require(directory and re.fullmatch('[0-9a-f]{64}', name) is not None, 'bundle_receipt_path_invalid')
        parent = RECEIPTS_ROOT + '/' + name
        entries = names(parent)
        require(set(entries) == {('transaction.json', False), ('committed.json', False)},
                'bundle_receipt_completion_missing', code='SRV060')
        paths.extend(parent + '/' + child for child, _ in entries)
    for path in sorted(paths):
        with opened_resource(source.boundary, path) as (_, info):
            records[path] = ((info.st_dev, info.st_ino), source.boundary.read_bytes(path))
    source.check_current()
    return records, directories


class ReceiptSnapshot:
    """Retain bytes and bounded directory observations through publication."""

    def __init__(self, source, *, imported_manifest=None):
        self.source = source
        self.records, self.directories = _observe(source)
        self.payloads = {p: record[1] for p, record in self.records.items()}
        verify_imported_receipts(imported_manifest, self.payloads)
        self.journals = completed_receipts(self.payloads, source.configuration.project_id)
        self.verify_current()

    def _recheck_files(self):
        try:
            current = _observe(self.source)
        except BundleError as error:
            raise BundleError('bundle_receipt_inventory_changed', code=None, exit_code=6) from error
        if current != (self.records, self.directories):
            raise BundleError('bundle_receipt_inventory_changed', code=None, exit_code=6)

    def verify_current(self):
        self._recheck_files()
        from ..proposals.receipts import HistoricalProposalJournal
        # Pure historical completion readers must not route through the active
        # journal/retry API. Recheck their complete owned group and unchanged
        # directory/inode/byte observations, never current publication authority.
        historical = completed_receipts(self.payloads, self.source.configuration.project_id)
        require(tuple(j.source_bytes for j in historical) ==
                tuple(j.source_bytes for j in self.journals), 'bundle_receipt_inventory_changed')
        try:
            for journal in self.journals:
                if type(journal) is not HistoricalProposalJournal:
                    read_transaction_completion(self.source, journal.data['transaction_id'])
        except ReceiptError as error:
            raise BundleError(error.reason, code=None, exit_code=error.exit_code) from error
        self._recheck_files()
