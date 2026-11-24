"""The live resource observer distinguishes late own forks from foreign load."""
import ast
from copy import deepcopy
import gzip
from pathlib import Path

import pytest


@pytest.fixture
def observer(tmp_path):
    # Load the actual observer functions without preparing or running a workload.
    script = Path(__file__).parents[1] / 'tools/analyzer_benchmark/measured_v2/benchmark.py.gz'
    module = ast.parse(gzip.decompress(script.read_bytes()))
    names = {'process', 'measured_descendant', 'environment'}
    nodes = [node for node in module.body if isinstance(node, ast.FunctionDef) and node.name in names]
    assert {node.name for node in nodes} == names
    proc = tmp_path / 'proc'
    proc.mkdir()
    (proc / 'swaps').write_text('Filename Type Size Used Priority\n')
    (proc / 'loadavg').write_text('0.00 0.00 0.00 1/10 99\n')

    def path(value):
        value = str(value)
        if value.startswith('/proc') or value.startswith('/sys'):
            return tmp_path / value.lstrip('/')
        return Path(value)

    namespace = {'Path': path, 'clock': lambda: 'fixture-observation'}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(script), 'exec'), namespace)

    def add(pid, ppid, start, command=b'python benchmark.py', comm='python'):
        target = proc / str(pid)
        target.mkdir(exist_ok=True)
        fields = ['0'] * 20
        fields[0], fields[1], fields[19] = 'S', str(ppid), str(start)
        (target / 'stat').write_text(str(pid) + ' (' + comm + ') ' + ' '.join(fields))
        (target / 'cmdline').write_bytes(command)
        return namespace['process'](pid)

    return namespace, add


def test_late_own_forks_are_not_competing_but_same_named_foreign_load_is(observer):
    functions, add = observer
    root = add(40, 1, 10, b'time benchmark.py', 'time')
    add(41, 40, 11, b'python parent.py')
    # These processes appear after the old RSS-tree exclusion snapshot.
    add(42, 41, 12, b'python benchmark.py', 'time')
    add(43, 42, 12, b'python benchmark.py')
    add(50, 1, 10, b'python benchmark.py')
    add(51, 50, 12, b'python specroad.analyzers')
    result = functions['environment'](set(), root)
    assert {row['pid'] for row in result['competing_processes']} == {50, 51}
    # Without a measured wrapper (preflight), no benchmark is exempted.
    result = functions['environment'](set())
    assert {row['pid'] for row in result['competing_processes']} == {40, 42, 43, 50, 51}


@pytest.mark.parametrize('fault', [
    'missing-root', 'missing-parent', 'reused-root', 'reused-parent',
    'reused-candidate', 'reparented-candidate', 'reparented-parent',
    'vanished-candidate', 'cycle', 'younger-parent', 'other-root',
])
def test_unproven_or_changed_ancestry_is_never_excluded(observer, fault):
    functions, add = observer
    root = add(40, 1, 10)
    parent = add(41, 40, 11)
    candidate = add(42, 41, 12)
    rows = {row['pid']: deepcopy(row) for row in (root, parent, candidate)}
    calls = {}

    def read(pid):
        calls[pid] = calls.get(pid, 0) + 1
        row = deepcopy(rows.get(pid))
        if fault == 'missing-root' and pid == 40:
            return None
        if fault == 'missing-parent' and pid == 41:
            return None
        if fault == 'vanished-candidate' and pid == 42:
            return None
        if row is None:
            return None
        if fault == 'reused-root' and pid == 40:
            row['start_ticks'] += 1
        if fault == 'reused-parent' and pid == 41 and calls[pid] > 1:
            row['start_ticks'] += 1
        if fault == 'reused-candidate' and pid == 42:
            row['start_ticks'] += 1
        if fault == 'reparented-candidate' and pid == 42:
            row['ppid'] = 1
        if fault == 'reparented-parent' and pid == 41 and calls[pid] > 1:
            row['ppid'] = 1
        if fault == 'cycle' and pid == 41:
            row['ppid'] = 42
        if fault == 'younger-parent' and pid == 41:
            row['start_ticks'] = 13
        return row

    functions['process'] = read
    if fault == 'other-root':
        root = dict(root, pid=99)
    assert functions['measured_descendant'](candidate, root) is False


def test_environment_keeps_a_late_unprovable_process_as_competing(observer):
    functions, add = observer
    root = add(40, 1, 10, b'time parent.py', 'time')
    add(41, 400, 11, b'python benchmark.py')
    result = functions['environment'](set(), root)
    assert result['competing_processes'] == [{'pid': 41, 'comm': 'python'}]
