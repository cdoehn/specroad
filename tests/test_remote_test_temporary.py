"""Remote scratch space belongs to the run, including supervised child processes."""
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

import execnet

from dev.test_hosts import pool
from support.catalog_project import make_catalog_project
from verification_support.process_environment import test_environment as isolated_environment


def test_remote_preparation_creates_private_separate_scratch_for_each_run(tmp_path, monkeypatch):
    monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path / 'state'))
    monkeypatch.setenv('SPECROAD_TEST_CONTROL_HOME', str(tmp_path / 'control'))
    node = 'tests/test_subject.py::test_subject'
    root = make_catalog_project(tmp_path / 'controller', ids=[node],
                                source='def test_subject():\n    assert True\n')
    host_root = tmp_path / 'host'
    host_root.mkdir(mode=0o700)
    config = tmp_path / 'hosts.json'
    config.write_text(json.dumps(dict(format_version=1, hosts=[dict(
        name='synthetic', ssh='synthetic', directory=str(host_root), workers=1)])))

    class LocalTransport:
        # Replace only the SSH/copy transport. Execute the real preparation,
        # source verification and CPU probe in actual separate interpreters.
        def __init__(self, host):
            pass

        def python(self, script, *, executable=None):
            result = subprocess.run([executable or sys.executable, '-I', '-B', '-'],
                input=script, text=True, env=isolated_environment(os.environ),
                capture_output=True, check=True, timeout=30)
            return json.loads(result.stdout)

        def copy(self, source, target):
            shutil.copytree(source, target, dirs_exist_ok=True)

        def options(self):
            return []

    monkeypatch.setattr(pool, 'Transport', LocalTransport)
    monkeypatch.setattr(pool, 'check', lambda *a, **k: dict(account='a' * 64, hostname='synthetic'))
    monkeypatch.setattr(pool, 'python_path', lambda *a: sys.executable)
    # No rsync is used by this local transport; no external prerequisites.
    monkeypatch.setattr(pool.shutil, 'which', lambda name: '/synthetic/rsync')
    original_environment = {key: os.environ.get(key)
                            for key in ('TMPDIR', 'TMP', 'TEMP', 'PYTEST_DEBUG_TEMPROOT')}
    temporary_roots = []
    for index, live in enumerate((False, True)):
        output = tmp_path / f'output-{index}'
        output.mkdir()
        profile, _ = pool.prepare_pool(root, output, config, {node: node}, None, 1, live=live)
        source = Path(profile['workers']['gw0']['root'])
        temporary = source.parent / 'tmp'
        assert source.parent.parent == host_root / 'runs'
        assert temporary.is_dir() and temporary.stat().st_mode & 0o777 == 0o700
        assert not temporary.is_symlink() and temporary.stat().st_uid == os.getuid()
        assert execnet.XSpec(profile['proxies'][0]).env == {
            key: str(temporary) for key in original_environment}
        assert temporary not in temporary_roots
        (temporary / 'diagnostic').write_text(str(index))
        temporary_roots.append(temporary)
        assert source.is_dir() and not (source / 'tmp').exists()
    assert [(p / 'diagnostic').read_text() for p in temporary_roots] == ['0', '1']
    assert {key: os.environ.get(key) for key in original_environment} == original_environment


def test_proxy_scratch_is_inherited_before_supervisor_worker_and_child_start(tmp_path):
    work, temporary = tmp_path / 'source', tmp_path / 'scratch'
    work.mkdir(mode=0o700)
    temporary.mkdir(mode=0o700)
    supervisor = Path(__file__).resolve().parents[1] / 'tools/dev/test_hosts/attempt_supervisor.py'
    group = execnet.Group()
    try:
        group.makegateway(pool.proxy_gateway('srproxy0', 'popen', sys.executable,
                                            str(work), temporary=temporary))
        worker = group.makegateway('popen//via=srproxy0//python=' +
                                   shlex.join([sys.executable, str(supervisor)]))
        channel = worker.remote_exec('''
import json, os, subprocess, sys, tempfile
from pathlib import Path
names = ('TMPDIR', 'TMP', 'TEMP', 'PYTEST_DEBUG_TEMPROOT')
child_code = "import json,tempfile; from pathlib import Path; " \
             "p=Path(tempfile.mkdtemp()); (p/'data').write_bytes(b'child'); " \
             "print(json.dumps(dict(root=tempfile.gettempdir(), path=str(p))))"
with tempfile.TemporaryDirectory() as scratch:
    path = Path(scratch)
    (path/'data').write_bytes(b'worker')
    child = json.loads(subprocess.check_output([sys.executable, '-I', '-B', '-c', child_code]))
    channel.send(dict(environment={key:os.environ.get(key) for key in names},
                      root=tempfile.gettempdir(), path=str(path), child=child))
''')
        result = channel.receive(timeout=30)
        channel.waitclose(timeout=30)
        assert result['environment'] == {key: str(temporary)
            for key in ('TMPDIR', 'TMP', 'TEMP', 'PYTEST_DEBUG_TEMPROOT')}
        assert result['root'] == result['child']['root'] == str(temporary)
        assert Path(result['path']).parent == temporary
        child = Path(result['child']['path'])
        assert child.parent == temporary and (child / 'data').read_bytes() == b'child'
        assert not Path(result['path']).exists()
    finally:
        group.terminate(timeout=10)
