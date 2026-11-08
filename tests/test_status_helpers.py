"""Read-only repository status contracts, using native runtime records."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from uuid import uuid4

import pytest

from verification_support.runtime_history import RuntimeHistory
from test_runtime_history import complete

ROOT = Path(__file__).resolve().parents[1]


def configure_lane(workspace, apply, exchange):
    (apply / 'verification').mkdir(parents=True)
    (apply / 'verification/test_runtime_policy.json').write_text(json.dumps(dict(
        format_version=1, selection='latest_valid_fifth', database='patchharbor-exchange')))
    local = apply / '.patchharbor'
    local.mkdir()
    repo_id = str(uuid4())
    (local / 'id').write_text(repo_id + '\n')
    exchange.mkdir()
    (local / 'config.json').write_text(json.dumps(dict(format_version=1,
        exchange_directory=str(exchange), bundle_suffix='', archive_directory='PatchHarbor-Archive')))
    registry = workspace / 'config/patchharbor/registry.json'
    registry.parent.mkdir(parents=True, exist_ok=True)
    value = json.loads(registry.read_text()) if registry.exists() else dict(format_version=1, repositories={})
    value['repositories'][repo_id] = str(apply)
    registry.write_text(json.dumps(value))
    lock = workspace / 'state/patchharbor/locks' / f'repository-{repo_id}.lock'
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.touch(mode=0o600)
    return lock


def lane(workspace, suffix, seconds):
    dev = workspace / f'specroad-dev{suffix}'
    apply = workspace / f'specroad-apply{suffix}'
    exchange = workspace / f'exchange{suffix}'
    names = ['tools/apply_status.py', 'tools/test_time.py']
    names += [path.relative_to(ROOT).as_posix() for path in (ROOT / 'tools/dev/status').glob('*.py')]
    for name in names:
        target = dev / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / name).read_bytes())
    lock = configure_lane(workspace, apply, exchange)
    started = time.time() - 1
    pairs = {}
    # The current native writer supplies real schema/records. The display's
    # explicit per-lane binding does not require installing a new writer policy.
    storage = workspace / f'storage{suffix}'
    storage.mkdir()
    database = exchange / 'specroad-test-runtime-history.sqlite3'
    with RuntimeHistory(storage, path=database) as store:
        run = store.begin('a' * 64, 2)
        for identity, value in [('merge.slow', seconds), ('other.fast', 1)]:
            pairs[complete(store, run, identity, seconds=value)] = identity
        store.finish(run, 0)
    bundle = apply / 'build/apply-1-local'
    gate = bundle / 'W/gate'
    gate.mkdir(parents=True)
    (gate / 'catalog.json').write_text(json.dumps(dict(catalog_valid=True,
        collection_exit_code=0, source_sha256='a' * 64, nodeid_to_test_id=pairs)))
    (gate / 'nodeids.txt').write_text('\n'.join(pairs) + '\n')
    progress = dict(kind='specroad-apply-progress-v1', format_version=1,
        active_commit_id='W', phase='testing', committed=[], remaining_commit_ids=['W'])
    first = bundle / 'progress-0000.json'
    first.write_text(json.dumps(progress))
    os.utime(first, (started, started))
    progress.update(active_commit_id=None, phase='completed', actual_head='b' * 40,
        remaining_commit_ids=[], committed=[dict(commit_id='W', commit='b' * 40, gate={'tests': len(pairs)})])
    (bundle / 'progress-0001.json').write_text(json.dumps(progress))
    return dev, apply, database, lock


def invoke(dev, name, workspace, *arguments):
    result = subprocess.run([sys.executable, '-I', '-B', str(dev / 'tools' / name), '--json', *arguments],
        cwd=workspace, env={**os.environ, 'XDG_STATE_HOME': str(workspace / 'state'),
                           'XDG_CONFIG_HOME': str(workspace / 'config')},
        stdin=subprocess.DEVNULL, capture_output=True, text=True, check=False)
    return result.returncode, json.loads(result.stdout)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_repository_location_selects_own_status_and_runtime_history(tmp_path):
    for suffix, seconds in [('', 10), ('2', 20)]:
        dev, apply, database, lock = lane(tmp_path, suffix, seconds)
        before = digest(database)
        code, status = invoke(dev, 'apply_status.py', tmp_path)
        assert code == 0 and status['repository'] == str(apply)
        assert status['database'] == str(database) and not status['database_explicit']
        assert status['status'] == 'completed' and status['tests']['passed'] == 2
        code, runtimes = invoke(dev, 'test_time.py', tmp_path)
        assert code == 0 and runtimes['repository'] == str(apply)
        assert runtimes['tests'][0]['duration_ns'] == seconds * 3_000_000_000
        assert digest(database) == before


def test_explicit_paths_filter_current_measurements_without_writes(tmp_path):
    first, apply, one, lock = lane(tmp_path, '', 10)
    second, apply2, two, lock2 = lane(tmp_path, '2', 20)
    archive = tmp_path / 'archive.sqlite3'
    archive.write_bytes(two.read_bytes())
    before = [digest(path) for path in (one, two, archive)]
    code, report = invoke(first, 'test_time.py', tmp_path,
        '--apply-dir', str(apply2), '--database', str(archive),
        '--match', 'MERGE', '--min-seconds', '45', '-n', '1')
    assert code == 0 and report['repository'] == str(apply2)
    assert report['database'] == str(archive) and report['database_explicit']
    assert report['apply_directory_explicit'] and report['matching_measurements'] == 1
    assert [row['test_name'] for row in report['tests']] == ['merge.slow']
    assert report['tests'][0]['duration_ns'] == 60_000_000_000
    assert [digest(path) for path in (one, two, archive)] == before


def test_missing_explicit_source_never_falls_back_or_creates_a_database(tmp_path):
    dev, apply, database, lock = lane(tmp_path, '', 10)
    before = digest(database)
    missing = tmp_path / 'missing'
    for helper in ('apply_status.py', 'test_time.py'):
        for option in ('--database', '--apply-dir'):
            code, report = invoke(dev, helper, tmp_path, option, str(missing))
            assert code == 2 and report['status'] == 'unavailable'
            assert not missing.exists()
            assert digest(database) == before


@pytest.mark.skipif(os.name != 'posix', reason='Native POSIX flock observation')
def test_overview_distinguishes_real_busy_and_free_locks_without_reserving(tmp_path):
    import fcntl
    dev, apply, one, lock = lane(tmp_path, '', 10)
    other, apply2, two, lock2 = lane(tmp_path, '2', 20)
    original = [digest(path) for path in (one, two, lock, lock2)]
    with lock.open('rb') as held:
        fcntl.flock(held.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        code, report = invoke(dev, 'apply_status.py', tmp_path, '--all')
        assert code == 0
        assert [item['availability']['state'] for item in report['repositories']] == ['busy', 'free']
        assert all(item['availability']['reserved'] is False for item in report['repositories'])
        with lock2.open('rb') as free:
            fcntl.flock(free.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    code, report = invoke(dev, 'apply_status.py', tmp_path, '--all')
    assert code == 0 and [item['availability']['state'] for item in report['repositories']] == ['free', 'free']
    assert [digest(path) for path in (one, two, lock, lock2)] == original
