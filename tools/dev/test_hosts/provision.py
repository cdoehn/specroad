"""Explicit, idempotent preparation. Never called by an Apply gate."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from .environment import environment, digest
from .ssh import Transport


def environment_dir(host, expected):
    return Path(host.directory) / 'environments' / digest(expected)


def python_path(host, expected):
    return str(environment_dir(host, expected) / 'venv/bin/python')


def check(host, expected=None, *, transport=None):
    expected = environment() if expected is None else expected
    remote = transport or Transport(host)
    script = Path(__file__).with_name('environment.py').read_text()
    observed = remote.python(script, executable=sys.executable if host.ssh is None else python_path(host, expected))
    required = ('rsync', 'git', 'ionice') if host.ssh is not None else ('git', 'ionice')
    if observed['environment'] != expected or not all(observed['tools'].get(n) for n in required):
        raise ValueError(host.name + ': environment mismatch or missing rsync/git/ionice; run test-hosts prepare')
    return {**observed, 'host': host.name, 'environment_sha256': digest(expected), 'ready': True}


def prepare(host, *, transport=None, uv=None, non_interactive=False):
    expected = environment()
    if expected['system'] != 'Linux' or expected['implementation'] != 'CPython':
        raise ValueError('Preparation supports CPython on Linux only')
    remote = transport or Transport(host)
    if host.ssh is not None and not non_interactive:
        remote.control('connect')
    # OS installation is a separate, visible native sudo prompt, not a stored password.
    distro = remote.python("import json,platform; from pathlib import Path; print(json.dumps({'machine':platform.machine(),'os':Path('/etc/os-release').read_text()}))")
    entries = dict(line.split('=', 1) for line in distro['os'].splitlines() if '=' in line)
    if entries.get('ID', '').strip('"') not in ('ubuntu', 'debian') or distro['machine'] != expected['machine']:
        raise ValueError('Preparation requires Ubuntu/Debian with the coordinator architecture')
    sudo = ['sudo', *(['-n'] if non_interactive else [])]
    remote.run([*sudo, 'apt-get', 'update'], interactive=not non_interactive, timeout=900)
    remote.run([*sudo, 'apt-get', 'install', '-y', 'rsync', 'git', 'util-linux', 'ca-certificates',
                'python3', 'python3-venv', 'libsqlite3-0', 'libbz2-1.0', 'liblzma5'],
               interactive=not non_interactive, timeout=1800)
    if host.ssh is None:
        return check(host, expected, transport=remote)
    binary = Path(uv or shutil.which('uv') or '')
    if not binary.is_file():
        raise ValueError('Coordinator needs uv (or --uv PATH) to provision an exact managed Python')
    binary = binary.resolve()
    destination = environment_dir(host, expected)
    # mkdir must not follow someone else's symlink or reuse a public directory.
    script = """import json,os,stat
from pathlib import Path
p=Path(%r)
for q in reversed((p,*p.parents)):
    if q.is_symlink(): raise ValueError('linked host directory')
p.mkdir(parents=True,exist_ok=True,mode=0o700)
if p.stat().st_uid!=os.getuid() or p.stat().st_mode & 0o077: raise ValueError('host directory must be private')
print(json.dumps(True))
""" % host.directory
    remote.python(script)
    remote.run(['mkdir', '-p', str(destination)])
    with tempfile.TemporaryDirectory(prefix='specroad-host-setup-') as temporary:
        local = Path(temporary)
        shutil.copyfile(binary, local / 'uv')
        (local / 'requirements.txt').write_text(''.join(f'{name}=={version}\n' for name, version in expected['packages'].items()))
        (local / 'environment.json').write_text(json.dumps(expected, sort_keys=True))
        remote.copy(str(local) + '/', str(destination) + '/')
    remote.run(['chmod', '700', str(destination / 'uv')])
    prefix = ['env', 'UV_PYTHON_INSTALL_DIR=' + str(Path(host.directory) / 'python'),
              'UV_CACHE_DIR=' + str(Path(host.directory) / 'cache'), str(destination / 'uv')]
    remote.run([*prefix, 'python', 'install', expected['python']], timeout=1800)
    if remote.run(['test', '-x', str(destination / 'venv/bin/python')], check=False).returncode:
        remote.run([*prefix, 'venv', '--managed-python', '--python', expected['python'], str(destination / 'venv')], timeout=1800)
    remote.run([*prefix, 'pip', 'sync', '--python', str(destination / 'venv/bin/python'),
                '--only-binary', ':all:', str(destination / 'requirements.txt')], timeout=1800)
    return check(host, expected, transport=remote)
