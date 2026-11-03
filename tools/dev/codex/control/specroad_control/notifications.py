"""Linux inotify, with explicit overflow and watched-directory loss handling."""
import ctypes
import os
from pathlib import Path
import struct
from .errors import ControlError

IN_MODIFY = 0x2
IN_CLOSE_WRITE = 0x8
IN_MOVED_FROM = 0x40
IN_MOVED_TO = 0x80
IN_CREATE = 0x100
IN_DELETE = 0x200
IN_DELETE_SELF = 0x400
IN_MOVE_SELF = 0x800
IN_Q_OVERFLOW = 0x4000
IN_IGNORED = 0x8000
MASK = IN_MODIFY | IN_CLOSE_WRITE | IN_MOVED_FROM | IN_MOVED_TO | IN_CREATE | IN_DELETE | IN_DELETE_SELF | IN_MOVE_SELF
HEADER = struct.Struct("iIII")


class Notifications:
    def __init__(self, directory: Path):
        self.directory = directory
        self.identity = (directory.stat().st_dev, directory.stat().st_ino)
        libc = ctypes.CDLL(None, use_errno=True)
        libc.inotify_init1.argtypes = [ctypes.c_int]
        libc.inotify_init1.restype = ctypes.c_int
        libc.inotify_add_watch.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_uint32]
        libc.inotify_add_watch.restype = ctypes.c_int
        self.fd = libc.inotify_init1(os.O_NONBLOCK | os.O_CLOEXEC)
        if self.fd < 0:
            raise ControlError("inotify_unavailable", "No filesystem event source; polling is not substituted.")
        if libc.inotify_add_watch(self.fd, os.fsencode(directory), MASK) < 0:
            os.close(self.fd)
            raise ControlError("exchange_unavailable", "Cannot watch the configured Exchange.")

    def fileno(self):
        return self.fd

    def consume(self) -> bool:
        changed = False
        while True:
            try:
                raw = os.read(self.fd, 65536)
            except BlockingIOError:
                break
            if not raw:
                break
            offset = 0
            while offset < len(raw):
                if offset + HEADER.size > len(raw):
                    raise ControlError("inotify_protocol_error", "Truncated filesystem event.")
                _watch, mask, _cookie, length = HEADER.unpack_from(raw, offset)
                offset += HEADER.size
                if offset + length > len(raw):
                    raise ControlError("inotify_protocol_error", "Truncated filesystem name.")
                offset += length
                if mask & (IN_DELETE_SELF | IN_MOVE_SELF | IN_IGNORED):
                    raise ControlError("exchange_replaced", "Exchange disappeared or was replaced; manual restart is required.")
                changed = changed or bool(mask & (MASK | IN_Q_OVERFLOW))
        return changed

    def close(self):
        os.close(self.fd)
