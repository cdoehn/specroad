"""Exclusive standalone runtime copies using existing guarded file primitives."""
import os
import stat

from . import _contract


class _PreparedRuntime:
    """Own one exclusive copy; use existing descriptor-bound passive reads."""

    def __init__(self, source, workspace):
        from ._files import PassiveFile, directory, require
        parent = directory(workspace.parent, owned=True)
        descriptor = os.open(parent.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        child = None
        try:
            info = os.fstat(descriptor)
            require((info.st_dev, info.st_ino) == parent._root_identity, 'runtime_parent_changed')
            os.mkdir(workspace.name, mode=0o700, dir_fd=descriptor)
            child = os.open(workspace.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                            dir_fd=descriptor)
            info = os.fstat(child)
            self.identity = info.st_dev, info.st_ino
            self.path = workspace / _contract.ARTIFACT_FILENAME
            output = os.open(_contract.ARTIFACT_FILENAME,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=child)
            with os.fdopen(output, 'wb') as stream:
                if stream.write(source.raw) != len(source.raw):
                    raise OSError('incomplete private runtime write')
                stream.flush(); os.fsync(stream.fileno())
            os.fsync(child)
            parent._check_root()
            info = workspace.lstat()
            require((info.st_dev, info.st_ino) == self.identity, 'runtime_workspace_changed')
            self.captured = PassiveFile(self.path, expected_sha256=_contract.ARTIFACT_SHA256,
                                        limit=_contract.MAX_ARTIFACT_BYTES)
        finally:
            if child is not None:
                os.close(child)
            os.close(descriptor)

    def verify(self):
        from ._files import directory, require
        boundary = directory(self.path.parent, owned=True)
        require(boundary._root_identity == self.identity, 'runtime_workspace_changed')
        for path in (self.path.parent, self.path):
            info = path.lstat()
            require(info.st_uid == os.getuid() and not stat.S_IMODE(info.st_mode) & 0o077,
                    'runtime_private_access_changed')
        self.captured.verify_current()
