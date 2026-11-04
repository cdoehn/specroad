"""Schema changes in the shared writer/receipt/recovery namespaces.

Only the native migration adapter prepares this closed branch. Existing v1
transactions retain their parser and behavior. No retry or rollback is implicit.
"""
from hashlib import sha256
import os
from ..model.canonical import canonical_json_bytes as jcs, canonical_json_sha256 as digest
from ..storage.json_syntax import parse_json_object as parsed
from ..bundles.migration_source import verify_source_backup
from ..migration.plan_values import b64, file_bindings
from ..migration.transaction_target import materialized_files, validate_transaction_target
from .schema_transition_values import (FORMAT, TransitionJournal, TransitionRequest,
    SchemaTransitionError, require, authoring, transaction_receipt, request_receipt, result_object)
from ._schema_transition_io import read, write_new, complete_owned_image, external_backup, project_files, check_parents, move_image
from ._lock_files import LockFiles
from .locking import HeldProjectLock
from .publication_values import PublicationAuthority
from .receipt_values import transaction_receipt_path, request_receipt_path, TransactionCompletion
from ._journal_codec import _transaction, _hash
from ._journal_io import _read
from ._staging_files import _write_new
from ..authoring._bootstrap_io import rename_function, rename_new


def _checkpoint(event):
    """Internal durability boundary; no data-defined callback is registered."""


def _archive_path(journal):
    if journal.data['state'] == 'committed': return journal.receipt_root
    return '.specroad/recovery/transaction-audit/schema-' + sha256(journal.data['transaction_id'].encode()).hexdigest()


def _backup(journal, raw):
    descriptor = journal.data['backup']
    require(len(raw) == descriptor['size'], 'transition_backup_changed')
    backup = verify_source_backup(raw, expected_sha256=descriptor['sha256'],
        expected_source_files_sha256=descriptor['source_files_sha256'])
    op = journal.plan.data['operations'][0]
    require(file_bindings(backup.files) == op['source_files'], 'transition_source_binding')
    from ..migration.plan_recheck import recheck_migration_plan
    recheck_migration_plan(journal.plan.source_bytes, backup.files, expected_target_version='0.2.0',
        expected_inputs_sha256=op['inputs_sha256'], expected_plan_sha256=journal.plan.sha256)
    return backup


def _images(journal, backup):
    images = {'source.zip': backup.source_bytes}
    target = materialized_files(journal.plan, backup.files)
    for index, row in enumerate(journal.plan.data['operations'][0]['changes']):
        path = row['path']
        if path in backup.files: images['before/' + str(index) + '.bin'] = backup.files[path]
        if path in target: images['staging/' + str(index) + '.bin'] = target[path]
    return images


def _verify_images(files, prefix, journal, backup, *, partial=False):
    expected = _images(journal, backup)
    # Known pending journal/move files are retained, but each actual byte must
    # match its deterministic purpose. Unknown work never gets cleaned away.
    from ..migration._backup_source import _scan
    names = [p[len(prefix)+1:] for p in _scan(files) if p.startswith(prefix + '/')]
    required = {'journal.json'} | (set() if partial else set(expected))
    require(required <= set(names), 'transition_images_missing')
    for name in names:
        raw = read(files, prefix + '/' + name)
        if name == 'journal.json':
            require(raw == journal.source_bytes, 'transition_journal_changed')
        elif name in expected:
            require(raw == expected[name] or partial and expected[name].startswith(raw), 'transition_image_changed')
        elif name.startswith('journal.') and name.endswith('.pending'):
            possible = [journal.successor(state, count).source_bytes
                for state, count in ((journal.data['state'], journal.data['published_count']),
                    ('prepared',0), ('committing',journal.data['published_count']),
                    ('committing',min(len(journal.plan.data['operations'][0]['changes']),journal.data['published_count']+1)),
                    ('rolling_back',journal.data['published_count']),
                    ('rolling_back',max(0,journal.data['published_count']-1)),
                    ('rolled_back',0), ('committed',len(journal.plan.data['operations'][0]['changes'])))]
            require(any(name == 'journal.' + sha256(value).hexdigest() + '.pending'
                        and value.startswith(raw) for value in possible),
                    'transition_pending_journal_changed')
        elif name.startswith('moves/') and name.endswith('.bin'):
            possible = [(p, b) for p, b in backup.files.items()] + list(materialized_files(journal.plan, backup.files).items())
            require(any(name == 'moves/' + sha256((p + ':' + sha256(b).hexdigest()).encode()).hexdigest() + '.bin'
                        and b.startswith(raw) for p, b in possible), 'transition_pending_image_changed')
        elif name == 'transaction.json' and journal.data['state'] == 'committed':
            require(transaction_receipt(journal).startswith(raw), 'transition_receipt_changed')
        else:
            raise SchemaTransitionError('transition_unknown_work')


