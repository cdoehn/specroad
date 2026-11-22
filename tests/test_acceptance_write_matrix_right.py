"""Foreign state, lost images and repeated original receipts across real clients."""
import json
import pytest

from specroad.changes import guarded_write, schema_transition, inspect_write_state, read_guarded_completion
from specroad.changes.receipt_values import transaction_receipt_path, request_receipt_path
from specroad.changes.write_guard_values import validate_transaction, MARKER_PATH
from specroad.changes.normal_access import require_normal_access
from support.read_only import inventory, no_write_attempts
from test_acceptance_write_matrix import client, points, CLIENTS
from test_snapshot_guard import FAILURES


@pytest.mark.parametrize('kind', CLIENTS)
@pytest.mark.parametrize('damage', ['foreign_lock', 'marker_bytes', 'lost_image', 'foreign_guard'])
def test_foreign_or_missing_state_is_retained_without_repair(tmp_path, monkeypatch, kind, damage):
    root, before, target, request, transaction, project, run = client(tmp_path / 'case', kind)
    point = points('staged', before, target, request)[0]
    observed = []
    def corrupt(event):
        if event != point: return
        observed.append(event)
        if damage == 'foreign_lock':
            path = root / '.specroad/locks/project.json'; path.write_bytes(b'foreign owner record')
        elif damage == 'marker_bytes':
            path = root / MARKER_PATH; path.write_bytes(b'foreign guard bytes')
        elif damage == 'lost_image':
            path = root / ('.specroad/write-state/staging/' + point.split(':')[1] + '.bin'); path.unlink()
        else:
            path = root / '.specroad/write-state/foreign.bin'; path.write_bytes(b'foreign user bytes')
    with monkeypatch.context() as patch:
        patch.setattr(guarded_write, '_checkpoint', corrupt)
        patch.setattr(schema_transition, '_checkpoint', corrupt)
        with pytest.raises(FAILURES): run()
    assert observed == [point]
    retained = inventory(root)
    with no_write_attempts():
        assert inspect_write_state(root, expected_project_id=project)['state'] != 'clean'
        with pytest.raises(FAILURES): require_normal_access(root)
        with pytest.raises(FAILURES): read_guarded_completion(root, transaction, expected_project_id=project)
    assert inventory(root) == retained
    for path, raw in before.items(): assert (root / path).read_bytes() == raw
    for path in target.keys() - before.keys(): assert not (root / path).exists()


@pytest.mark.parametrize('kind', CLIENTS)
def test_confirmed_original_request_has_one_receipt_and_preserves_its_semantics(tmp_path, kind):
    root, before, target, request, transaction, project, run = client(tmp_path / 'case', kind)
    run()
    raw = (root / transaction_receipt_path(transaction)).read_bytes()
    write = validate_transaction(raw)
    request_raw = (root / request_receipt_path(request)).read_bytes()
    assert write['marker']['request_id'] == request
    assert json.loads(request_raw)['transaction_id'] == transaction
    retained = inventory(root)
    with no_write_attempts():
        first = read_guarded_completion(root, transaction, expected_project_id=project).data
        second = read_guarded_completion(root, transaction, expected_project_id=project).data
    assert first == second and first['replayed'] and first['commit_completed']
    assert first['result_object'] == json.loads(request_raw)['result_object']
    assert (root / transaction_receipt_path(transaction)).read_bytes() == raw
    assert list((root / '.specroad/requests').glob('*.json')) == [root / request_receipt_path(request)]
    assert inventory(root) == retained


@pytest.mark.parametrize('kind', CLIENTS)
@pytest.mark.parametrize('damage', ['missing', 'changed', 'extra'])
def test_receipt_damage_never_becomes_a_second_write_or_false_completion(tmp_path, kind, damage):
    root, before, target, request, transaction, project, run = client(tmp_path / 'case', kind)
    run(); path = root / request_receipt_path(request)
    if damage == 'missing': path.unlink()
    elif damage == 'changed': path.write_bytes(b'{}')
    else: (root / transaction_receipt_path(transaction)).with_name('extra.json').write_bytes(b'{}')
    retained = inventory(root)
    with no_write_attempts(), pytest.raises(FAILURES):
        read_guarded_completion(root, transaction, expected_project_id=project)
    for path, raw in target.items(): assert (root / path).read_bytes() == raw
    assert inventory(root) == retained


@pytest.mark.parametrize('kind', CLIENTS)
@pytest.mark.parametrize('part', ['marker', 'image', 'transaction', 'request', 'completion'])
@pytest.mark.parametrize('when', ['before', 'after'])
def test_actual_receipt_and_image_sync_failure_keeps_original_observed_state(tmp_path, monkeypatch, kind, part, when):
    import errno, os
    from specroad.changes.receipt_values import completion_marker_path
    root, before, target, request, transaction, project, run = client(tmp_path / 'case', kind)
    stage = points('staged', before, target, request)[0].split(':')[1]
    relative = {'marker': MARKER_PATH, 'image': '.specroad/write-state/staging/' + stage + '.bin',
        'transaction': transaction_receipt_path(transaction), 'request': request_receipt_path(request),
        'completion': completion_marker_path(transaction)}[part]
    original = os.fsync; observed = []
    def fail(fd):
        actual = os.readlink('/proc/self/fd/' + str(fd))
        if actual == str(root / relative):
            observed.append(actual)
            if when == 'after': original(fd)
            raise OSError(errno.EIO, 'Owned fsync refusal')
        return original(fd)
    with monkeypatch.context() as patch:
        patch.setattr(os, 'fsync', fail)
        with pytest.raises(FAILURES): run()
    assert observed
    retained = inventory(root)
    with no_write_attempts():
        assert inspect_write_state(root, expected_project_id=project)['state'] == 'corrupted'
        with pytest.raises(FAILURES): require_normal_access(root)
        with pytest.raises(FAILURES): read_guarded_completion(root, transaction, expected_project_id=project)
    assert inventory(root) == retained
