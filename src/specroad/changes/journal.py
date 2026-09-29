"""Native building-journal lifecycle: validate, create, read; never publish model files."""
from ..storage.project import ProjectSource
from .locking import HeldProjectLock
from .publication_check import recheck_publication
from .journal_values import BuildingJournal,JournalError,JOURNAL_VERSION
from ._journal_codec import journal_path,_hash
from ._journal_inventory import prepare_building_journal,verify_building_journal

def begin_building_journal(preflight, *, held_lock, transaction_id, authority, gates=()):
    """Revalidate under the native writer lock, then fsync a new building record.

    Only operational directories/journal are created. On failure retain all
    created files; a leftover namespace blocks normal writers until recovery.
    Never call a normative publisher, never mark prepared, never clean a blocker.
    """
    if type(held_lock) is not HeldProjectLock:
        raise JournalError('native_writer_lock_required',exit_code=2)
    journal=prepare_building_journal(preflight,transaction_id=transaction_id)
    # This gate requires no unresolved journal. Do not exempt an existing record
    # merely because it carries our transaction ID or says building/committed.
    recheck_publication(preflight,preflight.request,held_lock=held_lock,
                        transaction_id=transaction_id,authority=authority,gates=gates)
    from ._journal_io import persist_building_record
    persist_building_record(journal,held_lock)
    return journal


def read_building_journal(source, transaction_id, *, expected_sha256=None, preflight=None):
    """Read an existing record, not a recovery decision or a write capability."""
    if type(source) is not ProjectSource:
        raise JournalError('bound_project_source_required',exit_code=2)
    path=journal_path(transaction_id)
    if expected_sha256 is not None and not _hash(expected_sha256):
        raise JournalError('invalid_expected_journal_hash',exit_code=2)
    from ._journal_io import read_record
    source.check_current()
    raw=read_record(source,path)
    journal=BuildingJournal(raw); v=journal.data
    if (journal.path != path or v['project_id'] != source.configuration.project_id
            or v['root_identity'] != list(source.boundary._root_identity)):
        raise JournalError('journal_project_binding_mismatch',exit_code=6,path=path)
    if expected_sha256 is not None and journal.sha256 != expected_sha256:
        raise JournalError('journal_bytes_changed',exit_code=6,path=path)
    if preflight is not None:
        verify_building_journal(journal,preflight)
    source.check_current()
    return journal
