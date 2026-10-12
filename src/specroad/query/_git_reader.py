"""Private local Git execution, storage boundary and raw object verification."""
import errno
from hashlib import new as new_hash
import os
from pathlib import Path
import stat
import subprocess

from ..model.errors import ModelError
from ..security import SafetyViolation


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


class _GitObjectReader:
    """Execution mechanics used only by an explicitly bound Git source."""

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
