"""Compose native project extraction inside one guarded sandbox bootstrap.

Only independently verified input selects bytes. Nested extraction proof keeps
its genuine inodes when the complete project directory is published last.
"""
from contextlib import ExitStack
from hashlib import sha256
import os

from ..authoring._bootstrap_io import (BootstrapError, BootstrapTree, STAGING,
    directory, identity, info_at, metadata, rename_function, verify_tree)
from ..authoring._bootstrap_record import _identity, _metadata
from ..authoring._bootstrap_recovery import _read
from ..authoring._bootstrap_root import BootstrapRoot, root_destination
from ..bundles._extraction_record import COMPLETED as PROJECT_COMPLETED, checked_inventory
from ..bundles.extraction import extract_bundle, _check_names, _directories
from ..bundles.manifest import MANIFEST_NAME
from ..changes._lock_files import LockFiles
from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..storage.json_syntax import parse_json_object

COMPLETED = ('.specroad', 'recovery', 'sandbox-bootstrap')
FORMAT = 'specroad-ai-sandbox-bootstrap-v1'
PROJECT_RECORD = '/'.join((*PROJECT_COMPLETED, 'journal.json'))


def _require(condition):
    if not condition:
        raise BootstrapError('sandbox_bootstrap_inventory_invalid')


def _project_content(container):
    return {**container.files, MANIFEST_NAME: container.manifest_bytes}


def _project_inventory(parent, container):
    """Admit the actual native extraction record, never a copied marker."""
    content = _project_content(container)
    directories = _directories(content)
    with directory(parent, ('project',)) as project:
        project_info = os.fstat(project)
        with directory(project, PROJECT_COMPLETED) as receipt:
            receipt_info = os.fstat(receipt)
            limit = 4096 + sum(1024 + 2 * len(p.encode('utf-8')) for p in set(content) | directories)
            raw, _ = _read(receipt, 'journal.json', limit)
        expected = {p: {'size': len(b), 'sha256': sha256(b).hexdigest()} for p, b in content.items()}
        native, _ = checked_inventory(raw, root_identity=identity(project_info),
            stage_identity=identity(receipt_info), inventory=expected)
        content[PROJECT_RECORD] = raw
        directories.add('/'.join(PROJECT_COMPLETED))
        captured = {}
        for path in sorted(set(content) | directories):
            parts = path.split('/')
            with directory(project, parts[:-1]) as fd:
                if path in directories:
                    with directory(fd, (parts[-1],)) as child:
                        value = metadata(os.fstat(child))
                else:
                    observed, value = _read(fd, parts[-1], len(content[path]))
                    _require(observed == content[path])
            if path in native:
                _require(value == native[path])
            captured['project/' + path] = value
        captured['project'] = metadata(project_info)
    return content, directories, captured


class SandboxTree(BootstrapTree):
    def __init__(self, held, function, opening):
        super().__init__(held, function, {}, completed=COMPLETED)
        self.opening = opening

    def prepare_sandbox(self, content, root_created):
        for path in sorted(_directories(content), key=lambda p: (p.count('/'), p)):
            parts = path.split('/')
            with directory(self.fd, parts[:-1]) as parent:
                self.check()
                os.mkdir(parts[-1], mode=0o755, dir_fd=parent)
                self.inventory[path] = metadata(os.stat(parts[-1], dir_fd=parent, follow_symlinks=False))
                os.fsync(parent)
        for path, raw in sorted(content.items()):
            self.write(path, raw)
        def guard():
            self.check()
            self.opening.verify_current()
        target = self.held.boundary.root / STAGING / 'project'
        extract_bundle(self.opening.container.project.source_bytes, target,
            expected_sha256=self.opening.container.project.sha256, _recheck_input=guard)
        guard()
        _, _, project = _project_inventory(self.fd, self.opening.container.project)
        self.inventory.update(project)
        self.units = sorted(p for p in self.inventory if '/' not in p)
        self.units.remove('project'); self.units.append('project')
        self.check()
        verify_tree(self.fd, self.inventory)
        journal = {'format': FORMAT, 'state': 'prepared',
            'source_sha256': self.opening.source.sha256,
            'root_identity': identity(os.fstat(self.held.root_fd)), 'root_created': root_created,
            'stage_identity': self.stage_identity, 'units': self.units,
            'reused_directories': {}, 'entries': self.inventory}
        self.write('journal.json', canonical_json_bytes(journal))
        os.fsync(self.fd)


