"""Typed findings from completed status observations and stored positions."""
from ..diagnostics import Diagnostic, code_metadata


def _diagnostic(value, path, position):
    if value.status == 'current':
        return None
    code = {'unreviewed': 'SRV025', 'suspect': 'SRV026', 'invalid': 'SRV027'}[value.status]
    metadata = code_metadata(code)
    category = ('review_outcome' if value.reason == 'current_review_rejected'
        else 'relation_structure' if value.status == 'invalid' else 'relation_review')
    related = (value.relation_id, value.target_id)
    if value.selected_review_id is not None:
        related += (value.selected_review_id,)
    return Diagnostic(code, metadata['default_severity'], category, metadata['meaning'],
        rule_id='core:relation-review-status', artifact_id=value.source_id,
        path=path, location={'pointer': '/relations/' + str(position)},
        rationale=value.reason or 'relation_' + value.status, related_ids=related)