def _held(held, journal):
    require(type(held) is HeldProjectLock, 'transition_native_lock_required', exit_code=7)
    held.check()
    value = held.record.data; data = journal.data
    require(value['kind'] in ('writer', 'recovery')
        and value['command'] in ('migrate apply', 'recover run', 'recover discard')
        and value['project_id'] == data['project_id'] and value['transaction_id'] == data['transaction_id']
        and (value['kind'] != 'writer' or value['request_id'] == journal.plan.data['request_id'])
        and list(held._files.boundary._root_identity) == data['root_identity'], 'transition_lock_binding', exit_code=7)


def _exclude(journal, prefix):
    paths = [prefix, '.specroad/locks/project.json']
    request = journal.plan.data['request_id']
    if request is not None: paths.append(request_receipt_path(request))
    return tuple(paths)


def _prefix(journal, source, actual):
    """Derive the actual complete effect prefix, independently of the cursor."""
    changes = journal.plan.data['operations'][0]['changes']
    target = materialized_files(journal.plan, source)
    changed = {r['path'] for r in changes}
    require({p: b for p, b in actual.items() if p not in changed} ==
            {p: b for p, b in source.items() if p not in changed}, 'transition_unrelated_files_changed')
    count = 0; before_seen = False
    for row in changes:
        p = row['path']; observed = actual.get(p)
        if observed == target.get(p) and not before_seen:
            count += 1
        elif observed == source.get(p): before_seen = True
        else: raise SchemaTransitionError('transition_unproven_file_prefix')
    return count


