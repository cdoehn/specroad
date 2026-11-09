"""Public fixed Proposal basis over native sources, never a write grant."""
from dataclasses import dataclass

from ..changes.target_model import TargetModel
from ..model.model_manifest import ModelManifest
from .values import require


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
        require(manifest.data['scope_descriptor'] == {
            'scope_version': 'scope-v1', 'scope_kind': 'specification', 'selector': {},
            'configuration_id': None, 'closure_profile': 'core-closure-v1',
            'boundary_policy': 'closed'}, 'proposal_specification_scope_required')
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


def build_proposal_basis(model):
    """Use the native scope/closure/hash service with no configurable selector."""
    return ProposalBasis(model)


def prepare_proposal_for_model(model, **fields):
    """Bind declarative authoring to actual basis and planned target bytes.

    This is preparation, not publication. Supplied allocated identities and
    actual ChangePlans retain their native validation and metadata contracts.
    """
    from ..changes import ChangePlan
    from .authoring import prepare_proposal
    from .context import ProposalContext, reconstruct_proposal_target
    basis = build_proposal_basis(model)
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
