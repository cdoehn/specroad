"""Finish C.2 without repeating a single normative target write.

Durable transaction/request receipts precede the committed journal replacement.
A failure keeps its operational evidence; no overwrite, retry or rollback.
"""
from hashlib import sha256
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
from ._publication_observation import _root, _stamp, _parent
from ._journal_io import _read
from ._staging_files import _write_new, _image, _names
from ._target_checks import _gates, _empty_target_gates
from .publication_check import _same_request
from .publication_values import PublicationPreflight, PublicationAuthority
from .committing_values import CommittingJournal
from .committing_read import _observed_files
from .locking import HeldProjectLock
from .staging import _own_lock
from .execution_values import ChangeExecutionError
from .receipt_values import ReceiptError, TransactionCompletion
from .receipt_projection import prepare_completion_receipts


class _ReceiptSession:
    def __init__(self, preflight, journal, held, authority, gates):
        self.preflight, self.journal, self.held = preflight, journal, held
        self.authority, self.gates = authority, tuple(gates)
        self.files = held._files
        self.source = _root(preflight._model)
        _own_lock(held, self.source, journal)
        self.prefix = tuple(journal.path.split('/')[:-1])
        self.image_ids, self.receipts, self.receipt_dirs = {}, {}, {}
        self.pending = None
        self.mutation = self.committed_possible = False
        with self.files.directory(self.prefix) as directory:
            if directory is None:
                raise ReceiptError('completion_journal_missing', exit_code=5)
            _names(directory, ['journal.json', 'before', 'staging'])
            self.directory_id = guards._identity(os.fstat(directory))
            self.journal_id = guards._identity(os.stat('journal.json', dir_fd=directory, follow_symlinks=False))
            if _read(directory, 'journal.json', expected_identity=self.journal_id) != journal.source_bytes:
                raise ReceiptError('completion_journal_changed', exit_code=6)
        _observed_files(self.files, journal, self.image_ids, capture=True)
        self.expected = {**preflight._model.source_files,
                         **{d.path: d.content for d in preflight.request.documents},
                         **{d.path: d.content for d in preflight._package_files}}
        self.target_snapshot = self.observe_target()
        self.check()

    def observe_target(self):
        self.source.check_current()
        expected_json = tuple(sorted(p for p in self.expected if self.source.classify(p) in CURRENT_JSON_CLASSES))
        if current_json_paths(self.source) != expected_json:
            raise ReceiptError('completion_target_inventory_changed', exit_code=6)
        states, parents = {}, {}
        for path, raw in sorted(self.expected.items()):
            parents.update(_parent(self.source, path, check_rights=lambda *args: None, writable=False))
            with opened_resource(self.source.boundary, path) as (fd, info):
                if info.st_nlink != 1:
                    raise ReceiptError('completion_hardlink_refused', path=path, exit_code=7)
                observed = fingerprint_reader(lambda n: os.read(fd, n), info.st_size)
                if observed.size != len(raw) or observed.sha256 != sha256(raw).hexdigest():
                    raise ReceiptError('completion_target_changed', path=path, exit_code=6)
                states[path] = {**_stamp(info), 'size': info.st_size, 'sha256': observed.sha256}
        self.source.check_current()
        if current_json_paths(self.source) != expected_json:
            raise ReceiptError('completion_target_inventory_changed', exit_code=6)
        return canonical_json_bytes({'files': states, 'parents': parents})

    def check(self):
        _own_lock(self.held, self.source, self.journal)
        with self.files.directory(self.prefix) as directory:
            if directory is None or guards._identity(os.fstat(directory)) != self.directory_id:
                raise ReceiptError('completion_directory_changed', exit_code=6)
            _names(directory, ['journal.json', 'before', 'staging'] + ([] if self.pending is None else [self.pending]))
            if _read(directory, 'journal.json', expected_identity=self.journal_id) != self.journal.source_bytes:
                raise ReceiptError('completion_journal_changed', exit_code=6)
        _observed_files(self.files, self.journal, self.image_ids, capture=False)
        if self.observe_target() != self.target_snapshot:
            raise ReceiptError('completion_target_identity_changed', exit_code=6)
        for parts, identity in self.receipt_dirs.items():
            with self.files.directory(parts) as directory:
                if directory is None or guards._identity(os.fstat(directory)) != identity:
                    raise ReceiptError('receipt_directory_changed', exit_code=6)
        for path, (raw, identity) in self.receipts.items():
            with self.files.directory(tuple(path.split('/')[:-1])) as directory:
                if directory is None or _read(directory, path.rsplit('/', 1)[-1], expected_identity=identity) != raw:
                    raise ReceiptError('completion_receipt_changed', exit_code=6)
        self.held.check()

    def validate_target(self):
        self.check()
        preflight, model = self.preflight, self.preflight._model
        request = preflight.request
        documents = tuple(ModelDocument(e['path'], self.source.boundary.read_bytes(e['path']))
                          for e in request.data['target_files'])
        root = model.manifest([parse_json_object(d.content) for d in documents],
                              request.plan.data['base']['scope_descriptor']).sha256
        if root != request.data['target_root_sha256']:
            raise ReceiptError('completion_target_root_mismatch', exit_code=6)
        registered, missing = _gates(self.gates, preflight._policy, request.plan, model)
        report = _empty_target_gates(validate_model(documents, profile=model.profile, gates=registered),
                                     registered, model.profile)
        decision = assess_validation(report, fail_on=model.configuration.data['validation_policy'].get('fail_on', 'error'),
                                     strict=preflight._strict, documents=documents)
        if missing or not report.complete or not decision.passed:
            raise ReceiptError('completion_target_not_validated')
        detached = request.detached()
        try:
            allowed = self.authority.check(detached)
        except Exception as error:
            raise ReceiptError('completion_authority_failed', exit_code=7) from error
        _same_request(detached, request)
        if type(allowed) is not bool or not allowed:
            raise ReceiptError('completion_authorization_denied', exit_code=7)
        self.check()

    def store(self, record):
        self.check()
        parts, name = tuple(record.path.split('/')[:-1]), record.path.rsplit('/', 1)[-1]
        self.mutation = True
        with self.files.directory(parts, create=True) as directory:
            for length in range(1, len(parts) + 1):
                prefix = parts[:length]
                with self.files.directory(prefix) as parent:
                    identity = guards._identity(os.fstat(parent))
                    if prefix in self.receipt_dirs and self.receipt_dirs[prefix] != identity:
                        raise ReceiptError('receipt_directory_changed', exit_code=6)
                    self.receipt_dirs[prefix] = identity
            self.check()
            identity = _write_new(directory, name, record.source_bytes)
            self.receipts[record.path] = (record.source_bytes, identity)
            self.check()

    def commit(self, successor):
        self.check()
        self.mutation = True
        with self.files.directory(self.prefix) as directory:
            name = 'journal.complete'
            identity = _write_new(directory, name, successor.source_bytes)
            self.pending = name
            self.check()
            _image(directory, name, len(successor.source_bytes), successor.sha256, identity=identity)
            self.committed_possible = True
            os.replace(name, 'journal.json', src_dir_fd=directory, dst_dir_fd=directory)
            self.journal, self.journal_id, self.pending = successor, identity, None
            os.fsync(directory)
            self.check()


