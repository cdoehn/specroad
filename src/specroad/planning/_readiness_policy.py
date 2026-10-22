"""Closed v1 data admission; no legacy migration and no review authority."""
import re

from ..graph.scope_descriptors import ScopeDescriptor
from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..storage.json_syntax import parse_json_object
from ..verification import VerificationEvaluation


def readiness_policy(value):
    value = parse_json_object(canonical_json_bytes(value))
    if 'format_version' not in value:
        return value, 'legacy_readiness_policy_unsupported'
    if (value['format_version'] != '1.0.0' or
            not {'format_version', 'blocker_decisions'} <= set(value) or
            set(value) - {'format_version', 'blocker_decisions', 'verification_evaluation'}):
        raise ModelError('release_readiness_policy_fields_invalid')
    if 'verification_evaluation' in value:
        VerificationEvaluation(canonical_json_bytes(value['verification_evaluation']))
    decisions = value['blocker_decisions']
    if type(decisions) is not list:
        raise ModelError('release_blocker_decisions_required')
    seen = set()
    for decision in decisions:
        if type(decision) is not dict or set(decision) != {'subject_id', 'subject_sha256',
                'decision', 'reason', 'scope_descriptor', 'configuration_sha256', 'human_review_id'}:
            raise ModelError('release_blocker_decision_fields_invalid')
        for key in ('subject_id', 'reason', 'human_review_id'):
            if type(decision[key]) is not str or not decision[key].strip():
                raise ModelError('release_blocker_decision_text_required')
        for key in ('subject_sha256', 'configuration_sha256'):
            item = decision[key]
            if key == 'configuration_sha256' and item is None:
                continue
            if type(item) is not str or re.fullmatch('[0-9a-f]{64}', item) is None:
                raise ModelError('release_blocker_decision_hash_required')
        if decision['decision'] not in ('risk_eliminated', 'risk_accepted', 'issue_resolved'):
            raise ModelError('release_blocker_decision_unknown')
        ScopeDescriptor(decision['scope_descriptor'])
        if decision['subject_id'] in seen:
            raise ModelError('release_blocker_decision_duplicate')
        seen.add(decision['subject_id'])
    value['blocker_decisions'].sort(key=lambda d: d['subject_id'].encode('utf-8'))
    return value, None
