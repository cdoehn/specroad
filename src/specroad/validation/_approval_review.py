"""Human meaning confirmation, separate from formal fields and service statuses.

Only an explicitly trusted verifier can authenticate/currently bind a review.
This adapter is not an authentication service or language/compound detector.
"""
from ..model.errors import ModelError
from .approval_values import HUMAN_CRITERIA, ReviewVerification
from ._approval_findings import _finding


def observe_human_review(context, review, verifier):
    issues=[]
    human_status='missing'; authenticated=False; current=False
    if review is None:
        issues.append(_finding(context,'approval_human_review_missing'))
    else:
        data=review.data
        try:
            bound=(data['input_sha256']==context.input_sha256 and data['requirement_id']==context.requirement_id
                and data['requirement_sha256']==context.requirement_sha256
                and data['force_statement_sha256']==context.force_statement_sha256)
        except ModelError:
            bound=False
        human_status='unverified'
        if not bound:
            human_status='stale';issues.append(_finding(context,'approval_review_binding_mismatch'))
        elif data['reviewer']['actor_type']!='human':
            human_status='nonhuman';issues.append(_finding(context,'approval_nonhuman_review',code='SRV030'))
        elif verifier is None:
            issues.append(_finding(context,'approval_review_verifier_unavailable',code='APPROVAL_UNAVAILABLE'))
        else:
            try:
                evidence=verifier.check(context,review)
                if (type(evidence) is not ReviewVerification or evidence.input_sha256!=context.input_sha256
                        or evidence.review_sha256!=review.sha256):
                    raise ModelError('approval_review_verifier_unbound')
                authenticated=evidence.authenticated_human;current=evidence.current
                if not authenticated or not current:
                    issues.append(_finding(context,'approval_review_not_authenticated_or_current'))
                elif data['compound']:
                    human_status='compound'
                    issues.append(_finding(context,'approval_human_confirmed_compound',code='SRV162',origin='core_rule'))
                elif data['decision']!='confirmed':
                    human_status='rejected';issues.append(_finding(context,'approval_human_review_rejected'))
                elif any(data['criteria'].get(name) is not True for name in HUMAN_CRITERIA):
                    human_status='incomplete';issues.append(_finding(context,'approval_human_criteria_unconfirmed'))
                else: human_status='confirmed'
            except Exception:
                human_status='verification_failed'
                issues.append(_finding(context,'approval_review_verification_failed',code='APPROVAL_UNAVAILABLE'))
    return issues, human_status, authenticated, current
