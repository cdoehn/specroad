"""Container integrity, then native model integrity, then a bounded result."""
from ..model.errors import ModelError
from ..security import SafetyViolation
from ..srx.errors import SrxError
from ._model_verification import verify_model
from .container import BundleContainer
from .errors import BundleError


def _result(container, externally_bound, scope):
    return {'format_version': 'bundle-verify-v1', 'manifest': container.manifest,
        'file': {'size': len(container.source_bytes), 'sha256': container.sha256},
        'validation_scope': scope, 'container_verified': True,
        'model_root_verified': True, 'closure_verified': True,
        'external_hash_verified': externally_bound, 'creator_authenticated': False,
        'full_semantic_validation': False, 'approval_granted': False, 'write_authorized': False}


def verify_bundle(raw, *, expected_sha256=None):
    """Return byte-derived integrity/closure facts, never authenticity or approval.

    The external expectation binds the entire ZIP before model reconstruction.
    Successful verification concerns precisely the supplied closed inventory;
    it does not attest the original project's completeness or release readiness.
    """
    try:
        container = BundleContainer(raw, expected_sha256=expected_sha256)
        from ..force_operations import current, permit
        try:
            scope = verify_model(container)
            model_verified = True
        except (ModelError, BundleError, SrxError, SafetyViolation) as error:
            if not permit(False, gate='schema:bundle_model', subject='bundle',
                    observed={'reason': getattr(error, 'reason', type(error).__name__)},
                    requested='report_actual_readable_inventory'):
                raise
            scope = 'container_manifest_and_payload_only'
            model_verified = False
        result = _result(container, expected_sha256 is not None, scope)
        call = current()
        if call is not None and call.decisions.summary['used']:
            from hashlib import sha256
            result.update(format_version='force-bundle-verify-v1', force=call.decisions.summary,
                container_verified=False, model_root_verified=model_verified,
                closure_verified=model_verified, external_hash_verified=(expected_sha256 is not None
                    and sha256(raw).hexdigest() == expected_sha256))
        return result
    except SafetyViolation as error:
        raise BundleError('unsafe_bundle_model', code='SRV083', exit_code=7) from error
    except ModelError as error:
        raise BundleError(error.reason, exit_code=getattr(error, 'exit_code', 3)) from error
    except SrxError as error:
        raise BundleError(error.reason, code=error.code) from error
