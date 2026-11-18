"""Convert passive foreign control state into a native initial local draft."""
from ..changes import TargetPolicy, prepare_authoring_request
from ..changes.target import prepare_change_target
from ..changes.target_model import _default_scope
from ..model.canonical import canonical_json_bytes
from ..proposals.authoring import Proposal
from ..proposals._create_control import COMMAND, GATE
from ..proposals._draft_qualification import publication_gates
from ..authoring.execution import _apply_saved_plan, _replay
from ..storage.project import ProjectSource
from ._files import require

POLICY = TargetPolicy(COMMAND, '1', (GATE,))


def draft(original):
    value = original.data
    plan = value['change_plan']
    value.update(revision=1, content_revision=1, maturity='draft', proposal_status='draft',
        reviews=[], control_history=[], created_by=plan['actor'], updated_by=plan['actor'],
        created_at=plan['planned_at'], updated_at=plan['planned_at'])
    result = Proposal(canonical_json_bytes(value), path=original.path)
    require(result.binding.content_sha256 == original.binding.content_sha256, 'return_draft_content_changed')
    return result


def request(proposal):
    plan = proposal.data['change_plan']
    return prepare_authoring_request(command_id='proposal create', actor=plan['actor'],
        request_id=plan['request_id'], operations=[{'op':'proposal_create','record':proposal.data}])


def replay(root, proposal):
    return _replay(ProjectSource(root), request(proposal), COMMAND)


def publish(model, proposal, *, authority, transaction_id):
    value = proposal.data['change_plan']
    gates = publication_gates(model, proposal)
    checked = prepare_change_target(model, [{'op':'proposal_create','record':proposal.data}],
        change_plan_id=value['change_plan_id'], request_id=value['request_id'],
        actor=value['actor'], planned_at=value['planned_at'], scope_descriptor=_default_scope(),
        metadata_policy_version=value['metadata_policy_version'], policy=POLICY, gates=gates)
    checked.require_valid()
    return _apply_saved_plan(checked.plan, model, command_id=COMMAND, authority=authority,
        transaction_id=transaction_id, gates=gates, bound_policy=POLICY)
