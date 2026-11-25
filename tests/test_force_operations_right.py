"""21.e2.R: exact original identities, closed proof groups and noninherited authority."""
from hashlib import sha256
import json
import os
import pytest

from specroad.changes.force_operational_receipts import read_force_attempt
from specroad.model.errors import ModelError
from specroad.changes._lock_files import LockFiles
from specroad.changes.force_operational_receipts import completed_attempts
from support.force_cases import fixture, replacement, files
from test_force_operations import operational, apply, marker


@pytest.mark.parametrize('change', ['inode', 'mode'])
def test_equal_original_bytes_do_not_hide_replaced_identity_or_mode(tmp_path, change):
    root, path = fixture(tmp_path / 'project'); old, raw, _ = marker(root)
    plan = operational(replacement(root, path, b'new bytes'))
    result = apply(root, plan)
    original = root / old
    if change == 'inode':
        other = original.with_name('replacement'); other.write_bytes(raw); os.replace(other, original)
    else: original.chmod(original.stat().st_mode ^ 0o100)
    before = files(root)
    with pytest.raises(ModelError) as error:
        read_force_attempt(root, result['completion']['transaction_id'], expected_project_id=plan.data['project_id'])
    assert error.value.exit_code == 6 and files(root) == before
    with pytest.raises(ModelError): apply(root, plan)
    assert files(root) == before


@pytest.mark.parametrize('file', ['before.json', 'owner.json', 'complete.json', 'receipts/request.json'])
def test_corrupt_original_proof_cannot_certify_success(tmp_path, file):
    root, path = fixture(tmp_path / 'project'); marker(root)
    plan = operational(replacement(root, path, b'new bytes')); result = apply(root, plan)
    tx = result['completion']['transaction_id']
    proof = root / '.specroad/write-state/force-attempts' / tx / file
    proof.write_bytes(b'{}')
    before = files(root)
    with pytest.raises((ModelError, ValueError)):
        read_force_attempt(root, tx, expected_project_id=plan.data['project_id'])
    assert files(root) == before


@pytest.mark.parametrize('extra', ['unknown.json', 'receipts/unknown.json'])
def test_extra_attempt_file_cannot_be_silently_ignored(tmp_path, extra):
    root, path = fixture(tmp_path / 'project'); marker(root)
    plan = operational(replacement(root, path, b'new bytes')); result = apply(root, plan)
    tx = result['completion']['transaction_id']
    (root / '.specroad/write-state/force-attempts' / tx / extra).write_bytes(b'{}')
    before = files(root)
    with pytest.raises(ModelError): read_force_attempt(root, tx, expected_project_id=plan.data['project_id'])
    assert files(root) == before


def test_passive_portable_proof_does_not_claim_current_old_source(tmp_path):
    from specroad.changes.force_receipts import receipt_group
    from specroad.changes.force_history import read_force_group
    root, path = fixture(tmp_path / 'project'); old, _, _ = marker(root)
    plan = operational(replacement(root, path, b'new bytes')); result = apply(root, plan)
    tx = result['completion']['transaction_id']; prefix = '.specroad/write-state/force-attempts/' + tx
    with LockFiles(root) as current:
        write = completed_attempts(current, check_originals=False)[0]
    group = receipt_group(write)
    for name in ('before.json', 'owner.json', 'complete.json'): group[prefix + '/' + name] = (root / prefix / name).read_bytes()
    (root / old).write_bytes(b'later observation')
    history = read_force_group(group, plan.data['project_id']).data
    assert history['force']['used'] and not history['approval_granted'] and not history['write_authorized']
    with pytest.raises(ModelError): read_force_attempt(root, tx, expected_project_id=plan.data['project_id'])


@pytest.mark.parametrize('which', ['inode', 'bytes'])
def test_change_during_original_proof_read_is_detected(tmp_path, monkeypatch, which):
    import specroad.changes.force_operational_receipts as reader
    root, path = fixture(tmp_path / 'project'); marker(root)
    plan = operational(replacement(root, path, b'new bytes')); result = apply(root, plan)
    tx = result['completion']['transaction_id']; suffix = '.specroad/write-state/force-attempts/' + tx + '/before.json'
    real = reader._read_path; count = 0
    def changed(fileset, path, **kwargs):
        nonlocal count
        data = real(fileset, path, **kwargs)
        if path == suffix:
            count += 1
            if count == 2:
                original = root / path
                other = original.with_name('replacement'); other.write_bytes(data if which == 'inode' else b'{}')
                os.replace(other, original)
        return data
    monkeypatch.setattr(reader, '_read_path', changed)
    with pytest.raises((ModelError, ValueError)):
        read_force_attempt(root, tx, expected_project_id=plan.data['project_id'])
    assert (root / path).read_bytes() == b'new bytes'


def test_missing_attempt_is_structured_not_success(tmp_path):
    root, _ = fixture(tmp_path / 'project'); before = files(root)
    with pytest.raises(ModelError) as error:
        read_force_attempt(root, 'not-an-existing-attempt', expected_project_id='test-project')
    assert error.value.exit_code == 6 and files(root) == before
