"""Structural Proposal validation over native inputs, without control writes."""
from dataclasses import dataclass

from ..model.canonical import canonical_json_bytes
from ..storage.json_syntax import parse_json_object
from .context import ProposalContext, reconstruct_proposal_target
from .values import require
from ._validation_result import validation_success


@dataclass(frozen=True, init=False)
class ProposalValidation:
    """Owned observation, never review evidence or a prepared control operation."""
    canonical_bytes: bytes

    def __init__(self, context):
        require(type(context) is ProposalContext, 'proposal_native_context_required')
        # The original already validates the schema, content binding and plan
        # correspondence. The native fold checks references and applicability.
        # Full semantic qualification belongs to proposal check, not validate.
        target = reconstruct_proposal_target(context)
        original = context.original
        value = original.data
        # Explanations may refer to an existing or newly planned requirement /
        # issue, including one removed by this plan. They are passive references.
        known = {item['id'] for item in (*context.basis.artifacts, *target.artifacts)}
        for index, change in enumerate(value.get('changes', [])):
            require(all(ref in known for ref in change['requirement_or_issue_ids']),
                    'proposal_requirement_reference_missing', path=original.path,
                    pointer='/changes/' + str(index) + '/requirement_or_issue_ids')
        report = validation_success(context)
        object.__setattr__(self, 'canonical_bytes', canonical_json_bytes(report))

    @property
    def data(self):
        return parse_json_object(self.canonical_bytes)


def validate_proposal(context):
    return ProposalValidation(context)
