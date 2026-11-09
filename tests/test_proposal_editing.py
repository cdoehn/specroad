"""Four native authoring actions and real, explicitly synthetic review history."""
from dataclasses import replace

import pytest

from specroad.changes import ChangePlan, prepare_change_plan
from specroad.model.audit_values import Actor, Revision, UtcTimestamp
from specroad.model.canonical import canonical_json_bytes
from specroad.model.record_contracts import SPECIAL_STATES
from specroad.proposals import (Proposal, ProposalChanges, ProposalContext,
    prepare_proposal_change, prepare_proposal_change_for_model, assess_proposal)
from specroad.proposals.values import content_sha256
from support.read_only import no_write_attempts
from test_proposal_changes import sequence, create, plan, explanation


EDITOR = Actor('human', 'synthetic-proposal-editor')
TIME = UtcTimestamp('2026-11-09T00:00:00Z')


def in_state(proposal, status):
    # A value-level state, not evidence of approval or an authenticated decision.
    value = proposal.data
    value.update(proposal_status=status, maturity=SPECIAL_STATES['proposal'][1][status])
    return Proposal(canonical_json_bytes(value), path=proposal.original.path)


def fields(proposal, action):
    first, second = ProposalChanges(proposal).change_ids
    if action == 'add':
        return dict(action=action, change_plan=plan([create(c) for c in 'ABC']),
                    explanation=explanation('C'))
    if action == 'update':
        return dict(action=action, change_plan=plan([create(c) for c in 'AC']),
                    change_id=second, explanation=explanation('C'))
    if action == 'remove':
        return dict(action=action, change_plan=plan([create('B')]), change_id=first)
    return dict(action=action, change_plan=plan([create(c) for c in 'BA']),
                change_id=first, position=1)


def edit(proposal, action, **overrides):
    options = dict(expected_revision=Revision(proposal.data['revision']), actor=EDITOR,
                   planned_at=TIME, **fields(proposal, action))
    options.update(overrides)
    return prepare_proposal_change(proposal, **options)


@pytest.mark.parametrize('status', ['draft', 'in_review', 'approved'])
@pytest.mark.parametrize('action,expected', [('add', 'ABC'), ('update', 'AC'),
                                           ('remove', 'B'), ('move', 'BA')])
def test_authoring_actions_reset_open_states_and_advance_exactly_once(status, action, expected):
    source = in_state(sequence()[0], status)
    raw = source.source_bytes
    with no_write_attempts():
        prepared = edit(source, action)
    after = prepared.proposal.data
    assert ''.join(op['artifact']['statement'] for op in after['change_plan']['operations']) == expected
    assert after['proposal_status'] == after['maturity'] == 'draft'
    assert (after['revision'], after['content_revision']) == (2, 2)
    assert after['content_sha256'] != source.binding.content_sha256
    assert after['content_sha256'] == content_sha256(after)
    assert after['updated_at'] == TIME.value and after['updated_by'] == EDITOR.as_fields()
    for key in ('id', 'id_scheme', 'created_at', 'created_by', 'base', 'reviews', 'control_history'):
        assert after[key] == source.data[key]
    assert source.source_bytes == raw and prepared.revision.before is source.original
    assert len(prepared.changed_change_ids) == 1 and prepared.changed
    assert prepared.request.data['command_id'] == 'proposal change ' + action
    assert prepared.request.data['namespace'] == 'normative_write'
    assert prepared.request.data['operations'] == after['change_plan']['operations']
    assert prepared.request.data['route'] == 'proposal_management'
    assert prepared.request.data['actor'] == EDITOR.as_fields()
    assert prepared.write_authorized is prepared.proposal.write_authorized is False
    assert prepared.request.data['write_authorized'] is False
    assert prepared.request.data['actor_authenticated'] is False


@pytest.mark.parametrize('actor_type', ['human', 'ai', 'ci', 'tool'])
def test_authoring_binds_explicit_editor_to_common_specialist_request_policy(actor_type):
    source = sequence()[0]
    actor = Actor(actor_type, 'synthetic-editor')
    with no_write_attempts():
        prepared = edit(source, 'update', actor=actor, request_id='synthetic:edit:one')
    assert prepared.proposal.data['updated_by'] == actor.as_fields()
    assert prepared.proposal.data['created_by'] == source.data['created_by']
    assert prepared.request.data['request_id'] == 'synthetic:edit:one'
    assert prepared.request.data['receipt_checked'] is False
    assert prepared.request.data['idempotency_guaranteed'] is False


def test_full_plan_and_explanations_are_owned_across_chained_edits():
    source = sequence()[0]
    options = fields(source, 'update')
    with no_write_attempts():
        first = prepare_proposal_change(source, expected_revision=Revision(1),
                                       actor=EDITOR, planned_at=TIME, **options)
    options['explanation']['rationale'] = 'Caller mutation'
    data = first.proposal.data
    data['changes'].clear()
    request = first.request.data
    request['operations'].clear()
    assert first.proposal.data['changes'][1]['rationale'] == 'Synthetic change C'
    assert first.request.data['operations']
    with no_write_attempts():
        second = prepare_proposal_change(first.proposal, action='remove',
            change_plan=plan([create('C')]), change_id=ProposalChanges(first.proposal).change_ids[0],
            expected_revision=Revision(2), actor=EDITOR, planned_at=TIME)
    assert (second.proposal.data['revision'], second.proposal.data['content_revision']) == (3, 3)
    assert second.proposal.data['updated_at'] == '2026-11-09T00:00:00.000001Z'
    assert first.proposal.data['revision'] == 2 and source.data['revision'] == 1


