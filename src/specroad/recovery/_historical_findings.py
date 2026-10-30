"""Passive original-history findings; no present approval or write authority.

Native qualification is separate and always reruns trusted observations. These
deterministic findings remain readable from the completed plan's original bytes
after loss of its roots or services. They do not authenticate stored labels.
"""
from ..graph.relations import SourceRelations
from ..graph.review_status import RelationReviewStatuses
from ..storage.json_syntax import parse_json_object
from ._evidence_history import evidence_assessments


def historical_findings(model):
    findings = list(evidence_assessments(model))
    if any(a['artifact_type'] == 'relation_review' for a in model.artifacts):
        statuses = RelationReviewStatuses(tuple(SourceRelations(d.content, path=d.path)
                                               for d in model.documents))
        for status in statuses.statuses:
            if status.status != 'current':
                findings.append({'kind': 'relation_review_history',
                    'relation_id': status.relation_id, 'observed_status': status.status,
                    'current_approval': False})
    from ..proposals import ProposalOriginal
    for document in model.documents:
        if parse_json_object(document.content)['artifact_type'] != 'proposal':
            continue
        original = ProposalOriginal(document.content, path=document.path)
        value = original.data
        findings.append({'kind': 'proposal_original_history', 'path': document.path,
            'original_sha256': original.sha256, 'binding': original.binding.data,
            'observed_status': value['proposal_status'], 'reviews': value.get('reviews', []),
            'control_history': value['control_history'], 'current_qualification_checked': False,
            'write_authorized': False})
    return tuple(findings)