class _Session:
    def __init__(self, held, journal, backup, *, gates=(), authority=None, recover=False):
        self.held, self.files = held, held._files
        self.journal, self.backup = journal, backup
        self.gates, self.authority, self.recover = tuple(gates), authority, recover
        self.prefix = journal.path.rsplit('/', 1)[0]
        with self.files.directory(tuple(self.prefix.split('/'))) as fd:
            require(fd is not None,'transition_work_changed')
            info=os.fstat(fd);self.work_identity=(info.st_dev,info.st_ino)
        self.source = backup.files
        self.target = materialized_files(journal.plan, self.source)
        self.live_count = journal.data['published_count']
        self.parents = check_parents(self.files, [r['path'] for r in journal.plan.data['operations'][0]['changes']])
        self.prepared = journal.data['images_prepared']
        self.archived = False
        self.receipts_complete = False

    def guard(self, *, work=True):
        _held(self.held, self.journal)
        with self.files.directory(tuple(self.prefix.split('/'))) as fd:
            require(fd is not None,'transition_work_changed')
            info=os.fstat(fd)
            require((info.st_dev,info.st_ino)==self.work_identity,'transition_work_changed')
        expected_active = () if self.archived else (self.prefix,)
        require(self.files.journal_entries() == expected_active, 'transition_active_set_changed')
        if work:
            _verify_images(self.files, self.prefix, self.journal, self.backup, partial=not self.prepared)
        if self.journal.data['state'] == 'committed' and (self.archived or self.receipts_complete):
            require(read(self.files,self.prefix+'/transaction.json') == transaction_receipt(self.journal),
                    'transition_receipt_changed')
            receipt = request_receipt(self.journal)
            if receipt is not None:
                require(read(self.files,receipt.path) == receipt.source_bytes, 'transition_request_receipt_changed')
        actual, modes, _ = project_files(self.files, exclude=_exclude(self.journal, self.prefix))
        require(_prefix(self.journal, self.source, actual) == self.live_count, 'transition_file_prefix_changed')
        for path, mode in modes.items():
            expected = self.journal.data['source_modes'].get(path, 0o644)
            require(mode == expected, 'transition_file_mode_changed')
        current_parents = check_parents(self.files, [r['path'] for r in self.journal.plan.data['operations'][0]['changes']])
        for key, expected in self.parents.items():
            if expected is not None: require(current_parents[key] == expected, 'transition_parent_changed')
        self.parents = current_parents
        request_id = self.journal.plan.data['request_id']
        if request_id is not None:
            raw = read(self.files, request_receipt_path(request_id), optional=True)
            expected = request_receipt(self.journal) if self.journal.data['state'] == 'committed' else None
            require(raw is None or expected is not None and expected.source_bytes.startswith(raw), 'transition_request_collision')
        require(external_backup(self.files,self.journal.data['backup']).source_bytes == self.backup.source_bytes,
                'transition_backup_changed')
        self.held.check()

    def authorize(self):
        require(type(self.authority) is PublicationAuthority, 'transition_authority_required', exit_code=7)
        before = TransitionRequest.from_journal(self.journal)
        allowed = self.authority.check(before)
        require(type(allowed) is bool and allowed, 'transition_not_authorized', exit_code=7)
        require(before._raw == TransitionRequest.from_journal(self.journal)._raw, 'transition_authority_input_changed')

    def validate(self):
        report = validate_transaction_target(self.journal.plan, self.source, self.target, gates=self.gates)
        require(report.data == self.journal.data['validation'], 'transition_validation_changed')
        actual = external_backup(self.files, self.journal.data['backup'])
        require(actual.source_bytes == self.backup.source_bytes, 'transition_backup_changed')
        self.authorize(); self.guard()

    def save(self, state, count):
        self.guard()
        successor = self.journal.successor(state, count)
        name = 'journal.' + successor.sha256 + '.pending'
        path = self.prefix + '/' + name
        complete_owned_image(self.files,path,successor.source_bytes,guard=self.guard)
        # The old journal remains authoritative until this guarded atomic replace.
        self.guard()
        with self.files.directory(tuple(self.prefix.split('/'))) as fd:
            require(_read(fd, name) == successor.source_bytes, 'transition_pending_journal_changed')
            os.replace(name, 'journal.json', src_dir_fd=fd, dst_dir_fd=fd)
            self.journal = successor
            os.fsync(fd)
        _checkpoint('journal:' + state + ':' + str(count))
        self.guard()

    def effect(self, index, *, rollback=False):
        changes = self.journal.plan.data['operations'][0]['changes']
        path = changes[index]['path']
        before = self.target.get(path) if rollback else self.source.get(path)
        after = self.source.get(path) if rollback else self.target.get(path)
        mode = self.journal.data['source_modes'].get(path, 0o644)
        def observed(): self.live_count = index if rollback else index + 1
        move_image(self.files, self.prefix, path, after, before=before, mode=mode,
                   guard=self.guard, after=observed)
        _checkpoint(('rollback:' if rollback else 'effect:') + str(index))
        self.guard()
        self.save('rolling_back' if rollback else 'committing', self.live_count)

    def finish(self):
        self.guard()
        journal = self.journal
        if journal.data['state'] == 'committed':
            path = self.prefix + '/transaction.json'; raw = transaction_receipt(journal)
            complete_owned_image(self.files,path,raw,guard=self.guard)
            receipt = request_receipt(journal)
            if receipt is not None:
                complete_owned_image(self.files,receipt.path,receipt.source_bytes,guard=self.guard)
            self.receipts_complete = True
            _checkpoint('receipts')
            self.guard()
        destination = _archive_path(journal)
        rename = rename_function()
        with self.files.directory(tuple(destination.split('/')[:-1]), create=True) as target:
            with self.files.directory(('.specroad', 'transactions')) as parent:
                self.guard()
                rename_new(rename, parent, journal.data['transaction_id'], target, destination.rsplit('/', 1)[-1])
        self.prefix = destination; self.archived = True
        _checkpoint('archived')
        self.guard()
        return journal


