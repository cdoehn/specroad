"""Independent native model and closure verification over owned ZIP bytes."""
from ..exchange._export_scope import export_scope, resource_identity
from ..graph.scope_descriptors import ScopeDescriptor
from ..model.errors import ModelError
from ..security import SafetyViolation
from ..srx.errors import SrxError
from .container import BundleContainer
from .errors import BundleError
from .manifest import require
from ._payload_model import payload_model


def _verify(container, externally_bound):
    manifest = container.manifest
    if manifest['bundle_kind'] != 'project':
        from ._partial_verification import verify_partial_model
        verify_partial_model(container)
        return _result(container, externally_bound, 'partial_payload_model')
    model = payload_model(container)
    descriptor = ScopeDescriptor(manifest['scope_descriptor'])
    closure, native, artifacts, _ = export_scope(model, descriptor)
    require(set(closure.artifact_ids) == {a['id'] for a in model.artifacts}
            and set(closure.resource_ids) == {resource_identity(r) for r in model.resources}
            and not closure.boundary_references, 'bundle_project_closure_incomplete')
    require(native.sha256 == model.manifest(artifacts, descriptor.data).sha256,
            'bundle_project_manifest_mismatch', code='SRV060')
    for key, actual in (('origin_model_root_sha256', native.sha256),
                        ('bundle_model_root_sha256', native.sha256),
                        ('configuration_sha256', native.data['configuration_sha256']),
                        ('profile_sha256', native.data['profile_sha256'])):
        require(manifest[key] == actual, 'bundle_model_binding_mismatch', code='SRV060')
    return _result(container, externally_bound, 'closed_project_payload_model')


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
        return _verify(BundleContainer(raw, expected_sha256=expected_sha256), expected_sha256 is not None)
    except SafetyViolation as error:
        raise BundleError('unsafe_bundle_model', code='SRV083', exit_code=7) from error
    except ModelError as error:
        raise BundleError(error.reason, exit_code=getattr(error, 'exit_code', 3)) from error
    except SrxError as error:
        raise BundleError(error.reason, code=error.code) from error
