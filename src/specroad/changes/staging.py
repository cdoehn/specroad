"""Durably stage checked before/after bytes, then replace only the journal.

Native local Linux and cooperating writers are the supported boundary. Failure
never cleans up operational bytes, retries a transaction or publishes a target.
No on-disk prepared flag is trusted without rechecking its images and bindings.
"""
from hashlib import sha256
import os
from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..security import SafetyViolation
from ..security import paths as guards
from ..storage.project import ProjectSource
from ..storage.byte_binding import fingerprint_reader
from ._journal_codec import _hash, journal_path
from ._journal_inventory import prepare_building_journal, verify_building_journal
from ._journal_io import _read
from ._lock_files import LockFiles
from .journal_values import BuildingJournal, JournalError
from .lock_values import ProjectLockError
from .locking import HeldProjectLock
from .publication_values import PublicationPreflight, PublicationAuthority
from .publication_check import _observe, _same_request
from ._publication_observation import _root
from .execution_values import PublicationRequest, ChangeExecutionError
from .target import assess_change_target
from .staging_values import PreparedJournal, StagingError

_BLOCK = 65536
_PENDING = 'journal.prepared'


def verify_prepared_journal(journal, preflight):
    """Independently bind all inventory fields; no disk reads or success inference."""
    if type(journal) is not PreparedJournal:
        raise StagingError('prepared_journal_required', exit_code=2)
    expected = prepare_building_journal(preflight,
        transaction_id=journal.data['transaction_id']).data
    expected['state'] = 'prepared'
    if canonical_json_bytes(expected) != canonical_json_bytes(journal.data):
        raise StagingError('prepared_plan_inventory_mismatch', exit_code=6, path=journal.path)


def _payloads(journal, preflight):
    verify_building_journal(journal, preflight)
    before = preflight._model.source_files
    after = {d.path: d.content for d in preflight.request.documents}
    values = []
    for entry in journal.data['files']:
        if entry['existed_before']:
            values.append((entry['before_image_path'], before[entry['path']],
                           entry['before_size'], entry['before_sha256']))
        values.append((entry['staging_path'], after[entry['path']],
                       entry['after_size'], entry['after_sha256']))
    for path, raw, size, digest in values:
        if type(raw) is not bytes or len(raw) != size or sha256(raw).hexdigest() != digest:
            raise StagingError('staging_input_binding_mismatch', path=path, exit_code=6)
    return tuple(values)


def _own_lock(held, source, journal):
    # Only this narrow staging path admits exactly the independently verified
    # own journal. Ordinary publication and writer-acquisition gates stay closed.
    held.check()
    v = held.record.data
    j = journal.data
    if (v['kind'] != 'writer' or v['command'] != 'change apply'
            or v['transaction_id'] != j['transaction_id'] or v['request_id'] != j['request_id']
            or v['project_id'] != j['project_id']
            or source.configuration.project_id != j['project_id']
            or source.boundary.root != held._files.boundary.root
            or list(source.boundary._root_identity) != j['root_identity']
            or source.boundary._root_identity != held._files.boundary._root_identity):
        raise StagingError('staging_lock_binding_mismatch', exit_code=6)
    expected = ('.specroad/transactions/' + j['transaction_id'],)
    if held._files.journal_entries() != expected:
        raise StagingError('staging_recovery_set_changed', exit_code=5)
    source.check_current()


def _recheck(preflight, journal, held, authority, gates):
    """Rerun the existing target/permission contracts within the own-journal gate."""
    source = _root(preflight._model)
    _own_lock(held, source, journal)
    request = preflight.request
    def live():
        _own_lock(held, source, journal)
        observed = _observe(source, preflight._model, request, preflight._package_files)
        if canonical_json_bytes(observed) != preflight._footprint:
            raise StagingError('staging_source_changed', exit_code=6)
    live()
    checked = assess_change_target(request.plan, preflight._model.snapshot(),
        policy=preflight._policy, gates=tuple(gates), strict=preflight._strict)
    if not checked.target_validated:
        raise StagingError('staging_target_not_validated')
    _same_request(PublicationRequest._create(checked, preflight._model), request)
    outgoing = request.detached()
    try:
        allowed = authority.check(outgoing)
    except Exception as error:
        raise StagingError('staging_authority_failed', exit_code=7) from error
    _same_request(outgoing, request)
    if type(allowed) is not bool or not allowed:
        raise StagingError('staging_authorization_denied', exit_code=7)
    live()
    return source


