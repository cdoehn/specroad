"""Read-only binding of a writer's interrupted journal.next derivative.

This file never authorizes publication or advances a cursor. Known bytes stay
in the work inventory and are archived with the actual recovery result.
"""
import os

from ._committing_state import _initial_committing, _acknowledge
from .staging_values import PreparedJournal
from .committing_values import CommittingJournal
from .receipt_values import CommittedJournal
from .recovery_values import RecoveryError


def writer_next_in(directory, journal):
    try:
        os.stat('journal.next', dir_fd=directory, follow_symlinks=False)
    except FileNotFoundError:
        return None
    if type(journal) is PreparedJournal:
        expected = _initial_committing(journal)
    elif type(journal) is CommittingJournal:
        count = journal.data['published_count']
        if count >= len(journal.data['files']):
            raise RecoveryError('recovery_writer_successor_unproven', exit_code=6)
        expected = _acknowledge(journal, count)
    elif type(journal) is CommittedJournal and journal.data['files']:
        # Full-target recovery can finish a last move before its acknowledgement.
        # The retained writer derivative must be exactly that final prefix.
        expected = journal.predecessor
    else:
        raise RecoveryError('recovery_writer_successor_unproven', exit_code=6)
    from ._recovery_inputs import _prefix_image
    return _prefix_image(directory, 'journal.next', expected.source_bytes)


def writer_next(files, journal):
    with files.directory(tuple(journal.path.split('/')[:-1])) as directory:
        if directory is None:
            raise RecoveryError('recovery_work_missing', exit_code=6)
        return writer_next_in(directory, journal)
