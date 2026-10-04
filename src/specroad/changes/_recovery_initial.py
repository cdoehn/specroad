"""Initial rollback publication with its established staging error contract."""
from ._recovery_files import write_recovery_file


def write_initial_successor(directory, name, raw, *, before_publish):
    return write_recovery_file(directory, name, raw, before_publish=before_publish,
        conflict_reason='recovery_journal_successor_conflict',
        stage_reason='recovery_initial_stage')
