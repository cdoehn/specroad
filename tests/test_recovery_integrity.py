"""Corrupt diagnosis is an observation, never permission to alter evidence."""
from hashlib import sha256
from unittest.mock import patch
import pytest
from specroad.changes import inspect_recovery, project_lock, ProjectLockError
from specroad.storage.read_only import validate_project_read_only
from support.recovery import pending, tree
from support.publication import options


def row(root, **kwargs):
    return inspect_recovery(root, **kwargs).data['transactions'][0]


def test_invalid_journal_is_corrupt_without_loading_or_writing(tmp_path):
    _, _, _, journal = pending(tmp_path)
    raw = b'{broken'
    (tmp_path / journal.path).write_bytes(raw)
    (tmp_path / 'specroad.json').write_bytes(b'broken model')
    before = tree(tmp_path)
    with patch('specroad.storage.project.ProjectSource.__init__', side_effect=AssertionError('model load')):
        value = inspect_recovery(tmp_path).data
    assert value['corrupt_detected'] and value['normal_access_blocked']
    observed = value['transactions'][0]
    assert observed['state'] == 'corrupt' and observed['observed_state'] is None
    assert observed['journal_sha256'] == sha256(raw).hexdigest()
    assert observed['blockers'][0]['path'] == journal.path
    assert observed['permitted_actions'] == []
    assert tree(tmp_path) == before


def test_missing_active_journal_is_a_concrete_corrupt_blocker(tmp_path):
    _, _, _, journal = pending(tmp_path)
    (tmp_path / journal.path).unlink()
    before = tree(tmp_path)
    observed = row(tmp_path)
    assert observed['state'] == 'corrupt' and observed['journal_sha256'] is None
    assert observed['blockers'][0]['path'] == journal.path
    assert tree(tmp_path) == before


@pytest.mark.parametrize('key', ['before_image_path', 'staging_path'])
@pytest.mark.parametrize('damage', ['missing', 'changed'])
def test_prepared_mandatory_bytes_diagnosed_without_preflight(tmp_path, key, damage):
    _, _, _, journal = pending(tmp_path, 'prepared')
    path = journal.data['files'][0][key]
    if damage == 'missing':
        (tmp_path / path).unlink()
    else:
        (tmp_path / path).write_bytes(b'wrong bytes')
    before = tree(tmp_path)
    observed = row(tmp_path)
    assert observed['state'] == 'corrupt' and observed['observed_state'] == 'prepared'
    assert observed['journal_schema_validated']
    assert observed['blockers'][0]['path'] == path
    assert observed['permitted_actions'] == []
    assert not observed['critical_inputs_verified']
    assert tree(tmp_path) == before


def test_prepared_images_validated_without_authorizing_discard(tmp_path):
    _, _, _, journal = pending(tmp_path, 'prepared')
    before = tree(tmp_path)
    observed = row(tmp_path)
    assert observed['state'] == 'prepared' and observed['critical_inputs_verified']
    assert all(r['status'] == 'verified' for r in observed['critical_resources'])
    assert not observed['base_verified'] and observed['permitted_actions'] == []
    assert tree(tmp_path) == before


def test_incomplete_building_is_not_guessed_to_be_corrupt(tmp_path):
    pending(tmp_path)
    before = tree(tmp_path)
    observed = row(tmp_path)
    assert observed['state'] == 'building' and observed['blockers'] == []
    assert observed['permitted_actions'] == []
    assert tree(tmp_path) == before


def test_corrupt_active_transaction_blocks_normal_model_read_and_writer(tmp_path):
    _, _, preflight, journal = pending(tmp_path)
    (tmp_path / journal.path).write_bytes(b'broken')
    before = tree(tmp_path)
    with patch('specroad.storage.project.ProjectSource.__init__', side_effect=AssertionError('normal load')):
        result = validate_project_read_only(tmp_path, profile_resources=[], core_key='unused').data
    assert result['normal_operation_started'] is False and result['exit_code'] == 5
    with pytest.raises(ProjectLockError):
        with project_lock(tmp_path, **options(preflight)):
            pytest.fail('ordinary writer acquired')
    assert tree(tmp_path) == before


def test_all_mandatory_image_failures_remain_visible(tmp_path):
    _, _, _, journal = pending(tmp_path, 'prepared')
    paths = [e[k] for e in journal.data['files']
             for k in ('before_image_path', 'staging_path') if e[k] is not None]
    for path in paths: (tmp_path / path).unlink()
    before = tree(tmp_path)
    value = row(tmp_path)
    assert {b['path'] for b in value['blockers']} == set(paths)
    assert value['state'] == 'corrupt' and tree(tmp_path) == before
