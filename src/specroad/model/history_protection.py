"""One protected-original predicate for already qualified native records.

Schema/state qualification remains with the caller; this does not grant approval.
"""


def protected_record(value):
    return (value['artifact_type'] in ('baseline', 'evidence', 'relation_review') or
            value['artifact_type'] == 'proposal' and
            value['proposal_status'] in ('rejected', 'applied', 'stale'))
