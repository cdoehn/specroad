"""Real draft/check/review/edit/renewed approval/apply; synthetic actors only."""
import json
import pytest

from specroad.model.errors import ModelError
from specroad.proposals import ProposalOriginal
from specroad.model.canonical import canonical_json_bytes as jcs
from specroad.proposals.check import check_proposal_project
from specroad.proposals.history import assess_proposal
from specroad.proposals.context import specification_manifest
from support.proposal_dialog import DialogCase
from support.read_only import inventory, no_write_attempts


def test_public_dialog_requires_renewed_approval_and_publishes_the_exact_revised_target(tmp_path):
    case = DialogCase(tmp_path/'project')
    original_sources = dict(case.initial_model.source_files)
    assert case.created['write_state'] == 'committed'
    assert case.created['completion']['current_target_verified']
    for path, raw in original_sources.items():
        assert (case.root/path).read_bytes() == raw
    first_check = check_proposal_project(case.root, case.original.data['id'], services=case.services)
    assert first_check.exit_code == 0, first_check.as_dict()
    case.start(); case.approve()
    approved = case.original
    assert approved.data['proposal_status'] == 'approved'
    edit = case.prepare()
    outcome = case.publish(edit)
    assert outcome['write_state'] == 'committed' and not outcome['approval_granted']
    assert (case.root/approved.path).read_bytes() == edit.revision.after.source_bytes
    case.remember_edit()
    revised = case.original
    assert revised.data['revision'] == approved.data['revision'] + 1
    assert revised.data['content_revision'] == approved.data['content_revision'] + 1
    assert revised.data['proposal_status'] == 'draft'
    assert revised.data['reviews'] == approved.data['reviews']
    assert revised.data['control_history'] == approved.data['control_history']
    history = assess_proposal(revised, case.inputs(case.model, revised), case.model, services=case.services)
    assert history['effective_human_approvals'] == 0
    assert not history['current_approval']
    for path, raw in original_sources.items():
        assert (case.root/path).read_bytes() == raw
    with pytest.raises(ModelError) as refused:
        case.apply(dry_run=True)
    assert refused.value.reason == 'proposal_apply_requires_approved'
    second_check = check_proposal_project(case.root, revised.data['id'], services=case.services)
    assert second_check.exit_code == 0, second_check.as_dict()
    assert second_check.as_dict()['result']['binding'] == revised.binding.data
    assert first_check.as_dict()['result']['binding'] != revised.binding.data
    case.start(); case.approve()
    assert case.original.binding == revised.binding
    assert case.original.data['proposal_status'] == 'approved'
    assert len(case.original.data['reviews']) == 2 * len(approved.data['reviews'])
    case.before = case.model
    final = case.apply()
    assert final['project_writes_performed'] and not final['replayed']
    inputs, after = case.completion_inputs()
    applied = ProposalOriginal((case.root/revised.path).read_bytes(), path=revised.path)
    assessment = assess_proposal(applied, inputs, after, services=case.services)
    assert applied.data['proposal_status'] == 'applied'
    assert assessment['historical_valid'] and assessment['observed_status'] == 'applied'
    assert specification_manifest(after).sha256 == second_check.as_dict()['result']['target_model_root_sha256']
    goal = next(a for a in case.initial_model.artifacts if a['artifact_type'] == 'goal')
    expected = {**goal, 'statement': 'Revised dialogue goal', 'revision': goal['revision'] + 1,
        'updated_by': revised.data['change_plan']['actor'],
        'updated_at': '2026-01-01T00:00:00.000001Z'}
    path = next(d.path for d in case.initial_model.documents if json.loads(d.content)['id'] == goal['id'])
    assert (case.root/path).read_bytes() == jcs(expected)
    for source_path, raw in original_sources.items():
        if source_path != path:
            assert (case.root/source_path).read_bytes() == raw
    assert final['completion']['current_target_verified']


@pytest.mark.parametrize('action', ['add', 'update', 'remove', 'move'])
def test_all_four_changes_publish_through_native_writer_without_applying_the_inner_plan(tmp_path, action):
    case = DialogCase(tmp_path/'project')
    if action in ('remove', 'move'):
        case.publish(case.prepare('add')); case.remember_edit()
    before = case.original
    edit = case.prepare(action)
    outcome = case.publish(edit)
    assert outcome['write_state'] == 'committed'
    assert outcome['changed_change_ids'] == list(edit.changed_change_ids)
    assert len(edit.changed_change_ids) == 1
    assert (case.root/before.path).read_bytes() == jcs(outcome['proposal']) == edit.revision.after.source_bytes
    assert outcome['proposal']['revision'] == before.data['revision'] + 1
    for path, raw in case.initial_model.source_files.items():
        assert (case.root/path).read_bytes() == raw
    assert [op.op for op in case.requests[-1].plan.operations] == ['proposal_change']


def test_dry_run_and_canonical_noop_preserve_bytes_and_create_no_completion(tmp_path):
    case = DialogCase(tmp_path/'project')
    before = inventory(case.root)
    with no_write_attempts():
        preview = case.publish(case.prepare(dry_run=True), authority=None)
    assert preview['dry_run'] and preview['write_state'] == 'not_committed'
    assert preview['completion'] is None and inventory(case.root) == before
    noop = case.publish(case.prepare('move'))
    assert noop['no_change'] and noop['completion'] is None
    assert noop['write_state'] == 'not_committed' and noop['changed_change_ids'] == []
    assert inventory(case.root) == before