def _restore(tree, content):
    with directory(tree.held.root_fd, (STAGING,)) as fd:
        tree.fd = os.dup(fd)
    tree.stage_identity = identity(os.fstat(tree.fd))
    # The expected input, not a stored length, bounds the control record.
    project = tree.opening.container.project
    names = set(content) | {'project/' + p for p in _project_content(project)}
    limit = 16384 + sum(4096 + 8 * len(p.encode('utf-8')) for p in names)
    raw, journal_metadata = _read(tree.fd, 'journal.json', limit)
    value = parse_json_object(raw)
    _require(set(value) == {'format', 'state', 'root_identity', 'root_created', 'stage_identity',
        'units', 'reused_directories', 'entries', 'source_sha256'} and canonical_json_bytes(value) == raw)
    _require(value['format'] == FORMAT and value['state'] == 'prepared'
        and value['root_identity'] == identity(os.fstat(tree.held.root_fd))
        and value['stage_identity'] == tree.stage_identity
        and value['source_sha256'] == tree.opening.source.sha256
        and type(value['root_created']) is bool and value['reused_directories'] == {})
    staged = info_at(tree.fd, 'project') is not None
    published = info_at(tree.held.root_fd, 'project') is not None
    _require(staged != published)
    project_content, project_dirs, _ = _project_inventory(
        tree.fd if staged else tree.held.root_fd, project)
    expected = {**content, **{'project/' + p: b for p, b in project_content.items()}}
    directories = _directories(content) | {'project'} | {'project/' + p for p in project_dirs}
    entries = value['entries']
    _require(type(entries) is dict and set(entries) == set(expected) | directories)
    tokens = {_identity(value['root_identity']), _identity(value['stage_identity'])}
    _require(len(tokens) == 2)
    for path, item in entries.items():
        token = _metadata(item, 'directory' if path in directories else 'file')
        _require(token not in tokens)
        tokens.add(token)
        if path in expected:
            _require(item['size'] == len(expected[path]) and item['sha256'] == sha256(expected[path]).hexdigest())
    units = sorted(p for p in entries if '/' not in p)
    units.remove('project'); units.append('project')
    _require(value['units'] == units and _identity(journal_metadata['identity']) not in tokens)
    tree.inventory, tree.units = entries, units
    tree.inventory['journal.json'] = journal_metadata
    tree.checked_locations()


def publish_sandbox(opening):
    parent, target = root_destination(opening.output, invalid_reason='sandbox_target_invalid')
    _require(parent == opening.output_parent.root and target == opening.output)
    content = {'runtime/specroad.pyz': opening.container.payloads['runtime/specroad.pyz'],
        'runtime/patchharbor-1.8.0.pyz': opening.pyz.raw,
        'reference/outbound.zip': opening.source.raw, 'reference/result.zip': opening.reference.raw}
    function = rename_function()
    tree = None
    recovering = False
    with ExitStack() as stack:
        parent_held = stack.enter_context(LockFiles(parent)); parent_held.acquire()
        _require(parent_held.boundary._root_identity == opening.output_parent._root_identity)
        destination = BootstrapRoot(parent_held, target)
        _require((destination.current is None) == (opening.output_boundary is None))
        opening.verify_current()
        try:
            if destination.current is None:
                destination.create()
            held = destination.acquire(stack)
            opening.effects.update(sandbox_root=str(target), bootstrap_state='publishing')
            def guard():
                parent_held.require_held()
                _check_names(held, tree)
                opening.verify_current()
            if info_at(held.root_fd, STAGING) is not None:
                recovering = True
                tree = SandboxTree(held, function, opening)
                try:
                    _restore(tree, content)
                except (ModelError, ValueError, TypeError, KeyError, RecursionError) as error:
                    raise BootstrapError('sandbox_bootstrap_inventory_invalid') from error
            else:
                if os.listdir(held.root_fd):
                    raise BootstrapError('sandbox_target_not_empty')
                tree = SandboxTree(held, function, opening)
                tree.create()
                tree.prepare_sandbox(content, destination.created)
            guard()
            tree.publish(guard=guard)
            tree.cleanup()
            guard()
        except BaseException as original:
            # Recovery must never use a partially decoded journal for cleanup.
            if recovering:
                opening.effects['bootstrap_state'] = 'recovery_required'
                raise
            try:
                if tree is not None or destination.created:
                    destination.rollback(tree, original)
            except BaseException:
                opening.effects['bootstrap_state'] = 'recovery_required'
                raise
            opening.effects['bootstrap_state'] = ('complete' if tree is not None and tree.committed
                else 'rolled_back' if tree is not None else 'not_started')
            if not os.path.lexists(target):
                opening.effects['sandbox_root'] = None
            raise
        finally:
            if tree is not None:
                tree.close()
    payload = {**content, **{'project/' + p: b for p, b in _project_content(opening.container.project).items()}}
    opening.effects['bootstrap_state'] = 'complete'
    directories = {p.rsplit('/', 1)[0] for p in payload if '/' in p}
    directories |= {p.split('/')[0] for p in payload}
    for name in tuple(directories):
        parts = name.split('/')
        directories.update('/'.join(parts[:n]) for n in range(1, len(parts)))
    return payload, directories
