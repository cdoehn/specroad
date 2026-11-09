"""Exact projection depth, immutable preimages and revision-boundary failures."""
from copy import deepcopy
from hashlib import sha256

import pytest

from specroad.model.audit_values import UtcTimestamp, Revision
from specroad.model.canonical import canonical_json_bytes
from specroad.model.errors import ModelError
from specroad.model.record_contracts import SPECIAL_STATES
from specroad.proposals import ProposalOriginal, ProposalRevision, ProposalError
from specroad.proposals.values import content_sha256
from support.read_only import no_write_attempts
from test_proposal_changes import sequence, plan
from test_proposal_revisions import revise, EDITOR, TIME


def original(**fields):
    source = sequence()[0].original
    value = source.data
    value.update(fields)
    value['content_sha256'] = content_sha256(value)
    return ProposalOriginal(canonical_json_bytes(value), path=source.path)


EXCLUDED = ('revision', 'created_at', 'created_by', 'updated_at', 'updated_by',
            'content_revision', 'content_sha256', 'maturity', 'proposal_status',
            'reviews', 'control_history')


@pytest.mark.parametrize('field', EXCLUDED)
@pytest.mark.parametrize('depth', ['extension', 'operation'])
def test_excluded_top_level_names_remain_content_at_every_nested_location(field, depth):
    before = original()
    value = before.data
    if depth == 'extension':
        value['extensions'] = {'test.projection': {'array': [{field: 'content'}]}}
    else:
        operations = deepcopy(value['change_plan']['operations'])
        operations[0]['artifact']['extensions'] = {'test.projection': {field: 'content'}}
        value['change_plan'] = plan(operations).data
    expected = sha256(canonical_json_bytes({key: v for key, v in value.items()
                                           if key not in EXCLUDED})).hexdigest()
    with no_write_attempts():
        prepared = revise(before, value)
    assert prepared.content_changed
    assert prepared.after.data['content_revision'] == 2
    assert prepared.after.data['content_sha256'] == expected != before.data['content_sha256']


@pytest.mark.parametrize('status', ['draft', 'in_review', 'approved'])
def test_content_change_resets_open_state_preserving_original_control_values(status):
    before = original(proposal_status=status, maturity=SPECIAL_STATES['proposal'][1][status])
    value = before.data
    value['title'] = 'Actual new content'
    with no_write_attempts():
        changed = revise(before, value)
    assert changed.after.data['proposal_status'] == changed.after.data['maturity'] == 'draft'
    assert changed.after.data['reviews'] == before.data['reviews']
    assert changed.after.data['control_history'] == before.data['control_history']
    assert before.data['proposal_status'] == status


@pytest.mark.parametrize('status', ['rejected', 'stale', 'applied'])
def test_terminal_records_cannot_gain_a_new_content_or_control_revision(status):
    before = original(proposal_status=status, maturity=SPECIAL_STATES['proposal'][1][status])
    for field, replacement in [('title', 'New terminal content'), ('reviews', [{'synthetic': 'review'}])]:
        value = before.data
        value[field] = replacement
        with no_write_attempts(), pytest.raises(ProposalError, match='proposal_terminal_revision_changed'):
            revise(before, value)
    assert revise(before, before.data).after is before


@pytest.mark.parametrize('field', ['schema_version', 'id', 'id_scheme', 'artifact_type',
    'revision', 'created_at', 'created_by', 'updated_at', 'updated_by', 'content_revision', 'content_sha256'])
def test_caller_cannot_remove_or_replace_owned_identity_audit_or_counters(field):
    before = original()
    for remove in (False, True):
        value = before.data
        if remove:
            del value[field]
        else:
            value[field] = True if field in ('revision', 'content_revision') else 'caller-forgery'
        with no_write_attempts(), pytest.raises(ProposalError) as failure:
            revise(before, value)
        assert failure.value.reason == 'proposal_managed_field_changed'
        assert failure.value.pointer == '/' + field


