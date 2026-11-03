"""Validate ownership, path stability and Linux peer identity of Codex's socket.

Allows the existing Codex-managed symlink without allowing arbitrary links.
This helper never starts a daemon or changes file permissions.
"""
import os
from pathlib import Path
import re
import socket
import stat
import struct

from .errors import ControlError

DAEMON_TEMP_ROOT = Path("/tmp")

def trusted_daemon_socket(path: Path) -> Path:
    """Accept the Codex daemon's owned, private link into its /tmp directory.

    Never follow an arbitrary symlink, even if it eventually resolves to an
    owned socket. The Codex-managed link lives in a private control directory
    and points to a private socket in /tmp/codex-daemon-<uid>/.
    """
    try:
        link = path.lstat()
        if stat.S_ISSOCK(link.st_mode) and link.st_uid == os.getuid():
            return path
        parent = path.parent.lstat()
        if (not stat.S_ISLNK(link.st_mode) or link.st_uid != os.getuid()
                or not stat.S_ISDIR(parent.st_mode) or parent.st_uid != os.getuid()
                or parent.st_mode & 0o077):
            raise ValueError('untrusted link or its directory')
        target = Path(os.readlink(path))
        root = DAEMON_TEMP_ROOT
        expected_parent = root / ('codex-daemon-' + str(os.getuid()))
        if (not target.is_absolute() or target.parent != expected_parent
                or re.fullmatch(r'[0-9a-f]{64}', target.name) is None):
            raise ValueError('outside Codex daemon directory')
        root_info = root.lstat()
        if (not stat.S_ISDIR(root_info.st_mode)
                or not ((root_info.st_uid == 0 and root_info.st_mode & stat.S_ISVTX)
                        or (root_info.st_uid == os.getuid() and not root_info.st_mode & 0o077))):
            raise ValueError('untrusted temporary directory')
        directory = expected_parent.lstat()
        if (not stat.S_ISDIR(directory.st_mode) or directory.st_uid != os.getuid()
                or directory.st_mode & 0o077):
            raise ValueError('untrusted daemon directory')
        actual = target.lstat()  # Do not follow any further symlinks.
        if (not stat.S_ISSOCK(actual.st_mode) or actual.st_uid != os.getuid()
                or actual.st_mode & 0o077):
            raise ValueError('untrusted socket')
        return target
    except FileNotFoundError:
        raise ControlError('codex_daemon_unavailable', 'Codex daemon socket or target is absent.') from None
    except (OSError, ValueError):
        raise ControlError('codex_socket_untrusted', 'Codex daemon socket link or target is not private and owned.') from None


def identity(info):
    return (info.st_dev, info.st_ino, info.st_uid, stat.S_IFMT(info.st_mode))


def socket_identity(path):
    try:
        return identity(path.lstat())
    except OSError:
        return None


def connected_peer_uid(sock):
    """Linux kernel's connected-peer credential, not a caller-provided PID."""
    try:
        data = sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize('3i'))
        return struct.unpack('3i', data)[1]
    except (AttributeError, ValueError, OSError, struct.error):
        raise ControlError("codex_socket_untrusted", "Cannot verify the Codex daemon peer credentials.") from None
