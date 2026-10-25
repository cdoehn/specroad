"""Native model integrity after the separate container-integrity stage.

The input owns already checked ZIP bytes. These checks reconstruct closure and
native hashes; they neither read an origin nor manufacture a success result.
"""
from ..exchange._export_scope import export_scope, resource_identity
from ..graph.scope_descriptors import ScopeDescriptor
from ._payload_model import payload_model
from .manifest import require


def _verify_project_model(container, manifest):
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


def verify_model(container):
    """Return the checked model scope only after every native check succeeds."""
    manifest = container.manifest
    if manifest['bundle_kind'] != 'project':
        from ._partial_verification import verify_partial_model
        verify_partial_model(container)
        return 'partial_payload_model'
    _verify_project_model(container, manifest)
    return 'closed_project_payload_model'
