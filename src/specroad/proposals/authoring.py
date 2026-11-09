"""Prepare owned Proposal data. No project access, execution or write authority."""
from dataclasses import dataclass

from ..changes import ChangePlan
from ..model.audit import actor, new_artifact_audit
from ..model.audit_values import UtcTimestamp
from ..model.canonical import canonical_json_bytes
from ..model.identity_values import ArtifactIdentity, RANDOM_SCHEME
from ..model.versions import SCHEMA_VERSION
from .values import ProposalOriginal, CONTENT_EXCLUSIONS, content_sha256, require


@dataclass(frozen=True, init=False)
class Proposal:
    """A complete declarative authoring object, never an execution ticket."""
    original: ProposalOriginal

    def __init__(self, raw, *, path):
        original = ProposalOriginal(raw, path=path)
        require('changes' in original.data, 'proposal_explanations_required', pointer='/changes')
        object.__setattr__(self, 'original', original)

    @property
    def data(self):
        return self.original.data

    @property
    def source_bytes(self):
        return self.original.source_bytes

    @property
    def binding(self):
        return self.original.binding

    @property
    def content_data(self):
        return {name: value for name, value in self.data.items() if name not in CONTENT_EXCLUSIONS}

    @property
    def control_data(self):
        return {name: value for name, value in self.data.items() if name in CONTENT_EXCLUSIONS}

    @property
    def write_authorized(self):
        return False


def prepare_proposal(*, identity, title, rationale, change_plan, changes,
                     model_provenance=None):
    """Use only explicit allocated identity and native plan values.

    Inventory completeness and allocation under the writer lock belong to the
    publishing host. This constructor cannot attest them or approve any change.
    No defaults infer an actor, a clock, a source or a model version.
    """
    require(type(identity) is ArtifactIdentity and identity.artifact_type == 'proposal'
            and identity.id_scheme == RANDOM_SCHEME, 'proposal_identity_required')
    require(type(change_plan) is ChangePlan, 'native_proposal_plan_required')
    plan = ChangePlan(change_plan.source_bytes).data
    value = {'schema_version': SCHEMA_VERSION, 'id': identity.id,
             'id_scheme': identity.id_scheme, 'artifact_type': 'proposal',
             'title': title, 'rationale': rationale, 'maturity': 'draft',
             'proposal_status': 'draft', 'content_revision': 1,
             'relations': [], 'extensions': {}, 'reviews': [], 'control_history': [],
             'base': plan['base'], 'change_plan': plan, 'changes': changes,
             **new_artifact_audit(actor=actor(plan['actor']),
                                  planned_at=UtcTimestamp(plan['planned_at'])).as_fields()}
    if model_provenance is not None:
        from ..model.proposal_fields import MODEL_FIELDS
        require(type(model_provenance) is dict
                and set(model_provenance) == set(MODEL_FIELDS) | {'unknown_reasons'},
                'proposal_model_fields_required')
        value.update(model_provenance)
    value['content_sha256'] = content_sha256(value)
    return Proposal(canonical_json_bytes(value), path=identity.path)
