"""Normal read-only completion and request proof for full-snapshot writers."""
from hashlib import sha256
from ..storage.project import ProjectSource
from ..storage.json_syntax import parse_json_object as parsed
from ..model.canonical import canonical_json_sha256 as digest
from ._schema_transition_io import read
from .receipt_values import transaction_receipt_path, request_receipt_path, RequestReceipt
from .schema_transition_values import require, SchemaTransitionError
from .execution_values import ChangeExecutionError
from .normal_completion import NormalCompletionProof
from .snapshot_write_values import check_write, result


class SnapshotCompletion:
    """Actual normal receipt bytes; never a reconstructed legacy journal."""
    def __init__(self, proof):
        self.proof=proof
        self.plan=check_write(proof.write)
        self.source_bytes=proof.read(transaction_receipt_path(proof.write['marker']['transaction_id']))
        self.sha256=sha256(self.source_bytes).hexdigest()
        self.receipt_root=transaction_receipt_path(proof.write['marker']['transaction_id']).rsplit('/',1)[0]
        self.data=dict(backup=proof.write['validation']['backup'],
            project_id=proof.write['marker']['project_id'],transaction_id=proof.write['marker']['transaction_id'],
            validation=proof.write['validation']['qualification'])
        self.check()

    def check(self):self.proof.check()
    def __bool__(self):raise TypeError('A receipt is not write authority')


def completion_proof(files, transaction_id):
    raw=read(files,transaction_receipt_path(transaction_id))
    if parsed(raw).get('format_version')=='transaction-receipt-v2':
        source=ProjectSource(files.boundary.root)
        try:
            proof=NormalCompletionProof(files,source,transaction_id)
            return SnapshotCompletion(proof)
        except ChangeExecutionError as error:
            raise SchemaTransitionError(getattr(error,'reason','transition_receipt_changed'),
                exit_code=getattr(error,'exit_code',6)) from error
    require(parsed(raw).get('format_version') in
        ('schema-transition-receipt-v1', 'merge-transition-receipt-v1'),
        'invalid_write_receipt')
    from .schema_transition_recovery import completion_proof as legacy
    return legacy(files,transaction_id)


def historical_request(files, plan, project_id):
    identity=plan.data['request_id']
    if identity is None:return None
    raw=read(files,request_receipt_path(identity),optional=True)
    if raw is None:return None
    receipt=RequestReceipt(raw)
    if receipt.data['format_version']!='request-receipt-v2':
        from .schema_transition_recovery import historical_request as legacy
        return legacy(files,plan,project_id)
    source=ProjectSource(files.boundary.root,expected_project_id=project_id)
    proof=NormalCompletionProof(files,source,receipt.data['transaction_id'])
    require(proof.read(request_receipt_path(identity))==raw,'transition_request_receipt_changed')
    # Even an intent conflict needs a genuine intact receipt before diagnosis.
    actual=receipt.data['operations_sha256'];expected=digest(plan.data['operations'])
    if actual!=expected:
        from .idempotency_values import RequestIdConflict
        raise RequestIdConflict(identity,actual,expected,path=receipt.path)
    require(proof.write['marker']['project_id']==project_id
        and proof.write['marker']['command_id'] in ('migrate apply','merge apply'),
        'transition_request_kind_mismatch')
    check_write(proof.write);proof.check()
    return result(proof.write,current=False)
