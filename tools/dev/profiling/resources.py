"""Linux process counters and affinity, without external monitoring processes."""
import os
from pathlib import Path
import resource
import threading
import time


def counters(pid):
    directory = Path('/proc') / str(pid)
    result = {}
    for name in ('io', 'status', 'schedstat', 'stat'):
        try:
            result[name] = (directory / name).read_text()
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            result[name] = None
    return result


def phase_snapshot():
    usage = resource.getrusage(resource.RUSAGE_SELF)
    return dict(time_ns=time.time_ns(), monotonic_ns=time.monotonic_ns(),
                pid=os.getpid(), tid=threading.get_native_id(),
                affinity=sorted(os.sched_getaffinity(0)),
                user_s=usage.ru_utime, system_s=usage.ru_stime,
                maxrss_kib=usage.ru_maxrss, minor_faults=usage.ru_minflt,
                major_faults=usage.ru_majflt, voluntary_switches=usage.ru_nvcsw,
                involuntary_switches=usage.ru_nivcsw, proc=counters(os.getpid()))


def cpu_slots():
    """Prefer separate physical cores before their SMT siblings."""
    first, siblings, seen = [], [], set()
    for cpu in sorted(os.sched_getaffinity(0)):
        topology = Path('/sys/devices/system/cpu') / f'cpu{cpu}' / 'topology'
        try:
            key = tuple((topology / name).read_text().strip()
                        for name in ('physical_package_id', 'core_id'))
        except OSError:
            key = ('unknown', cpu)
        (siblings if key in seen else first).append(cpu)
        seen.add(key)
    return first + siblings


def process_tree(pid):
    """Snapshot just this launcher and descendants, including threaded parents."""
    result, pending = {}, [pid]
    while pending:
        current = pending.pop()
        if current in result:
            continue
        result[current] = counters(current)
        try:
            for task in (Path('/proc') / str(current) / 'task').iterdir():
                try:
                    pending.extend(map(int, (task / 'children').read_text().split()))
                except (FileNotFoundError, ProcessLookupError, PermissionError):
                    pass
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            pass
    return dict(time_ns=time.time_ns(), processes=result)
