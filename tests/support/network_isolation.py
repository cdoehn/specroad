"""Linux x86-64 test-process network isolation, never installed in the host.

The trusted bootstrap uses only stdlib and the kernel ABI. It must execute in
a fresh child before product imports/threads; collection merely reads a string.
No privilege, external program, network namespace or persistent setting is used.
This is a network boundary, not a general filesystem/process sandbox. Caller
audit tripwires separately detect product attempts at forbidden capabilities.
ABI: https://docs.kernel.org/userspace-api/seccomp_filter.html and Linux UAPI
seccomp.h, filter.h, audit.h, prctl.h, asm/unistd_64.h.
"""

NETWORK_ISOLATION = r'''
import ctypes, errno, os, sys
if sys.platform != 'linux' or os.uname().machine != 'x86_64':
    raise RuntimeError('The acceptance environment must be Linux x86-64')
if os.getuid() == 0 or os.geteuid() == 0:
    raise RuntimeError('The acceptance process must be nonprivileged')
with open('/proc/self/status', encoding='ascii') as _status:
    _capabilities = dict(line.split(':', 1) for line in _status if line.startswith(('CapEff:', 'CapPrm:')))
assert set(_capabilities) == {'CapEff', 'CapPrm'}
assert all(int(value.strip(), 16) == 0 for value in _capabilities.values())

class _SockFilter(ctypes.Structure):
    _fields_ = [('code', ctypes.c_ushort), ('jt', ctypes.c_ubyte),
               ('jf', ctypes.c_ubyte), ('k', ctypes.c_uint32)]
class _SockFprog(ctypes.Structure):
    _fields_ = [('len', ctypes.c_ushort), ('filter', ctypes.POINTER(_SockFilter))]

_libc = ctypes.CDLL(None, use_errno=True)
_libc.syscall.restype = ctypes.c_long
# Check the ABI before the syscall number, including the x32 convention.
_instructions = [(0x20, 0, 0, 4), (0x15, 1, 0, 0xc000003e),
                 (0x06, 0, 0, 0x80000000), (0x20, 0, 0, 0),
                 (0x35, 0, 1, 0x40000000), (0x06, 0, 0, 0x00050001)]
# socket..getsockopt, accept4/recvmmsg/sendmmsg; also prohibit io_uring's
# alternative socket/connection path and ptrace/process-memory escapes.
_denied_syscalls = (*range(41, 56), 101, 288, 299, 307, 310, 311, 425, 426, 427)
for _number in _denied_syscalls:
    _instructions.extend([(0x15, 0, 1, _number), (0x06, 0, 0, 0x00050001)])
_instructions.append((0x06, 0, 0, 0x7fff0000))
_filters = (_SockFilter * len(_instructions))(*(_SockFilter(*i) for i in _instructions))
_program = _SockFprog(len(_filters), _filters)
if _libc.prctl(38, 1, 0, 0, 0) != 0:
    raise OSError(ctypes.get_errno(), 'PR_SET_NO_NEW_PRIVS')
if _libc.prctl(22, 2, ctypes.byref(_program), 0, 0) != 0:
    raise OSError(ctypes.get_errno(), 'PR_SET_SECCOMP')
assert _libc.prctl(39, 0, 0, 0, 0) == 1
assert _libc.prctl(21, 0, 0, 0, 0) == 2
# Real raw syscalls avoid a Python mock proving only its own interception.
# Neither probe sends bytes or names an endpoint; socket creation itself fails.
for _family in (1, 2, 10):
    ctypes.set_errno(0)
    _fd = _libc.syscall(41, _family, 1, 0)
    if _fd >= 0:
        os.close(_fd)
        raise AssertionError('Kernel network filter did not deny socket creation')
    assert ctypes.get_errno() == errno.EPERM
# Invalid arguments would otherwise yield EBADF/EINVAL, not our EPERM.
for _number in (42, 425, 426, 427):
    ctypes.set_errno(0)
    assert _libc.syscall(_number, -1, 0, 0, 0, 0, 0) == -1
    assert ctypes.get_errno() == errno.EPERM
network_isolation = {'method': 'linux-x86_64-seccomp-network-v1',
                     'nonprivileged': True, 'no_new_privs': True,
                     'socket_families_denied': ['unix', 'ipv4', 'ipv6']}
'''
