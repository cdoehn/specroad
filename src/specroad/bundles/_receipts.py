"""Completed operational bytes, checked separately from the normative model.

The portable set contains native archived completion markers and their linked
receipts. It never contains active work, and supplies no live publication proof.
"""
import re

from ..changes.receipt_projection import request_for_transaction
from ..changes.receipt_read import read_transaction_completion
from ..changes.receipt_values import (CommittedJournal, TransactionReceipt,
    RequestReceipt, ReceiptError, completion_marker_path)
from ..model.canonical import canonical_json_bytes
from ..model.operational_paths import REQUESTS_ROOT, RECEIPTS_ROOT
from ..security.resource_access import opened_resource, directory_entries
from .errors import BundleError
from .manifest import require


def receipt_path(path):
    return any(path == root or path.startswith(root + '/') for root in (REQUESTS_ROOT, RECEIPTS_ROOT))


def _path_kind(path):
    if re.fullmatch(re.escape(REQUESTS_ROOT) + r'/[0-9a-f]{64}\.json', path):
        return 'request'
    match = re.fullmatch(re.escape(RECEIPTS_ROOT) + r'/[0-9a-f]{64}/(transaction|committed)\.json', path)
    require(match is not None, 'bundle_receipt_path_invalid')
    return match[1]


def completed_receipts(files, project_id):
    """Verify a closed set of owned native bytes, independent of host identity."""
    try:
        values = {}
        for path, raw in files.items():
            kind = _path_kind(path)
            value = {'request': RequestReceipt, 'transaction': TransactionReceipt,
                     'committed': CommittedJournal}[kind](raw)
            expected = completion_marker_path(value.data['transaction_id']) if kind == 'committed' else value.path
            require(path == expected, 'bundle_receipt_path_binding', code='SRV060')
            values[path] = value
        used, journals = set(), []
        for path, journal in values.items():
            if type(journal) is not CommittedJournal:
                continue
            data = journal.data
            require(data['project_id'] == project_id, 'bundle_receipt_project_binding', code='SRV060')
            refs = data['receipts']
            transaction = values.get(refs['transaction']['path'])
            require(type(transaction) is TransactionReceipt, 'bundle_transaction_receipt_missing', code='SRV060')
            tx = transaction.data
            require(transaction.sha256 == refs['transaction']['sha256']
                    and canonical_json_bytes(tx['journal']) == journal.predecessor.source_bytes,
                    'bundle_transaction_receipt_binding', code='SRV060')
            authoring = tx['journal']['authoring_binding']
            require(tx['command_id'] == authoring['command_id']
                    and tx['operations_sha256'] == authoring['operation_sequence_sha256']
                    and canonical_json_bytes(tx['operations']) == canonical_json_bytes(authoring['operations']),
                    'bundle_receipt_operations_binding', code='SRV060')
            linked = {path, transaction.path}
            if refs['request'] is not None:
                request = values.get(refs['request']['path'])
                require(type(request) is RequestReceipt, 'bundle_request_receipt_missing', code='SRV060')
                require(request.sha256 == refs['request']['sha256']
                        and canonical_json_bytes(request.data) == canonical_json_bytes(request_for_transaction(transaction).data),
                        'bundle_request_receipt_binding', code='SRV060')
                linked.add(request.path)
            require(not used.intersection(linked), 'bundle_receipt_multiple_owners', code='SRV060')
            used.update(linked)
            journals.append(journal)
        require(used == set(files), 'bundle_receipt_completion_missing', code='SRV060')
        return tuple(journals)
    except ReceiptError as error:
        raise BundleError(error.reason) from error


def verify_payload_receipts(container):
    files = {p: b for p, b in container.files.items() if receipt_path(p)}
    manifest = container.manifest
    require(not files or (manifest['bundle_kind'] == 'project'
            and manifest['idempotency_scope'] == 'portable'), 'bundle_receipts_not_portable')
    completed_receipts(files, manifest['project_id'])
    return files


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

    def __init__(self, source):
        self.source = source
        self.records, self.directories = _observe(source)
        self.payloads = {p: record[1] for p, record in self.records.items()}
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
        try:
            for journal in self.journals:
                read_transaction_completion(self.source, journal.data['transaction_id'])
        except ReceiptError as error:
            raise BundleError(error.reason, code=None, exit_code=error.exit_code) from error
        self._recheck_files()
