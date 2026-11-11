"""Real isolated pytest/xdist integration; no system strace dependency for the gate."""
import json
import os
from pathlib import Path

import pytest

from dev.profiling.common import digest, write_json
from dev.profiling.runner import check_observation, execution_command, freeze
from dev.profiling.store import Store, reader
from support.catalog_project import make_catalog_project, execute

SOURCE = '''from pathlib import Path
import pytest

@pytest.fixture(autouse=True)
def setup_effect(request):
    p = Path('build/effects')
    with p.open('a') as stream:
        stream.write('setup:' + request.node.name + '\\n')
    if 'broken' in request.node.name:
        raise ValueError('intentional setup failure')
    yield
    with p.open('a') as stream:
        stream.write('teardown:' + request.node.name + '\\n')

@pytest.mark.parametrize('value', [1, 2], ids=['first', 'second'])
def test_target(value):
    with Path('build/effects').open('a') as stream:
        stream.write('call:' + str(value) + '\\n')

def test_broken():
    raise AssertionError('setup must prevent the test body')

def test_unselected():
    raise AssertionError('unselected test was executed')
'''


@pytest.mark.parametrize('keyword,passed', [('second', True), ('broken', False)])
def test_frozen_selected_profile_has_exact_effects_and_native_outcomes(tmp_path, keyword, passed):
    ids = ['tests/test_subject.py::' + name for name in
           ('test_target[first]', 'test_target[second]', 'test_broken', 'test_unselected')]
    root = make_catalog_project(tmp_path / 'repository', source=SOURCE, ids=ids)
    # The shared fixture copies Python tools; add the profiling data schema.
    schema = Path(__file__).resolve().parents[1] / 'tools/dev/profiling/schema.sql'
    (root / 'tools/dev/profiling/schema.sql').write_bytes(schema.read_bytes())
    directory = root / 'build/run'
    directory.mkdir()
    (directory / 'raw').mkdir()
    snapshot = directory / 'snapshot'
    source, _ = freeze(root, snapshot)
    collection = directory / 'collection-request.json'
    write_json(collection, dict(selectors=['tests/test_subject.py', 'tests/test_subject.py::test_target'],
                                keyword=keyword, marker='', source_sha256=source))
    output = directory / 'collection.json'
    result = execute(snapshot, 'profile_tests.py', ['_collect', '--request', str(collection), '--output', str(output)])
    assert result.returncode == 0, (result.stdout + result.stderr).decode()
    pairs = json.loads(output.read_text())['pairs']
    assert len(pairs) == 1
    assert not (snapshot / 'build/effects').exists()
    database = root / 'build/profiles.sqlite3'
    request = dict(run='run', repository=str(root), snapshot=str(snapshot), directory=str(directory),
                   database=str(database), pairs=pairs, cpus=[min(os.sched_getaffinity(0))],
                   selection_sha256=digest(pairs), source_sha256=source, host_resources=None)
    write_json(directory / 'execution.json', request)
    with Store(database, root, create=True) as store:
        store.create_run('run', root, directory, {})
        store.select('run', pairs, {}, source, digest(pairs), 1)
    command = execution_command(snapshot, directory, request, 1, 1, 'strace')
    # Exercise the native command and plugin directly. Real strace availability
    # remains a prerequisite of the explicit diagnostic CLI, not of Apply CI.
    args = command[command.index(str(snapshot / 'tools/pytest_entry.py')) + 1:]
    result = execute(snapshot, 'pytest_entry.py', args)
    observation = json.loads((directory / 'observations.json').read_text())
    with Store(database, root) as store:
        status = store.finish('run', 'passed' if passed else 'failed', result.returncode,
                              outcomes=observation['test_outcomes'])
    if passed:
        check_observation(observation, pairs, result.returncode, None)
        assert status == 'passed'
        assert (snapshot / 'build/effects').read_text().splitlines() == [
            'setup:test_target[second]', 'call:2', 'teardown:test_target[second]']
    else:
        assert result.returncode != 0 and status == 'failed'
        assert (snapshot / 'build/effects').read_text().splitlines() == ['setup:test_broken']
    with reader(database) as db:
        phases = {row[0] for row in db.execute('SELECT phase FROM phases')}
        assert phases == ({'setup', 'call', 'teardown'} if passed else {'setup', 'teardown'})
        assert db.execute('SELECT COUNT(*) FROM python_functions').fetchone()[0] > 0
    assert not (root / 'build/effects').exists()
