"""Public fixed Proposal basis over native sources, never a write grant."""
from dataclasses import dataclass

from ..changes.target_model import TargetModel
from ..model.model_manifest import ModelManifest
from .values import require


def fixed_proposal_scope():
    """Fresh native descriptor; compatibility dictionaries are not authority."""
    from ..graph.scope_descriptors import ScopeDescriptor
    return ScopeDescriptor({'scope_version': 'scope-v1', 'scope_kind': 'specification',
        'selector': {}, 'configuration_id': None, 'closure_profile': 'core-closure-v1',
        'boundary_policy': 'closed'})


def require_proposal_scope(value, *, exit_code=3):
    """A valid general selector is not necessarily a valid Proposal selector."""
    from ..graph.scope_descriptors import ScopeDescriptor
    descriptor = ScopeDescriptor(value)
    require(descriptor.data == fixed_proposal_scope().data, 'proposal_specification_scope_required',
        pointer='/base/scope_descriptor', exit_code=exit_code)
    return descriptor


@dataclass(frozen=True, init=False)
class ProposalBasis:
    """Owned canonical manifest of the supplied complete specification model.

    Source discovery and live-source freshness belong to the calling reader.
    Neither the resulting hash nor this value attests a review or authorizes IO.
    """
    _manifest_bytes: bytes

    def __init__(self, model):
        require(type(model) is TargetModel, 'proposal_native_model_required')
        from .context import specification_manifest
        manifest = specification_manifest(model.snapshot())
        require_proposal_scope(manifest.data['scope_descriptor'])
        object.__setattr__(self, '_manifest_bytes', manifest.canonical_bytes)

    @property
    def manifest(self):
        from ..storage.json_syntax import parse_json_object
        return ModelManifest(parse_json_object(self._manifest_bytes))

    @property
    def data(self):
        manifest = self.manifest
        return {'scope_descriptor': manifest.data['scope_descriptor'],
                'model_root_sha256': manifest.sha256}

    @property
    def write_authorized(self):
        return False


def build_proposal_basis(model, *, scope_descriptor=None, configuration_id=None):
    """Explicit overrides must name the same complete, unconfigured scope."""
    require(configuration_id is None, 'proposal_configuration_forbidden',
            pointer='/configuration_id')
    if scope_descriptor is not None:
        require_proposal_scope(scope_descriptor)
    return ProposalBasis(model)


def prepare_proposal_for_model(model, *, scope_descriptor=None, configuration_id=None, **fields):
    """Bind declarative authoring to actual basis and planned target bytes.

    This is preparation, not publication. Supplied allocated identities and
    actual ChangePlans retain their native validation and metadata contracts.
    """
    from ..changes import ChangePlan
    from .authoring import prepare_proposal
    from .context import ProposalContext, reconstruct_proposal_target
    basis = build_proposal_basis(model, scope_descriptor=scope_descriptor,
                                 configuration_id=configuration_id)
    plan = fields.get('change_plan')
    require(type(plan) is ChangePlan, 'native_proposal_plan_required')
    observed = plan.data['base']
    require(observed['scope_descriptor'] == basis.data['scope_descriptor'],
            'proposal_specification_scope_required')
    require(observed['model_root_sha256'] == basis.data['model_root_sha256'],
            'proposal_original_basis_mismatch', exit_code=6)
    proposal = prepare_proposal(**fields)
    reconstruct_proposal_target(ProposalContext(proposal.original, model))
    return proposal
