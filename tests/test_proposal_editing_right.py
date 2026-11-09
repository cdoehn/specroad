"""No-op byte preservation, end-state isolation and fail-closed authoring input."""
import json

import pytest

from specroad.changes import ChangePlan, prepare_change_plan
from specroad.changes.request_ids import AuthoringError
from specroad.model.audit_values import Actor, Revision
from specroad.model.canonical import canonical_json_bytes
from specroad.model.errors import ModelError
from specroad.model.identity_values import ArtifactIdentity
from specroad.proposals import (Proposal, ProposalChanges, ProposalError, prepare_proposal,
    prepare_proposal_change, prepare_proposal_change_for_model)
from specroad.proposals.values import content_sha256
from support.read_only import no_write_attempts
from support.records import ref
from test_proposal_changes import sequence, create, plan, explanation
from test_proposal_editing import EDITOR, TIME, edit, fields, in_state, authoring_draft, native_plan


def forbid_entropy(monkeypatch):
    def blocked(size):
        pytest.fail('Rejected/no-op request must not allocate a change ID')
    monkeypatch.setattr('secrets.token_bytes', blocked)


@pytest.mark.parametrize('status', ['draft', 'in_review', 'approved'])
@pytest.mark.parametrize('action', ['update', 'move'])
def test_noop_preserves_all_original_bytes_state_and_audit(status, action, monkeypatch):
    source = in_state(sequence()[0], status)
    raw = json.dumps(source.data, indent=4).encode() + b'\n'
    source = Proposal(raw, path=source.original.path)
    ordered = ProposalChanges(source)
    options = dict(change_plan=ordered.change_plan, change_id=ordered.change_ids[0])
    if action == 'update':
        options['explanation'] = explanation('A')
    else:
        options['position'] = 0
    forbid_entropy(monkeypatch)
    with no_write_attempts():
        prepared = prepare_proposal_change(source, action=action, expected_revision=Revision(1),
            actor=EDITOR, planned_at=TIME, **options)
    assert prepared.proposal is source and prepared.proposal.source_bytes == raw
    assert prepared.revision.after is source.original
    assert prepared.changed_change_ids == () and not prepared.changed
    assert not prepared.revision.content_changed and not prepared.write_authorized
    assert prepared.proposal.binding == source.binding


@pytest.mark.parametrize('status', ['rejected', 'stale', 'applied'])
@pytest.mark.parametrize('action', ['add', 'update', 'remove', 'move'])
def test_terminal_original_cannot_be_reopened_or_allocate_identity(status, action, monkeypatch):
    source = in_state(sequence()[0], status)
    raw = source.source_bytes
    forbid_entropy(monkeypatch)
    with no_write_attempts(), pytest.raises(ProposalError) as error:
        edit(source, action)
    assert error.value.reason == 'proposal_terminal_revision_changed'
    assert source.source_bytes == raw


@pytest.mark.parametrize('status', ['validated', 'checked'])
def test_intermediate_review_states_are_not_editable_persisted_authoring_states(status, monkeypatch):
    source = in_state(sequence()[0], status)
    forbid_entropy(monkeypatch)
    with no_write_attempts(), pytest.raises(ProposalError, match='authoring_status_invalid'):
        edit(source, 'add')


@pytest.mark.parametrize('status', ['rejected', 'stale', 'applied'])
def test_new_submission_requires_a_separate_allocated_proposal_identity(status):
    previous = in_state(sequence()[0], status)
    identity = ArtifactIdentity(ref('PROP', '1'), 'random128-v1', 'proposal', 'SR')
    with no_write_attempts():
        new = prepare_proposal(identity=identity, title='Separate synthetic submission',
            rationale='New work originating from ' + previous.data['id'],
            change_plan=plan([]), changes=[])
        prepared = prepare_proposal_change(new, action='add', change_plan=plan([create('C')]),
            explanation=explanation('C'), expected_revision=Revision(1), actor=EDITOR, planned_at=TIME)
    assert previous.data['id'] != new.data['id'] == prepared.proposal.data['id']
    assert previous.data['proposal_status'] == status
    assert new.data['proposal_status'] == prepared.proposal.data['proposal_status'] == 'draft'
    assert (new.data['revision'], prepared.proposal.data['revision']) == (1, 2)


