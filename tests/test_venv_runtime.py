"""Real no-pip venv startup, base-library binding and isolation contracts."""

import encodings
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

from support.processes import run_core, run_python
from support.virtualenvs import create_no_pip_venv


def test_fresh_venv_finds_base_stdlib_without_loading_site(tmp_path):
    python = create_no_pip_venv(tmp_path / 'env with spaces')
    project = tmp_path / 'project'
    project.mkdir()
    body = """
import encodings, json, os, zlib
import specroad
print(json.dumps({
    'runtime_ok': specroad.check_runtime() is None,
    'stdlib': encodings.__file__,
    'isolated': sys.flags.isolated, 'no_site': sys.flags.no_site,
    'site_loaded': 'site' in sys.modules, 'bytecode': sys.dont_write_bytecode,
    'executable': sys.executable, 'path': os.environ['PATH'],
    'virtual_env': os.environ.get('VIRTUAL_ENV'),
    'extension_ok': zlib.decompress(zlib.compress(b'payload')) == b'payload',
}))
"""
    result = run_core(body, project, python=python, capture=True)
    assert result.returncode == 0, result.stderr
    record = json.loads(result.stdout)
    assert Path(record.pop('stdlib')).resolve() == Path(encodings.__file__).resolve()
    assert Path(record.pop('executable')).absolute() == python.absolute()
    assert record == {'runtime_ok': True, 'isolated': 1, 'no_site': 1,
                      'site_loaded': False, 'bytecode': True, 'path': '',
                      'virtual_env': None, 'extension_ok': True}
    assert list(project.iterdir()) == []


def test_nested_unactivated_venv_retains_real_base_interpreter(tmp_path):
    outer = create_no_pip_venv(tmp_path / 'outer')
    inner = tmp_path / 'inner'
    # Exercise the nested creation used by the CI development environment.
    body = ('import sys;sys.path.insert(0,' + repr(str(Path(__file__).parent)) + ');'
            'from support.virtualenvs import create_no_pip_venv;'
            'create_no_pip_venv(' + repr(str(inner)) + ')')
    created = run_python(['-I', '-B', '-c', body], tmp_path, python=outer)
    assert created.returncode == 0, created.stderr
    python = inner / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    result = run_core('import specroad; assert specroad.check_runtime() is None',
                      tmp_path, python=python)
    assert result.returncode == 0, result.stderr


def test_no_pip_venv_is_real_and_does_not_inherit_system_packages(tmp_path):
    env = tmp_path / 'env'
    python = create_no_pip_venv(env)
    # This independent probe loads site to confirm it really is a venv,
    # without changing the strict production-test helper's startup flags.
    body = """
import importlib.util, json, sys
print(json.dumps({'prefix': sys.prefix, 'base_prefix': sys.base_prefix,
                  'pip': importlib.util.find_spec('pip') is not None,
                  'pytest': importlib.util.find_spec('pytest') is not None}))
"""
    result = run_python(['-I', '-B', '-c', body], tmp_path, python=python, capture=True)
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert Path(data['prefix']).resolve() == env.resolve()
    assert data['prefix'] != data['base_prefix']
    assert data['pip'] is False and data['pytest'] is False


def test_venv_does_not_execute_project_or_site_hooks(tmp_path):
    env = tmp_path / 'env'
    python = create_no_pip_venv(env)
    project = tmp_path / 'project'
    project.mkdir()
    marker = tmp_path / 'executed'
    poison = 'open(' + repr(str(marker)) + ", 'w').write('executed')\n"
    (project / 'sitecustomize.py').write_text(poison)
    sites = list(env.rglob('site-packages'))
    assert sites
    for site in sites:
        (site / 'sitecustomize.py').write_text(poison)
        (site / 'startup.pth').write_text('import pathlib; pathlib.Path(' + repr(str(marker)) + ').touch()\n')
    with patch.dict(os.environ, {'PYTHONPATH': str(project), 'PYTHONHOME': str(project),
                                 'VIRTUAL_ENV': str(project), 'GH_TOKEN': 'must-not-cross'}):
        before = dict(os.environ)
        result = run_core("import specroad, os; assert specroad.check_runtime() is None; "
                          "assert os.environ.get('GH_TOKEN') is None; "
                          "assert sys.flags.isolated == sys.flags.no_site == 1", project, python=python)
        assert result.returncode == 0, result.stderr
        assert dict(os.environ) == before
    assert not marker.exists()
