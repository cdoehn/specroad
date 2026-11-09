"""Small complete native Proposal inputs for public read-validation cases."""
from specroad.model.canonical import canonical_json_bytes
from specroad.proposals import prepare_proposal_for_model
from .model import put


def validation_project(root, *, changed=False, bundled=False):
    from test_proposal_basis import project, fields, planned_change
    model = project(root, bundled=bundled)
    proposal = prepare_proposal_for_model(model, **(planned_change(model) if changed else fields(model)))
    put(root, proposal.original.path, proposal.original.source_bytes)
    return model, proposal.original


def replace_proposal(root, original, **fields):
    value = original.data
    value.update(fields)
    put(root, original.path, canonical_json_bytes(value))
    return value
