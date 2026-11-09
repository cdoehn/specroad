"""Native revision preparation and fresh verification of synthetic review history."""
from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
import json

import pytest

from specroad.model.audit_values import Actor, Revision, UtcTimestamp
from specroad.model.canonical import canonical_json_bytes
from specroad.proposals import ProposalOriginal, ProposalRevision, ProposalError
from specroad.proposals.values import content_sha256
from support.read_only import no_write_attempts
from test_proposal_changes import sequence


EDITOR = Actor('human', 'synthetic-revision-author')
TIME = UtcTimestamp('2026-11-09T00:00:00Z')


def revise(original, value, *, actor=EDITOR, planned_at=TIME, expected_revision=None):
    return ProposalRevision(original, value, expected_revision=(
        Revision(original.data['revision']) if expected_revision is None else expected_revision),
        actor=actor, planned_at=planned_at)


def test_content_revision_is_independent_of_physical_revision_and_owns_all_values():
    original = sequence()[0].original
    value = original.data
    value['rationale'] = 'An actual new explanation'
    with no_write_attempts():
        prepared = revise(original, value)
    saved = prepared.after.data
    assert (saved['revision'], saved['content_revision']) == (2, 2)
    assert saved['content_sha256'] != original.binding.content_sha256
    assert saved['content_sha256'] == content_sha256(saved)
    assert saved['updated_at'] == TIME.value and saved['updated_by'] == EDITOR.as_fields()
    assert saved['created_by'] == original.data['created_by']
    assert saved['created_at'] == original.data['created_at']
    value['extensions']['test:after'] = saved['rationale'] = 'Caller mutation'
    assert prepared.after.data['rationale'] == 'An actual new explanation'
    assert prepared.before is original and original.data['revision'] == 1
    assert prepared.changed and prepared.content_changed and not prepared.write_authorized


@pytest.mark.parametrize('field', ['revision', 'created_at', 'created_by', 'updated_at',
    'updated_by', 'content_revision', 'content_sha256', 'maturity', 'proposal_status',
    'reviews', 'control_history'])
def test_hash_excludes_exact_management_fields_but_not_nested_homonyms(field):
    value = sequence()[0].data
    changed = deepcopy(value)
    changed[field] = {'synthetic': 'changed excluded value'}
    assert content_sha256(changed) == content_sha256(value)
    changed['extensions'] = {'test:nested': {field: ['included', 1]}}
    assert content_sha256(changed) != content_sha256(value)


@pytest.mark.parametrize('field', ['title', 'rationale', 'base', 'change_plan', 'changes',
                                  'relations', 'extensions', 'provider', 'unknown_reasons'])
def test_hash_covers_complete_business_values_including_unknown_future_content(field):
    value = sequence()[0].data
    changed = deepcopy(value)
    changed[field] = {'synthetic': field}
    # Independent RFC-8785 projection oracle, not an expected value from the producer.
    excluded = {'revision', 'created_at', 'created_by', 'updated_at', 'updated_by',
                'content_revision', 'content_sha256', 'maturity', 'proposal_status',
                'reviews', 'control_history'}
    expected = sha256(canonical_json_bytes({k: v for k, v in changed.items() if k not in excluded})).hexdigest()
    assert content_sha256(changed) == expected != content_sha256(value)


def test_canonical_noop_retains_noncanonical_original_bytes_and_audit():
    original = sequence()[0].original
    raw = json.dumps(original.data, indent=3, ensure_ascii=False).encode() + b'\n'
    original = ProposalOriginal(raw, path=original.path)
    with no_write_attempts():
        prepared = revise(original, dict(reversed(list(original.data.items()))))
    assert prepared.after is original and prepared.after.source_bytes == raw
    assert not prepared.changed and not prepared.content_changed and not prepared.write_authorized


