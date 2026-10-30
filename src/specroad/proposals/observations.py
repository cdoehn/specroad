"""Explicit host observations of existing originals, never persisted schemas.

The host interprets its actual original evidence. The kernel binds the exact
location and complete native context before asking its installed verifier to
verify that interpretation. Neither a row hash nor an actor label authenticates
the observation. No callbacks can be selected by project or Work data.
"""
from dataclasses import dataclass
from hashlib import sha256
from typing import Callable

from ..model.audit_values import Actor, UtcTimestamp
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from .context import ProposalContext
from .values import ProposalOriginal, ProposalBinding, require


def _ordinal(value):
    require(type(value) is int and value >= 0, 'proposal_observation_index_invalid')


def _row(original, field, index):
    require(type(original) is ProposalOriginal, 'proposal_original_required')
    _ordinal(index)
    rows = original.data.get(field, [])
    require(index < len(rows), 'proposal_observation_original_missing')
    return canonical_json_bytes(rows[index])


@dataclass(frozen=True)
class ProposalReviewObservation:
    original: ProposalOriginal
    index: int
    context: ProposalContext
    reviewer: Actor
    reviewed_at: UtcTimestamp
    decision: str
    observed_revision: int

    def __post_init__(self):
        _row(self.original, 'reviews', self.index)
        require(type(self.context) is ProposalContext and type(self.reviewer) is Actor
                and type(self.reviewed_at) is UtcTimestamp,
                'proposal_native_review_observation_required')
        require(self.decision in ('approved', 'rejected', 'withdrawn'),
                'proposal_review_decision_invalid')
        require(type(self.observed_revision) is int and self.observed_revision > 0,
                'proposal_observed_revision_invalid')

    @property
    def row_bytes(self):
        return _row(self.original, 'reviews', self.index)

    @property
    def binding(self):
        return self.context.original.binding

    @property
    def data(self):
        return {'kind': 'review', 'original_sha256': self.original.sha256,
            'path': self.original.path, 'pointer': '/reviews/' + str(self.index),
            'row_sha256': sha256(self.row_bytes).hexdigest(),
            'context_sha256': self.context.sha256, 'binding': self.binding.data,
            'actor': self.reviewer.as_fields(), 'at': self.reviewed_at.value,
            'decision': self.decision, 'observed_revision': self.observed_revision}


@dataclass(frozen=True)
class ProposalControlObservation:
    original: ProposalOriginal
    index: int
    context: ProposalContext
    actor: Actor
    occurred_at: UtcTimestamp
    before: str
    after: str
    reason: str
    result_bytes: bytes

    def __post_init__(self):
        _row(self.original, 'control_history', self.index)
        require(type(self.context) is ProposalContext and type(self.actor) is Actor
                and type(self.occurred_at) is UtcTimestamp
                and type(self.reason) is str and bool(self.reason.strip())
                and type(self.result_bytes) is bytes and bool(self.result_bytes),
                'proposal_native_control_observation_required')
        transitions = {'draft': {'validated', 'rejected', 'stale'},
            'validated': {'checked', 'rejected', 'stale'},
            'checked': {'in_review', 'rejected', 'stale'},
            'in_review': {'approved', 'rejected', 'stale'},
            'approved': {'applied', 'rejected', 'stale'}}
        require(self.after in transitions.get(self.before, ()),
                'proposal_control_transition_invalid')
        # The existing typed proposal_control event contract has these fields.
        # Additional source fields are preserved for the provenance verifier.
        from ..storage.json_syntax import parse_json_object
        row = parse_json_object(self.row_bytes)
        expected = {'from': self.before, 'to': self.after, 'reason': self.reason,
                    'result_sha256': sha256(self.result_bytes).hexdigest()}
        require(all(row.get(k) == v for k, v in expected.items()),
                'proposal_control_original_mismatch')

    @property
    def row_bytes(self):
        return _row(self.original, 'control_history', self.index)

    @property
    def binding(self):
        return self.context.original.binding

    @property
    def data(self):
        return {'kind': 'control', 'original_sha256': self.original.sha256,
            'path': self.original.path, 'pointer': '/control_history/' + str(self.index),
            'row_sha256': sha256(self.row_bytes).hexdigest(),
            'context_sha256': self.context.sha256, 'binding': self.binding.data,
            'actor': self.actor.as_fields(), 'at': self.occurred_at.value,
            'from': self.before, 'to': self.after, 'reason': self.reason,
            'result_sha256': sha256(self.result_bytes).hexdigest()}


@dataclass(frozen=True)
class ProposalVerification:
    """A trusted verifier's exact observation, not a reusable approval grant."""
    input_sha256: str
    original_sha256: str
    origin_verified: bool
    actor_verified: bool
    decision_current: bool

    def __post_init__(self):
        for digest in (self.input_sha256, self.original_sha256):
            require(type(digest) is str and len(digest) == 64
                    and all(c in '0123456789abcdef' for c in digest),
                    'proposal_verifier_binding_invalid')
        require(all(type(value) is bool for value in
                    (self.origin_verified, self.actor_verified, self.decision_current)),
                'proposal_verifier_boolean_required')


@dataclass(frozen=True)
class ProposalVerifier:
    verifier_id: str
    version: str
    check: Callable

    def __post_init__(self):
        require(all(type(value) is str and bool(value.strip())
                    for value in (self.verifier_id, self.version)) and callable(self.check),
                'proposal_trusted_verifier_required')


@dataclass(frozen=True)
class ProposalVerificationInput:
    observation: ProposalReviewObservation | ProposalControlObservation
    native_result: bytes
    current_context: ProposalContext
    publication: object = None

    def __post_init__(self):
        require(type(self.observation) in (ProposalReviewObservation, ProposalControlObservation)
                and type(self.native_result) is bytes and bool(self.native_result)
                and type(self.current_context) is ProposalContext,
                'proposal_verification_inputs_required')
        from .publication import ProposalPublication
        require(self.publication is None or type(self.publication) is ProposalPublication,
                'proposal_native_publication_required')

    @property
    def sha256(self):
        return canonical_json_sha256({'observation': self.observation.data,
            'native_result_sha256': sha256(self.native_result).hexdigest(),
            'current_context_sha256': self.current_context.sha256,
            'publication_sha256': None if self.publication is None else self.publication.sha256})


def verify_observation(verifier, inputs):
    require(type(verifier) is ProposalVerifier and type(inputs) is ProposalVerificationInput,
            'proposal_trusted_verifier_required')
    observed = verifier.check(inputs)
    require(type(observed) is ProposalVerification, 'proposal_native_verification_required')
    require(observed.input_sha256 == inputs.sha256 and observed.original_sha256 ==
            sha256(inputs.observation.row_bytes).hexdigest(), 'proposal_verifier_binding_changed', exit_code=6)
    require(observed.origin_verified and observed.actor_verified,
            'proposal_original_provenance_unverified', exit_code=7)
    return observed
