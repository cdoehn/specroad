"""prepared -> committing: durable per-file acknowledgement, then live target root.

An active journal remains until later receipt/finalization code completes C.2.
No retry, rollback, journal deletion, or committed marker is performed here.
Supported targets are the artifact writes in the existing PublicationRequest.
"""
from hashlib import sha256
from ._discard_basis_contract import match_basis_version
import os
from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..model.paths import CURRENT_JSON_CLASSES
from ..result_contract import ResultContractError
from ..security import SafetyViolation
from ..security import paths as guards
from ..security.resource_access import opened_resource
from ..storage.byte_binding import fingerprint_reader
from ..storage.resource_discovery import current_json_paths
from ..storage.json_syntax import parse_json_object
from ..validation import ModelDocument, validate_model, assess_validation
from .journal_values import JournalError
from ._journal_io import _read
from ._journal_inventory import prepare_building_journal
from .staging_values import PreparedJournal
from .staging import verify_prepared_journal, _own_lock, _recheck, _materialized_target
from ._staging_files import _image, _write_new, _names
from ._publication_io import replace_bound_image
from .publication_values import PublicationPreflight, PublicationAuthority
from .publication_check import _rights
from ._publication_observation import _stamp
from .locking import HeldProjectLock
from .execution_values import ChangeExecutionError
from ._target_checks import _gates, _empty_target_gates
from .committing_values import CommittingJournal, CommitPublicationError, PublishedFiles
from ._committing_state import _initial_committing, _acknowledge, next_publication


def verify_committing_journal(journal, preflight):
    """Bind the entire inventory independently; no disk or authority inference."""
    if type(journal) is not CommittingJournal:
        raise CommitPublicationError('committing_journal_required', exit_code=2)
    expected = prepare_building_journal(preflight,
        transaction_id=journal.data['transaction_id']).data
    match_basis_version(expected, journal.data)
    count = journal.data['published_count']
    expected.update(state='committing', published_count=count)
    for index, entry in enumerate(expected['files']):
        entry['published'] = index < count
    if canonical_json_bytes(expected) != canonical_json_bytes(journal.data):
        raise CommitPublicationError('committing_inventory_mismatch', exit_code=6)


