"""State-specific critical inputs and conservative, write-free cache policy."""
import os
from hashlib import sha256
from unittest.mock import patch
import pytest
from specroad.changes import (inspect_recovery, inspect_recovery_protection,
    check_cache_removal, RecoveryError)
from support.recovery import pending, tree, discard, recovery_options
from support.receipts import published, finish
from specroad.changes import project_lock
from test_transaction_recovery_rollback import partial_commit
from test_transaction_recovery_completion import crash_after_last_target


def first(root):
    return inspect_recovery(root).data['transactions'][0]


def test_missing_rollback_before_image_is_named_and_preserved_as_missing(tmp_path):
    _, _, journal = partial_commit(tmp_path)
    entry = journal.data['files'][0]
    path = entry['before_image_path']
    (tmp_path / path).unlink()
    before = tree(tmp_path)
    value = first(tmp_path)
    assert value['state'] == 'corrupt'
    assert any(b['path'] == path and b['reason'] == 'recovery_before_image_missing'
               for b in value['blockers'])
    inventory = inspect_recovery_protection(tmp_path).data
    item = next(i for i in inventory['resources'] if i['path'] == path)
    assert item['status'] == 'missing' and item['sha256'] is None
    assert item['cache_removal_allowed'] is False
    assert tree(tmp_path) == before


def test_intact_partial_commit_keeps_rollback_available_without_granting_it(tmp_path):
    _, _, journal = partial_commit(tmp_path)
    value = first(tmp_path)
    assert value['state'] == 'committing' and value['blockers'] == []
    assert value['critical_inputs_verified'] and not value['complete_target_verified']
    assert value['permitted_actions'] == []


def test_last_target_consumed_stage_is_not_misdiagnosed_as_corrupt(tmp_path):
    _, _, _, journal, _ = crash_after_last_target(tmp_path)
    assert not (tmp_path / journal.data['files'][0]['staging_path']).exists()
    before = tree(tmp_path)
    value = first(tmp_path)
    assert value['state'] == 'committing' and value['complete_target_verified']
    assert value['blockers'] == [] and value['critical_inputs_verified']
    assert tree(tmp_path) == before


def test_unrecognized_live_bytes_are_not_inferred_from_journal_hashes(tmp_path):
    _, _, journal = partial_commit(tmp_path)
    path = journal.data['files'][0]['path']
    (tmp_path / path).write_bytes(b'foreign target bytes')
    before = tree(tmp_path)
    value = first(tmp_path)
    assert value['state'] == 'corrupt' and any(b['path'] == path for b in value['blockers'])
    assert tree(tmp_path) == before


def test_missing_committed_receipt_is_not_a_completed_transaction(tmp_path):
    with published(tmp_path) as (_, _, preflight, held, journal):
        completion = finish(preflight, held, journal)
    path = completion.data['receipts']['transaction']['path']
    (tmp_path / path).unlink()
    before = tree(tmp_path)
    value = first(tmp_path)
    assert value['observed_state'] == 'committed' and value['state'] == 'corrupt'
    assert any(b['path'] == path and b['role'] == 'receipt' for b in value['blockers'])
    assert tree(tmp_path) == before


def test_complete_committed_receipts_are_protected_and_verified(tmp_path):
    with published(tmp_path) as (_, _, preflight, held, journal):
        finish(preflight, held, journal)
    before = tree(tmp_path)
    value = first(tmp_path)
    assert value['state'] == 'committed' and value['blockers'] == []
    inventory = inspect_recovery_protection(tmp_path).data
    assert {'request_receipt', 'transaction_receipt'} <= {i['role'] for i in inventory['resources']}
    assert all(not i['cache_removal_allowed'] for i in inventory['resources'])
    assert tree(tmp_path) == before


def test_partial_building_image_is_not_guessed_or_deleted(tmp_path):
    _, _, _, journal = pending(tmp_path)
    path = journal.data['files'][0]['staging_path']
    (tmp_path / path).parent.mkdir(parents=True)
    (tmp_path / path).write_bytes(b'{')
    before = tree(tmp_path)
    value = first(tmp_path)
    assert value['state'] == 'building' and value['blockers'] == []
    item = next(i for i in value['critical_resources'] if i['path'] == path)
    assert item['status'] == 'partial_unverified' and not value['critical_inputs_verified']
    assert tree(tmp_path) == before


def test_full_invalid_building_image_is_detected(tmp_path):
    _, _, _, journal = pending(tmp_path)
    entry = journal.data['files'][0]
    path = tmp_path / entry['staging_path']
    path.parent.mkdir(parents=True)
    path.write_bytes(b'X' * entry['after_size'])
    before = tree(tmp_path)
    value = first(tmp_path)
    assert value['state'] == 'corrupt' and value['blockers'][0]['path'] == entry['staging_path']
    assert tree(tmp_path) == before