@pytest.mark.parametrize('field', ['reviews', 'control_history'])
def test_history_prefix_is_not_replaced_reordered_or_deleted(field):
    # Passive, explicitly synthetic history shapes do not assert human authority.
    before = original(**{field: [{'synthetic': 'first'}, {'synthetic': 'second'}]})
    for replacement in ([], list(reversed(before.data[field])), [{'synthetic': 'replacement'}], None):
        value = before.data
        value[field] = replacement
        with no_write_attempts(), pytest.raises(ProposalError, match='proposal_history_rewritten'):
            revise(before, value)


def test_content_and_review_updates_cannot_be_smuggled_into_the_same_preparation():
    before = original()
    value = before.data
    value['title'] = 'New content'
    value['reviews'].append({'synthetic': 'pretended approval'})
    with no_write_attempts(), pytest.raises(ProposalError, match='proposal_content_and_control_mixed'):
        revise(before, value)


@pytest.mark.parametrize('status', ['validated', 'checked'])
def test_a_partial_review_start_cannot_be_a_prepared_end_state(status):
    before = original()
    value = before.data
    value.update(proposal_status=status, maturity=SPECIAL_STATES['proposal'][1][status])
    with no_write_attempts(), pytest.raises(ProposalError, match='proposal_review_start_incomplete'):
        revise(before, value)


@pytest.mark.parametrize('planned,expected', [
    ('2026-10-31T23:59:59Z', '2026-11-01T00:00:00.000000123Z'),
    ('2026-11-01T00:00:00.000000124Z', '2026-11-01T00:00:00.000000124Z')])
def test_explicit_audit_time_uses_exact_existing_annex_k_successor(planned, expected):
    before = original(updated_at='2026-10-31T23:59:59.999999123Z')
    value = before.data
    value['rationale'] = 'New content'
    with no_write_attempts():
        changed = revise(before, value, planned_at=UtcTimestamp(planned))
    assert changed.after.data['updated_at'] == expected


def test_timestamp_overflow_fails_before_returning_a_changed_candidate():
    before = original(updated_at='9999-12-31T23:59:59.999999Z')
    value = before.data
    value['title'] = 'No room for another write'
    with no_write_attempts(), pytest.raises(ModelError, match='timestamp_overflow'):
        revise(before, value)
    assert revise(before, before.data).after is before


@pytest.mark.parametrize('where', ['input', 'output'])
def test_json_number_rounding_cannot_lose_content_or_incremented_revision(where):
    before = original(revision=9007199254740992) if where == 'output' else original()
    value = before.data
    value['title'] = 'Changed content'
    if where == 'input':
        value['extensions'] = {'test.integer': 9007199254740993}
    with no_write_attempts(), pytest.raises(ModelError, match='number_roundtrip_loss'):
        revise(before, value)


@pytest.mark.parametrize('field', ['reviews', 'control_history'])
def test_boolean_and_number_homonyms_cannot_rewrite_a_history_prefix(field):
    before = original(**{field: [{'synthetic': True}]})
    value = before.data
    value[field][0]['synthetic'] = 1
    with no_write_attempts(), pytest.raises(ProposalError, match='proposal_history_rewritten'):
        revise(before, value)


@pytest.mark.parametrize('fault', ['original', 'actor', 'time', 'expected', 'bool', 'candidate'])
def test_revision_preparation_requires_native_typed_binding_and_audit(fault):
    before = original()
    args = dict(original=before, candidate=before.data, expected_revision=Revision(1),
                actor=EDITOR, planned_at=TIME)
    if fault == 'original':
        args['original'] = before.data
    elif fault == 'actor':
        args['actor'] = EDITOR.as_fields()
    elif fault == 'time':
        args['planned_at'] = TIME.value
    elif fault in ('expected', 'bool'):
        args['expected_revision'] = 1 if fault == 'expected' else True
    else:
        args['candidate'] = []
    with no_write_attempts(), pytest.raises(ProposalError):
        ProposalRevision(**args)