def publish_schema_transition(plan, *, held_lock, backup_descriptor, authority, gates=()):
    """Called only with the common live migrate-apply writer lock and real backup."""
    require(type(held_lock) is HeldProjectLock and type(authority) is PublicationAuthority,
            'transition_native_inputs_required', exit_code=7)
    require(held_lock.record.data['kind'] == 'writer' and held_lock.record.data['command'] == 'migrate apply',
            'transition_writer_lock_required', exit_code=7)
    authoring(plan); rename_function()
    files = held_lock._files
    backup = external_backup(files, backup_descriptor)
    source, modes, _ = project_files(files, exclude=('.specroad/locks/project.json',))
    require(source == backup.files, 'transition_source_changed')
    report = validate_transaction_target(plan, source, materialized_files(plan, source), gates=tuple(gates))
    journal = TransitionJournal(jcs({'format_version': FORMAT, 'state': 'building',
        'transaction_id': held_lock.record.data['transaction_id'], 'project_id': backup.manifest['project_id'],
        'root_identity': list(files.boundary._root_identity), 'plan_bytes_base64': b64(plan.source_bytes),
        'request_id': plan.data['request_id'], 'plan_sha256': plan.sha256, 'backup': backup_descriptor, 'source_modes': modes,
        'published_count': 0, 'images_prepared': False, 'validation': report.data}))
    _held(held_lock, journal)
    request = TransitionRequest.from_journal(journal)
    allowed = authority.check(request)
    require(type(allowed) is bool and allowed and request._raw == TransitionRequest.from_journal(journal)._raw,
            'transition_not_authorized', exit_code=7)
    require(not files.journal_entries(), 'transition_recovery_required', exit_code=5)
    require(project_files(files, exclude=('.specroad/locks/project.json',))[:2] == (source, modes), 'transition_source_changed')
    require(external_backup(files, backup_descriptor).source_bytes == backup.source_bytes, 'transition_backup_changed')
    request_id = plan.data['request_id']
    if request_id is not None:
        require(read(files, request_receipt_path(request_id), optional=True) is None, 'transition_request_collision')
    require(read(files, transaction_receipt_path(journal.data['transaction_id']), optional=True) is None, 'transition_id_collision')
    from ._recovery_evidence import evidence_root
    for destination in (journal.receipt_root,_archive_path(journal),evidence_root(journal.data['transaction_id'])):
        with files.directory(tuple(destination.split('/'))) as existing:
            require(existing is None,'transition_id_collision')
    with files.directory(('.specroad','transactions'), create=True) as parent:
        os.mkdir(journal.data['transaction_id'], mode=0o700, dir_fd=parent); os.fsync(parent)
    write_new(files, journal.path, journal.source_bytes)
    _checkpoint('journal:building:0')
    session = _Session(held_lock, journal, backup, gates=gates, authority=authority)
    session.guard()
    for name, raw in _images(journal, backup).items():
        session.guard(); write_new(files, session.prefix + '/' + name, raw)
        _checkpoint('image:' + name)
    session.prepared = True
    session.validate(); session.save('prepared', 0)
    session.validate(); session.save('committing', 0)
    for index in range(len(plan.data['operations'][0]['changes'])): session.effect(index)
    session.validate(); session.save('committed', session.live_count)
    session.finish()
    return completion_data(session.journal, current=True)


def completion_data(journal, *, current=False):
    receipt = request_receipt(journal)
    result = result_object(journal)
    return {**result, 'format_version': 'migration-transaction-v1', 'backup': journal.data['backup'],
        'plan_sha256': journal.plan.sha256, 'journal_sha256': journal.sha256,
        'replayed': not current, 'current_target_verified': current, 'approval_granted': False,
        'receipts': {'transaction': {'path': transaction_receipt_path(journal.data['transaction_id']),
                                    'sha256': sha256(transaction_receipt(journal)).hexdigest()},
                     'request': None if receipt is None else {'path': receipt.path, 'sha256': receipt.sha256}}}
