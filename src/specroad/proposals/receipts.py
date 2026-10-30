"""Read-only original Proposal receipts using the existing closed contracts.

The historical value has deliberately a different type from live journals.
It cannot be passed to publishing, rollback, resume or request-retry APIs.
No new persisted fields, result labels or paths are accepted here.
"""
from dataclasses import dataclass
from hashlib import sha256

from ..changes._journal_codec import validate_building_document
from ..changes.receipt_values import (RequestReceipt, transaction_receipt_path,
    completion_marker_path, _result, _created_ids)
from ..changes.values import ChangeOperation
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..storage.json_syntax import parse_json_object
from .values import require


@dataclass(frozen=True, init=False)
class HistoricalProposalJournal:
    source_bytes: bytes

    @classmethod
    def _checked(cls, raw):
        result = object.__new__(cls)
        object.__setattr__(result, 'source_bytes', raw)
        return result

    def __init__(self, *args, **kwargs):
        raise TypeError('Use read_proposal_receipts with complete original receipts')

    @property
    def data(self):
        return parse_json_object(self.source_bytes)

    def __bool__(self):
        raise TypeError('A historical receipt is not an active recovery or apply grant')


def read_proposal_receipts(files, project_id):
    """Read exactly one complete group, preserving all original file bytes."""
    require(type(files) is dict and files and all(type(p) is str and type(b) is bytes
            for p, b in files.items()), 'proposal_original_receipts_required')
    transactions = [(path, parse_json_object(raw)) for path, raw in files.items()
                    if path.endswith('/transaction.json')]
    require(len(transactions) == 1, 'proposal_original_completion_required')
    path, receipt = transactions[0]
    require(set(receipt) == {'format_version', 'outcome', 'journal', 'journal_sha256',
            'command_id', 'operations', 'operations_sha256', 'created_ids', 'result_object'}
            and receipt['format_version'] == 'transaction-receipt-v1'
            and receipt['outcome'] == 'committed' and receipt['command_id'] == 'proposal apply',
            'proposal_original_transaction_invalid')
    journal = receipt['journal']
    require(type(journal) is dict and journal.get('state') == 'committing'
            and type(journal.get('files')) is list and type(journal.get('published_count')) is int
            and journal['published_count'] == len(journal['files'])
            and all(type(row) is dict and row.get('published') is True for row in journal['files']),
            'proposal_original_publication_incomplete')
    building = {**journal, 'state': 'building', 'published_count': 0,
                'files': [{**row, 'published': False} for row in journal['files']]}
    validate_building_document(building, historical_proposal=True)
    require(journal['project_id'] == project_id, 'proposal_completion_project_mismatch', exit_code=6)
    require(path == transaction_receipt_path(journal['transaction_id'])
            and receipt['journal_sha256'] == sha256(canonical_json_bytes(journal)).hexdigest(),
            'proposal_original_receipt_binding_invalid')
    require(type(receipt['operations']) is list, 'proposal_original_operations_invalid')
    operations = [ChangeOperation(op).data for op in receipt['operations']]
    authoring = journal['authoring_binding']
    require(operations == authoring['operations']
            and receipt['operations_sha256'] == canonical_json_sha256(operations)
            == authoring['operation_sequence_sha256'], 'proposal_completion_operations_mismatch')
    require(operations and operations[-1]['op'] == 'proposal_control'
            and operations[-1]['events'][0]['from'] == 'approved'
            and operations[-1]['events'][-1]['to'] == 'applied',
            'proposal_completion_control_mismatch')
    original = HistoricalProposalJournal._checked(canonical_json_bytes(journal))
    result = _result(original, _created_ids(operations))
    require(receipt['created_ids'] == _created_ids(operations) and receipt['result_object'] == result,
            'proposal_original_result_mismatch')
    refs = {'transaction': {'path': path, 'sha256': sha256(files[path]).hexdigest()}, 'request': None}
    used = {path}
    if journal['request_id'] is not None:
        from ..changes.receipt_values import request_receipt_path
        request_path = request_receipt_path(journal['request_id'])
        require(request_path in files, 'proposal_original_request_missing')
        request = RequestReceipt(files[request_path])
        expected = {'format_version': 'request-receipt-v1', 'namespace': 'normative_write',
            'request_id': journal['request_id'], 'project_id': project_id,
            'transaction_id': journal['transaction_id'], 'actor': journal['actor'],
            'operations_sha256': receipt['operations_sha256'],
            'base_model_root_sha256': journal['base_model_root_sha256'],
            'target_model_root_sha256': journal['target_model_root_sha256'],
            'result': 'committed', 'created_ids': receipt['created_ids'], 'result_object': result,
            'transaction_receipt': refs['transaction']}
        require(request.data == expected, 'proposal_original_request_binding_invalid')
        refs['request'] = {'path': request_path, 'sha256': request.sha256}
        used.add(request_path)
    marker = completion_marker_path(journal['transaction_id'])
    require(marker in files and parse_json_object(files[marker]) ==
            {**journal, 'state': 'committed', 'receipts': refs},
            'proposal_original_completion_invalid')
    used.add(marker)
    require(used == set(files), 'proposal_completion_receipt_set_mismatch')
    return HistoricalProposalJournal._checked(files[marker])