def _image(parent, name, size, digest, *, identity=None):
    """Hash the complete current regular file through a freshly verified descriptor."""
    before = os.stat(name, dir_fd=parent, follow_symlinks=False)
    guards._regular(before)
    if before.st_nlink != 1:
        raise StagingError('staging_hardlink_refused', path=name, exit_code=7)
    if before.st_size != size or (identity is not None and guards._identity(before) != identity):
        raise StagingError('staging_image_changed', path=name, exit_code=6)
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, 'O_NONBLOCK', 0)
                 | getattr(os, 'O_CLOEXEC', 0), dir_fd=parent)
    try:
        first = os.fstat(fd)
        guards._regular(first)
        if guards._signature(first) != guards._signature(before):
            raise StagingError('staging_image_changed', path=name, exit_code=6)
        observed = fingerprint_reader(lambda n: os.read(fd, n), size)
        after = os.stat(name, dir_fd=parent, follow_symlinks=False)
        if (observed.size != size or observed.sha256 != digest
                or guards._signature(first) != guards._signature(after)
                or guards._signature(first) != guards._signature(os.fstat(fd))):
            raise StagingError('staging_image_changed', path=name, exit_code=6)
        return guards._identity(first)
    finally:
        os.close(fd)


def _write_new(parent, name, raw):
    """Exclusive private file, complete bounded writes, fsync, stable readback."""
    fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
                 | getattr(os, 'O_CLOEXEC', 0), 0o600, dir_fd=parent)
    try:
        identity = guards._identity(os.fstat(fd))
        view = memoryview(raw)
        offset = 0
        while offset < len(view):
            chunk = view[offset:offset + _BLOCK]
            count = os.write(fd, chunk)
            if type(count) is not int or not 0 < count <= len(chunk):
                raise StagingError('staging_short_write', path=name, exit_code=5)
            offset += count
        os.fsync(fd)
        if os.fstat(fd).st_size != len(raw):
            raise StagingError('staging_incomplete_write', path=name, exit_code=5)
    finally:
        os.close(fd)
    os.fsync(parent)
    _image(parent, name, len(raw), sha256(raw).hexdigest(), identity=identity)
    return identity


def _translate(error, *, possible, prepared):
    if isinstance(error, StagingError):
        error.mutation_possible |= possible
        error.prepared_possible |= prepared
        return error
    if isinstance(error, (JournalError, ChangeExecutionError, ModelError)):
        return StagingError(error.reason, path=getattr(error, 'path', None),
            exit_code=getattr(error, 'exit_code', 3), mutation_possible=possible,
            prepared_possible=prepared)
    if isinstance(error, SafetyViolation):
        return StagingError('unsafe_staging_path', exit_code=7,
                            mutation_possible=possible, prepared_possible=prepared)
    return StagingError('staging_io_failure', exit_code=5,
                        mutation_possible=possible, prepared_possible=prepared)


def _names(directory, wanted):
    if set(os.listdir(directory)) != set(wanted):
        raise StagingError('staging_namespace_changed', exit_code=6)


def _images_on_disk(files, journal, identities=None):
    """Complete exact image namespace, including a deliberately empty before set."""
    entries = journal.data['files']
    prefix = tuple(journal.path.split('/')[:-1])
    for folder, path_key, size_key, hash_key in (
            ('staging', 'staging_path', 'after_size', 'after_sha256'),
            ('before', 'before_image_path', 'before_size', 'before_sha256')):
        values = [e for e in entries if e[path_key] is not None]
        with files.directory((*prefix, folder)) as fd:
            if fd is None:
                raise StagingError('staging_directory_missing', exit_code=5)
            _names(fd, [e[path_key].rsplit('/', 1)[-1] for e in values])
            for entry in values:
                path = entry[path_key]
                _image(fd, path.rsplit('/', 1)[-1], entry[size_key], entry[hash_key],
                       identity=None if identities is None else identities[path])


