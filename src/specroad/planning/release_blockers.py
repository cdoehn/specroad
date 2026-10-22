"""Passive Release blocker reviews and explicit trusted host observations.

The shared ReviewVerifier authenticates a supplied review; project data never
selects code. Neither these values nor a positive observation authorize writes.
"""
from dataclasses import dataclass
import re

from ..model.audit import actor
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.errors import ModelError
from ..model.waiver_fields import waiver_time
from ..storage.json_syntax import parse_json_object
from ..validation import ReviewVerifier, ReviewVerification


@dataclass(frozen=True, init=False)
class HumanReleaseBlockerReview:
    _encoded: bytes

    def __init__(self, value):
        raw = canonical_json_bytes(value)
        data = parse_json_object(raw)
        if set(data) != {'review_id', 'subject_id', 'decision_sha256', 'reviewer',
                         'reviewed_at', 'decision', 'criteria'}:
            raise ModelError('release_blocker_review_fields_invalid')
        for key in ('review_id', 'subject_id'):
            if type(data[key]) is not str or not data[key].strip() or '\0' in data[key]:
                raise ModelError('release_blocker_review_identity_required')
        if (type(data['decision_sha256']) is not str or
                re.fullmatch('[0-9a-f]{64}', data['decision_sha256']) is None):
            raise ModelError('release_blocker_review_hash_required')
        actor(data['reviewer']); waiver_time(data['reviewed_at'])
        if data['decision'] not in ('confirmed', 'rejected'):
            raise ModelError('release_blocker_review_decision_invalid')
        if type(data['criteria']) is not dict:
            raise ModelError('release_blocker_review_criteria_required')
        object.__setattr__(self, '_encoded', raw)

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def sha256(self):
        return canonical_json_sha256(self.data)

    def __bool__(self):
        raise TypeError('A passive review is not human confirmation')


@dataclass(frozen=True, init=False)
class ReleaseBlockerReviewContext:
    """Detached exact Readiness input passed to the explicitly trusted verifier."""
    _encoded: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError('The Readiness assessment supplies the review context')

    @classmethod
    def _create(cls, binding, subject, decision):
        result = object.__new__(cls)
        value = {'binding': binding, 'input_sha256': canonical_json_sha256(binding),
                 'subject': subject, 'decision': decision}
        object.__setattr__(result, '_encoded', canonical_json_bytes(value))
        return result

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def input_sha256(self):
        return self.data['input_sha256']

    def __bool__(self):
        raise TypeError('A review context is not an approval')


def blocker_review_inputs(reviews, verifier):
    if type(reviews) not in (tuple, list) or any(type(r) is not HumanReleaseBlockerReview for r in reviews):
        raise ModelError('typed_release_blocker_reviews_required')
    if verifier is not None and type(verifier) is not ReviewVerifier:
        raise ModelError('typed_release_blocker_verifier_required')
    owned = [HumanReleaseBlockerReview(r.data) for r in reviews]
    indexed = {r.data['review_id']: r for r in owned}
    if len(indexed) != len(owned):
        raise ModelError('release_blocker_review_duplicate')
    identity = None if verifier is None else {'id': verifier.verifier_id, 'version': verifier.version}
    return indexed, {'reviews': [{'review_id': key, 'sha256': indexed[key].sha256}
                                for key in sorted(indexed)], 'verifier': identity}