def authoring_draft(tmp_path, *, language_registry=None):
    from test_proposal_originals import draft
    model, value = draft(tmp_path, language_registry=language_registry)
    value['changes'] = []
    value['content_sha256'] = content_sha256(value)
    return model, value


def native_plan(model, proposal, operations):
    """Actual ordered fold, lifecycle, metadata and final native model root."""
    from specroad.changes.lifecycle import prepare_change_lifecycle
    from specroad.changes._target_materialization import materialize_target
    from specroad.model.paths import artifact_path
    from specroad.proposals.context import specification_manifest
    from specroad.validation import ModelDocument
    from support.change_plans import document, result
    value = document(operations, [])
    folded = prepare_change_lifecycle(model.artifacts, operations,
        metadata_policy_version=value['metadata_policy_version'], actor=value['actor'],
        planned_at=value['planned_at'], source_files=model.source_files, **model.reservations)
    changed = [item for item in folded.candidates if item.changed]
    # The test's operation targets exactly one standard artifact.
    artifacts = [item.data for item in changed]
    target = materialize_target(model, tuple(ModelDocument(
        artifact_path(a['artifact_type'], a['id'], 'SR'), canonical_json_bytes(a)) for a in artifacts))
    value['base'] = proposal.data['base']
    value['result_artifacts'] = [result(a) for a in artifacts]
    value['expected_result']['model_root_sha256'] = specification_manifest(target).sha256
    return prepare_change_plan(value)


def test_native_authoring_invalidates_approval_but_preserves_verified_history(tmp_path):
    from specroad.changes._target_materialization import materialize_target
    from specroad.validation import ModelDocument
    from support.folds import edit as goal_edit
    from support.languages import small_restore_registry
    from test_proposal_history import history
    inputs, current = history(tmp_path, draft_factory=authoring_draft,
                              language_registry=small_restore_registry())
    before = inputs.originals[-1]
    proposal = Proposal(before.source_bytes, path=before.path)
    model = inputs.contexts[-1].basis
    goal = next(a for a in model.artifacts if a['artifact_type'] == 'goal')
    original_documents = current.documents
    with no_write_attempts():
        report = assess_proposal(before, inputs, current)
        assert report['current_approval'] and report['effective_human_approvals'] == 1
        bound_plan = native_plan(model, proposal, [goal_edit(goal, 'New synthetic content')])
        prepared = prepare_proposal_change_for_model(model, proposal, action='add',
            change_plan=bound_plan, explanation=explanation('new content'),
            expected_revision=Revision(before.data['revision']), actor=EDITOR, planned_at=TIME)
    after = prepared.proposal.original
    assert (after.data['revision'], after.data['content_revision']) == (before.data['revision'] + 1, 2)
    assert after.data['reviews'] == before.data['reviews']
    assert after.data['control_history'] == before.data['control_history']
    assert after.data['proposal_status'] == after.data['maturity'] == 'draft'
    assert after.binding.change_plan_sha256 == bound_plan.sha256
    assert current.documents == original_documents
    rebuilt = replace(inputs, originals=(*inputs.originals, after),
        contexts=(*inputs.contexts, ProposalContext(after, model)))
    current = materialize_target(current, (ModelDocument(after.path, after.source_bytes),))
    with no_write_attempts():
        report = assess_proposal(after, rebuilt, current)
    assert report['historical_valid'] and not report['current_approval']
    assert report['effective_human_approvals'] == 0 and not report['write_authorized']


def test_native_edit_sequence_recomputes_ordered_target_without_extra_revision(tmp_path):
    from specroad.proposals.context import reconstruct_proposal_target
    from support.folds import edit as goal_edit
    from support.languages import small_restore_registry
    from test_proposal_originals import original
    model, value = authoring_draft(tmp_path, language_registry=small_restore_registry())
    saved = original(value)
    source = Proposal(saved.source_bytes, path=saved.path)
    goal = next(a for a in model.artifacts if a['artifact_type'] == 'goal')
    a, b, c = [goal_edit(goal, text) for text in ('First', 'Second', 'Third')]
    operations = []
    actions = [('add', [a], 'First'), ('add', [a, b], 'Second'),
               ('move', [b, a], 'First'), ('update', [b, c], 'Third'),
               ('remove', [c], 'Third'), ('remove', [], goal['statement'])]
    original_documents = model.documents
    identities = []
    with no_write_attempts():
        for index, (action, operations, statement) in enumerate(actions, 2):
            options = dict(action=action, change_plan=native_plan(model, source, operations),
                expected_revision=Revision(source.data['revision']), actor=EDITOR, planned_at=TIME)
            ids = ProposalChanges(source).change_ids
            if action == 'add':
                options['explanation'] = explanation(statement)
            elif action == 'move':
                options.update(change_id=ids[0], position=1)
            elif action == 'update':
                options.update(change_id=ids[1], explanation=explanation(statement))
            else:
                options['change_id'] = ids[0]
            prepared = prepare_proposal_change_for_model(model, source, **options)
            source = prepared.proposal
            target = reconstruct_proposal_target(ProposalContext(source.original, model))
            final = next(a for a in target.artifacts if a['id'] == goal['id'])
            assert final['statement'] == statement
            assert final['revision'] == goal['revision'] + int(bool(operations))
            assert source.data['revision'] == source.data['content_revision'] == index
            assert source.data['proposal_status'] == 'draft' and prepared.changed
            identities.append(ProposalChanges(source).change_ids)
    assert identities[2] == tuple(reversed(identities[1]))
    assert identities[3] == identities[2] and identities[-1] == ()
    assert model.documents == original_documents
