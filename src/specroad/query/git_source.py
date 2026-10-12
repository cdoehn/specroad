"""Explicit, local-only Git object reads; no checkout or project execution.

This adapter binds raw repository-root paths to one commit. Project/model
interpretation and the shared comparison-source contract belong to its callers.
"""
from dataclasses import dataclass
import errno
from hashlib import new as new_hash
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
from types import MappingProxyType

from ..model.errors import ModelError
from ..model.paths import project_path
from ..security import ProjectBoundary, SafetyViolation


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


def _environment():
    result = {key: value for key, value in os.environ.items() if not key.upper().startswith('GIT_')}
    result.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_SYSTEM=os.devnull,
                  GIT_CONFIG_GLOBAL=os.devnull, GIT_OPTIONAL_LOCKS='0',
                  GIT_NO_REPLACE_OBJECTS='1', GIT_NO_LAZY_FETCH='1',
                  GIT_TERMINAL_PROMPT='0', GIT_PROTOCOL_FROM_USER='0',
                  GIT_ALLOW_PROTOCOL='', GIT_ATTR_NOSYSTEM='1',
                  GIT_LITERAL_PATHSPECS='1')
    return result


def _storage(boundary, expected=None):
    boundary._check_root()
    directory = boundary.root / '.git'
    info = directory.lstat()
    identity = (info.st_dev, info.st_ino)
    if (not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode)
            or getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0)):
        raise SafetyViolation('Git storage must be an ordinary local directory')
    if expected is not None and identity != expected:
        raise SafetyViolation('Git storage changed during use')
    # Ordinary local stores only: no linked worktrees, alternates, symlinks or
    # special files through which the child could escape the explicit root.
    for name in ('commondir', 'info/grafts', 'objects/info/alternates', 'objects/info/http-alternates'):
        if os.path.lexists(directory / name):
            raise SafetyViolation('Indirect Git object stores are not supported')
    def failed(error):
        raise error
    for parent, directories, files in os.walk(directory, followlinks=False, onerror=failed):
        for name in directories + files:
            item = (Path(parent) / name).lstat()
            if (stat.S_ISLNK(item.st_mode)
                    or not (stat.S_ISREG(item.st_mode) or stat.S_ISDIR(item.st_mode))
                    or getattr(item, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0)):
                raise SafetyViolation('Linked or special Git storage is not supported')
    boundary._check_root()
    return identity


@dataclass(frozen=True, init=False)
class GitObjectSource:
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

    def _run(self, *arguments):
        _storage(self._boundary, self._storage_identity)
        argv = [self._executable, '--no-pager', '--no-replace-objects',
                '--no-lazy-fetch', '--no-optional-locks',
                '--git-dir=' + str(self.root / '.git'),
                '--work-tree=' + str(self.root),
                '-c', 'core.hooksPath=' + os.devnull,
                '-c', 'core.fsmonitor=false', '-c', 'gc.auto=0',
                '-c', 'maintenance.auto=false', '-c', 'protocol.allow=never',
                '-c', 'core.warnAmbiguousRefs=true', *arguments]
        try:
            completed = subprocess.run(argv, cwd=self.root, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=_environment(),
                shell=False, check=False)
        except OSError as error:
            _storage(self._boundary, self._storage_identity)
            raise OSError(error.errno or errno.EIO, 'Git execution unavailable') from error
        _storage(self._boundary, self._storage_identity)
        if completed.returncode != 0 or completed.stderr:
            raise ModelError('git_object_read_failed')
        return completed.stdout

    def _object(self, kind, oid):
        raw = self._run('cat-file', kind, oid)
        header = kind.encode('ascii') + b' ' + str(len(raw)).encode('ascii') + b'\0'
        digest = new_hash('sha1' if len(oid) == 40 else 'sha256', header + raw, usedforsecurity=False).hexdigest()
        if digest != oid:
            raise ModelError('git_object_identity_mismatch')
        return raw

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
