"""Private local Git execution, storage boundary and raw object verification."""
import errno
from hashlib import new as new_hash
import os
from pathlib import Path
import re
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

    def _run(self, *arguments, input_bytes=None):
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
            standard_input = {'stdin': subprocess.DEVNULL} if input_bytes is None else {'input': input_bytes}
            completed = subprocess.run(argv, cwd=self.root, **standard_input,
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

    def _optional_object(self, kind, oid):
        """Read one exact object, or the native protocol's explicit absence.

        No nonzero exit, stderr, malformed reply or content/hash mismatch is
        absence. The batch request is a full object ID, never a path/revision
        expression. The usual local-only execution and store guards apply.
        """
        if (kind not in ('commit', 'tree', 'blob') or type(oid) is not str
                or not re.fullmatch(r'(?:[0-9a-f]{40}|[0-9a-f]{64})', oid)):
            raise ModelError('git_object_identity_invalid')
        token = oid.encode('ascii')
        output = self._run('cat-file', '--batch', input_bytes=token + b'\n')
        if output == token + b' missing\n':
            return None
        header, separator, body = output.partition(b'\n')
        if not separator or not body.endswith(b'\n'):
            raise ModelError('git_object_response_invalid')
        raw = body[:-1]
        if header != token + b' ' + kind.encode('ascii') + b' ' + str(len(raw)).encode('ascii'):
            raise ModelError('git_object_response_invalid')
        object_header = kind.encode('ascii') + b' ' + str(len(raw)).encode('ascii') + b'\0'
        digest = new_hash('sha1' if len(oid) == 40 else 'sha256',
                          object_header + raw, usedforsecurity=False).hexdigest()
        if digest != oid:
            raise ModelError('git_object_identity_mismatch')
        return raw
