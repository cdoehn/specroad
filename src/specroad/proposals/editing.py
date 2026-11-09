"""Proposal authoring through native ordered plans, routing and revisions.

These owned before/after values are preparation for a writer, not a writer
capability. Live preimages, locking, request receipts and publication remain
the responsibility of the publishing host. No review is inferred from a row.
"""
from dataclasses import dataclass

from ..changes import ChangePlan
from ..changes.authoring import prepare_authoring_request
from ..changes.authoring_values import AuthoringRequest
from ..model.audit_values import Actor, Revision, UtcTimestamp
from .authoring import Proposal
from .change_order import ProposalChanges
from .revisions import ProposalRevision
from .values import require


_UNSET = object()


def _arguments(action, change_id, position, explanation):
    required = {'add': {'explanation'}, 'update': {'change_id', 'explanation'},
                'remove': {'change_id'}, 'move': {'change_id', 'position'}}[action]
    supplied = {key for key, value in (('change_id', change_id), ('position', position),
                ('explanation', explanation)) if value is not _UNSET}
    allowed = required | ({'position'} if action == 'add' else set())
    require(required <= supplied <= allowed, 'proposal_change_arguments', exit_code=2)


@dataclass(frozen=True, init=False)
class ProposalEdit:
    """One complete edit, with the original bytes and common request binding."""
    revision: ProposalRevision
    proposal: Proposal
    request: AuthoringRequest
    changed_change_ids: tuple

    def __init__(self, *args, **kwargs):
        raise TypeError('Use prepare_proposal_change or prepare_proposal_change_for_model')

    @classmethod
    def _prepare(cls, proposal, changes, request, *, expected_revision, actor, planned_at):
        value = proposal.data
        value.update(changes=changes.changes, change_plan=changes.change_plan.data)
        revision = ProposalRevision(proposal.original, value,
            expected_revision=expected_revision, actor=actor, planned_at=planned_at)
        result = object.__new__(cls)
        object.__setattr__(result, 'revision', revision)
        object.__setattr__(result, 'proposal', proposal if not revision.changed else
                           Proposal(revision.after.source_bytes, path=proposal.original.path))
        object.__setattr__(result, 'request', request)
        object.__setattr__(result, 'changed_change_ids', changes.changed_change_ids)
        return result

    @property
    def changed(self):
        return self.revision.changed

    @property
    def write_authorized(self):
        return False


def prepare_proposal_change(proposal, *, action, change_plan, expected_revision,
        actor, planned_at, request_id=None, dry_run=False, change_id=_UNSET,
        position=_UNSET, explanation=_UNSET):
    """Prepare add/update/remove/move, then advance the Proposal exactly once.

    The supplied plan is complete, including its declared target. For observed
    native basis/target verification use prepare_proposal_change_for_model.
    Neither entry point opens storage or provides replay/idempotency authority.
    """
    require(type(proposal) is Proposal, 'native_proposal_required')
    require(type(action) is str and action in ('add', 'update', 'remove', 'move'),
            'proposal_change_action_invalid', pointer='/action', exit_code=2)
    _arguments(action, change_id, position, explanation)
    require(type(expected_revision) is Revision, 'proposal_expected_revision_required')
    require(type(actor) is Actor and type(planned_at) is UtcTimestamp,
            'proposal_explicit_audit_required')
    before = proposal.data
    require(expected_revision.value == before['revision'], 'proposal_revision_conflict', exit_code=6)
    require(before['proposal_status'] not in ('rejected', 'stale', 'applied'),
            'proposal_terminal_revision_changed')
    require(before['proposal_status'] in ('draft', 'in_review', 'approved'),
            'proposal_authoring_status_invalid')
    require(type(change_plan) is ChangePlan, 'native_proposal_plan_required')
    request = prepare_authoring_request(command_id='proposal change ' + action,
        actor=actor, operations=change_plan.data['operations'],
        request_id=request_id, dry_run=dry_run)
    changes = ProposalChanges(proposal)
    if action == 'add':
        changes = changes.add(change_plan, explanation=explanation,
                              position=None if position is _UNSET else position)
    elif action == 'update':
        changes = changes.update(change_id, change_plan=change_plan, explanation=explanation)
    elif action == 'remove':
        changes = changes.remove(change_id, change_plan=change_plan)
    else:
        changes = changes.move(change_id, position, change_plan=change_plan)
    return ProposalEdit._prepare(proposal, changes, request,
        expected_revision=expected_revision, actor=actor, planned_at=planned_at)


def prepare_proposal_change_for_model(model, proposal, **fields):
    """Recompute the resulting target using the common native plan contract."""
    from .context import ProposalContext, reconstruct_proposal_target
    result = prepare_proposal_change(proposal, **fields)
    reconstruct_proposal_target(ProposalContext(result.proposal.original, model))
    return result
