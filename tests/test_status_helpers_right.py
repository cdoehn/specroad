"""Uncertain native state never becomes a false idle or successful measurement."""
import json
import os

import pytest

from verification_support.runtime_history import RuntimeHistory
from test_runtime_history import complete
from test_status_helpers import digest, invoke, lane


@pytest.mark.skipif(os.name != 'posix', reason='Native POSIX flock observation')
@pytest.mark.parametrize('fault', [
    'missing-lock', 'lock-link', 'lock-hardlink', 'registry-json',
    'registry-duplicate', 'registry-version', 'registry-mapping',
    'missing-registry', 'identity-link', 'identity-invalid',
])
def test_uncertain_native_binding_never_reports_free_or_repairs_files(tmp_path, fault):
    dev, apply, database, lock = lane(tmp_path, '', 10)
    registry = tmp_path / 'config/patchharbor/registry.json'
    identity = apply / '.patchharbor/id'
    original = tmp_path / 'preserved'
    original.write_bytes(b'unchanged unrelated file')
    if fault == 'missing-lock':
        lock.unlink()
    elif fault in ('lock-link', 'lock-hardlink'):
        lock.unlink()
        if fault == 'lock-link':
            lock.symlink_to(original)
        else:
            os.link(original, lock)
    elif fault == 'identity-link':
        saved = tmp_path / 'saved-id'
        saved.write_bytes(identity.read_bytes())
        identity.unlink()
        identity.symlink_to(saved)
    elif fault == 'identity-invalid':
        identity.write_text('not-a-repository-id')
    elif fault == 'missing-registry':
        registry.unlink()
    elif fault == 'registry-json':
        registry.write_text('{')
    elif fault == 'registry-duplicate':
        registry.write_text('{"format_version":1,"format_version":1,"repositories":{}}')
    else:
        value = json.loads(registry.read_text())
        if fault == 'registry-version':
            value['format_version'] = True
        else:
            value['repositories'][identity.read_text().strip()] = str(tmp_path / 'elsewhere')
        registry.write_text(json.dumps(value))
    before = digest(database)
    code, report = invoke(dev, 'apply_status.py', tmp_path)
    assert code == 0 and report['availability']['state'] == 'unknown'
    assert report['availability']['reserved'] is False
    assert digest(database) == before and original.read_bytes() == b'unchanged unrelated file'
    if fault == 'missing-lock':
        assert not lock.exists()
    if fault == 'missing-registry':
        assert not registry.exists()


@pytest.mark.skipif(os.name != 'posix', reason='Native POSIX flock observation')
def test_unfinished_progress_is_not_free_even_when_native_lock_is_free(tmp_path):
    dev, apply, database, lock = lane(tmp_path, '', 10)
    progress = apply / 'build/apply-1-local/progress-0001.json'
    value = json.loads(progress.read_text())
    value.update(phase='testing', active_commit_id='W', committed=[], remaining_commit_ids=['W'])
    progress.write_text(json.dumps(value))
    code, report = invoke(dev, 'apply_status.py', tmp_path)
    assert code == 0 and report['availability']['state'] == 'unknown'
    assert report['availability']['reason'] == 'unfinished_progress'


@pytest.mark.skipif(os.name != 'posix', reason='Native POSIX flock observation')
def test_overview_keeps_busy_evidence_when_one_status_source_is_broken(tmp_path):
    import fcntl
    dev, apply, database, lock = lane(tmp_path, '', 10)
    second, apply2, database2, lock2 = lane(tmp_path, '2', 20)
    (apply / 'verification/test_runtime_policy.json').write_text('{')
    with lock.open('rb') as held:
        fcntl.flock(held.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        code, report = invoke(dev, 'apply_status.py', tmp_path, '--all')
    assert code == 0
    first, other = report['repositories']
    assert first['status'] == 'unavailable' and first['availability']['state'] == 'busy'
    assert other['status'] == 'completed' and other['availability']['state'] == 'free'


def test_missing_and_unregistered_targets_are_distinct_and_not_created(tmp_path):
    dev, apply, database, lock = lane(tmp_path, '', 10)
    (apply / '.patchharbor/id').unlink()
    code, report = invoke(dev, 'apply_status.py', tmp_path, '--all')
    assert code == 0
    assert [item['availability']['state'] for item in report['repositories']] == ['unregistered', 'missing']
    assert not (tmp_path / 'specroad-apply2').exists()
    assert not (tmp_path / 'exchange2').exists()


def test_latest_failed_attempt_suppresses_old_slow_success(tmp_path):
    dev, apply, database, lock = lane(tmp_path, '', 10)
    with RuntimeHistory(tmp_path / 'storage', path=database) as store:
        run = store.begin('b' * 64, 2)
        complete(store, run, 'merge.slow', seconds=200, failure='call')
        store.finish(run, 1)
    before = digest(database)
    code, report = invoke(dev, 'test_time.py', tmp_path, '--match', 'merge')
    assert code == 0 and report['status'] == 'no_matches'
    assert report['valid_measurements'] == 1 and report['without_valid_measurement'] == 1
    assert report['tests'] == [] and digest(database) == before


def test_invalid_latest_collection_does_not_fall_back_to_all_history(tmp_path):
    dev, apply, database, lock = lane(tmp_path, '', 10)
    catalog = apply / 'build/apply-1-local/W/gate/catalog.json'
    value = json.loads(catalog.read_text())
    value['catalog_valid'] = False
    catalog.write_text(json.dumps(value))
    code, report = invoke(dev, 'test_time.py', tmp_path)
    assert code == 2 and report['status'] == 'unavailable'
