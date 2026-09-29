"""Immutable audit data. Hash agreement is not authentication or live permission."""
from dataclasses import dataclass
from hashlib import sha256
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.errors import ModelError
from ..storage.json_syntax import parse_json_object
from .committing_values import CommittingJournal, CommitPublicationError
from .execution_values import ChangeExecutionError
from ._journal_codec import _hash, _transaction
from .request_ids import normalize_request_id


def transaction_receipt_path(transaction_id):
    token = sha256(_transaction(transaction_id).encode('utf-8')).hexdigest()
    return '.specroad/transactions/receipts/' + token + '/transaction.json'


def completion_marker_path(transaction_id):
    return transaction_receipt_path(transaction_id).rsplit('/', 1)[0] + '/committed.json'


def request_receipt_path(request_id):
    value = normalize_request_id(request_id)
    if value is None:
        raise ReceiptError('request_identity_required', exit_code=2)
    return '.specroad/requests/' + sha256(value.value.encode('utf-8')).hexdigest() + '.json'


class ReceiptError(ChangeExecutionError):
    """A failed acknowledgement may follow a durable commit; never reapply blindly."""
    def __init__(self, reason, *, exit_code=3, mutation_possible=False,
                 committed_possible=False, path=None):
        super().__init__(reason, exit_code=exit_code, write_state='unknown')
        self.path = path
        self.mutation_possible = mutation_possible
        self.committed_possible = committed_possible

    def diagnostic(self):
        return {**super().diagnostic(), 'path': self.path,
                'mutation_possible': self.mutation_possible,
                'committed_possible': self.committed_possible,
                'normative_write_attempted': False, 'receipt_verified': False,
                'recovery_required': True}


def _object(raw):
    if type(raw) is not bytes:
        raise ReceiptError('receipt_bytes_required', exit_code=2)
    try:
        return parse_json_object(raw)
    except ModelError as error:
        raise ReceiptError('invalid_receipt_json') from error


def _full_journal(value):
    try:
        journal = CommittingJournal(canonical_json_bytes(value))
    except (ModelError, ChangeExecutionError, TypeError, ValueError) as error:
        raise ReceiptError('invalid_receipt_journal') from error
    if journal.data['published_count'] != len(journal.data['files']):
        raise ReceiptError('complete_publication_required')
    return journal


def _created_ids(operations):
    values = []
    for operation in operations:
        if operation['op'] == 'create': values.append(operation['artifact']['id'])
        elif operation['op'] == 'relation_add': values.append(operation['relation']['relation_id'])
    return sorted(set(values))


def _result(journal, created_ids):
    data = journal.data
    return {'exit_code': 0, 'status': 'success', 'write_state': 'committed',
            'transaction_id': data['transaction_id'], 'request_id': data['request_id'],
            'target_model_root_sha256': data['target_model_root_sha256'],
            'published_paths': [e['path'] for e in data['files']],
            'created_ids': created_ids}


@dataclass(frozen=True, init=False)
class TransactionReceipt:
    _raw: bytes

    def __init__(self, raw):
        value = _object(raw)
        fields = {'format_version', 'outcome', 'journal', 'journal_sha256', 'command_id',
                  'operations', 'operations_sha256', 'created_ids', 'result_object'}
        if set(value) != fields or value['format_version'] != 'transaction-receipt-v1' or value['outcome'] != 'committed':
            raise ReceiptError('invalid_transaction_receipt_schema')
        journal = _full_journal(value['journal'])
        from .values import ChangeOperation
        try:
            if type(value['operations']) is not list:
                raise ReceiptError('invalid_receipt_operations')
            operations = [ChangeOperation(op).data for op in value['operations']]
        except (ModelError, ChangeExecutionError) as error:
            raise ReceiptError('invalid_receipt_operations') from error
        if (value['command_id'] != 'change apply'
                or value['journal_sha256'] != journal.sha256
                or value['operations_sha256'] != canonical_json_sha256(operations)):
            raise ReceiptError('receipt_binding_mismatch')
        ids = value['created_ids']
        if (type(ids) is not list or any(type(i) is not str or not i for i in ids)
                or ids != _created_ids(operations)
                or canonical_json_bytes(value['result_object']) != canonical_json_bytes(_result(journal, ids))):
            raise ReceiptError('invalid_receipt_result')
        object.__setattr__(self, '_raw', raw)

    @property
    def data(self): return _object(self._raw)
    @property
    def source_bytes(self): return self._raw
    @property
    def sha256(self): return sha256(self._raw).hexdigest()
    @property
    def path(self): return transaction_receipt_path(self.data['journal']['transaction_id'])
    def __bool__(self): raise TypeError('Receipt data is not a verified live completion')


