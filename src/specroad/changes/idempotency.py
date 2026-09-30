"""Decide a normative retry before any new plan or publication.

Identity normalization is pure, confirmed disk receipts have one reader, and
result values contain no writer capability. A miss still needs a locked recheck.
"""
from ..model.errors import ModelError
from ..security import SafetyViolation
from ..storage.project import ProjectSource
from .authoring_values import AuthoringRequest
from .execution_values import ChangeExecutionError
from .receipt_values import ReceiptError
from .receipt_read import _read_confirmed_request as _confirmed_receipt
from ._request_identity import request_identity
from .idempotency_values import RequestIdConflict, RequestResolution


def resolve_normative_request(source, request):
    """Return the SAME stored semantic result/IDs for the same ID + op hash.

    Supply prepare_authoring_request(...) BEFORE planning or taking a writer
    lock. The historical actor/base/target are returned, not relabelled as the
    retry's actor or today's model. A receipt alone without committed proof is
    never success. This is not a generic analyzer request-ID lookup.
    """
    if type(source) is not ProjectSource or type(request) is not AuthoringRequest:
        raise ReceiptError('typed_normative_request_and_source_required', exit_code=2)
    try:
        identity = request_identity(request)
        if not identity.applicable:
            return RequestResolution._create(identity.request_id, applicable=False)
        receipt = _confirmed_receipt(source, identity.request_id)
        if receipt is not None and receipt.data['operations_sha256'] != identity.operations_sha256:
            raise RequestIdConflict(identity.request_id, receipt.data['operations_sha256'],
                                    identity.operations_sha256, path=receipt.path)
        return RequestResolution._create(identity.request_id, receipt)
    except (OSError, ModelError, SafetyViolation, ChangeExecutionError) as error:
        if isinstance(error, ReceiptError):
            raise
        raise ReceiptError(getattr(error, 'reason', 'request_receipt_read_failed'),
            exit_code=getattr(error, 'exit_code', 7 if isinstance(error, SafetyViolation) else 5),
            path=getattr(error, 'path', None)) from error
    except (KeyError, TypeError, ValueError) as error:
        raise ReceiptError('normative_request_fields_invalid', exit_code=2) from error
