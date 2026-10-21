"""Explicit, local-only Git object reads; no checkout or project execution.

This adapter binds raw repository-root paths to one commit. Project/model
interpretation and the shared comparison-source contract belong to its callers.
"""
from dataclasses import dataclass
import errno
import os
from pathlib import Path
import re
import shutil
from types import MappingProxyType

from ..model.errors import ModelError
from ..model.paths import project_path
from ..security import ProjectBoundary, SafetyViolation
from ._git_reader import _GitObjectReader, _environment, _storage, subprocess


def _reference(value):
    if (type(value) is not str or not re.fullmatch(r'[\w.+@/-]+', value)
            or value.startswith('-') or '..' in value
            or any(not part or part.startswith('.') or part.endswith(('.', '.lock'))
                   for part in value.split('/'))):
        raise ModelError('git_reference_required')
    return value


def _oid(raw, *, width=None):
    pattern = rb'(?:[0-9a-f]{40}|[0-9a-f]{64})' if width is None else rb'[0-9a-f]{' + str(width).encode() + rb'}'
    if not re.fullmatch(pattern, raw):
        raise ModelError('git_object_identity_invalid')
    return raw.decode('ascii')


@dataclass(frozen=True, init=False)
class GitObjectSource(_GitObjectReader):
    """Raw owned bytes from one resolved commit, never current-tree fallback.

    Construct only for an explicitly requested Git comparison. Importing the
    module and using other query operations do not discover or execute Git.
    """
    root: Path
    commit_id: str
    paths: tuple
    _boundary: ProjectBoundary
    _storage_identity: tuple
    _executable: str
    _entries: object

    def __init__(self, root, reference):
        reference = _reference(reference)
        boundary = ProjectBoundary(root)
        executable = shutil.which('git', path=os.defpath)
        if executable is None or not Path(executable).is_absolute():
            raise OSError(errno.ENOENT, 'A trusted system Git executable is required')
        identity = _storage(boundary)
        object.__setattr__(self, 'root', boundary.root)
        object.__setattr__(self, '_boundary', boundary)
        object.__setattr__(self, '_storage_identity', identity)
        object.__setattr__(self, '_executable', executable)
        raw = self._run('rev-parse', '--verify', '--end-of-options', reference + '^{commit}')
        commit = _oid(raw.removesuffix(b'\n'))
        object.__setattr__(self, 'commit_id', commit)
        commit_bytes = self._object('commit', commit)
        first = commit_bytes.split(b'\n', 1)[0]
        if not first.startswith(b'tree '):
            raise ModelError('git_commit_tree_missing')
        tree = _oid(first[5:], width=len(commit))
        root_tree = self._object('tree', tree)
        raw = self._run('ls-tree', '-r', '-t', '-z', '--full-tree', commit)
        if raw and not raw.endswith(b'\0'):
            raise ModelError('git_tree_inventory_invalid')
        entries = {}
        trees = {'': tree}
        tree_rows = {}
        for row in raw.split(b'\0')[:-1]:
            try:
                metadata, path = row.split(b'\t', 1)
                mode, kind, token = metadata.split(b' ')
                path = project_path(path.decode('utf-8'))
            except (ValueError, UnicodeError) as error:
                raise ModelError('git_tree_inventory_invalid') from error
            oid = _oid(token, width=len(commit))
            if path in entries:
                raise ModelError('git_tree_inventory_invalid')
            if mode == b'040000' and kind == b'tree':
                trees[path] = oid
            elif (mode, kind) not in ((b'100644', b'blob'), (b'100755', b'blob'),
                                     (b'120000', b'blob'), (b'160000', b'commit')):
                raise ModelError('git_tree_inventory_invalid')
            entries[path] = (mode, kind, oid)
            parent, _, name = path.rpartition('/')
            tree_rows.setdefault(parent, []).append(
                mode.lstrip(b'0') + b' ' + name.encode('utf-8') + b'\0' + bytes.fromhex(oid))
        if set(tree_rows) - set(trees):
            raise ModelError('git_tree_inventory_invalid')
        for path, oid in sorted(trees.items()):
            tree_bytes = root_tree if path == '' else self._object('tree', oid)
            if b''.join(tree_rows.get(path, ())) != tree_bytes:
                raise ModelError('git_tree_inventory_mismatch')
        object.__setattr__(self, '_entries', MappingProxyType(entries))
        object.__setattr__(self, 'paths', tuple(sorted(path for path, entry in entries.items() if entry[1] != b'tree')))

    def read_bytes(self, path):
        path = project_path(path)
        if path not in self._entries:
            raise ModelError('git_path_missing', path=path)
        mode, kind, oid = self._entries[path]
        if mode not in (b'100644', b'100755') or kind != b'blob':
            raise SafetyViolation('Git input must be a regular blob')
        for index in range(1, len(path.split('/'))):
            parent = '/'.join(path.split('/')[:index])
            if parent + '/specroad.json' in self._entries:
                raise SafetyViolation('Nested project roots cannot be combined')
        return self._object('blob', oid)

    def read_optional_bytes(self, path):
        """Observe an existing binding's path, including missing Git objects.

        The original constructor validated the complete immutable tree. Recheck
        the commit and the requested path's trees before using that inventory.
        A missing object/path yields None; unsafe paths and unreadable/corrupt
        objects remain errors. This does not relax read_bytes or construction.
        """
        path = project_path(path)
        commit = self._optional_object('commit', self.commit_id)
        if commit is None:
            return None
        first = commit.split(b'\n', 1)[0]
        if not first.startswith(b'tree '):
            raise ModelError('git_commit_tree_missing')
        tree = _oid(first[5:], width=len(self.commit_id))
        if self._optional_object('tree', tree) is None:
            return None
        parts = path.split('/')
        for index in range(1, len(parts)):
            parent = '/'.join(parts[:index])
            entry = self._entries.get(parent)
            if entry is None:
                return None
            mode, kind, oid = entry
            if mode != b'040000' or kind != b'tree':
                raise SafetyViolation('Git path parents must be ordinary trees')
            if parent + '/specroad.json' in self._entries:
                raise SafetyViolation('Nested project roots cannot be combined')
            if self._optional_object('tree', oid) is None:
                return None
        entry = self._entries.get(path)
        if entry is None:
            return None
        mode, kind, oid = entry
        if mode not in (b'100644', b'100755') or kind != b'blob':
            raise SafetyViolation('Git input must be a regular blob')
        return self._optional_object('blob', oid)
