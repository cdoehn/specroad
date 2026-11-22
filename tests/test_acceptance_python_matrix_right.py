"""20.h.R: complete public read parity, unavailable profiles and unactivated venvs."""
from hashlib import sha256
import json
from pathlib import Path

import pytest
from specroad.cli.application import execute_request
from specroad.storage import _relation_cache
from support.network_isolation import NETWORK_ISOLATION
from support.security_boundary import CORE_GUARD
from support.processes import run_python
from support.portable import files_under
from support.transport_outbound import request, tree
from support.transport_return import offline_export
from test_proposal_basis import project
from test_query_read_integration import COMMANDS, project_pair, request as read_request, arguments
from test_acceptance_python_matrix import (MINORS, matrix_runtimes, matrix_distribution,
    runtime_prefix, fresh_cli, runtime_evidence)


def fresh_request(row, minor, source, cwd, value):
    program = (NETWORK_ISOLATION + runtime_prefix(row, minor) + CORE_GUARD
        + 'import json\nsys.path.insert(0,' + repr(str(source)) + ')\n'
        + 'from specroad.cli.application import execute_request\n'
        + 'result=execute_request(' + repr(value) + ').result\n'
        + 'print(json.dumps(result.as_dict()))\n')
    child = run_python(['-I', '-S', '-B', '-c', program], cwd,
                       python=row['executable'], capture=True)
    assert child.returncode == 0, child.stderr
    return json.loads(child.stdout)


@pytest.mark.parametrize('minor', MINORS)
@pytest.mark.parametrize('command', COMMANDS)
def test_all_readers_have_identical_full_results_in_new_cwds_and_both_invocations(tmp_path, matrix_distribution, matrix_runtimes, minor, command):
    row = matrix_runtimes[minor]
    root, baseline, _ = project_pair(tmp_path)
    (root / _relation_cache.CACHE_PATH).parent.mkdir(parents=True)
    value = read_request(command, root, baseline)
    reference = execute_request(value).result
    assert reference.exit_code == 0
    expected = reference.as_dict()
    protected = files_under(root), files_under(baseline)
    for route, source in zip(('module', 'pyz'), matrix_distribution):
        for invocation in ('cli', 'request'):
            cwd = tmp_path / (route + '-' + invocation); cwd.mkdir()
            (cwd / 'specroad.py').write_text('raise AssertionError("cwd import")\n')
            if invocation == 'cli':
                result = fresh_cli(row, minor, source, cwd, arguments(command, root, baseline))
                assert result.returncode == 0, result.stderr
                actual = json.loads(result.stdout)
            else:
                actual = fresh_request(row, minor, source, cwd, value)
            assert actual == expected
            assert (files_under(root), files_under(baseline)) == protected


@pytest.mark.parametrize('minor', MINORS)
@pytest.mark.parametrize('route', ('module', 'pyz'))
def test_missing_cli_inputs_and_unoffered_python_profile_never_gain_authority(tmp_path, matrix_distribution, matrix_runtimes, minor, route):
    row = matrix_runtimes[minor]; source = matrix_distribution[route == 'pyz']
    root = tmp_path / 'project'; project(root, bundled=True)
    value = request(tmp_path, root, matrix_distribution[1])
    value['options']['--runtime-profile'] = 'python-bundled'
    protected = tree(tmp_path)
    result = offline_export(tmp_path, source, value, python=row['executable'],
        after='assert not any(n.startswith("patchharbor") for n in sys.modules)')
    assert result['code'] == 2, result
    assert tree(tmp_path) == protected and not list((tmp_path / 'output').iterdir())
    program = (NETWORK_ISOLATION + runtime_prefix(row, minor) + CORE_GUARD
        + 'import json\nsys.path.insert(0,' + repr(str(source)) + ')\n'
        + 'from specroad.cli.application import dispatch_result\n'
        + 'results=[(r.exit_code,r.as_dict()) for r in (dispatch_result(args) for args in (["artifact","show"],["command","describe"]))]\n'
        + 'print(json.dumps(results))\n')
    result = run_python(['-I', '-S', '-B', '-c', program], tmp_path,
                        python=row['executable'], capture=True)
    assert result.returncode == 0, result.stderr
    for code, outcome in json.loads(result.stdout):
        assert code == 2 and outcome['diagnostics']
    assert tree(tmp_path) == protected


@pytest.mark.parametrize('minor', MINORS)
@pytest.mark.parametrize('route', ('module', 'pyz'))
def test_unactivated_no_pip_environment_runs_the_same_distribution(tmp_path, matrix_distribution, matrix_runtimes, minor, route, record_property):
    row = matrix_runtimes[minor]; source = matrix_distribution[route == 'pyz']
    environment = tmp_path / 'venv'
    program = 'import venv;venv.EnvBuilder(with_pip=False,symlinks=False).create(' + repr(str(environment)) + ')'
    created = run_python(['-I', '-S', '-B', '-c', program], tmp_path, python=row['executable'], capture=True)
    assert created.returncode == 0, created.stderr
    executable = environment / 'bin/python'
    assert executable.is_file()
    assert not list(environment.glob('lib/python*/site-packages/pip*'))
    unactivated = {**row, 'executable': str(executable), 'sha256': sha256(executable.read_bytes()).hexdigest()}
    cwd = tmp_path / 'unrelated'; cwd.mkdir()
    before = files_under(matrix_distribution[0].parent), files_under(environment)
    result = fresh_cli(unactivated, minor, source, cwd, ['version', '--format=json'])
    assert result.returncode == 0, result.stderr
    version = json.loads(result.stdout)['result']
    assert version['runtime']['python_version'] == row['version']
    evidence = runtime_evidence(unactivated, minor, source, cwd)
    assert evidence['runtime'] == version
    assert (files_under(matrix_distribution[0].parent), files_under(environment)) == before
    assert files_under(cwd) == {}
    record_property('unactivated_python_matrix', json.dumps(evidence, sort_keys=True))