@pytest.mark.parametrize('override,reason', [
    ({'expected_revision': Revision(2)}, 'proposal_revision_conflict'),
    ({'expected_revision': 1}, 'proposal_expected_revision_required'),
    ({'actor': {'actor_type': 'human', 'actor_id': 'synthetic'}}, 'proposal_explicit_audit_required'),
    ({'planned_at': TIME.value}, 'proposal_explicit_audit_required')])
def test_stale_or_untyped_audit_fails_before_allocation(override, reason, monkeypatch):
    source = sequence()[0]
    forbid_entropy(monkeypatch)
    with no_write_attempts(), pytest.raises(ProposalError) as error:
        edit(source, 'add', **override)
    assert error.value.reason == reason
    if reason == 'proposal_revision_conflict':
        assert error.value.exit_code == 6


@pytest.mark.parametrize('actor_type', ['ai', 'ci'])
def test_normative_nonhuman_edit_requires_request_id_before_allocation(actor_type, monkeypatch):
    source = sequence()[0]
    forbid_entropy(monkeypatch)
    with no_write_attempts(), pytest.raises(AuthoringError, match='normative_request_id_required'):
        edit(source, 'add', actor=Actor(actor_type, 'synthetic-editor'))


@pytest.mark.parametrize('actor_type', ['ai', 'ci'])
def test_dry_run_is_only_preview_with_no_receipt_or_write_grant(actor_type):
    source = sequence()[0]
    with no_write_attempts():
        prepared = edit(source, 'update', actor=Actor(actor_type, 'synthetic'), dry_run=True)
    assert prepared.changed and prepared.request.data['route'] == 'preview'
    assert prepared.request.data['request_id'] is None
    assert not prepared.request.data['idempotency_guaranteed'] and not prepared.write_authorized
    assert source.data['revision'] == 1


@pytest.mark.parametrize('action,extra', [('add', {'change_id': None}),
    ('update', {'position': None}), ('remove', {'explanation': None}),
    ('move', {'explanation': explanation('A')})])
def test_irrelevant_options_are_rejected_not_silently_ignored(action, extra, monkeypatch):
    source = sequence()[0]
    forbid_entropy(monkeypatch)
    with no_write_attempts(), pytest.raises(ProposalError, match='proposal_change_arguments'):
        edit(source, action, **extra)


@pytest.mark.parametrize('action,missing', [('add', 'explanation'), ('update', 'change_id'),
                                         ('remove', 'change_id'), ('move', 'position')])
def test_required_action_options_must_be_explicit(action, missing, monkeypatch):
    source = sequence()[0]
    options = fields(source, action)
    del options[missing]
    forbid_entropy(monkeypatch)
    with no_write_attempts(), pytest.raises(ProposalError, match='proposal_change_arguments'):
        prepare_proposal_change(source, expected_revision=Revision(1), actor=EDITOR, planned_at=TIME, **options)


@pytest.mark.parametrize('action', [None, '', 'review', 'create', [], True])
def test_unknown_action_never_selects_another_workflow(action, monkeypatch):
    source = sequence()[0]
    forbid_entropy(monkeypatch)
    with no_write_attempts(), pytest.raises(ProposalError, match='proposal_change_action_invalid'):
        options = fields(source, 'add')
        options['action'] = action
        prepare_proposal_change(source, expected_revision=Revision(1), actor=EDITOR,
                                planned_at=TIME, **options)


def test_content_revision_cannot_substitute_for_expected_physical_revision(monkeypatch):
    source = sequence()[0]
    value = source.data
    value['revision'] = 4
    source = Proposal(canonical_json_bytes(value), path=source.original.path)
    forbid_entropy(monkeypatch)
    with no_write_attempts(), pytest.raises(ProposalError, match='proposal_revision_conflict'):
        edit(source, 'add', expected_revision=Revision(source.data['content_revision']))


