"""Owned stored-field projection for the query selection stage."""
from ..srx import MISSING
from ..srx.pointers import resolve_tokens


def project_item(artifact, identifier, pointers):
    if pointers:
        values = {}
        for pointer, tokens in pointers:
            value = resolve_tokens(artifact, tokens, rule_id='query-projection')
            values[pointer] = {'state': 'missing'} if value is MISSING else value
        item = {'id': identifier, 'artifact_type': artifact['artifact_type'], 'values': values}
    else:
        fields = ('id', 'artifact_type', 'title', 'revision', 'maturity',
                  'implementation_status', 'verification_plan_status')
        item = {name: artifact[name] for name in fields if name in artifact}
    return item
