"""Schema changes in the shared writer/receipt/recovery namespaces.

Only compiled migration/merge adapters prepare these closed branches. Existing v1
transactions retain their parser and behavior. No retry or rollback is implicit.
"""
from hashlib import sha256
import os
from ..model.canonical import canonical_json_bytes as jcs
from ..migration.plan_values import b64
from ._snapshot_dispatch import materialized_files, validate_target, command_for, format_for, is_merge
from .schema_transition_values import (FORMAT, TransitionJournal, TransitionRequest,
    SchemaTransitionError, require, authoring, transaction_receipt, request_receipt, result_object)
from ._schema_transition_proof import _backup, _images, _verify_images, _prefix
from ._schema_transition_io import read, write_new, complete_owned_image, external_backup, project_files, check_parents, move_image
from .locking import HeldProjectLock
from .publication_values import PublicationAuthority
from .receipt_values import transaction_receipt_path, request_receipt_path
from ._journal_io import _read
from ..authoring._bootstrap_io import rename_function, rename_new


def _checkpoint(event):
    """Internal durability boundary; no data-defined callback is registered."""


def _archive_path(journal):
    if journal.data['state'] == 'committed': return journal.receipt_root
    return '.specroad/recovery/transaction-audit/schema-' + sha256(journal.data['transaction_id'].encode()).hexdigest()


def _held(held, journal):
    require(type(held) is HeldProjectLock, 'transition_native_lock_required', exit_code=7)
    held.check()
    value = held.record.data; data = journal.data
    require(value['kind'] in ('writer', 'recovery')
        and value['command'] in (command_for(journal.plan), 'recover run', 'recover discard')
        and (value['kind'] != 'writer' or value['command'] == command_for(journal.plan))
        and value['project_id'] == data['project_id'] and value['transaction_id'] == data['transaction_id']
        and (value['kind'] != 'writer' or value['request_id'] == journal.plan.data['request_id'])
        and list(held._files.boundary._root_identity) == data['root_identity'], 'transition_lock_binding', exit_code=7)


def _exclude(journal, prefix):
    paths = [prefix, '.specroad/locks/project.json']
    request = journal.plan.data['request_id']
    if request is not None: paths.append(request_receipt_path(request))
    return tuple(paths)


class _Session:
    def __init__(self, held, journal, backup, *, gates=(), authority=None, recover=False, merge_context=None):
        self.merge_context = merge_context
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
        self.extra_evidence = {}

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
        actual, modes, _ = project_files(self.files, exclude=(*_exclude(self.journal, self.prefix), *self.extra_evidence))
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
        if self.recover:
            from .schema_transition_recovery import takeover_evidence
            require(takeover_evidence(self.files, self.journal) == self.extra_evidence,
                    'transition_takeover_evidence_changed')
        require(external_backup(self.files,self.journal.data['backup'],plan=self.journal.plan).source_bytes == self.backup.source_bytes,
                'transition_backup_changed')
        if self.merge_context is not None: self.merge_context.check()
        self.held.check()

    def authorize(self):
        require(type(self.authority) is PublicationAuthority, 'transition_authority_required', exit_code=7)
        before = TransitionRequest.from_journal(self.journal)
        allowed = self.authority.check(before)
        require(type(allowed) is bool and allowed, 'transition_not_authorized', exit_code=7)
        require(before._raw == TransitionRequest.from_journal(self.journal)._raw, 'transition_authority_input_changed')

    def validate(self):
        report = validate_target(self.journal.plan, self.source, self.target, gates=self.gates,merge_context=self.merge_context)
        require(report.data == self.journal.data['validation'], 'transition_validation_changed')
        actual = external_backup(self.files, self.journal.data['backup'],plan=self.journal.plan)
        require(actual.source_bytes == self.backup.source_bytes, 'transition_backup_changed')
        self.authorize()
        if self.merge_context is not None:
            refreshed=validate_target(self.journal.plan,self.source,self.target,merge_context=self.merge_context)
            require(refreshed.data==self.journal.data['validation'],'transition_validation_changed')
        self.guard()

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


def publish_schema_transition(plan, *, held_lock, backup_descriptor, authority, gates=(), merge_context=None):
    """Called only with the common live policy-bound writer lock and real backup."""
    require(type(held_lock) is HeldProjectLock and type(authority) is PublicationAuthority,
            'transition_native_inputs_required', exit_code=7)
    require(held_lock.record.data['kind'] == 'writer' and held_lock.record.data['command'] == command_for(plan),
            'transition_writer_lock_required', exit_code=7)
    authoring(plan); rename_function()
    files = held_lock._files
    backup = external_backup(files, backup_descriptor,plan=plan)
    source, modes, _ = project_files(files, exclude=('.specroad/locks/project.json',))
    require(source == backup.files, 'transition_source_changed')
    report = validate_target(plan, source, materialized_files(plan, source), gates=tuple(gates),merge_context=merge_context)
    journal = TransitionJournal(jcs({'format_version': format_for(plan), 'state': 'building',
        'transaction_id': held_lock.record.data['transaction_id'], 'project_id': backup.manifest['project_id'],
        'root_identity': list(files.boundary._root_identity), 'plan_bytes_base64': b64(plan.source_bytes),
        'request_id': plan.data['request_id'], 'plan_sha256': plan.sha256, 'backup': backup_descriptor, 'source_modes': modes,
        'published_count': 0, 'images_prepared': False, 'validation': report.data}))
    _held(held_lock, journal)
    request = TransitionRequest.from_journal(journal)
    allowed = authority.check(request)
    require(type(allowed) is bool and allowed and request._raw == TransitionRequest.from_journal(journal)._raw,
            'transition_not_authorized', exit_code=7)
    if merge_context is not None:
        refreshed=validate_target(plan,source,materialized_files(plan,source),merge_context=merge_context)
        require(refreshed.data==report.data,'transition_validation_changed')
    require(not files.journal_entries(), 'transition_recovery_required', exit_code=5)
    require(project_files(files, exclude=('.specroad/locks/project.json',))[:2] == (source, modes), 'transition_source_changed')
    require(external_backup(files, backup_descriptor,plan=plan).source_bytes == backup.source_bytes, 'transition_backup_changed')
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
    session = _Session(held_lock, journal, backup, gates=gates, authority=authority,merge_context=merge_context)
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
    return {**completion_data(session.journal, current=True),
        **({'evidence_currently_rechecked':True} if is_merge(plan) else {})}


def completion_data(journal, *, current=False):
    receipt = request_receipt(journal)
    result = result_object(journal)
    return {**result, **({'validation':journal.data['validation'],'evidence_currently_rechecked':False}
                       if is_merge(journal.plan) else {}),
        'format_version': 'merge-transaction-v1' if is_merge(journal.plan) else 'migration-transaction-v1', 'backup': journal.data['backup'],
        'plan_sha256': journal.plan.sha256, 'journal_sha256': journal.sha256,
        'replayed': not current, 'current_target_verified': current, 'approval_granted': False,
        'receipts': {'transaction': {'path': transaction_receipt_path(journal.data['transaction_id']),
                                    'sha256': sha256(transaction_receipt(journal)).hexdigest()},
                     'request': None if receipt is None else {'path': receipt.path, 'sha256': receipt.sha256}}}
