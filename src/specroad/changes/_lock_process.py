"""Native Linux ownership observations; unknown stays unknown, never PID-only proof.

The host key includes the boot and PID namespace, not a mutable hostname.
Unknown kernel data is represented by null. Acquisition still uses a real kernel
mutex; only explicit recovery may consider an unverifiable owner's risk.
"""
from __future__ import annotations
from hashlib import sha256
import os
import sys
from uuid import UUID
from .lock_values import OwnerIdentity, ProjectLockError


def _read(path):
    with open(path, 'rb') as stream:
        raw = stream.read(65537)
    if len(raw) > 65536:
        raise ValueError('kernel record too large')
    return raw


def _proc_stat(raw, pid):
    # comm can itself contain whitespace, parentheses and newlines.
    left, right = raw.find(b'('), raw.rfind(b')')
    if left < 1 or right <= left or int(raw[:left].strip()) != pid:
        raise ValueError('invalid proc stat')
    fields = raw[right + 1:].split()
    if len(fields) < 20 or fields[0] not in (b'R', b'S', b'D', b'Z', b'T', b't', b'X', b'x', b'K', b'W', b'P', b'I'):
        raise ValueError('invalid proc stat')
    token = fields[19]
    if not token.isdigit() or len(token) > 30:
        raise ValueError('invalid start time')
    return 'linux-startticks:' + token.decode('ascii'), fields[0].decode('ascii')


class LinuxOwnerProbe:
    """Trusted application-owned adapter; never loaded from project metadata."""
    def host_id(self):
        try:
            if not sys.platform.startswith('linux'):
                return None
            boot = str(UUID(_read('/proc/sys/kernel/random/boot_id').decode('ascii').strip()))
            ns = os.stat('/proc/self/ns/pid')  # A deliberate trusted kernel namespace link.
            value = f'{boot}:{ns.st_dev}:{ns.st_ino}'.encode('ascii')
            return 'linux-boot-pidns:' + sha256(value).hexdigest()
        except (OSError, ValueError, UnicodeError):
            return None

    def process(self, pid):
        if type(pid) is not int or not 0 < pid < 2**31:
            raise ProjectLockError('invalid_owner_pid', exit_code=2)
        try:
            token, state = _proc_stat(_read('/proc/' + str(pid) + '/stat'), pid)
            return ('dead' if state in ('Z', 'X', 'x') else 'alive'), token
        except FileNotFoundError:
            # An inaccessible/missing proc mount must not prove a dead process.
            try:
                _proc_stat(_read('/proc/self/stat'), os.getpid())
            except (OSError, ValueError):
                return 'unknown', None
            # hidepid can hide a live process even while our own proc entry is
            # readable. Signal 0 is a nonmutating existence/permission probe.
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return 'absent', None
            except OSError:
                return 'unknown', None
            return 'unknown', None
        except (OSError, ValueError, UnicodeError):
            return 'unknown', None

    def current(self):
        pid = os.getpid()
        state, token = self.process(pid)
        return OwnerIdentity(self.host_id(), pid, token if state == 'alive' else None)
