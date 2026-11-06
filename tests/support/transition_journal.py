"""Shared ownership oracle for real migration and merge journals."""
from dataclasses import FrozenInstanceError
import pytest
from specroad.changes.schema_transition_values import TransitionJournal, SchemaTransitionError
from specroad.model.canonical import canonical_json_bytes as jcs


def assert_owned_plan(journal, expected_bytes):
    original = journal.source_bytes
    borrowed_plan = journal.plan
    exported_plan = borrowed_plan.data
    exported_journal = journal.data
    exported_plan['operations'].clear()
    exported_journal['plan_bytes_base64'] = 'e30='
    with pytest.raises(FrozenInstanceError):
        borrowed_plan.source_bytes = b'{}'
    assert journal.source_bytes == original
    assert borrowed_plan.source_bytes == journal.plan.source_bytes == expected_bytes
    assert journal.plan.data['operations']
    assert not journal.plan.write_authorized and not journal.plan.execution_ready
    successor = journal.successor(journal.data['state'], journal.data['published_count'])
    assert successor.source_bytes == original
    assert successor.plan.source_bytes == expected_bytes
    # A newly captured journal must still validate its own plan binding.
    changed = journal.data
    changed['plan_sha256'] = '0' * 64
    with pytest.raises(SchemaTransitionError, match='transition_plan_binding'):
        TransitionJournal(jcs(changed))
    assert journal.source_bytes == original and journal.plan.source_bytes == expected_bytes
