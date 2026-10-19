"""Compatible waiver service facade over separate preparation and assessment.

The existing import paths remain available. Owned values, content projection
and UTC comparisons keep their shared implementations and exact contracts.
"""
from copy import copy
from ..changes.update_inputs import normalize_artifact_update_input
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.domain_fields import VERIFICATION_PLAN_STATUSES
from ..model.errors import ModelError
from ..model.waiver_fields import CONTENT_HASH_ALGORITHM, WAIVER_VERSION, waiver_time
from ..storage.domain_artifact import DomainArtifact
from .waiver_content import waiver_subject, waiver_content_sha256
from .waiver_values import (VerificationWaiver, WaiverContext, HumanWaiverReview,
    WaiverReviewVerification, WaiverReviewVerifier, WaiverAssessment)

from ._waiver_workflow import prepare_verification_waiver, prepare_verification_plan_update
from ._waiver_assessment import assess_verification_waiver