def test_last_change_removal_returns_empty_plan_with_one_revision():
    source = sequence('A')[0]
    with no_write_attempts():
        prepared = prepare_proposal_change(source, action='remove',
            change_id=ProposalChanges(source).change_ids[0], change_plan=plan([]),
            expected_revision=Revision(1), actor=EDITOR, planned_at=TIME)
    assert prepared.proposal.data['changes'] == []
    assert prepared.proposal.data['change_plan']['operations'] == []
    assert prepared.proposal.data['revision'] == prepared.proposal.data['content_revision'] == 2
    assert prepared.changed_change_ids == ProposalChanges(source).change_ids


@pytest.mark.parametrize('fault', ['base', 'result', 'target'])
def test_native_adapter_rejects_false_declarations_without_publishing(tmp_path, fault):
    from specroad.proposals.context import specification_manifest
    from support.folds import edit as goal_edit
    from support.languages import small_restore_registry
    model, value = authoring_draft(tmp_path, language_registry=small_restore_registry())
    from test_proposal_originals import original
    observed = original(value)
    source = Proposal(observed.source_bytes, path=observed.path)
    goal = next(a for a in model.artifacts if a['artifact_type'] == 'goal')
    bound_plan = native_plan(model, source, [goal_edit(goal, 'New synthetic content')])
    values = bound_plan.data
    del values['change_plan_sha256']
    if fault == 'base':
        values['base']['model_root_sha256'] = 'f' * 64
    elif fault == 'target':
        values['expected_result']['model_root_sha256'] = 'f' * 64
    else:
        from support.change_plans import result
        artifact = values['result_artifacts'][0]['artifact']
        artifact['statement'] = 'False declared target'
        values['result_artifacts'] = [result(artifact)]
    invalid = prepare_change_plan(values)
    root = specification_manifest(model).sha256
    with no_write_attempts(), pytest.raises(ModelError):
        prepare_proposal_change_for_model(model, source, action='add', change_plan=invalid,
            explanation=explanation('new'), expected_revision=Revision(1), actor=EDITOR, planned_at=TIME)
    assert source.source_bytes == observed.source_bytes and specification_manifest(model).sha256 == root


def test_noop_keeps_actual_current_review_qualification(tmp_path, monkeypatch):
    from specroad.proposals import assess_proposal
    from support.folds import edit as goal_edit
    from support.languages import small_restore_registry
    from test_proposal_originals import original
    from test_proposal_history import history

    def reviewed_draft(path, *, language_registry):
        model, value = authoring_draft(path, language_registry=language_registry)
        saved = original(value)
        proposal = Proposal(saved.source_bytes, path=saved.path)
        goal = next(a for a in model.artifacts if a['artifact_type'] == 'goal')
        value['change_plan'] = native_plan(model, proposal, [goal_edit(goal, 'Synthetic content')]).data
        value['changes'] = [{**explanation('A'), 'change_id': 'CHG-' + '0' * 26, 'targets': [goal['id']]}]
        value['content_sha256'] = content_sha256(value)
        return model, value

    inputs, current = history(tmp_path, draft_factory=reviewed_draft,
                              language_registry=small_restore_registry())
    saved = inputs.originals[-1]
    source = Proposal(saved.source_bytes, path=saved.path)
    forbid_entropy(monkeypatch)
    with no_write_attempts():
        before = assess_proposal(saved, inputs, current)
        prepared = prepare_proposal_change_for_model(inputs.contexts[-1].basis, source,
            action='update', change_id=source.data['changes'][0]['change_id'],
            change_plan=ChangePlan(canonical_json_bytes(source.data['change_plan'])),
            explanation=explanation('A'), expected_revision=Revision(saved.data['revision']),
            actor=EDITOR, planned_at=TIME)
        after = assess_proposal(prepared.proposal.original, inputs, current)
    assert prepared.proposal.source_bytes == saved.source_bytes
    assert before == after and after['current_approval']
    assert after['effective_human_approvals'] == 1
