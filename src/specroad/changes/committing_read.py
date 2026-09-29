"""Read-only observations of acknowledged publication; never resume or repair.

A move ahead of its acknowledgement is deliberately refused, not guessed into
an updated journal. Full recovery decides such states in a later workflow.
"""
import os
from ..model.errors import ModelError
from ..security import SafetyViolation
from ..security import paths as guards
from ..storage.project import ProjectSource
from ..result_contract import ResultContractError
from ._lock_files import LockFiles
from ._journal_codec import journal_path, _hash
from ._journal_io import _read
from ._staging_files import _image, _names
from .execution_values import ChangeExecutionError
from .committing_values import CommittingJournal, CommitPublicationError


def read_committing_journal(source, transaction_id, *, expected_sha256=None, preflight=None):
    """Verify observed prefix, images, and target bytes without lock or mutation.

    Returned journal data does not assert durability, receipt existence, a full
    model root, or an atomic snapshot. Active committing still blocks normal IO.
    """
    if type(source) is not ProjectSource:
        raise CommitPublicationError('bound_project_source_required', exit_code=2)
    if expected_sha256 is not None and not _hash(expected_sha256):
        raise CommitPublicationError('invalid_expected_journal_hash', exit_code=2)
    path = journal_path(transaction_id)
    try:
        source.check_current()
        with LockFiles(source.boundary.root) as files:
            if files.boundary._root_identity != source.boundary._root_identity:
                raise CommitPublicationError('committing_project_changed', exit_code=6)
            prefix = tuple(path.split('/')[:-1])
            identities = {}
            with files.directory(prefix) as directory:
                if directory is None:
                    raise CommitPublicationError('committing_journal_missing', exit_code=5)
                identity = guards._identity(os.stat('journal.json', dir_fd=directory,
                                                     follow_symlinks=False))
                raw = _read(directory, 'journal.json', expected_identity=identity)
                journal = CommittingJournal(raw)
                data = journal.data
                if (journal.path != path or data['project_id'] != source.configuration.project_id
                        or data['root_identity'] != list(source.boundary._root_identity)):
                    raise CommitPublicationError('committing_project_binding_mismatch', exit_code=6)
                if expected_sha256 is not None and journal.sha256 != expected_sha256:
                    raise CommitPublicationError('committing_journal_bytes_changed', exit_code=6)
                if preflight is not None:
                    from .committing import verify_committing_journal
                    verify_committing_journal(journal, preflight)
                # Two complete observations. Holding descriptors detects directory
                # replacement, hashing detects same-length/mtime-reset modifications.
                for repetition in range(2):
                    _names(directory, ['journal.json', 'staging', 'before'])
                    _observed_files(files, journal, identities, capture=repetition == 0)
                    if _read(directory, 'journal.json', expected_identity=identity) != raw:
                        raise CommitPublicationError('committing_journal_bytes_changed', exit_code=6)
                    source.check_current()
        source.check_current()
        return journal
    except (OSError, SafetyViolation, ModelError, ChangeExecutionError, ResultContractError) as error:
        if isinstance(error, CommitPublicationError):
            raise
        raise CommitPublicationError(getattr(error, 'reason', 'committing_read_failed'),
            path=getattr(error, 'path', path),
            exit_code=getattr(error, 'exit_code', 7 if isinstance(error, SafetyViolation) else 5)) from error


def _observed_files(files, journal, identities, *, capture):
    data = journal.data
    prefix = tuple(journal.path.split('/')[:-1])
    for folder, field, size, digest in (
            ('staging', 'staging_path', 'after_size', 'after_sha256'),
            ('before', 'before_image_path', 'before_size', 'before_sha256')):
        entries = [e for e in data['files'] if e[field] is not None
                   and (folder != 'staging' or not e['published'])]
        with files.directory((*prefix, folder)) as directory:
            if directory is None:
                raise CommitPublicationError('publication_images_missing', exit_code=5)
            directory_key = '/'.join((*prefix, folder))
            observed = guards._identity(os.fstat(directory))
            if not capture and identities[directory_key] != observed:
                raise CommitPublicationError('publication_directory_replaced', exit_code=6)
            identities[directory_key] = observed
            _names(directory, [e[field].rsplit('/', 1)[-1] for e in entries])
            for entry in entries:
                p = entry[field]
                identities[p] = _image(directory, p.rsplit('/', 1)[-1], entry[size], entry[digest],
                    identity=None if capture else identities[p])
    for entry in data['files']:
        parts = entry['path'].split('/')
        after = entry['published']
        expected = after or entry['existed_before']
        with files.directory(tuple(parts[:-1])) as directory:
            if not expected:
                if directory is not None:
                    try:
                        os.stat(parts[-1], dir_fd=directory, follow_symlinks=False)
                    except FileNotFoundError:
                        continue
                    raise CommitPublicationError('unacknowledged_target_exists', path=entry['path'], exit_code=6)
                continue
            if directory is None:
                raise CommitPublicationError('publication_target_missing', path=entry['path'], exit_code=5)
            side = 'after' if after else 'before'
            identities[entry['path']] = _image(directory, parts[-1], entry[side+'_size'],
                entry[side+'_sha256'], identity=None if capture else identities[entry['path']])
