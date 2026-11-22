"""Real hostile paths and inert project code under a nonprivileged offline Core."""
import json

import pytest

from support.command_parity import process_environment, run_python
from support.read_only import inventory
from test_acceptance_work_processes import distribution


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


@pytest.mark.parametrize('kind', ['module', 'specroad.pyz'])
@pytest.mark.parametrize('operand', ['../private.txt', '/outside/secret', 'escape',
                                    'C:/secret', 'a/../../private.txt', 'a\\secret'])
def test_native_path_boundary_refuses_hostile_names_without_reading_a_secret(
        tmp_path, distribution, kind, operand):
    root = tmp_path / 'project'; root.mkdir()
    secret = tmp_path / 'private.txt'; secret.write_bytes(b'SYNTHETIC-PRIVATE-CANARY')
    (root / 'allowed.txt').write_bytes(b'allowed native bytes')
    (root / 'escape').symlink_to(secret)
    before = inventory(tmp_path)
    body = ('import sys,json;sys.path.insert(0,' + repr(str(distribution / kind)) + ')\n'
            + '_protected_paths=' + repr((str(secret),)) + '\n' + READ_GUARD + CORE_GUARD + '''
from specroad.security import ProjectBoundary, SafetyViolation
assert 'SPECROAD_ACCEPTANCE_SECRET' not in os.environ
boundary = ProjectBoundary(sys.argv[1])
assert boundary.read_bytes('allowed.txt') == b'allowed native bytes'
try:
    boundary.read_bytes(sys.argv[2])
except SafetyViolation:
    pass
else:
    raise AssertionError('Unsafe input escaped the native boundary')
assert not _protected_read_attempts and not _capability_attempts
print(json.dumps(network_isolation))
''')
    child = run_python(body, [str(root), operand], cwd=tmp_path, environment=process_environment())
    assert child.returncode == 0, child.stderr
    assert json.loads(child.stdout)['socket_families_denied'] == ['unix', 'ipv4', 'ipv6']
    assert b'SYNTHETIC-PRIVATE-CANARY' not in child.stdout + child.stderr
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('kind', ['module', 'specroad.pyz'])
def test_allowed_native_work_ignores_project_python_and_secret_environment(tmp_path, distribution, kind, monkeypatch):
    from test_query_read_integration import project_pair, request
    from specroad.cli.application import execute_request
    root, reference, _ = project_pair(tmp_path)
    for name in ('sitecustomize.py', 'specroad.py', 'socket.py', 'worker.py'):
        (root / name).write_text('raise AssertionError("project code executed")\n')
    secret = tmp_path / 'private.txt'; secret.write_bytes(b'SYNTHETIC-PRIVATE-CANARY')
    monkeypatch.setenv('SPECROAD_ACCEPTANCE_SECRET', 'SYNTHETIC-ENV-CANARY')
    before = inventory(tmp_path)
    value = request('query', root, reference)
    expected = execute_request(value).result.as_dict()
    body = ('import sys,json;sys.path.insert(0,' + repr(str(distribution / kind)) + ')\n'
            + '_protected_paths=' + repr((str(secret),)) + '\n' + READ_GUARD + CORE_GUARD + '''
assert 'SPECROAD_ACCEPTANCE_SECRET' not in os.environ
from specroad.cli.application import execute_request
result = execute_request(json.loads(sys.argv[1])).result
assert result.exit_code == 0 and result.complete
assert not _protected_read_attempts and not _capability_attempts
print(json.dumps(result.as_dict()))
''')
    child = run_python(body, [json.dumps(value)], cwd=root, environment=process_environment())
    assert child.returncode == 0, child.stderr
    assert json.loads(child.stdout) == expected
    assert b'SYNTHETIC-ENV-CANARY' not in child.stdout + child.stderr
    assert inventory(tmp_path) == before
