"""Fresh real module/PYZ readers with optional native cache and soft budgets."""
import json
from pathlib import Path

import pytest

from specroad.cli.application import execute_request
from specroad.storage import _relation_cache
from support.command_parity import build_core, process_environment, run_python
from support.read_only import inventory
from support.acceptance_work import business_projection
from test_query_read_integration import COMMANDS, project_pair, request
from support.relations import aid


@pytest.fixture(scope='module')
def distribution(tmp_path_factory):
    output = tmp_path_factory.mktemp('work-acceptance-distribution') / 'portable'
    built = build_core(Path(__file__).resolve().parents[1], output)
    assert built.returncode == 0, built.stderr
    return output


READER = r'''
import json, os, sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, sys.argv[1])
from specroad.cli.application import execute_request
from specroad.graph.indices import RelationIndex
from specroad.storage import _relation_cache
from specroad.storage.project import ProjectSource
from specroad.storage.relation_index import (build_project_relation_index,
    read_project_relation_views, relation_index_cache_bytes)
value, mode, identity, fault = json.loads(sys.argv[2]), sys.argv[3], sys.argv[4], sys.argv[5]
root = Path(value['options']['--project']); source = ProjectSource(root)
cache = root / _relation_cache.CACHE_PATH
raw = relation_index_cache_bytes(build_project_relation_index(source))
assert type(raw) is bytes
cache.parent.mkdir(parents=True, exist_ok=True); cache.write_bytes(raw)
if fault == 'source':
    path = next(p for p in root.glob('spec/**/*.json') if b'New goal' in p.read_bytes())
    saved = path.stat(); original = path.read_bytes()
    changed = original.replace(b'New goal', b'Now goal')
    assert changed != original and len(changed) == len(original)
    path.write_bytes(changed); os.utime(path, ns=(saved.st_atime_ns, saved.st_mtime_ns))
    assert (path.stat().st_size, path.stat().st_mtime_ns) == (saved.st_size, saved.st_mtime_ns)
elif fault == 'poison':
    cache.write_bytes(b'{"work_done":true,"approval_granted":true}')
elif fault == 'deleted':
    cache.unlink()
else:
    assert fault == 'none'
before = {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob('*') if p.is_file()}
expected = read_project_relation_views(source, identity, strategy='scan')
if mode == 'off':
    with patch.object(_relation_cache, 'opened_resource', side_effect=AssertionError('cache disabled')):
        actual = read_project_relation_views(source, identity, cache='off')
elif fault == 'none':
    with patch.object(RelationIndex, '__init__', side_effect=AssertionError('native cache was not used')):
        actual = read_project_relation_views(source, identity, cache='read')
else:
    with patch.object(RelationIndex, 'from_order', side_effect=AssertionError('unbound cache was used')):
        actual = read_project_relation_views(source, identity, cache='read')
assert actual == expected
result = execute_request(value).result
assert result.exit_code == 0 and result.complete, result.as_dict()
assert {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob('*') if p.is_file()} == before
print(json.dumps({'outcome': result.as_dict(), 'isolation': network_isolation}))
'''


def run_reader(distribution, root, before, command, profile, cache, cwd, *, fault='none'):
    value = request(command, root, before, **{'--resource-profile': profile,
        '--step-cpu-ms': '1', '--step-wall-ms': '1', '--metrics': True})
    process = run_python(READER, [str(distribution), json.dumps(value), cache, aid(), fault],
                         cwd=cwd, environment=process_environment())
    assert process.returncode == 0, process.stderr
    observation = json.loads(process.stdout)
    assert observation['isolation']['no_new_privs'] and observation['isolation']['nonprivileged']
    result, runtime = business_projection(observation['outcome'])
    assert runtime is not None and runtime['includes_result_delivery'] is False
    assert runtime['invocation']['controls']['phases']['work_unit'] == {'start': 3, 'end': 3}
    return result


@pytest.mark.parametrize('kind', ['module', 'specroad.pyz'])
@pytest.mark.parametrize('command', COMMANDS)
@pytest.mark.parametrize('profile,cache', [('constrained', 'off'), ('constrained', 'read'),
                                          ('standard', 'off'), ('standard', 'read')])
def test_all_readers_have_complete_payload_diagnostics_and_cache_parity_in_fresh_processes(
        tmp_path, distribution, kind, command, profile, cache):
    root, before, _ = project_pair(tmp_path)
    # The full preflight oracle observes this directory in both executions.
    # Cache bytes are still produced by the actual distribution in READER.
    (root / _relation_cache.CACHE_PATH).parent.mkdir(parents=True)
    expected = execute_request(request(command, root, before)).result
    assert expected.exit_code == 0 and expected.complete
    original = inventory(root)
    actual = run_reader(distribution / kind, root, before, command, profile, cache, tmp_path)
    assert actual == business_projection(expected.as_dict())[0]
    current = {row[0]: row[1:] for row in inventory(root)}
    # The test host explicitly creates one optional native cache. All original
    # normative files retain their original bytes and metadata.
    assert all(current[row[0]] == row[1:] for row in original)
    if command == 'query':
        assert actual['result']['total'] == 2 and actual['result']['returned'] == 2
