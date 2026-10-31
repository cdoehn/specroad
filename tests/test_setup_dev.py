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
elif args[:2] == ['python', 'install'] and os.environ.get('CREATE_DURING_INSTALL'):
    env = Path.cwd() / '.venv'
    env.mkdir()
    (env / 'other-process').write_text('preserve')
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


@pytest.mark.parametrize('tool', ['git', 'uv'])
def test_missing_required_tool_fails_before_downloads_or_environment_changes(setup_project, tool):
    root, binary, _, invoke, calls = setup_project
    (binary / tool).unlink()
    result = invoke()
    assert result.returncode == 1
    assert tool.lower() in result.stderr.lower()
    assert not calls() and not (root / '.venv').exists()


@pytest.mark.parametrize('contents', ['', '3.13\n', '3.14\n3.14\n',
                                     '3.14\n--default\n', '3.14\n3.11-dev\n'])
def test_invalid_version_requests_do_not_reach_uv(setup_project, contents):
    root, _, _, invoke, calls = setup_project
    (root / '.python-versions').write_text(contents)
    result = invoke()
    assert result.returncode == 1
    assert '.python-versions' in result.stderr
    assert not calls() and not (root / '.venv').exists()


@pytest.mark.parametrize('state', ['file', 'linked', 'empty', 'missing_python',
                                  'wrong_version', 'foreign_prefix', 'system_python',
                                  'linked_config', 'invalid_reply'])
def test_incompatible_existing_environment_is_preserved_before_uv_runs(setup_project, state):
    root, _, _, invoke, calls = setup_project
    environment = root / '.venv'
    if state == 'file':
        environment.write_bytes(b'not an environment')
    elif state == 'linked':
        target = root / 'foreign'
        target.mkdir()
        (target / 'keep-me').write_bytes(b'do not touch')
        environment.symlink_to(target, target_is_directory=True)
    elif state == 'empty':
        environment.mkdir()
    else:
        virtual_environment(root, version=[3, 13] if state == 'wrong_version' else None,
                            prefix=str(root / 'foreign') if state == 'foreign_prefix' else None,
                            base_prefix=str(environment) if state == 'system_python' else '/base')
        if state == 'missing_python':
            (environment / 'bin/python').unlink()
        elif state == 'linked_config':
            config = environment / 'pyvenv.cfg'
            config.rename(root / 'foreign.cfg')
            config.symlink_to(root / 'foreign.cfg')
        elif state == 'invalid_reply':
            executable(environment / 'bin/python', "print('null')\n")
    before = {str(p.relative_to(root)): p.read_bytes()
              for p in root.rglob('*') if p.is_file()}
    result = invoke()
    assert result.returncode == 1
    assert 'Development setup failed:' in result.stderr
    assert not calls()
    after = {str(p.relative_to(root)): p.read_bytes()
             for p in root.rglob('*') if p.is_file()}
    assert after == before
    if state == 'linked':
        assert environment.is_symlink()


@pytest.mark.parametrize('command,count', [('python install', 1), ('venv', 2), ('pip install', 3)])
def test_tool_failure_prevents_later_steps_and_does_not_claim_success(setup_project, command, count):
    root, _, _, invoke, calls = setup_project
    result = invoke(FAIL_COMMAND=command)
    assert result.returncode == 1
    assert len(calls()) == count
    assert not (root / '.venv/dependencies-installed').exists()
    assert 'Development environment ready:' not in result.stdout
    if command == 'pip install':
        assert (root / '.venv/pyvenv.cfg').is_file()


def test_wrong_created_python_cannot_receive_project_packages(setup_project):
    root, _, _, invoke, calls = setup_project
    result = invoke(CREATED_VERSION='[3, 13]')
    assert result.returncode == 1
    assert len(calls()) == 2
    assert (root / '.venv/pyvenv.cfg').is_file()
    assert not (root / '.venv/dependencies-installed').exists()


def test_inherited_active_environment_cannot_redirect_setup(setup_project):
    root, _, home, invoke, calls = setup_project
    foreign = home / 'another-environment'
    foreign.mkdir()
    marker = foreign / 'keep-me'
    marker.write_bytes(b'foreign environment')
    result = invoke(VIRTUAL_ENV=str(foreign))
    assert result.returncode == 0, result.stderr
    assert marker.read_bytes() == b'foreign environment'
    assert (root / '.venv/dependencies-installed').is_file()
    assert str(foreign) not in repr(calls())


def test_environment_created_during_download_is_not_replaced(setup_project):
    root, _, _, invoke, calls = setup_project
    result = invoke(CREATE_DURING_INSTALL='1')
    assert result.returncode == 1
    assert len(calls()) == 1
    assert (root / '.venv/other-process').read_text() == 'preserve'
    assert not (root / '.venv/dependencies-installed').exists()
