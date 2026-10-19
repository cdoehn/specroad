"""Owned waiver inputs and explicit trusted review observations, never authority."""
from dataclasses import dataclass
from hashlib import sha256
import re
from typing import Callable

from ..configurations import EffectiveConfiguration
from ..graph.scope_descriptors import ScopeDescriptor
from ..model.audit import actor
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.errors import ModelError
from ..model.waiver_fields import validate_waiver_fields, waiver_time
from ..storage.json_syntax import parse_json_object
from .waiver_content import waiver_subject, waiver_content_sha256


def _text(value):
    if type(value) is not str or not value.strip() or '\0' in value:
        raise ModelError('waiver_text_required')


def _hash(value):
    if type(value) is not str or re.fullmatch('[0-9a-f]{64}', value) is None:
        raise ModelError('waiver_hash_required')


class _Owned:
    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def sha256(self):
        return sha256(self._encoded).hexdigest()

    def __bool__(self):
        raise TypeError('Inspect the waiver observation explicitly; it is not authority')


@dataclass(frozen=True, init=False)
class VerificationWaiver(_Owned):
    _encoded: bytes

    def __init__(self, value):
        raw = canonical_json_bytes(value)
        owned = parse_json_object(raw)
        validate_waiver_fields(owned)
        if 'format_version' in owned:
            ScopeDescriptor(owned['scope_descriptor'])
            waiver_time(owned['expiry_condition']['expires_at'])
        object.__setattr__(self, '_encoded', raw)


@dataclass(frozen=True, init=False)
class WaiverContext(_Owned):
    """A supplied subject, exact scope/configuration and explicit evaluation time.

    This is a per-subject observation, not scope membership or applicability.
    Configuration hashes use the existing effective-chain manifest contract.
    """
    _encoded: bytes

    def __init__(self, subject, scope_descriptor, *, evaluated_at, configuration=None):
        subject = waiver_subject(subject)
        if type(scope_descriptor) is not ScopeDescriptor:
            raise ModelError('typed_waiver_scope_required')
        scope = ScopeDescriptor(scope_descriptor.data).data
        waiver_time(evaluated_at)
        if configuration is None:
            if scope['configuration_id'] is not None:
                raise ModelError('waiver_configuration_required')
            binding = None
        else:
            if type(configuration) is not EffectiveConfiguration:
                raise ModelError('typed_waiver_configuration_required')
            if scope['configuration_id'] != configuration.configuration_id:
                raise ModelError('waiver_configuration_id_mismatch')
            binding = configuration.sha256
        value = {'version': 'waiver-assessment-v1', 'subject': subject.data,
            'subject_source_sha256': sha256(subject.source_bytes).hexdigest(),
            'subject_sha256': canonical_json_sha256(subject.data),
            'content_sha256': waiver_content_sha256(subject),
            'scope_descriptor': scope, 'configuration_sha256': binding,
            'evaluated_at': evaluated_at}
        object.__setattr__(self, '_encoded', canonical_json_bytes(value))


@dataclass(frozen=True, init=False)
class HumanWaiverReview(_Owned):
    """Passive declaration. Human labels alone are never a verified decision."""
    _encoded: bytes

    def __init__(self, value):
        raw = canonical_json_bytes(value)
        owned = parse_json_object(raw)
        if set(owned) != {'review_id', 'subject_id', 'waiver_sha256', 'reviewer', 'reviewed_at', 'decision'}:
            raise ModelError('waiver_review_fields_invalid')
        _text(owned['review_id']); _text(owned['subject_id']); _hash(owned['waiver_sha256'])
        actor(owned['reviewer']); waiver_time(owned['reviewed_at'])
        if type(owned['decision']) is not str or owned['decision'] not in ('confirmed', 'rejected'):
            raise ModelError('waiver_review_decision_invalid')
        object.__setattr__(self, '_encoded', raw)


@dataclass(frozen=True)
class WaiverReviewVerification:
    input_sha256: str
    review_sha256: str
    authenticated_human: bool
    current: bool

    def __post_init__(self):
        _hash(self.input_sha256); _hash(self.review_sha256)
        if type(self.authenticated_human) is not bool or type(self.current) is not bool:
            raise ModelError('waiver_verification_boolean_required')


@dataclass(frozen=True)
class WaiverReviewVerifier:
    """Trusted host code; never selected, imported or executed from project JSON."""
    verifier_id: str
    version: str
    check: Callable

    def __post_init__(self):
        _text(self.verifier_id); _text(self.version)
        if not callable(self.check):
            raise ModelError('waiver_review_verifier_required')


@dataclass(frozen=True, init=False)
class WaiverAssessment(_Owned):
    _encoded: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError('Use assess_verification_waiver')

    @classmethod
    def _create(cls, value):
        result = object.__new__(cls)
        object.__setattr__(result, '_encoded', canonical_json_bytes(value))
        return result
