"""Shared trusted child audit tripwires; original data never selects code.

Kernel network isolation remains separate from observable I/O attempt guards.
"""

READ_GUARD = r'''
import os, sys
_protected_read_attempts = []
_protected_paths = tuple(os.path.realpath(p) for p in _protected_paths)
def _guard_protected_reads(event, args):
    if event in ('open', 'os.listdir', 'os.scandir') and args:
        path = args[0]
        if isinstance(path, (str, bytes)):
            path = os.path.realpath(os.fsdecode(path))
            if any(path == p or path.startswith(p + os.sep) for p in _protected_paths):
                _protected_read_attempts.append(event)
                raise AssertionError('Product accessed a protected acceptance input')
sys.addaudithook(_guard_protected_reads)
'''

CORE_GUARD = r'''
_capability_attempts = []
def _guard_capabilities(event, args):
    if event.startswith('socket.') or event in (
            'subprocess.Popen', 'os.system', 'os.posix_spawn', 'os.exec',
            'os.fork', 'os.forkpty', 'pty.spawn'):
        _capability_attempts.append(event)
        raise AssertionError('Core requested a forbidden process or network capability')
sys.addaudithook(_guard_capabilities)
'''
