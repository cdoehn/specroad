"""Waiver-only assessment and guarded workflow preparation, without I/O."""
from ..changes.update_inputs import normalize_artifact_update_input
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.domain_fields import VERIFICATION_PLAN_STATUSES
from ..model.errors import ModelError
from ..model.waiver_fields import CONTENT_HASH_ALGORITHM, WAIVER_VERSION, waiver_time
from ..storage.domain_artifact import DomainArtifact
from .waiver_content import waiver_subject, waiver_content_sha256
from .waiver_values import (VerificationWaiver, WaiverContext, HumanWaiverReview,
    WaiverReviewVerification, WaiverReviewVerifier, WaiverAssessment)


def prepare_verification_waiver(context, *, reason, expires_at, human_review_id):
    """Bind a fresh passive candidate; this neither creates nor confirms a review."""
    if type(context) is not WaiverContext:
        raise ModelError('typed_waiver_context_required')
    value = context.data
    if waiver_time(expires_at) <= waiver_time(value['evaluated_at']):
        raise ModelError('waiver_deadline_not_future')
    return VerificationWaiver({'format_version': WAIVER_VERSION,
        'content_hash_algorithm': CONTENT_HASH_ALGORITHM, 'reason': reason,
        'scope_descriptor': value['scope_descriptor'],
        'expiry_condition': {'kind': 'utc_deadline', 'expires_at': expires_at},
        'human_review_id': human_review_id, 'artifact_sha256': value['content_sha256'],
        'configuration_sha256': value['configuration_sha256']})


def assess_verification_waiver(context, *, review=None, verifier=None):
    """Assess only the stored waiver, never full verification or release success."""
    if type(context) is not WaiverContext:
        raise ModelError('typed_waiver_context_required')
    if review is not None and type(review) is not HumanWaiverReview:
        raise ModelError('typed_waiver_review_required')
    if verifier is not None and type(verifier) is not WaiverReviewVerifier:
        raise ModelError('typed_waiver_verifier_required')
    value = context.data; subject = value['subject']; reasons = []
    stored = subject.get('verification_waiver')
    waiver = None if stored is None else VerificationWaiver(stored)
    if subject['verification_plan_status'] != 'waived':
        reasons.append('waiver_not_active')
    if waiver is None:
        reasons.append('waiver_missing')
    elif 'format_version' not in stored:
        reasons.append('legacy_waiver_unsupported')
    else:
        if stored['artifact_sha256'] != value['content_sha256']:
            reasons.append('waiver_content_changed')
        if canonical_json_bytes(stored['scope_descriptor']) != canonical_json_bytes(value['scope_descriptor']):
            reasons.append('waiver_scope_mismatch')
        if stored['configuration_sha256'] != value['configuration_sha256']:
            reasons.append('waiver_configuration_mismatch')
        if waiver_time(value['evaluated_at']) >= waiver_time(stored['expiry_condition']['expires_at']):
            reasons.append('waiver_expired')
    verified = False
    review_sha256 = None if review is None else review.sha256
    # No external verifier is invoked for a missing/stale/inactive/expired waiver.
    if not reasons:
        if review is None:
            reasons.append('waiver_review_missing')
        else:
            human = review.data
            if (human['review_id'] != stored['human_review_id'] or human['subject_id'] != subject['id']
                    or human['waiver_sha256'] != waiver.sha256):
                reasons.append('waiver_review_binding_mismatch')
            elif human['reviewer']['actor_type'] != 'human':
                reasons.append('waiver_review_nonhuman')
            elif human['decision'] != 'confirmed':
                reasons.append('waiver_review_rejected')
            elif waiver_time(human['reviewed_at']) > waiver_time(value['evaluated_at']):
                reasons.append('waiver_review_in_future')
            elif verifier is None:
                reasons.append('waiver_review_verifier_unavailable')
            else:
                try:
                    observation = verifier.check(context, review)
                    if (type(observation) is not WaiverReviewVerification
                            or observation.input_sha256 != context.sha256
                            or observation.review_sha256 != review_sha256):
                        reasons.append('waiver_review_verifier_unbound')
                    elif not observation.authenticated_human or not observation.current:
                        reasons.append('waiver_review_not_authenticated_or_current')
                    else:
                        verified = True
                except Exception:
                    reasons.append('waiver_review_verification_failed')
    return WaiverAssessment._create({'format_version': '1.0.0', 'kind': 'waiver-assessment-v1',
        'input_sha256': context.sha256, 'subject_id': subject['id'],
        'subject_sha256': value['subject_sha256'], 'content_sha256': value['content_sha256'],
        'waiver_sha256': None if waiver is None else waiver.sha256,
        'scope_descriptor': value['scope_descriptor'], 'configuration_sha256': value['configuration_sha256'],
        'evaluated_at': value['evaluated_at'], 'review_sha256': review_sha256,
        'review_verified': verified, 'waiver_result': 'waived' if not reasons else 'ineffective',
        'reasons': reasons, 'full_verification_evaluated': False, 'scope_membership_evaluated': False,
        'configuration_applicability_evaluated': False, 'release_readiness_evaluated': False,
        'write_authorized': False, 'approval_granted': False})


def prepare_verification_plan_update(subject, status, *, waiver=None):
    """Prepare native guarded update fields; the common writer still owns gates.

    This cannot persist an assessment or authorize a waiver. Currentness and
    human confirmation must be assessed against the actual evaluation context.
    Existing legacy data can be read, but cannot be reissued with this helper.
    """
    subject = waiver_subject(subject); value = subject.data
    if type(status) is not str or status not in VERIFICATION_PLAN_STATUSES:
        raise ModelError('invalid_verification_plan_status')
    fields = {'verification_plan_status': status}
    if waiver is not None:
        if type(waiver) is not VerificationWaiver or status != 'waived':
            raise ModelError('typed_active_waiver_required')
        fields['verification_waiver'] = VerificationWaiver(waiver.data).data
    if status == 'waived':
        chosen = fields.get('verification_waiver', value.get('verification_waiver'))
        if chosen is None or 'format_version' not in chosen:
            raise ModelError('versioned_waiver_required')
        VerificationWaiver(chosen)
        if chosen['artifact_sha256'] != waiver_content_sha256(subject):
            raise ModelError('waiver_content_changed')
    DomainArtifact(canonical_json_bytes({**value, **fields}), path=subject.path)
    patch = [{'op': 'add', 'path': '/' + key, 'value': item} for key, item in fields.items()]
    return normalize_artifact_update_input(value, patch=patch, expected_revision=value['revision'],
        expected_sha256=canonical_json_sha256(value))