def stage_building_journal(preflight, journal, *, held_lock, authority, gates=()):
    """building -> prepared without a single normative target write.

    Requires the still-held writer guard and its existing independently bound
    building journal. Existing/partial staging is never reused or auto-cleaned.
    A failure after journal replacement may leave a prepared record; it is not
    an acknowledged commit and remains blocked for explicit later recovery.
    """
    if (type(preflight) is not PublicationPreflight or type(journal) is not BuildingJournal
            or type(held_lock) is not HeldProjectLock or type(authority) is not PublicationAuthority
            or type(gates) not in (tuple, list)):
        raise StagingError('explicit_staging_inputs_required', exit_code=2)
    payloads = _payloads(journal, preflight)
    value = journal.data
    value['state'] = 'prepared'
    prepared = PreparedJournal(canonical_json_bytes(value))
    prefix = tuple(journal.path.split('/')[:-1])
    possible = replaced = False
    try:
        source = _recheck(preflight, journal, held_lock, authority, gates)
        files = held_lock._files
        with files.directory(prefix) as directory:
            if directory is None:
                raise StagingError('building_journal_missing', exit_code=5)
            directory_id = guards._identity(os.fstat(directory))
            record_id = guards._identity(os.stat('journal.json', dir_fd=directory, follow_symlinks=False))
            if _read(directory, 'journal.json', expected_identity=record_id) != journal.source_bytes:
                raise StagingError('building_journal_changed', exit_code=6)
            _names(directory, ['journal.json'])
            current_raw, current_id = journal.source_bytes, record_id
            expected_names = {'journal.json'}
            owned_directories = {}
            def same():
                _own_lock(held_lock, source, journal)
                with files.directory(prefix) as fresh:
                    if fresh is None or guards._identity(os.fstat(fresh)) != directory_id:
                        raise StagingError('staging_directory_replaced', exit_code=6)
                    _names(fresh, expected_names)
                    for folder, expected_id in owned_directories.items():
                        with files.directory((*prefix, folder)) as child:
                            if child is None or guards._identity(os.fstat(child)) != expected_id:
                                raise StagingError('staging_directory_replaced', exit_code=6)
                    if _read(fresh, 'journal.json', expected_identity=current_id) != current_raw:
                        raise StagingError('building_journal_changed', exit_code=6)
            identities = {}
            for folder in ('staging', 'before'):
                same()
                possible = True
                os.mkdir(folder, mode=0o700, dir_fd=directory)
                owned_directories[folder] = guards._identity(os.stat(folder, dir_fd=directory, follow_symlinks=False))
                expected_names.add(folder)
                os.fsync(directory)
                same()
            for path, raw, size, digest in payloads:
                same()
                with files.directory(tuple(path.split('/')[:-1])) as parent:
                    if parent is None:
                        raise StagingError('staging_directory_missing', exit_code=5)
                    identities[path] = _write_new(parent, path.rsplit('/', 1)[-1], raw)
                same()
            _images_on_disk(files, prepared, identities)
            # Fresh authority/target checks cannot hide later tampering of images.
            _recheck(preflight, journal, held_lock, authority, gates)
            same()
            _images_on_disk(files, prepared, identities)
            _write_id = _write_new(directory, _PENDING, prepared.source_bytes)
            expected_names.add(_PENDING)
            same()
            _images_on_disk(files, prepared, identities)
            # Verify the staged metadata as well as all payloads before replace.
            _image(directory, _PENDING, len(prepared.source_bytes), prepared.sha256,
                   identity=_write_id)
            # One final source/rights observation after writing the pending record.
            if canonical_json_bytes(_observe(source, preflight._model, preflight.request,
                    preflight._package_files)) != preflight._footprint:
                raise StagingError('staging_source_changed', exit_code=6)
            same()
            replaced = True  # Even a lost rename result may have installed prepared.
            os.replace(_PENDING, 'journal.json', src_dir_fd=directory, dst_dir_fd=directory)
            current_raw, current_id = prepared.source_bytes, _write_id
            expected_names.remove(_PENDING)
            os.fsync(directory)
            same()
            _images_on_disk(files, prepared, identities)
            if canonical_json_bytes(_observe(source, preflight._model, preflight.request,
                    preflight._package_files)) != preflight._footprint:
                raise StagingError('staging_source_changed', exit_code=6)
        held_lock.check()
        return prepared
    except (OSError, SafetyViolation, ModelError, ChangeExecutionError) as error:
        raise _translate(error, possible=possible, prepared=replaced) from error


def read_prepared_journal(source, transaction_id, *, expected_sha256=None, preflight=None):
    """Read and hash every image; no lock acquisition, repair, or durability claim."""
    if type(source) is not ProjectSource:
        raise StagingError('bound_project_source_required', exit_code=2)
    path = journal_path(transaction_id)
    if expected_sha256 is not None and not _hash(expected_sha256):
        raise StagingError('invalid_expected_journal_hash', exit_code=2)
    try:
        source.check_current()
        with LockFiles(source.boundary.root) as files:
            if files.boundary._root_identity != source.boundary._root_identity:
                raise StagingError('prepared_project_changed', exit_code=6)
            prefix = tuple(path.split('/')[:-1])
            with files.directory(prefix) as directory:
                if directory is None:
                    raise StagingError('prepared_journal_missing', exit_code=5)
                before = os.stat('journal.json', dir_fd=directory, follow_symlinks=False)
                ident = guards._identity(before)
                raw = _read(directory, 'journal.json', expected_identity=ident)
                journal = PreparedJournal(raw)
                v = journal.data
                if (journal.path != path or v['project_id'] != source.configuration.project_id
                        or v['root_identity'] != list(source.boundary._root_identity)):
                    raise StagingError('prepared_project_binding_mismatch', exit_code=6)
                if expected_sha256 is not None and journal.sha256 != expected_sha256:
                    raise StagingError('prepared_journal_bytes_changed', exit_code=6)
                if preflight is not None:
                    verify_prepared_journal(journal, preflight)
                _names(directory, ('journal.json', 'staging', 'before'))
                _images_on_disk(files, journal)
                if _read(directory, 'journal.json', expected_identity=ident) != raw:
                    raise StagingError('prepared_journal_bytes_changed', exit_code=6)
                _names(directory, ('journal.json', 'staging', 'before'))
        source.check_current()
        return journal
    except (OSError, SafetyViolation, ModelError, ChangeExecutionError) as error:
        raise _translate(error, possible=False, prepared=False) from error
