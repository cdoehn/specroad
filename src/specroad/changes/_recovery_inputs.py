"""Shared read-only journal, work-inventory and complete-base observations.

No lock acquisition, authorization callback, new planning or mutation lives in
this module. Diagnostic results are never reusable write capabilities.
"""
from hashlib import sha256
import os
from ..model.canonical import canonical_json_bytes
from ..security import paths as guards
from ..storage.json_syntax import parse_json_object
from .journal_values import BuildingJournal
from .staging_values import PreparedJournal
from .committing_values import CommittingJournal
from .receipt_values import CommittedJournal
from .publication_values import PublicationPreflight
from ._journal_codec import journal_path
from ._journal_io import _read
from ._journal_inventory import prepare_building_journal
from ._publication_observation import _root, observe_publication_files
from ._staging_files import _image
from .recovery_values import (RecoveryError, DiscardedJournal, RollingBackJournal,
                              RolledBackJournal)

_KNOWN = {'building': BuildingJournal, 'prepared': PreparedJournal,
          'committing': CommittingJournal, 'committed': CommittedJournal,
          'rolling_back': RollingBackJournal}


def _read_journal(files, transaction_id):
    path = journal_path(transaction_id)
    with files.directory(tuple(path.split('/')[:-1])) as directory:
        if directory is None:
            raise RecoveryError('recovery_journal_missing', path=path, exit_code=5)
        ident = guards._identity(os.fstat(directory))
        raw = _read(directory, 'journal.json')
    return raw, ident


def _parse(raw, transaction_id, files, expected_project_id=None):
    value = parse_json_object(raw)
    state = value.get('state')
    if state == 'rolled_back':
        cls = DiscardedJournal if 'discard' in value else RolledBackJournal
    else:
        cls = _KNOWN.get(state) if type(state) is str else None
    if cls is None:
        raise RecoveryError('recovery_journal_state_unsupported')
    journal = cls(raw)
    data = journal.data
    if (data['transaction_id'] != transaction_id
            or data['root_identity'] != list(files.boundary._root_identity)
            or (expected_project_id is not None and data['project_id'] != expected_project_id)):
        raise RecoveryError('recovery_journal_binding_mismatch', exit_code=6)
    return journal


def _unchanged_base(preflight, journal, files):
    """Independent inventory plus every live source byte, never journal hashes alone."""
    from .discard_preflight import DiscardPreflight
    if type(preflight) is DiscardPreflight:
        return preflight._check(files, journal)
    if type(preflight) is not PublicationPreflight:
        raise RecoveryError('recovery_base_preflight_required', exit_code=2)
    data = journal.data
    if data['state'] not in ('building', 'prepared'):
        raise RecoveryError('discard_state_forbidden', exit_code=6)
    expected = prepare_building_journal(preflight, transaction_id=data['transaction_id']).data
    expected['state'] = data['state']
    if 'discard_basis' not in data:
        expected.pop('discard_basis')
    if data != expected:
        raise RecoveryError('recovery_inventory_unproven', exit_code=6)
    model = preflight._model.snapshot()
    source = _root(model)
    if source.boundary._root_identity != files.boundary._root_identity:
        raise RecoveryError('recovery_base_root_mismatch', exit_code=6)
    return observe_publication_files(source, model, preflight.request,
                                    preflight._package_files, check_rights=lambda fd, path: None)


def _work(files, journal, *, raw=None, prefix=None, preflight=None):
    """Closed work inventory, including proven prefixes of interrupted writes.

    Prepared images remain complete. Building may have missing directories,
    subsets and short before/staging files, but only bytes of independently
    expected images. Even partial evidence is archived, never silently removed.
    """
    data = journal.data
    building = data['state'] == 'building'
    prefix = tuple(journal.path.split('/')[:-1]) if prefix is None else prefix
    with files.directory(prefix) as directory:
        if directory is None:
            raise RecoveryError('recovery_work_missing', exit_code=6)
        names = set(os.listdir(directory))
        permitted = {'journal.json', 'before', 'staging'}
        if building: permitted.add('journal.prepared')
        if ('journal.json' not in names or not names <= permitted
                or (not building and names != permitted)):
            raise RecoveryError('recovery_work_inventory_unproven', exit_code=6)
        actual = _read(directory, 'journal.json')
        if actual != (journal.source_bytes if raw is None else raw):
            raise RecoveryError('recovery_journal_changed', exit_code=6)
        result = {'': guards._identity(os.fstat(directory)), 'journal.json': sha256(actual).hexdigest()}
        if 'journal.prepared' in names:
            expected = journal.data; expected['state'] = 'prepared'
            content = canonical_json_bytes(expected)
            result['journal.prepared'] = _prefix_image(directory, 'journal.prepared', content)
    target = {} if not building or preflight is None else {d.path: d.content for d in preflight.request.documents}
    original = {} if not building or preflight is None else preflight._model.source_files
    for folder, path_key, size_key, hash_key in (
            ('staging', 'staging_path', 'after_size', 'after_sha256'),
            ('before', 'before_image_path', 'before_size', 'before_sha256')):
        if folder not in names:
            continue
        entries = {e[path_key].rsplit('/', 1)[-1]: e for e in data['files'] if e[path_key] is not None}
        with files.directory((*prefix, folder)) as fd:
            if fd is None:
                raise RecoveryError('recovery_work_inventory_unproven', exit_code=6)
            found = set(os.listdir(fd))
            if not found <= set(entries) or (not building and found != set(entries)):
                raise RecoveryError('recovery_work_inventory_unproven', exit_code=6)
            result[folder] = guards._identity(os.fstat(fd))
            for name in sorted(found):
                entry = entries[name]
                if building:
                    content = (target if folder == 'staging' else original).get(entry['path'])
                    if content is None:
                        raise RecoveryError('recovery_image_source_unproven', exit_code=6)
                    result[folder + '/' + name] = _prefix_image(fd, name, content)
                else:
                    inode = _image(fd, name, entry[size_key], entry[hash_key])
                    result[folder + '/' + name] = {'identity': inode, 'size': entry[size_key],
                                                'sha256': entry[hash_key]}
    return result


def _prefix_image(directory, name, expected):
    """Allow only a bounded prefix of an independently known interrupted write."""
    info = os.stat(name, dir_fd=directory, follow_symlinks=False)
    guards._regular(info)
    if info.st_size > len(expected):
        raise RecoveryError('recovery_partial_image_oversized', exit_code=6)
    digest = sha256(expected[:info.st_size]).hexdigest()
    inode = _image(directory, name, info.st_size, digest,
                   identity=guards._identity(info))
    return {'identity': inode, 'size': info.st_size, 'sha256': digest}
