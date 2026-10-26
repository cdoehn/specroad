"""Descriptor-bound Restore storage with exact expected membership after each effect."""
from hashlib import sha256
import os

from ..changes._journal_io import _read
from ..changes._publication_io import replace_bound_image
from ..changes._recovery_evidence import EvidenceRecord, persist_evidence
from ..changes._recovery_bytes import fingerprint_recovery_file
from ..changes._recovery_files import write_recovery_file
from ..security import paths as guards
from ._codec import file_row
from ._inventory import observe
from .values import RestoreError, require


class RestoreStore:
    def __init__(self, held, plan, layout):
        self.held = held
        self.files = held._files
        self.roots = plan.data['inventory']['roots']
        self.expected = {r['path']: dict(r) for r in plan.data['inventory']['entries']}
        self.own = layout['own']
        self.moves = {m['source']: m['target'] for m in layout['binding']['archive_moves']}
        self.moves[layout['active']] = layout['terminal']
        self.targets = layout['target']

    def check(self):
        self.held.check()
        inventory, _ = observe(self.files.boundary, self.roots)
        require(inventory['entries'] == [self.expected[p] for p in sorted(self.expected, key=lambda p: p.encode('utf-8'))],
                'restore_execution_inventory_conflict', exit_code=6)
        self.held.check()

    def _parent(self, path):
        parts = path.split('/')[:-1]
        self.check()
        with self.files.directory(parts, create=True):
            pass
        for i in range(1, len(parts) + 1):
            parent = '/'.join(parts[:i])
            if any(parent == r or parent.startswith(r + '/') for r in self.roots):
                require(self.expected.get(parent, {}).get('kind') in (None, 'missing', 'directory'),
                        'restore_parent_collision', path=parent, exit_code=7)
                self.expected[parent] = {'path': parent, 'kind': 'directory'}
        self.check()

    def create(self, path, raw):
        require(path in self.own and type(raw) is bytes and self.own[path] == raw,
                'restore_unbound_own_file', path=path, exit_code=7)
        require(path not in self.expected, 'restore_own_path_collision', path=path, exit_code=6)
        self._parent(path)
        record = EvidenceRecord(path, raw)
        persist_evidence(self.files, record, write_new=write_recovery_file, before_publish=self.check)
        self.expected[path] = {**file_row(path, raw), 'kind': 'file'}
        self.check()

    def publish(self, staged, path, raw):
        require(self.targets.get(path) == raw and self.own.get(staged) == raw,
                'restore_unbound_publication', path=path, exit_code=7)
        self._parent(path)
        self.check()
        token = fingerprint_recovery_file(self.files, staged)
        require(token is not None and token['sha256'] == sha256(raw).hexdigest()
                and token['size'] == len(raw), 'restore_stage_conflict', path=staged, exit_code=6)
        previous = fingerprint_recovery_file(self.files, path)
        source, target = staged.split('/'), path.split('/')
        with self.files.directory(source[:-1]) as source_dir:
            with self.files.directory(target[:-1]) as target_dir:
                require(source_dir is not None and target_dir is not None, 'restore_parent_changed', exit_code=6)
                def check():
                    self.check()
                    require(fingerprint_recovery_file(self.files, path) == previous,
                            'restore_target_changed', path=path, exit_code=6)
                replace_bound_image(source_dir, source[-1], target_dir, target[-1],
                    size=len(raw), digest=token['sha256'], identity=token['identity'],
                    mode=0o644 if previous is None else previous['mode'],
                    source_changed=lambda: RestoreError('restore_stage_conflict', path=staged, exit_code=6),
                    before_replace=check)
        del self.expected[staged]
        self.expected[path] = {**file_row(path, raw), 'kind': 'file'}
        self.check()

    def remove(self, path):
        self.check()
        expected = self.expected[path]
        require(expected['kind'] == 'file', 'restore_regular_removal_required', path=path, exit_code=7)
        token = fingerprint_recovery_file(self.files, path)
        require(token is not None and (token['size'], token['sha256']) == (expected['size'], expected['sha256']),
                'restore_removal_conflict', path=path, exit_code=6)
        parts = path.split('/')
        with self.files.directory(parts[:-1]) as directory:
            self.check()
            require(fingerprint_recovery_file(self.files, path) == token,
                    'restore_removal_conflict', path=path, exit_code=6)
            os.unlink(parts[-1], dir_fd=directory)
            os.fsync(directory)
        del self.expected[path]
        if path in self.roots:
            self.expected[path] = {'path': path, 'kind': 'missing'}
        self.check()

    def archive(self, path, destination):
        """Move one already completely inventoried entry; never delete a subtree."""
        require(self.moves.get(path) == destination, 'restore_unbound_archive', exit_code=7)
        require(destination not in self.expected, 'restore_archive_collision', exit_code=6)
        self._parent(destination)
        self.check()
        selected = [p for p in self.expected if p == path or p.startswith(path + '/')]
        require(selected and self.expected[path]['kind'] in ('file', 'directory'),
                'restore_archive_original_missing', path=path, exit_code=6)
        source, target = path.split('/'), destination.split('/')
        with self.files.directory(source[:-1]) as source_dir:
            with self.files.directory(target[:-1]) as target_dir:
                self.check()
                require(target[-1] not in os.listdir(target_dir), 'restore_archive_collision', exit_code=6)
                before = os.stat(source[-1], dir_fd=source_dir, follow_symlinks=False)
                guards._regular(before, directory=self.expected[path]['kind'] == 'directory')
                os.rename(source[-1], target[-1], src_dir_fd=source_dir, dst_dir_fd=target_dir)
                os.fsync(source_dir)
                os.fsync(target_dir)
                require(guards._identity(os.stat(target[-1], dir_fd=target_dir, follow_symlinks=False)) == guards._identity(before),
                        'restore_archive_changed', exit_code=6)
        for original in selected:
            row = self.expected.pop(original)
            relocated = destination + original[len(path):]
            self.expected[relocated] = {**row, 'path': relocated}
        self.check()

    def read(self, path):
        parts = path.split('/')
        with self.files.directory(parts[:-1]) as directory:
            require(directory is not None, 'restore_required_bytes_missing', path=path, exit_code=5)
            return _read(directory, parts[-1])
