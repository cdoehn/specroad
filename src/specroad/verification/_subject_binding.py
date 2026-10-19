"""Pure Appendix L projection and subject bindings for records and assessment.

Callers supply owned, natively validated subject data. Computing these hashes
neither assesses Evidence freshness nor grants verification or write authority.
"""
from ..model.canonical import canonical_json_sha256

CONTEXT_HASH_ALGORITHM = 'verification_context_hash-v1'
# Only these top-level fields are removed. Names inside semantic extensions,
# oracles and structured requirement data keep their original meaning.
_EXCLUDED = frozenset({'revision', 'created_at', 'created_by', 'updated_at',
    'updated_by', 'maturity', 'implementation_status', 'verification_plan_status',
    'verification_waiver', 'relations', 'tags'})


def project_subject(value):
    """Project an owned native subject value without modifying its fields."""
    projected = {key: item for key, item in value.items() if key not in _EXCLUDED}
    if 'provenance' in value:
        projected['provenance'] = [{key: item for key, item in source.items()
                                    if key != 'captured_at'} for source in value['provenance']]
    return projected


def subject_context_sha256(value):
    return canonical_json_sha256(project_subject(value))


def subject_binding(value):
    """Use the same projection for current-subject and explicit-contract bindings."""
    return {'artifact_id': value['id'], 'revision': value['revision'],
            'artifact_sha256': canonical_json_sha256(value),
            'verification_context_sha256': subject_context_sha256(value)}
