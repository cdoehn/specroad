"""Owned inputs for Requirement approval checks, never a persisted review format.

Trusted callers supply service observations and an explicit review verifier.
Hashes bind bytes, not authorship. These values confer no write authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import re
from typing import Callable

from ..model.audit import actor
from ..model.audit_values import UtcTimestamp
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.errors import ModelError
from ..profiles.composition_values import EffectiveProfile
from ..storage.json_syntax import parse_json_object
from ..srx.pointers import parse_pointer
from ..srx.errors import SrxError
from .values import ModelDocument

APPROVAL_VERSION = 'requirement-approval-v1'
PREREQUISITES = ('model_validation', 'verification_contract', 'relation_reviews',
                 'profile_rules', 'configuration', 'language_policy', 'placeholders')
HUMAN_CRITERIA = ('single_normative_force', 'single_testable_fact',
    'force_statement_meaning', 'scope_actor_conditions', 'observable_or_measurable',
    'terms_unambiguous', 'no_contradiction', 'structured_or_equivalent_contract')


def _text(value):
    if type(value) is not str or not value.strip():
        raise ModelError('approval_text_required')
    return value


def _hash(value):
    if type(value) is not str or re.fullmatch('[0-9a-f]{64}', value) is None:
        raise ModelError('approval_hash_required')
    return value


def _pointers(values):
    if type(values) not in (tuple, list):
        raise ModelError('approval_field_projection_required')
    result = []
    for value in values:
        try:
            tokens = parse_pointer(value, rule_id='approval-fields')
        except SrxError as error:
            raise ModelError('approval_pointer_invalid', pointer=value if type(value) is str else '') from error
        # Only actual normative data can be projected, not title/audit/Extensions.
        if not tokens or tokens[0] not in ('scope', 'actor', 'trigger', 'preconditions',
                'response', 'object', 'timing', 'thresholds', 'exceptions', 'relations'):
            raise ModelError('approval_pointer_outside_semantics', pointer=value)
        result.append(value)
    if len(set(result)) != len(result):
        raise ModelError('approval_duplicate_projection')
    return tuple(result)


@dataclass(frozen=True, init=False)
class ApprovalContext:
    """Exact loaded candidate/model, selected profile, configuration and projections.

    Quality rows contain four pointers: property, method, comparison, target.
    Interface pointers select either an interface/boundary ID, or source/target
    component IDs. This API adds no top-level fields to the artifact format.
    """
    documents: tuple
    requirement_id: str
    profile: EffectiveProfile | None
    input_sha256: str
    _encoded: bytes

    def __init__(self, requirement_id, documents, *, profile=None, configuration=None,
                 quality_fields=(), interface_fields=(), mode='transition'):
        _text(requirement_id)
        if type(documents) not in (tuple, list) or not documents or any(type(d) is not ModelDocument for d in documents):
            raise ModelError('approval_documents_required')
        if len({d.path for d in documents}) != len(documents):
            raise ModelError('approval_duplicate_source')
        if profile is not None and type(profile) is not EffectiveProfile:
            raise ModelError('approval_effective_profile_required')
        if configuration is not None and type(configuration) is not dict:
            raise ModelError('approval_configuration_required')
        if type(mode) is not str or mode not in ('transition', 'stored'):
            raise ModelError('approval_mode_invalid')
        if type(quality_fields) not in (tuple, list):
            raise ModelError('approval_quality_projection_required')
        rows = tuple(_pointers(row) for row in quality_fields)
        if any(len(row) != 4 for row in rows) or len(set(rows)) != len(rows):
            raise ModelError('approval_quality_projection_invalid')
        interface = _pointers(interface_fields)
        if len(interface) not in (0, 1, 2):
            raise ModelError('approval_interface_projection_invalid')
        documents = tuple(sorted(documents, key=lambda d:d.path))
        value = {'version':APPROVAL_VERSION, 'requirement_id':requirement_id, 'mode':mode,
            'sources':[{'path':d.path, 'sha256':sha256(d.content).hexdigest()} for d in documents],
            'profile':None if profile is None else profile.binding(), 'configuration':configuration,
            'quality_fields':[list(row) for row in rows], 'interface_fields':list(interface)}
        raw = canonical_json_bytes(value)
        for name, item in (('documents', documents), ('requirement_id', requirement_id),
                           ('profile', profile), ('_encoded',raw), ('input_sha256',sha256(raw).hexdigest())):
            object.__setattr__(self, name, item)

    @property
    def data(self):
        return parse_json_object(self._encoded)

    def requirement(self):
        values = [parse_json_object(d.content, path=d.path) for d in self.documents]
        matches = [value for value in values if value.get('id') == self.requirement_id]
        if len(matches) != 1 or matches[0].get('artifact_type') != 'requirement':
            raise ModelError('approval_requirement_missing_or_ambiguous')
        return matches[0]

    @property
    def requirement_sha256(self):
        return canonical_json_sha256(self.requirement())

    @property
    def force_statement_sha256(self):
        value = self.requirement()
        return canonical_json_sha256({'normative_force':value.get('normative_force'),
                                      'statement':value.get('statement')})


@dataclass(frozen=True)
class ApprovalPrerequisite:
    """A trusted caller's complete service observation, not self-authenticating proof.

    The binding must be the full ApprovalContext. Omission is unavailable, never
    success. A passing service must cite its own current evidence digest.
    """
    gate_id: str
    input_sha256: str
    status: str
    evidence_sha256: str | None = None

    def __post_init__(self):
        if type(self.gate_id) is not str or self.gate_id not in PREREQUISITES:
            raise ModelError('approval_prerequisite_unknown')
        _hash(self.input_sha256)
        if type(self.status) is not str or self.status not in ('passed','failed','unavailable'):
            raise ModelError('approval_prerequisite_status_invalid')
        if self.status == 'passed' or self.evidence_sha256 is not None:
            _hash(self.evidence_sha256)


@dataclass(frozen=True, init=False)
class HumanRequirementReview:
    """Passive review observation. Human actor labels are NOT authentication."""
    _encoded: bytes

    def __init__(self, data):
        fields={'review_id','input_sha256','requirement_id','requirement_sha256',
                'force_statement_sha256','reviewer','reviewed_at','decision','criteria','compound'}
        if type(data) is not dict or set(data) != fields:
            raise ModelError('approval_review_fields_invalid')
        # Canonical validation rejects foreign objects before user conversion hooks.
        raw = canonical_json_bytes(data)
        owned = parse_json_object(raw)
        for field in ('review_id', 'requirement_id'):
            _text(owned[field])
        for field in ('input_sha256','requirement_sha256','force_statement_sha256'):
            _hash(owned[field])
        actor(owned['reviewer']); UtcTimestamp(owned['reviewed_at'])
        if owned['decision'] not in ('confirmed', 'rejected') or type(owned['compound']) is not bool:
            raise ModelError('approval_review_decision_invalid')
        criteria=owned['criteria']
        if (type(criteria) is not dict or criteria.keys() - set(HUMAN_CRITERIA)
                or any(type(v) is not bool for v in criteria.values())):
            raise ModelError('approval_review_criteria_invalid')
        object.__setattr__(self, '_encoded', raw)

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def sha256(self):
        return sha256(self._encoded).hexdigest()


@dataclass(frozen=True)
class ReviewVerification:
    """Result of an explicitly trusted service, bound to candidate and review."""
    input_sha256: str
    review_sha256: str
    authenticated_human: bool
    current: bool

    def __post_init__(self):
        _hash(self.input_sha256); _hash(self.review_sha256)
        if type(self.authenticated_human) is not bool or type(self.current) is not bool:
            raise ModelError('approval_verification_boolean_required')


@dataclass(frozen=True)
class ReviewVerifier:
    """Explicit trusted code registration. Never selected or imported from JSON."""
    verifier_id: str
    version: str
    check: Callable

    def __post_init__(self):
        _text(self.verifier_id); _text(self.version)
        if not callable(self.check):
            raise ModelError('approval_review_verifier_required')


@dataclass(frozen=True, init=False)
class ApprovalAssessment:
    """Gate observation; no setter, writer, login/auth service or lifecycle command."""
    _encoded: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError('Use assess_requirement_approval')

    @classmethod
    def _create(cls, value):
        result=object.__new__(cls)
        object.__setattr__(result, '_encoded', canonical_json_bytes(value))
        return result

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def eligible_for_human_approval(self):
        return self.data['eligible_for_human_approval']

    def __bool__(self):
        raise TypeError('Inspect gate results explicitly; a report is not approval')
