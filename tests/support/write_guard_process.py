"""Fresh crash children; the named native boundary, not wall time, is the oracle."""
from pathlib import Path

from support.processes import run_python

ROOT = Path(__file__).resolve().parents[2]
TARGETS = {
    '_crash': 'test_write_guard',
    '_sync_crash': 'test_write_guard_right',
    '_snapshot_crash': 'test_write_guard_right',
    '_directory_crash': 'test_write_guard_right',
}


def crash_process(target, root, *arguments):
    # Trusted test-owned call sites only, never product/project-supplied code.
    module = TARGETS[target]
    paths = [str(ROOT / name) for name in ('src', 'tests', 'tools')]
    body = ('import sys; sys.path[:0] = ' + repr(paths) + '\n'
            + 'from ' + module + ' import ' + target + '\n'
            + target + '(*' + repr((str(root), *arguments)) + ')\n')
    return run_python(['-I', '-B', '-c', body], root)
