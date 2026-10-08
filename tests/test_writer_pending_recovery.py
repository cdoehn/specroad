"""Known writer successors survive recovery; conflicting evidence never does."""
import os
import pytest

from specroad.changes import (RecoveryError, RecoveryAuthority, LockRecord,
    prepare_discard_recovery, complete_published_transaction, transaction_recovery_lock)
from support.writer_boundaries import child, journal_at, CRASH_EXIT
from support.publication import TRANSACTION
from support.recovery import RECOVER, tree
from support.targets import ACTOR


def interrupted(root, state):
    _, trace = child(root.parent / 'control', 'writer')
    events = [e for e in trace['events'] if e['phase'] == 'publishing'
              and e['operation'] == 'fsync' and e['paths'][0].endswith('/journal.next')]
    assert len(events) == 2  # Initial committing record and the one-file acknowledgement.
    event = events[0 if state == 'prepared' else 1]
    bound, stopped = child(root, 'writer', 'publishing', event['ordinal'], exit_code=CRASH_EXIT)
    assert stopped['cut'] == event
    journal = journal_at(root)
    assert journal.data['state'] == state
    return bound, journal, (root / journal.path).with_name('journal.next')


@pytest.mark.parametrize('state', ['prepared', 'committing'])
def test_exact_pending_writer_record_is_preserved_in_recovery_archive(tmp_path, state):
    root = tmp_path / 'project'
    bound, _, pending = interrupted(root, state)
    raw = pending.read_bytes()
    result, = child(root, 'recover')
    assert result['outcome'] == ('base' if state == 'prepared' else 'target')
    assert result['files'] == bound['before' if state == 'prepared' else 'after']
    retained = list((root / '.specroad/recovery').rglob('journal.next'))
    assert len(retained) == 1 and retained[0].read_bytes() == raw


@pytest.mark.parametrize('state', ['prepared', 'committing'])
@pytest.mark.parametrize('change', ['foreign', 'oversized', 'other_cursor', 'symlink', 'hardlink'])
def test_unbound_pending_writer_record_blocks_without_recovery_mutation(tmp_path, state, change):
    import json
    from specroad.model.canonical import canonical_json_bytes
    root = tmp_path / 'project'
    _, journal, pending = interrupted(root, state)
    lock = LockRecord((root / '.specroad/locks/project.json').read_bytes())
    # Establish the existing explicit native recovery lease first. The operation
    # below must refuse unbound evidence without creating its own recovery output.
    with transaction_recovery_lock(root, TRANSACTION, project_id='sample',
            request_id=journal.data['request_id'],
            command='recover discard' if state == 'prepared' else 'recover run',
            expected_lock_sha256=lock.sha256, expected_journal_sha256=journal.sha256,
            authority=RECOVER, actor=ACTOR, reason='Writer derivative guard test', force=True) as held:
        raw = pending.read_bytes()
        if change == 'foreign': pending.write_bytes(b'foreign evidence')
        if change == 'oversized': pending.write_bytes(raw + b' ')
        if change == 'other_cursor':
            value = json.loads(raw)
            count = 1 - value['published_count']
            value['published_count'] = count
            value['files'][0]['published'] = bool(count)
            pending.write_bytes(canonical_json_bytes(value))
        if change in ('symlink', 'hardlink'):
            kept = root / 'notes/retained-journal.bin'
            pending.rename(kept)
            if change == 'symlink': pending.symlink_to(kept)
            else: os.link(kept, pending)
        before = tree(root)
        with pytest.raises(RecoveryError):
            if state == 'prepared':
                prepare_discard_recovery(root, TRANSACTION, expected_project_id='sample',
                    expected_journal_sha256=journal.sha256)
            else:
                complete_published_transaction(TRANSACTION, held_lock=held,
                    authority=RECOVER, expected_journal_sha256=journal.sha256)
        assert tree(root) == before


def test_pending_writer_record_is_rechecked_after_recovery_authorization(tmp_path):
    root = tmp_path / 'project'
    _, journal, pending = interrupted(root, 'committing')
    lock = LockRecord((root / '.specroad/locks/project.json').read_bytes())
    with transaction_recovery_lock(root, TRANSACTION, project_id='sample',
            request_id=journal.data['request_id'], command='recover run',
            expected_lock_sha256=lock.sha256, expected_journal_sha256=journal.sha256,
            authority=RECOVER, actor=ACTOR, reason='Writer derivative authority guard', force=True) as held:
        before = tree(root)
        raw = pending.read_bytes()
        def interfere(request):
            pending.write_bytes(raw[:17])  # Still a valid prefix, but a different observation.
            return True
        with pytest.raises(RecoveryError) as error:
            complete_published_transaction(TRANSACTION, held_lock=held,
                authority=RecoveryAuthority('interfering-test-host', '1', interfere),
                expected_journal_sha256=journal.sha256)
        assert error.value.reason == 'recovery_writer_successor_changed'
        before[pending.relative_to(root).as_posix()] = raw[:17]
        assert tree(root) == before
