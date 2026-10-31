"""Exercise the setup CLI with isolated external-tool fixtures, without downloads."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
VERSIONS = ["3.14", "3.13", "3.12", "3.11", "3.10"]


def executable(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!" + sys.executable + "\n" + body, encoding="utf-8")
    path.chmod(0o755)


def virtual_environment(root, version=None, prefix=None, base_prefix="/fixture/base"):
    environment = root / ".venv"
    environment.mkdir()
    (environment / "pyvenv.cfg").write_text("fixture = true\n")
    response = [version or [3, 14], str(environment) if prefix is None else prefix, base_prefix]
    executable(environment / "bin/python", "print(" + repr(json.dumps(response)) + ")\n")
    (environment / "keep-me").write_bytes(b"existing environment")


@pytest.fixture
def setup_project(tmp_path):
    root = tmp_path / "project with spaces $literal"
    (root / "tools").mkdir(parents=True)
    for name in ("tools/setup_dev.py", ".python-versions", "pyproject.toml"):
        shutil.copyfile(ROOT / name, root / name)
    home = tmp_path / "home"
    home.mkdir()
    binary = tmp_path / "bin"
    binary.mkdir()
    log = tmp_path / "commands.jsonl"
    executable(binary / "git", "print('git version fixture')\n")
    uv_source = '''import json, os
from pathlib import Path
import sys
args = sys.argv[1:]
with open(os.environ['SETUP_LOG'], 'a') as output:
    output.write(json.dumps({'args': args, 'cwd': os.getcwd()}) + '\\n')
command = ' '.join(args[:2]) if args[0] != 'venv' else 'venv'
if os.environ.get('FAIL_COMMAND') == command:
    raise SystemExit(23)
if args[0] == 'venv':
    env = Path(args[-1])
    (env / 'bin').mkdir(parents=True)
    (env / 'pyvenv.cfg').write_text('fixture = true\\n')
    version = json.loads(os.environ.get('CREATED_VERSION', '[3, 14]'))
    response = [version, str(env), '/fixture/base']
    python = env / 'bin/python'
    python.write_text('#!' + sys.executable + '\\nprint(' + repr(json.dumps(response)) + ')\\n')
    python.chmod(0o755)
elif args[:2] == ['pip', 'install']:
    (Path.cwd() / '.venv/dependencies-installed').write_text('dev + editable')
elif args[:2] != ['python', 'install']:
    raise SystemExit('unexpected tool command')
'''
    executable(binary / "uv", uv_source)
    environment = dict(os.environ, PATH=str(binary), HOME=str(home), SETUP_LOG=str(log))

    def invoke(*arguments, **overrides):
        return subprocess.run([sys.executable, "-I", "-B", str(root / "tools/setup_dev.py"),
                               *arguments], cwd=tmp_path,
                              env=dict(environment, **overrides), capture_output=True, text=True)

    def calls():
        return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []

    return root, binary, home, invoke, calls


def test_new_setup_installs_all_interpreters_and_one_project_environment(setup_project):
    root, _, _, invoke, calls = setup_project
    result = invoke()
    assert result.returncode == 0, result.stderr
    commands = calls()
    assert all(item['cwd'] == str(root) for item in commands)
    assert [item['args'] for item in commands] == [
        ['python', 'install', *VERSIONS],
        ['venv', '--python', '3.14', '--no-python-downloads', str(root / '.venv')],
        ['pip', 'install', '--python', str(root / '.venv/bin/python'), '--link-mode', 'copy',
         '--group', 'dev', '--editable', '.'],
    ]
    assert (root / '.venv/dependencies-installed').read_text() == 'dev + editable'
    assert not (root / 'uv.lock').exists()


def test_repeated_setup_preserves_existing_environment_and_local_contents(setup_project):
    root, _, _, invoke, calls = setup_project
    virtual_environment(root)
    original_python = (root / '.venv/bin/python').read_bytes()
    for _ in range(2):
        result = invoke()
        assert result.returncode == 0, result.stderr
    assert (root / '.venv/keep-me').read_bytes() == b'existing environment'
    assert (root / '.venv/bin/python').read_bytes() == original_python
    assert [item['args'][:2] for item in calls()] == [
        ['python', 'install'], ['pip', 'install'], ['python', 'install'], ['pip', 'install']]


def test_user_local_uv_is_found_without_changing_shell_configuration(setup_project):
    _, binary, home, invoke, calls = setup_project
    target = home / '.local/bin/uv'
    target.parent.mkdir(parents=True)
    (binary / 'uv').rename(target)
    profile = home / '.profile'
    profile.write_bytes(b'unchanged profile\n')
    result = invoke()
    assert result.returncode == 0, result.stderr
    assert len(calls()) == 3
    assert profile.read_bytes() == b'unchanged profile\n'


@pytest.mark.parametrize('arguments', [('--help',), ('--unknown-option',)])
def test_help_and_invalid_arguments_do_not_begin_setup(setup_project, arguments):
    root, _, _, invoke, calls = setup_project
    result = invoke(*arguments)
    assert result.returncode == (0 if arguments == ('--help',) else 2)
    assert not calls()
    assert not (root / '.venv').exists()
