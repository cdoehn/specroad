"""Read CPU affinity and Linux cgroup quotas; never change host limits."""
import os
from pathlib import Path, PurePosixPath
import re
import sys


def _absolute(value):
    path = PurePosixPath(value)
    if not path.is_absolute() or '..' in path.parts:
        raise ValueError('Invalid cgroup path')
    return path


def _unescape(value):
    return re.sub(r'\\([0-7]{3})', lambda match: chr(int(match[1], 8)), value)


def _optional(path):
    try:
        return path.read_text(encoding='ascii').strip()
    except FileNotFoundError:
        return None


def _quota(directory, version):
    if version == 2:
        value = _optional(directory/'cpu.max')
        if value is None:
            return None
        fields = value.split()
        if len(fields) != 2:
            raise ValueError('Invalid cgroup CPU quota')
        quota, period = fields
    else:
        quota = _optional(directory/'cpu.cfs_quota_us')
        period = _optional(directory/'cpu.cfs_period_us')
        if quota is None and period is None:
            return None
        if quota is None or period is None:
            raise ValueError('Incomplete cgroup CPU quota')
    if not re.fullmatch(r'[0-9]+', period) or int(period) < 1:
        raise ValueError('Invalid cgroup CPU period')
    if quota == ('max' if version == 2 else '-1'):
        return None
    if not re.fullmatch(r'[0-9]+', quota) or int(quota) < 1:
        raise ValueError('Invalid cgroup CPU quota')
    return max(1, int(quota)//int(period))


def cgroup_limits(cgroup=Path('/proc/self/cgroup'), mountinfo=Path('/proc/self/mountinfo')):
    """Include every visible ancestor limit, for unified and CPU v1 mounts."""
    if not sys.platform.startswith('linux'):
        return []
    groups = []
    for line in Path(cgroup).read_text().splitlines():
        fields = line.split(':', 2)
        if len(fields) != 3:
            raise ValueError('Invalid process cgroup membership')
        _, controllers, path = fields
        if not controllers or 'cpu' in controllers.split(','):
            groups.append((2 if not controllers else 1, _absolute(path)))
    mounts = []
    for line in Path(mountinfo).read_text().splitlines():
        left, separator, right = line.partition(' - ')
        detail, fields = left.split(), right.split()
        if not separator or len(fields) < 3 or len(detail) < 6:
            raise ValueError('Invalid process mount information')
        if fields[0] == 'cgroup2':
            version = 2
        elif fields[0] == 'cgroup' and 'cpu' in fields[2].split(','):
            version = 1
        else:
            continue
        mounts.append((version, _absolute(_unescape(detail[3])),
                       Path(_absolute(_unescape(detail[4])))))
    limits = []
    for version, group in groups:
        for mounted_version, mount_root, directory in mounts:
            if mounted_version != version or not group.is_relative_to(mount_root):
                continue
            current = directory/str(group.relative_to(mount_root))
            while True:
                limit = _quota(current, version)
                if limit is not None:
                    limits.append(limit)
                if current == directory:
                    break
                current = current.parent
    return limits


def available_cpus():
    counts = [max(1, os.cpu_count() or 1)]
    if hasattr(os, 'sched_getaffinity'):
        # A present but unreadable host constraint must not silently overbook.
        counts.append(max(1, len(os.sched_getaffinity(0))))
    counts.extend(cgroup_limits())
    return min(counts)
