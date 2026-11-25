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


def _observe(source, *, local_observation=False):
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
        # Normal readers do not claim unrelated loose operational files as
        # receipt payload. Canonical transaction names still require a directory.
        if local_observation and not directory and re.fullmatch('[0-9a-f]{64}', name) is None:
            continue
        require(directory and re.fullmatch('[0-9a-f]{64}', name) is not None, 'bundle_receipt_path_invalid')
        parent = RECEIPTS_ROOT + '/' + name
        entries = names(parent)
        # Removing optional history can leave an empty directory. Its absence
        # of bytes is observed and rechecked; a partial group is never accepted.
        if local_observation and not entries:
            continue
        if ('journal.json', False) in entries:
            pending = [parent]
            while pending:
                directory_path = pending.pop()
                for child, is_directory in names(directory_path):
                    path = directory_path + '/' + child
                    if is_directory:
                        pending.append(path)
                    else:
                        require(_path_kind(path) in ('migration_original', 'transaction'),
                                'bundle_receipt_path_invalid')
                        paths.append(path)
            continue
        require(set(entries) == {('transaction.json', False), ('committed.json', False)},
                'bundle_receipt_completion_missing', code='SRV060')
        paths.extend(parent + '/' + child for child, _ in entries)
    from ..changes.force_lock import ATTEMPTS
    for transaction, is_directory in names(ATTEMPTS, True):
        require(is_directory, 'force_attempt_directory_required')
        parent = ATTEMPTS + '/' + transaction
        require(set(names(parent)) == {('owner.json', False), ('before.json', False), ('complete.json', False), ('receipts', True)},
            'force_attempt_incomplete')
        paths.extend((parent + '/owner.json', parent + '/before.json', parent + '/complete.json'))
        for name, directory in names(parent + '/receipts'):
            path = parent + '/receipts/' + name
            require(not directory and _path_kind(path) in ('transaction', 'committed', 'request'),
                'force_attempt_receipt_path')
            paths.append(path)
    for path in sorted(paths):
        with opened_resource(source.boundary, path) as (_, info):
            records[path] = ((info.st_dev, info.st_ino), source.boundary.read_bytes(path))
    source.check_current()
    return records, directories


class ReceiptSnapshot:
    """Retain bytes and bounded directory observations through publication."""

    def __init__(self, source, *, imported_manifest=None, local_observation=False):
        self.source = source
        require(not local_observation or imported_manifest is None,
                'bundle_import_requires_complete_receipt_inventory')
        self._local_observation = local_observation
        self.records, self.directories = _observe(source, local_observation=local_observation)
        self.payloads = {p: record[1] for p, record in self.records.items()}
        verify_imported_receipts(imported_manifest, self.payloads)
        self.journals = completed_receipts(self.payloads, source.configuration.project_id)
        self.verify_current()

    def _recheck_files(self):
        try:
            current = _observe(self.source, local_observation=self._local_observation)
        except BundleError as error:
            raise BundleError('bundle_receipt_inventory_changed', code=None, exit_code=6) from error
        if current != (self.records, self.directories):
            raise BundleError('bundle_receipt_inventory_changed', code=None, exit_code=6)

    def verify_current(self):
        self._recheck_files()
        from ..proposals.receipts import HistoricalProposalJournal
        from ..migration.receipts import HistoricalMigrationJournal
        from ..changes.force_history import ForceAudit
        # Pure historical completion readers must not route through the active
        # journal/retry API. Recheck their complete owned group and unchanged
        # directory/inode/byte observations, never current publication authority.
        historical = completed_receipts(self.payloads, self.source.configuration.project_id)
        require(tuple(j.source_bytes for j in historical) ==
                tuple(j.source_bytes for j in self.journals), 'bundle_receipt_inventory_changed')
        try:
            for journal in self.journals:
                if type(journal) not in (HistoricalProposalJournal, HistoricalMigrationJournal, ForceAudit):
                    read_transaction_completion(self.source, journal.data['transaction_id'])
        except ReceiptError as error:
            raise BundleError(error.reason, code=None, exit_code=error.exit_code) from error
        self._recheck_files()
