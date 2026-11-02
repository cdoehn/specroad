"""Compose native project extraction inside one guarded sandbox bootstrap.

Only independently verified input selects bytes. Nested extraction proof keeps
its genuine inodes when the complete project directory is published last.
"""
from contextlib import ExitStack
import os

from ..authoring._bootstrap_io import (BootstrapError, BootstrapTree, STAGING,
    directory, identity, info_at, metadata, rename_function, verify_tree)
from ..authoring._bootstrap_root import BootstrapRoot, root_destination
from ..bundles.extraction import extract_bundle, _check_names, _directories
from ..changes._lock_files import LockFiles
from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError

from ._sandbox_inventory import (COMPLETED, FORMAT, _require, _project_content,
    _project_inventory, _restore)


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
