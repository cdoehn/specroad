"""Passive waiver/workflow preparation for the existing guarded update writer.

Preparing an operation neither evaluates nor authorizes an exception. Shared
value, content-projection and deadline contracts remain the only definitions.
"""
from ..changes.update_inputs import normalize_artifact_update_input
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.domain_fields import VERIFICATION_PLAN_STATUSES
from ..model.errors import ModelError
from ..model.waiver_fields import CONTENT_HASH_ALGORITHM, WAIVER_VERSION, waiver_time
from ..storage.domain_artifact import DomainArtifact
from .waiver_content import waiver_subject, waiver_content_sha256
from .waiver_values import VerificationWaiver, WaiverContext


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