class _Publisher:
    """One owned call under a native lock. Each mutation updates only its own binding."""
    def __init__(self, preflight, journal, held, authority, gates):
        self.preflight, self.journal, self.held = preflight, journal, held
        self.authority, self.gates = authority, gates
        self.files = held._files
        self.source = _recheck(preflight, journal, held, authority, gates)
        self.prefix = tuple(journal.path.split('/')[:-1])
        self.entries = journal.data['files']
        self.paths = {e['path']: e for e in self.entries}
        footprint = parse_json_object(preflight._footprint)
        self.states, self.parents = footprint['files'], footprint['parents']
        self.root_stamp = footprint['root']
        self.expected_bytes = {**preflight._model.source_files,
                              **{d.path:d.content for d in preflight._package_files}}
        self.images, self.folders = {}, {}
        self.pending = None
        self.renamed = 0  # observed moves, possibly one ahead of durable journal
        self.mutation = self.publication = False
        self.acknowledged = 0
        with self.files.directory(self.prefix) as fd:
            if fd is None:
                raise CommitPublicationError('prepared_journal_missing', exit_code=5)
            _names(fd, ['journal.json', 'staging', 'before'])
            self.folders[self.prefix] = guards._identity(os.fstat(fd))
            self.journal_identity = guards._identity(os.stat('journal.json', dir_fd=fd,
                                                             follow_symlinks=False))
            if _read(fd, 'journal.json', expected_identity=self.journal_identity) != journal.source_bytes:
                raise CommitPublicationError('prepared_journal_changed', exit_code=6)
        for folder in ('staging', 'before'):
            parts = (*self.prefix, folder)
            with self.files.directory(parts) as fd:
                if fd is None:
                    raise CommitPublicationError('publication_images_missing', exit_code=5)
                self.folders[parts] = guards._identity(os.fstat(fd))
        self._check_images(capture=True)
        _materialized_target(self.files, journal, preflight, gates)
        # Any mutation by a trusted verifier invalidates the source/image bindings.
        _recheck(preflight, journal, held, authority, gates)
        self.check()

    def _check_images(self, *, capture=False):
        for folder, key, size, digest in (
                ('staging','staging_path','after_size','after_sha256'),
                ('before','before_image_path','before_size','before_sha256')):
            wanted = [e for i,e in enumerate(self.entries)
                      if e[key] is not None and (folder != 'staging' or i >= self.renamed)]
            with self.files.directory((*self.prefix, folder)) as fd:
                if fd is None:
                    raise CommitPublicationError('publication_images_missing', exit_code=5)
                _names(fd, [e[key].rsplit('/',1)[-1] for e in wanted])
                for entry in wanted:
                    path = entry[key]
                    identity = _image(fd, path.rsplit('/',1)[-1], entry[size], entry[digest],
                                      identity=None if capture else self.images[path])
                    if capture:
                        self.images[path] = identity

    def _check_files(self):
        source = self.source
        source.check_current()
        expected_json = tuple(sorted(p for p in self.expected_bytes
                                     if source.classify(p) in CURRENT_JSON_CLASSES))
        if current_json_paths(source) != expected_json:
            raise CommitPublicationError('publication_file_set_changed', exit_code=6)
        if _stamp(os.lstat(source.boundary.root)) != self.root_stamp:
            raise CommitPublicationError('publication_root_changed', exit_code=6)
        for path, wanted in self.parents.items():
            if not path:
                continue
            try:
                with self.files.directory(tuple(path.split('/'))) as fd:
                    observed = None if fd is None else _stamp(os.fstat(fd))
            except FileNotFoundError:
                observed = None
            if observed != wanted:
                raise CommitPublicationError('publication_parent_changed', path=path, exit_code=6)
        for path, raw in sorted(self.expected_bytes.items()):
            with opened_resource(source.boundary, path) as (fd, info):
                seen = fingerprint_reader(lambda n: os.read(fd,n), info.st_size)
                state = {**_stamp(info), 'size':seen.size, 'sha256':seen.sha256}
                if state != self.states[path] or seen.sha256 != sha256(raw).hexdigest():
                    raise CommitPublicationError('publication_file_changed', path=path, exit_code=6)
        if current_json_paths(source) != expected_json:
            raise CommitPublicationError('publication_file_set_changed', exit_code=6)

    def check(self):
        _own_lock(self.held, self.source, self.journal)
        for parts, identity in self.folders.items():
            with self.files.directory(parts) as fd:
                if fd is None or guards._identity(os.fstat(fd)) != identity:
                    raise CommitPublicationError('publication_directory_replaced', exit_code=6)
        with self.files.directory(self.prefix) as fd:
            _names(fd, ['journal.json','staging','before'] +
                   ([] if self.pending is None else [self.pending]))
            if _read(fd,'journal.json',expected_identity=self.journal_identity) != self.journal.source_bytes:
                raise CommitPublicationError('publication_journal_changed', exit_code=6)
        self._check_images()
        self._check_files()
        self.held.check()

    def save(self, successor):
        """A durable journal transition is required before any next target rename."""
        self.check()
        self.mutation = True
        pending = 'journal.next'
        with self.files.directory(self.prefix) as directory:
            identity = _write_new(directory, pending, successor.source_bytes)
            self.pending = pending
            self.check()
            _image(directory,pending,len(successor.source_bytes),successor.sha256,identity=identity)
            os.replace(pending,'journal.json',src_dir_fd=directory,dst_dir_fd=directory)
            # A lost result above leaves unknown journal state and immediately stops.
            self.journal, self.journal_identity, self.pending = successor, identity, None
            os.fsync(directory)
            self.check()
            self.acknowledged = successor.data['published_count']

    def _create_parents(self, path):
        parts = tuple(path.split('/')[:-1])
        for i in range(1,len(parts)+1):
            key = '/'.join(parts[:i])
            if self.parents[key] is not None:
                continue
            self.check()
            with self.files.directory(parts[:i-1]) as fd:
                if fd is None:
                    raise CommitPublicationError('publication_parent_missing', exit_code=5)
                _rights(fd, '/'.join(parts[:i-1]))
                self.mutation = True
                os.mkdir(parts[i-1], mode=0o700, dir_fd=fd)
                info = os.stat(parts[i-1],dir_fd=fd,follow_symlinks=False)
                guards._regular(info,directory=True)
                if info.st_dev != os.fstat(self.files.root_fd).st_dev:
                    raise CommitPublicationError('publication_cross_device',exit_code=7)
                self.parents[key] = _stamp(info)
                os.fsync(fd)
            self.check()

    def publish(self, index):
        entry = self.entries[index]
        self.check()
        self._create_parents(entry['path'])
        with self.files.directory(tuple(entry['path'].split('/')[:-1])) as target:
            with self.files.directory((*self.prefix,'staging')) as stage:
                if target is None or stage is None:
                    raise CommitPublicationError('publication_directory_missing',exit_code=5)
                if os.fstat(target).st_dev != os.fstat(stage).st_dev:
                    raise CommitPublicationError('publication_cross_device',exit_code=7)
                _rights(target,entry['path'])
                name = entry['staging_path'].rsplit('/',1)[-1]
                identity = self.images[entry['staging_path']]
                _image(stage,name,entry['after_size'],entry['after_sha256'],identity=identity)
                mode = self.states[entry['path']]['mode'] if entry['existed_before'] else 0o644
                if mode & 0o7000:
                    raise CommitPublicationError('unsafe_publication_mode',exit_code=7)
                def before_mutation():
                    self.mutation = True

                def before_replace():
                    self.check()
                    _rights(target, entry['path'])
                    self.publication = True

                def after_replace(info):
                    self.renamed = index + 1
                    self.states[entry['path']] = {**_stamp(info), 'size':entry['after_size'],
                                                  'sha256':entry['after_sha256']}
                    self.expected_bytes[entry['path']] = next(
                        d.content for d in self.preflight.request.documents
                        if d.path == entry['path'])

                replace_bound_image(stage, name, target, entry['path'].rsplit('/', 1)[-1],
                    size=entry['after_size'], digest=entry['after_sha256'], identity=identity,
                    mode=mode,
                    source_changed=lambda: CommitPublicationError(
                        'publication_image_replaced', exit_code=6),
                    before_mutation=before_mutation, before_replace=before_replace,
                    after_replace=after_replace)
        self.check()
        self.save(_acknowledge(self.journal,index))

    def target_root(self):
        """Read every final document; bind unchanged resources with the same live check."""
        self.check()
        model = self.preflight._model
        paths = [d['path'] for d in self.preflight.request.data['target_files']]
        documents = tuple(ModelDocument(path,self.source.boundary.read_bytes(path)) for path in paths)
        if [{'path':d.path,'sha256':sha256(d.content).hexdigest()} for d in documents] != self.preflight.request.data['target_files']:
            raise CommitPublicationError('published_target_inventory_mismatch',exit_code=6)
        root = model.manifest([parse_json_object(d.content) for d in documents],
                             self.preflight.request.plan.data['base']['scope_descriptor']).sha256
        if root != self.journal.data['target_model_root_sha256']:
            raise CommitPublicationError('published_target_root_mismatch',exit_code=6)
        registered, missing = _gates(self.gates,self.preflight._policy,self.preflight.request.plan,model)
        report = validate_model(documents,profile=model.profile,gates=registered)
        report = _empty_target_gates(report,registered,model.profile)
        result = assess_validation(report,fail_on=model.configuration.data['validation_policy'].get('fail_on','error'),
                                   strict=self.preflight._strict,documents=documents)
        if missing or not report.complete or not result.passed:
            raise CommitPublicationError('published_target_validation_failed')
        self.check()
        return root