@pytest.mark.parametrize('kind', ['symlink', 'hardlink', 'fifo'])
def test_prepared_unsafe_image_is_not_opened_as_recovery_bytes(tmp_path, kind):
    _, _, _, journal = pending(tmp_path, 'prepared')
    path = tmp_path / journal.data['files'][0]['before_image_path']
    outside = tmp_path / 'not-an-image'; outside.write_bytes(path.read_bytes())
    path.unlink()
    if kind == 'symlink': path.symlink_to(outside)
    elif kind == 'hardlink': os.link(outside, path)
    else: os.mkfifo(path)
    value = first(tmp_path)
    assert value['state'] == 'corrupt' and value['blockers'][0]['role'] == 'before_image'
    assert outside.exists() and os.path.lexists(path)


@pytest.mark.parametrize('path', [
    '.specroad', '.specroad/transactions', '.specroad/transactions/t/journal.json',
    '.specroad/transactions/t/before/0.bin', '.specroad/transactions/t/staging/0.bin',
    '.specroad/transactions/receipts/r/transaction.json', '.specroad/recovery/archive/x',
    '.specroad/requests/r.json', '.specroad/cache', '.specroad/cache/../transactions/t'])
def test_recovery_paths_and_parents_are_never_cache_candidates(tmp_path, path):
    pending(tmp_path, 'prepared')
    before = tree(tmp_path)
    with pytest.raises(RecoveryError): check_cache_removal(tmp_path, [path])
    assert tree(tmp_path) == before


def test_cache_check_does_not_delete_even_valid_candidates(tmp_path):
    pending(tmp_path, 'prepared')
    cache = tmp_path / '.specroad/cache/data'; cache.parent.mkdir(); cache.write_bytes(b'cache')
    before = tree(tmp_path)
    value = check_cache_removal(tmp_path, ['.specroad/cache/data']).data
    assert value['selection_checked'] and not value['write_authorized']
    assert value['recheck_at_write_required'] and value['files_deleted'] == 0
    assert value['candidates'][0]['sha256'] == sha256(b'cache').hexdigest()
    assert tree(tmp_path) == before


@pytest.mark.parametrize('kind', ['symlink', 'hardlink', 'parent_symlink', 'directory'])
def test_cache_aliases_cannot_hide_recovery_evidence(tmp_path, kind):
    _, _, _, journal = pending(tmp_path, 'prepared')
    cache = tmp_path / '.specroad/cache'; cache.mkdir()
    image = tmp_path / journal.data['files'][0]['before_image_path']
    path = cache / 'candidate'
    if kind == 'symlink': path.symlink_to(image)
    elif kind == 'hardlink': os.link(image, path)
    elif kind == 'directory': path.mkdir()
    else:
        path.symlink_to(image.parent, target_is_directory=True); path = path / image.name
    before = image.read_bytes()
    with pytest.raises(RecoveryError):
        check_cache_removal(tmp_path, [path.relative_to(tmp_path).as_posix()])
    assert image.read_bytes() == before and os.path.lexists(path)


def test_unknown_transaction_bytes_survive_inventory_with_broken_journal(tmp_path):
    _, _, _, journal = pending(tmp_path, 'prepared')
    (tmp_path / journal.path).write_bytes(b'not JSON')
    unknown = (tmp_path / journal.path).with_name('unknown-proof.bin'); unknown.write_bytes(b'proof')
    before = tree(tmp_path)
    with patch('specroad.storage.project.ProjectSource.__init__', side_effect=AssertionError('model load')):
        value = inspect_recovery_protection(tmp_path).data
    protected = {i['path']: i for i in value['resources']}
    for path, content in before.items():
        if path.startswith('.specroad/transactions/'):
            assert protected[path]['sha256'] == sha256(content).hexdigest()
            assert not protected[path]['cache_removal_allowed']
    assert tree(tmp_path) == before


def test_recovery_audit_is_protected_after_discard(tmp_path):
    _, _, preflight, journal = pending(tmp_path, 'prepared')
    with project_lock(tmp_path, **recovery_options(preflight)) as held:
        result = discard(preflight, journal, held).data
    before = tree(tmp_path)
    value = inspect_recovery_protection(tmp_path).data
    found = {i['path']: i for i in value['resources']}
    for name in ('intent.json', 'journal.before.json', 'completed.json'):
        path = result['audit_path'] + '/' + name
        assert found[path]['role'] == 'recovery_audit' and not found[path]['cache_removal_allowed']
    assert tree(tmp_path) == before


def test_required_image_replacement_during_observation_is_rejected(tmp_path, monkeypatch):
    from specroad.changes import _recovery_integrity as integrity
    _, _, _, journal = pending(tmp_path, 'prepared')
    path = tmp_path / journal.data['files'][0]['before_image_path']
    original = integrity._fingerprint
    def observe(files, logical):
        result = original(files, logical)
        if logical == journal.data['files'][0]['before_image_path']:
            other = path.with_name('swap'); other.write_bytes(path.read_bytes()); other.replace(path)
        return result
    monkeypatch.setattr(integrity, '_fingerprint', observe)
    with pytest.raises(RecoveryError) as error: inspect_recovery(tmp_path)
    assert error.value.reason == 'recovery_status_changed'
