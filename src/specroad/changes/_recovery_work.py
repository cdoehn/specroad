"""Known terminal work and hash inventories shared by recovery callers."""
import os

from ..security import paths as guards
from .recovery_values import RecoveryError, RolledBackJournal
from ._journal_io import _read
from ._staging_files import _image


def read_terminal_work(files, journal, prefix):
    """A closed subset of known terminal images; every retained byte is checked."""
    with files.directory(prefix) as directory:
        if directory is None:
            return None
        names = set(os.listdir(directory))
        if not names <= {'journal.json', 'journal.next', 'before', 'staging', 'rollback'}:
            raise RecoveryError('recovery_work_inventory_unproven', exit_code=6)
        result = {'': guards._identity(os.fstat(directory))}
        if 'journal.json' in names:
            if _read(directory, 'journal.json') != journal.source_bytes:
                raise RecoveryError('recovery_journal_changed', exit_code=6)
            result['journal.json'] = {'identity': _image(directory, 'journal.json',
                len(journal.source_bytes), journal.sha256), 'size': len(journal.source_bytes),
                'sha256': journal.sha256}
        if 'journal.next' in names:
            from ._writer_pending import writer_next_in
            result['journal.next'] = writer_next_in(directory, journal)
    images = {'before': {}, 'staging': {}, 'rollback': {}}
    for index, entry in enumerate(journal.data['files']):
        for folder, key, size, digest in (
                ('before', 'before_image_path', 'before_size', 'before_sha256'),
                ('staging', 'staging_path', 'after_size', 'after_sha256')):
            if entry[key] is not None:
                images[folder][entry[key].rsplit('/', 1)[-1]] = (entry[size], entry[digest])
        if type(journal) is RolledBackJournal:
            suffix, size, digest = (('bin', 'before_size', 'before_sha256') if entry['existed_before']
                                    else ('removed', 'after_size', 'after_sha256'))
            images['rollback'][str(index) + '.' + suffix] = (entry[size], entry[digest])
    for folder in sorted(names - {'journal.json', 'journal.next'}):
        with files.directory((*prefix, folder)) as directory:
            if directory is None or not set(os.listdir(directory)) <= set(images[folder]):
                raise RecoveryError('recovery_work_inventory_unproven', exit_code=6)
            result[folder] = guards._identity(os.fstat(directory))
            for name in sorted(os.listdir(directory)):
                size, digest = images[folder][name]
                result[folder + '/' + name] = {'identity': _image(directory, name, size, digest),
                                               'size': size, 'sha256': digest}
    return result


def work_file_inventory(work):
    """Project checked file tokens into the existing canonical audit fields."""
    return [{'path': path, 'size': token['size'], 'sha256': token['sha256']}
            for path, token in sorted(work.items()) if type(token) is dict]
