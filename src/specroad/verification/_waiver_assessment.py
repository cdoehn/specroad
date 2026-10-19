"""Read-only waiver assessment over owned inputs and explicit host observations.

No workflow preparation, writer, clock, project loading or result persistence.
Content and deadline contracts are shared with the preparation path.
"""
from copy import copy

from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..model.waiver_fields import waiver_time
from .waiver_values import (VerificationWaiver, WaiverContext, HumanWaiverReview,
    WaiverReviewVerification, WaiverReviewVerifier, WaiverAssessment)


def assess_verification_waiver(context, *, review=None, verifier=None):
    """Assess only the stored waiver, never full verification or release success."""
    if type(context) is not WaiverContext:
        raise ModelError('typed_waiver_context_required')
    if review is not None and type(review) is not HumanWaiverReview:
        raise ModelError('typed_waiver_review_required')
    if verifier is not None and type(verifier) is not WaiverReviewVerifier:
        raise ModelError('typed_waiver_verifier_required')
    # Bind the whole observation before calling host code. A verifier receives
    # detached values, and cannot replace the input whose result we report.
    context_bytes, context_sha256 = context._encoded, context.sha256
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
    review_bytes = None if review is None else review._encoded
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
                observed_context = copy(context)
                observed_review = HumanWaiverReview(human)
                verifier_id, verifier_version, check = verifier.verifier_id, verifier.version, verifier.check
                try:
                    observation = check(observed_context, observed_review)
                    if (context._encoded != context_bytes or review._encoded != review_bytes
                            or observed_context._encoded != context_bytes
                            or observed_review._encoded != review_bytes
                            or verifier.verifier_id != verifier_id or verifier.version != verifier_version
                            or verifier.check is not check):
                        reasons.append('waiver_review_inputs_changed')
                    elif (type(observation) is not WaiverReviewVerification
                            or observation.input_sha256 != context_sha256
                            or observation.review_sha256 != review_sha256):
                        reasons.append('waiver_review_verifier_unbound')
                    else:
                        # Revalidate even typed host returns: a forged or changed
                        # value with truthy non-booleans is not a confirmation.
                        observation = WaiverReviewVerification(observation.input_sha256,
                            observation.review_sha256, observation.authenticated_human, observation.current)
                        if not observation.authenticated_human or not observation.current:
                            reasons.append('waiver_review_not_authenticated_or_current')
                        else:
                            verified = True
                except Exception:
                    reasons.append('waiver_review_verification_failed')
    return WaiverAssessment._create({'format_version': '1.0.0', 'kind': 'waiver-assessment-v1',
        'input_sha256': context_sha256, 'subject_id': subject['id'],
        'subject_sha256': value['subject_sha256'], 'content_sha256': value['content_sha256'],
        'waiver_sha256': None if waiver is None else waiver.sha256,
        'scope_descriptor': value['scope_descriptor'], 'configuration_sha256': value['configuration_sha256'],
        'evaluated_at': value['evaluated_at'], 'review_sha256': review_sha256,
        'review_verified': verified, 'waiver_result': 'waived' if not reasons else 'ineffective',
        'reasons': reasons, 'full_verification_evaluated': False, 'scope_membership_evaluated': False,
        'configuration_applicability_evaluated': False, 'release_readiness_evaluated': False,
        'write_authorized': False, 'approval_granted': False})
