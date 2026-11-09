"""One fixed specialization of the native scope service for all Proposal paths."""
from ..changes.target_model import TargetModel
from ..exchange._export_scope import export_scope
from ..graph.scope_descriptors import ScopeDescriptor
from .values import require


def fixed_proposal_scope():
    """Fresh native descriptor; compatibility dictionaries are not authority."""
    return ScopeDescriptor({'scope_version': 'scope-v1', 'scope_kind': 'specification',
        'selector': {}, 'configuration_id': None, 'closure_profile': 'core-closure-v1',
        'boundary_policy': 'closed'})


def require_proposal_scope(value, *, exit_code=3):
    """A valid general selector is not necessarily a valid Proposal selector."""
    descriptor = ScopeDescriptor(value)
    require(descriptor.data == fixed_proposal_scope().data, 'proposal_specification_scope_required',
        pointer='/base/scope_descriptor', exit_code=exit_code)
    return descriptor


def specification_manifest(model):
    require(type(model) is TargetModel, 'proposal_native_model_required')
    closure, manifest, _, _ = export_scope(model, fixed_proposal_scope())
    require(not closure.boundary_references, 'proposal_basis_not_closed')
    return manifest
