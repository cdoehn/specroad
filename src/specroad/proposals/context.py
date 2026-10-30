"""Read-only reconstruction of an embedded plan against its original basis."""
from dataclasses import dataclass

from ..changes._target_materialization import materialize_target
from ..changes._saved_plan_fold import fold_saved_plan
from ..changes.target_model import TargetModel
from ..changes.values import ChangePlan
from ..exchange._export_scope import export_scope
from ..graph.scope_descriptors import ScopeDescriptor
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.paths import artifact_path
from ..validation import ModelDocument
from .values import ProposalOriginal, SPECIFICATION_SCOPE, require


def specification_manifest(model):
    require(type(model) is TargetModel, 'proposal_native_model_required')
    closure, manifest, _, _ = export_scope(model, ScopeDescriptor(SPECIFICATION_SCOPE))
    require(not closure.boundary_references, 'proposal_basis_not_closed')
    return manifest


@dataclass(frozen=True)
class ProposalContext:
    """Actual full original project; its specification closure defines the basis.

    Project snapshots contain original configuration and effective-profile
    bytes. No caller-supplied root hash or quorum substitutes for those bytes.
    """
    original: ProposalOriginal
    basis: TargetModel

    def __post_init__(self):
        require(type(self.original) is ProposalOriginal and type(self.basis) is TargetModel,
                'proposal_native_context_required')
        object.__setattr__(self, 'basis', self.basis.snapshot())

    @property
    def minimum_approvals(self):
        return self.basis.configuration.data['validation_policy'].get(
            'minimum_human_proposal_approvals', 1)

    @property
    def sha256(self):
        return canonical_json_sha256({'original_sha256': self.original.sha256,
            'original_path': self.original.path, 'basis_sources_sha256': self.basis._sources_sha256,
            'profile': self.basis.profile.binding(), 'binding': self.original.binding.data})


def reconstruct_proposal_target(context):
    """Fold actual ordered operations and metadata; never execute a writer.

    A result declaration is checked against the computed candidate and full
    specification closure. The returned model is still not a qualified target.
    """
    require(type(context) is ProposalContext, 'proposal_native_context_required')
    original, model = context.original, context.basis
    manifest = specification_manifest(model)
    plan = ChangePlan(canonical_json_bytes(original.data['change_plan']))
    require(manifest.sha256 == plan.data['base']['model_root_sha256'],
            'proposal_original_basis_mismatch', path=original.path, exit_code=6)
    folded, normalize, _ = fold_saved_plan(plan, model,
        observed_base_root=manifest.sha256, observed_scope=SPECIFICATION_SCOPE)
    originals = {a['id']: d for a, d in zip(model.artifacts, model.documents)}
    documents = []
    from ..model.canonical import canonical_json_sha256
    from ..storage.json_syntax import parse_json_object
    for value in folded.artifacts:
        old = originals.get(value['id'])
        raw = (old.content if old is not None and canonical_json_sha256(
            parse_json_object(old.content)) == canonical_json_sha256(value) else canonical_json_bytes(value))
        documents.append(ModelDocument(
            artifact_path(value['artifact_type'], value['id'], model.configuration.id_prefix), raw))
    if normalize:
        from ..changes._normalization_target import normalization_documents
        documents, resources, _ = normalization_documents(model, plan.data['operations'])
        documents = (*documents, *resources)
    target = materialize_target(model, documents)
    actual = specification_manifest(target)
    require(actual.sha256 == plan.data['expected_result']['model_root_sha256'],
            'proposal_original_target_mismatch', path=original.path)
    return target
