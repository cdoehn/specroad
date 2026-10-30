"""Pure operational byte checks, separate from model hashes and filesystem proof.

The portable set contains native archived completion markers and their linked
receipts. It never contains active work, and supplies no live publication proof.
"""
import re
from hashlib import sha256

from ..changes.receipt_projection import request_for_transaction
from ..changes.receipt_values import (CommittedJournal, TransactionReceipt,
    RequestReceipt, ReceiptError, completion_marker_path)
from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..model.operational_paths import REQUESTS_ROOT, RECEIPTS_ROOT
from ..storage.json_syntax import parse_json_object
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
        # Historical Proposal completions have the same closed receipt
        # contracts, but a distinct read-only native type. Never admit them to
        # the live change-apply journal/retry constructors.
        from ..proposals.receipts import read_proposal_receipts
        from ..changes.receipt_values import transaction_receipt_path, request_receipt_path
        remaining = dict(files)
        proposal_journals, claimed = [], set()
        for path, raw in files.items():
            if _path_kind(path) != 'transaction':
                continue
            data = parse_json_object(raw)
            if data.get('command_id') != 'proposal apply':
                continue
            journal = data.get('journal')
            require(type(journal) is dict and type(journal.get('transaction_id')) is str,
                    'bundle_receipt_path_binding', code='SRV060')
            names = {transaction_receipt_path(journal['transaction_id']),
                     completion_marker_path(journal['transaction_id'])}
            if journal.get('request_id') is not None:
                names.add(request_receipt_path(journal['request_id']))
            require(path in names and names <= files.keys() and not claimed.intersection(names),
                    'bundle_receipt_completion_missing', code='SRV060')
            proposal_journals.append(read_proposal_receipts({p: files[p] for p in names}, project_id))
            claimed.update(names)
            for name in names:
                remaining.pop(name)
        files = remaining
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
        return tuple(journals + proposal_journals)
    except (ReceiptError, ModelError) as error:
        raise BundleError(error.reason) from error


def _check_exclusions(manifest):
    for item in manifest['excluded_contents']:
        operational = receipt_path(item['path'])
        require(operational == (item['reason'] == 'operational_receipts_excluded'),
                'bundle_receipt_exclusion_path')
        if operational:
            _path_kind(item['path'])


def verify_payload_receipts(container):
    files = {p: b for p, b in container.files.items() if receipt_path(p)}
    manifest = container.manifest
    _check_exclusions(manifest)
    require(not files or (manifest['bundle_kind'] == 'project'
            and manifest['idempotency_scope'] == 'portable'), 'bundle_receipts_not_portable')
    completed_receipts(files, manifest['project_id'])
    return files


def verify_imported_receipts(imported_manifest, payloads):
    """Check historical transport hashes independently of the model domain."""
    if imported_manifest is not None:
        manifest = parse_json_object(imported_manifest)
        _check_exclusions(manifest)
        # A complete group can disappear without leaving an orphan. Its
        # previously observed transport binding still forbids silently
        # certifying an empty or smaller history, even on explicit exclusion.
        for entry in manifest['entries']:
            if not receipt_path(entry['path']):
                continue
            raw = payloads.get(entry['path'])
            if (raw is None or len(raw) != entry['size']
                    or sha256(raw).hexdigest() != entry['sha256']):
                raise BundleError('bundle_imported_receipt_missing_or_changed', code=None, exit_code=6)