def publish_prepared_journal(preflight, journal, *, held_lock, authority, gates=()):
    """Publish all target files, retaining committing until later durable receipts.

    Raises on any failed boundary. Earlier target replacements and operational
    bytes remain recovery-blocked; no false no-write, resume or rollback promise.
    """
    if (type(preflight) is not PublicationPreflight or type(journal) is not PreparedJournal
            or type(held_lock) is not HeldProjectLock or type(authority) is not PublicationAuthority
            or type(gates) not in (tuple,list)):
        raise CommitPublicationError('explicit_publication_inputs_required',exit_code=2)
    session = None
    try:
        verify_prepared_journal(journal,preflight)
        session = _Publisher(preflight,journal,held_lock,authority,tuple(gates))
        session.save(_initial_committing(journal))
        while (index := next_publication(session.journal)) is not None:
            session.publish(index)
        root = session.target_root()
        return PublishedFiles._create(session.journal,root)
    except (OSError,SafetyViolation,ModelError,ChangeExecutionError,ResultContractError) as error:
        possible = session is not None and session.mutation
        publication = session is not None and session.publication
        count = session.acknowledged if session is not None else 0
        if isinstance(error, CommitPublicationError):
            error.mutation_possible |= possible
            error.publication_possible |= publication
            error.published_count = count
            if publication: error.write_state = 'unknown'
            raise
        code = getattr(error,'exit_code',7 if isinstance(error,SafetyViolation) else 5)
        reason = getattr(error,'reason','publication_io_failure')
        raise CommitPublicationError(reason,path=getattr(error,'path',None),exit_code=code,
             mutation_possible=possible,publication_possible=publication,published_count=count) from error