@dataclass(frozen=True, init=False)
class RequestReceipt:
    _raw: bytes

    def __init__(self, raw):
        value = _object(raw)
        fields = {'format_version', 'namespace', 'request_id', 'project_id', 'transaction_id',
                  'actor', 'operations_sha256', 'base_model_root_sha256',
                  'target_model_root_sha256', 'result', 'created_ids', 'result_object',
                  'transaction_receipt'}
        if (set(value) != fields or value['format_version'] != 'request-receipt-v1'
                or value['namespace'] != 'normative_write' or value['result'] != 'committed'):
            raise ReceiptError('invalid_request_receipt_schema')
        from .authoring import normalize_authoring_actor
        try:
            request_receipt_path(value['request_id'])
            normalize_authoring_actor(value['actor'])
            _transaction(value['transaction_id'])
        except (ModelError, TypeError, ValueError) as error:
            raise ReceiptError('invalid_request_receipt_identity') from error
        ref = value['transaction_receipt']
        if (type(ref) is not dict or set(ref) != {'path', 'sha256'}
                or ref['path'] != transaction_receipt_path(value['transaction_id'])
                or not _hash(ref['sha256']) or type(value['project_id']) is not str
                or not value['project_id'] or not all(_hash(value[k]) for k in
                    ('operations_sha256', 'base_model_root_sha256', 'target_model_root_sha256'))):
            raise ReceiptError('invalid_request_receipt_binding')
        ids, result = value['created_ids'], value['result_object']
        if (type(ids) is not list or any(type(i) is not str or not i for i in ids)
                or ids != sorted(set(ids)) or type(result) is not dict
                or set(result) != {'exit_code', 'status', 'write_state', 'transaction_id', 'request_id',
                                    'target_model_root_sha256', 'published_paths', 'created_ids'}
                or result.get('status') != 'success' or result.get('write_state') != 'committed'
                or type(result.get('exit_code')) is not int or result['exit_code'] != 0
                or type(result.get('published_paths')) is not list
                or any(type(p) is not str for p in result['published_paths'])
                or result['published_paths'] != sorted(set(result['published_paths']))
                or result.get('request_id') != value['request_id']
                or result.get('transaction_id') != value['transaction_id']
                or result.get('target_model_root_sha256') != value['target_model_root_sha256']
                or result.get('created_ids') != ids):
            raise ReceiptError('invalid_request_receipt_result')
        from ._journal_codec import _target_path
        try:
            for path in result['published_paths']: _target_path(path)
        except (ModelError, ChangeExecutionError) as error:
            raise ReceiptError('invalid_request_receipt_result') from error
        object.__setattr__(self, '_raw', raw)

    @property
    def data(self): return _object(self._raw)
    @property
    def source_bytes(self): return self._raw
    @property
    def sha256(self): return sha256(self._raw).hexdigest()
    @property
    def path(self): return request_receipt_path(self.data['request_id'])
    def __bool__(self): raise TypeError('Request receipt is not an idempotency decision')


@dataclass(frozen=True, init=False)
class CommittedJournal:
    _raw: bytes

    def __init__(self, raw):
        value = _object(raw)
        if value.get('state') != 'committed' or 'receipts' not in value:
            raise ReceiptError('committed_journal_required')
        refs = value.pop('receipts')
        value['state'] = 'committing'
        journal = _full_journal(value)
        if type(refs) is not dict or set(refs) != {'transaction', 'request'}:
            raise ReceiptError('invalid_committed_receipt_references')
        expected = {'transaction': transaction_receipt_path(value['transaction_id']),
                    'request': None if value['request_id'] is None else request_receipt_path(value['request_id'])}
        for kind, path in expected.items():
            ref = refs[kind]
            if path is None:
                if ref is not None: raise ReceiptError('unexpected_request_receipt')
            elif (type(ref) is not dict or set(ref) != {'path','sha256'}
                    or ref['path'] != path or not _hash(ref['sha256'])):
                raise ReceiptError('invalid_committed_receipt_references')
        object.__setattr__(self, '_raw', raw)

    @property
    def data(self): return _object(self._raw)
    @property
    def source_bytes(self): return self._raw
    @property
    def sha256(self): return sha256(self._raw).hexdigest()
    @property
    def path(self):
        from ._journal_codec import journal_path
        return journal_path(self.data['transaction_id'])
    @property
    def predecessor(self):
        data = self.data
        data.pop('receipts'); data['state'] = 'committing'
        return CommittingJournal(canonical_json_bytes(data))
    def __bool__(self): raise TypeError('A committed marker still needs its bound receipts')


@dataclass(frozen=True, init=False)
class TransactionCompletion:
    _raw: bytes

    @classmethod
    def _create(cls, journal, *, live=False, cleanup=False, warnings=()):
        obj = object.__new__(cls)
        object.__setattr__(obj, '_raw', canonical_json_bytes({
            'format_version': 'transaction-completion-v1', 'state': 'committed',
            'transaction_id': journal.data['transaction_id'],
            'request_id': journal.data['request_id'], 'project_id': journal.data['project_id'],
            'journal_sha256': journal.sha256, 'receipts': journal.data['receipts'],
            'target_model_root_sha256': journal.data['target_model_root_sha256'],
            'commit_completed': True, 'receipt_verified': True,
            'current_target_verified': live, 'cleanup_completed': cleanup,
            'cleanup_required': not cleanup, 'warnings': list(warnings),
            'normative_writes': 0, 'write_authorized': False,
            'idempotency_guaranteed': False, 'atomic_snapshot': False,
            'authenticity_verified': False, 'retry_dispatch_performed': False}))
        return obj

    def __init__(self, *args, **kwargs): raise TypeError('Use a verified completion path')
    @property
    def data(self): return _object(self._raw)
    def __bool__(self): raise TypeError('Inspect completion and cleanup separately')