def finalize_committing_journal(preflight, journal, *, held_lock, authority, gates=()):
    """Durably record a verified full target before publishing committed.

    No normative file is written, no work is cleaned, and no lock is acquired.
    The caller keeps the original native writer lock through this entire phase.
    Partial receipts and interrupted markers remain recovery evidence on error.
    """
    if (type(preflight) is not PublicationPreflight or type(journal) is not CommittingJournal
            or type(held_lock) is not HeldProjectLock or type(authority) is not PublicationAuthority
            or type(gates) not in (list, tuple)):
        raise ReceiptError('explicit_completion_inputs_required', exit_code=2)
    session = None
    try:
        transaction, request, committed = prepare_completion_receipts(preflight, journal)
        session = _ReceiptSession(preflight, journal, held_lock, authority, gates)
        session.validate_target()
        # Check both destinations before the first receipt write. Never truncate.
        for record in (transaction, request):
            if record is None: continue
            with session.files.directory(tuple(record.path.split('/')[:-1])) as directory:
                if directory is not None:
                    try:
                        os.stat(record.path.rsplit('/', 1)[-1], dir_fd=directory, follow_symlinks=False)
                    except FileNotFoundError:
                        pass
                    else:
                        raise ReceiptError('completion_receipt_already_exists', path=record.path, exit_code=6)
        session.store(transaction)
        if request is not None: session.store(request)
        session.commit(committed)
        return TransactionCompletion._create(committed, live=True)
    except (OSError, SafetyViolation, ModelError, ChangeExecutionError, ResultContractError) as error:
        result = error if isinstance(error, ReceiptError) else ReceiptError(
            getattr(error, 'reason', 'completion_io_failure'), path=getattr(error, 'path', None),
            exit_code=getattr(error, 'exit_code', 7 if isinstance(error, SafetyViolation) else 5))
        if session is not None:
            result.mutation_possible |= session.mutation
            result.committed_possible |= session.committed_possible
        raise result from (None if result is error else error)
