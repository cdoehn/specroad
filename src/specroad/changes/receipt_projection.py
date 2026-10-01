"""Pure receipt projections of independently checked publication inputs."""
from ..model.canonical import canonical_json_bytes
from .committing import verify_committing_journal
from .receipt_values import (ReceiptError, TransactionReceipt, RequestReceipt,
                             CommittedJournal, _result, _created_ids)


def _project_completion_receipts(journal, authoring):
    value = journal.data
    if value['published_count'] != len(value['files']):
        raise ReceiptError('complete_publication_required')
    ids = _created_ids(authoring['operations'])
    transaction = TransactionReceipt(canonical_json_bytes({
        'format_version': 'transaction-receipt-v1', 'outcome': 'committed',
        'journal': value, 'journal_sha256': journal.sha256,
        'command_id': authoring['command_id'], 'operations': authoring['operations'],
        'operations_sha256': authoring['operation_sequence_sha256'],
        'created_ids': ids, 'result_object': _result(journal, ids)}))
    receipt = None
    if value['request_id'] is not None:
        receipt = request_for_transaction(transaction)
    refs = {'transaction': {'path': transaction.path, 'sha256': transaction.sha256},
            'request': None if receipt is None else {'path': receipt.path, 'sha256': receipt.sha256}}
    return transaction, receipt, CommittedJournal(canonical_json_bytes({**value,
        'state': 'committed', 'receipts': refs}))


def prepare_completion_receipts(preflight, journal):
    """Prepare data only. The native finalizer must check disk before persisting it."""
    verify_committing_journal(journal, preflight)
    return _project_completion_receipts(journal, preflight.request.data['authoring_binding'])


def prepare_recovery_receipts(journal):
    """Rebuild the same receipts solely from a fully verified recovery journal."""
    from .committing_values import CommittingJournal
    if type(journal) is not CommittingJournal:
        raise ReceiptError('committing_journal_required', exit_code=2)
    return _project_completion_receipts(journal, journal.data['authoring_binding'])


def request_for_transaction(transaction):
    if type(transaction) is not TransactionReceipt:
        raise ReceiptError('typed_transaction_receipt_required', exit_code=2)
    data, value = transaction.data, transaction.data['journal']
    return RequestReceipt(canonical_json_bytes({
        'format_version': 'request-receipt-v1', 'namespace': 'normative_write',
        'request_id': value['request_id'], 'project_id': value['project_id'],
        'transaction_id': value['transaction_id'], 'actor': value['actor'],
        'operations_sha256': data['operations_sha256'],
        'base_model_root_sha256': value['base_model_root_sha256'],
        'target_model_root_sha256': value['target_model_root_sha256'],
        'result': 'committed', 'created_ids': data['created_ids'],
        'result_object': data['result_object'],
        'transaction_receipt': {'path': transaction.path, 'sha256': transaction.sha256}}))