def test_actual_control_revisions_keep_binding_and_fresh_human_history_qualification(tmp_path):
    from specroad.proposals import ProposalContext, assess_proposal
    from specroad.model.audit import actor
    from support.languages import small_restore_registry
    from test_proposal_history import history, verifier
    inputs, model = history(tmp_path, language_registry=small_restore_registry())
    prepared = [inputs.originals[0]]
    for observed in inputs.originals[1:]:
        before = prepared[-1]
        value = before.data
        for field in ('maturity', 'proposal_status', 'reviews', 'control_history'):
            if field in observed.data:
                value[field] = observed.data[field]
            else:
                value.pop(field, None)
        with no_write_attempts():
            revision = revise(before, value, actor=actor(observed.data['updated_by']),
                              planned_at=UtcTimestamp(observed.data['updated_at']))
        assert revision.after.source_bytes == observed.source_bytes
        assert revision.changed and not revision.content_changed
        assert revision.after.binding == before.binding
        prepared.append(revision.after)
    calls = []
    rebuilt = replace(inputs, originals=tuple(prepared), verifier=verifier(calls=calls))
    with no_write_attempts():
        report = assess_proposal(prepared[-1], rebuilt, model)
    assert calls and report['current_approval'] and report['effective_human_approvals'] == 1
    assert not report['write_authorized']
    value = prepared[-1].data
    value['rationale'] = 'New content after an actual bound review'
    with no_write_attempts():
        edited = revise(prepared[-1], value).after
    assert edited.data['revision'] == prepared[-1].data['revision'] + 1
    assert edited.data['content_revision'] == prepared[-1].data['content_revision'] + 1
    assert edited.data['reviews'] == prepared[-1].data['reviews']
    assert edited.data['control_history'] == prepared[-1].data['control_history']
    assert edited.data['proposal_status'] == edited.data['maturity'] == 'draft'
    from specroad.changes._target_materialization import materialize_target
    from specroad.validation import ModelDocument
    model = materialize_target(model, (ModelDocument(edited.path, edited.source_bytes),))
    rebuilt = replace(rebuilt, originals=(*rebuilt.originals, edited),
        contexts=(*rebuilt.contexts, ProposalContext(edited, inputs.contexts[-1].basis)))
    with no_write_attempts():
        report = assess_proposal(edited, rebuilt, model)
    assert report['historical_valid'] and not report['current_approval']
    assert report['effective_human_approvals'] == 0


def test_expected_revision_means_physical_revision_even_when_content_revision_is_one(tmp_path):
    from support.languages import small_restore_registry
    from test_proposal_history import history
    inputs, _ = history(tmp_path, language_registry=small_restore_registry())
    before = inputs.originals[-1]
    assert before.data['revision'] > before.data['content_revision'] == 1
    value = before.data
    value['rationale'] = 'New content'
    with no_write_attempts(), pytest.raises(ProposalError) as failure:
        revise(before, value, expected_revision=Revision(1))
    assert failure.value.reason == 'proposal_revision_conflict' and failure.value.exit_code == 6


def test_ordered_change_edit_feeds_one_revision_and_preserves_rebound_full_plan():
    from specroad.proposals import Proposal
    from test_proposal_changes import create, plan
    proposal, sequence_value = sequence()
    moved = sequence_value.move(sequence_value.change_ids[0], 1,
                                change_plan=plan([create('B'), create('A')]))
    value = proposal.data
    value.update(changes=moved.changes, change_plan=moved.change_plan.data)
    with no_write_attempts():
        prepared = revise(proposal.original, value)
        read = Proposal(prepared.after.source_bytes, path=proposal.original.path)
    assert prepared.changed and prepared.content_changed
    assert read.data['revision'] == read.data['content_revision'] == 2
    assert read.content_data['change_plan'] == moved.change_plan.data
    assert [row['change_id'] for row in read.content_data['changes']] == list(moved.change_ids)
    assert read.binding.change_plan_sha256 == moved.change_plan.sha256
    assert read.binding.base_model_root_sha256 == proposal.binding.base_model_root_sha256
    assert not read.write_authorized