def assess_blocker(binding, subject, decision, reviews, verifier):
    """Return one gate contribution without changing the subject or policy."""
    kind = subject['artifact_type']
    status = subject[kind + '_status']
    required = ({'mitigated': 'risk_eliminated', 'closed': 'risk_eliminated',
                 'accepted': 'risk_accepted'} if kind == 'risk' else
                {'resolved': 'issue_resolved', 'closed': 'issue_resolved'})
    report = {'input_sha256': canonical_json_sha256(binding), 'subject_id': subject['id'],
        'subject_sha256': canonical_json_sha256(subject), 'stored_status': status,
        'decision_sha256': None, 'review_sha256': None, 'review_verified': False,
        'verification': None, 'status': 'incomplete', 'reasons': []}

    def fail(reason, state='incomplete'):
        report['status'] = state
        report['reasons'].append(reason)
        return report

    if status in ('open', 'in_progress'):
        return fail(kind + '_status_open', 'failed')
    if status not in required:
        return fail('unclassified_status')
    if decision is None:
        return fail('blocker_decision_missing')
    report['decision_sha256'] = canonical_json_sha256({'format_version': 'release-blocker-decision-v1',
        'release_id': binding['release_id'], 'decision': decision})
    report['decision'] = decision
    if decision['subject_sha256'] != report['subject_sha256']:
        return fail('blocker_decision_subject_changed')
    if canonical_json_bytes(decision['scope_descriptor']) != canonical_json_bytes(binding['scope_descriptor']):
        return fail('blocker_decision_scope_mismatch')
    if decision['configuration_sha256'] != binding['configuration_sha256']:
        return fail('blocker_decision_configuration_mismatch')
    if decision['decision'] != required[status]:
        return fail('blocker_decision_status_mismatch')
    if kind == 'issue':
        criteria = subject.get('resolution_criteria')
        criteria = [criteria] if type(criteria) is str else criteria
        if (type(criteria) is not list or not criteria or
                any(type(item) is not str or not item.strip() for item in criteria)):
            return fail('issue_resolution_criteria_missing')
        expected = {'resolution_criteria': [True] * len(criteria)}
    elif required[status] == 'risk_eliminated':
        expected = {'risk_eliminated': True}
    else:
        expected = {'residual_risk_accepted': True}
    review = reviews.get(decision['human_review_id'])
    if review is None:
        return fail('blocker_review_missing')
    return _assess_review(binding, subject, decision, review, verifier, expected, report)


def _assess_review(binding, subject, decision, review, verifier, expected, report):
    """Authenticate the exact passive review, then require its human criteria."""
    def fail(reason, state='incomplete'):
        report['status'] = state
        report['reasons'].append(reason)
        return report

    data = review.data
    report['review_sha256'] = review.sha256
    report['review'] = data
    if (data['subject_id'] != subject['id'] or data['decision_sha256'] != report['decision_sha256']):
        return fail('blocker_review_binding_mismatch')
    if data['reviewer']['actor_type'] != 'human':
        return fail('blocker_review_nonhuman', 'failed')
    if waiver_time(data['reviewed_at']) > waiver_time(binding['evaluated_at']):
        return fail('blocker_review_in_future')
    if verifier is None:
        return fail('blocker_review_verifier_unavailable')
    context = ReleaseBlockerReviewContext._create(binding, subject, decision)
    original = context._encoded, review._encoded
    checked_review = HumanReleaseBlockerReview(data)
    verifier_id, version, check = verifier.verifier_id, verifier.version, verifier.check
    try:
        observation = check(context, checked_review)
        if (original != (context._encoded, review._encoded) or checked_review._encoded != original[1]
                or verifier.verifier_id != verifier_id or verifier.version != version or verifier.check is not check):
            return fail('blocker_review_inputs_changed')
        if (type(observation) is not ReviewVerification or
                observation.input_sha256 != report['input_sha256'] or observation.review_sha256 != report['review_sha256']):
            return fail('blocker_review_verifier_unbound')
        observation = ReviewVerification(observation.input_sha256, observation.review_sha256,
            observation.authenticated_human, observation.current)
        report['verification'] = {'input_sha256': observation.input_sha256,
            'review_sha256': observation.review_sha256, 'authenticated_human': observation.authenticated_human,
            'current': observation.current, 'verifier': {'id': verifier_id, 'version': version}}
        if not observation.authenticated_human or not observation.current:
            return fail('blocker_review_not_authenticated_or_current')
    except Exception:
        return fail('blocker_review_verification_failed')
    if data['decision'] != 'confirmed':
        return fail('blocker_review_rejected', 'failed')
    if canonical_json_bytes(data['criteria']) != canonical_json_bytes(expected):
        supplied = data['criteria']
        if set(supplied) == set(expected):
            values, needed = next(iter(supplied.values())), next(iter(expected.values()))
            if ((type(needed) is bool and values is False) or
                    (type(needed) is list and type(values) is list and len(values) == len(needed)
                     and all(type(v) is bool for v in values) and not all(values))):
                return fail('blocker_review_criteria_unconfirmed', 'failed')
        return fail('blocker_review_criteria_incomplete')
    report['review_verified'] = True
    report['status'] = 'passed'
    return report
