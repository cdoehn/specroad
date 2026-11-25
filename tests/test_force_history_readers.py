"""Local read observations retain real Force history and strict proof boundaries."""
from copy import deepcopy
from hashlib import sha256
import json

import pytest

from specroad.authoring._inspection_snapshot import InspectionSnapshot
from specroad.authoring.native_generic import author_generic
from specroad.bundles import prepare_project_bundle
from specroad.bundles.errors import BundleError
from specroad.changes.receipt_values import completion_marker_path, request_receipt_path, transaction_receipt_path
from specroad.model.operational_paths import RECEIPTS_ROOT
from specroad.query.impact import impact_artifact
from specroad.security import SafetyViolation
from support.force_cases import ACTOR, ALLOW, fixture
from support.model import put
from support.read_only import inventory, no_write_attempts


def forced_project(root):
    root, path = fixture(root)
    value = json.loads((root / path).read_bytes())
    result = author_generic(root, dict(command_id='artifact.update', target=value['id'],
        expected_revision=999, patch=[dict(op='replace', path='/title', value='Retained forced title')]),
        actor=ACTOR, authority=ALLOW, request_id='reader-proof', force=True)
    assert result['force']['used'] and result['completion']['commit_completed']
    return root, value['id'], result


def empty_history_directory(root):
    path = root / RECEIPTS_ROOT / sha256(b'absent-optional-history').hexdigest()
    path.mkdir(parents=True)
    return path


@pytest.mark.parametrize('reader', ['inspection', 'impact'])
def test_unclaimed_local_entries_do_not_hide_verified_force_history(tmp_path, reader):
    root, identity, result = forced_project(tmp_path / 'project')
    empty_history_directory(root)
    put(root, RECEIPTS_ROOT + '/retained.json', b'unrelated local file')
    before = inventory(root)
    with no_write_attempts():
        if reader == 'inspection':
            snapshot = InspectionSnapshot(root, None)
            origins = snapshot.model.force_provenance
            snapshot.verify_current()
        else:
            outcome = impact_artifact(root, identity)
            assert outcome.exit_code == 0 and outcome.complete
            origins = outcome.as_dict()['result']['force_provenance']
    assert origins and all(row['approval_granted'] is False for row in origins)
    assert any(row['transaction_id'] == result['completion']['transaction_id'] for row in origins)
    assert inventory(root) == before


@pytest.mark.parametrize('reader', ['inspection', 'impact'])
@pytest.mark.parametrize('missing', ['transaction', 'completion', 'request', 'changed_transaction'])
def test_claimed_force_receipts_still_require_the_complete_original_group(tmp_path, reader, missing):
    root, identity, result = forced_project(tmp_path / 'project')
    transaction = result['completion']['transaction_id']
    path = {'transaction': transaction_receipt_path(transaction),
            'completion': completion_marker_path(transaction),
            'request': request_receipt_path('reader-proof'),
            'changed_transaction': transaction_receipt_path(transaction)}[missing]
    if missing == 'changed_transaction':
        changed = deepcopy(json.loads((root / path).read_bytes()))
        changed['write']['actor']['actor_id'] = 'foreign-actor'
        put(root, path, json.dumps(changed).encode())
    else:
        (root / path).unlink()
    empty_history_directory(root)
    put(root, RECEIPTS_ROOT + '/retained.json', b'unrelated local file')
    before = inventory(root)
    with no_write_attempts():
        if reader == 'inspection':
            with pytest.raises(BundleError):
                InspectionSnapshot(root, None)
        else:
            outcome = impact_artifact(root, identity)
            assert outcome.exit_code in (3, 6) and not outcome.complete
            assert outcome.result is None
    assert inventory(root) == before


def test_empty_local_history_directory_is_rechecked_before_read_success(tmp_path):
    root, _ = fixture(tmp_path / 'project')
    empty = empty_history_directory(root)
    snapshot = InspectionSnapshot(root, None)
    assert not snapshot.model.force_provenance
    put(root, (empty / 'transaction.json').relative_to(root).as_posix(), b'{}')
    before = inventory(root)
    with no_write_attempts(), pytest.raises(BundleError) as caught:
        snapshot.verify_current()
    assert caught.value.reason == 'bundle_receipt_inventory_changed'
    assert caught.value.exit_code == 6 and inventory(root) == before


@pytest.mark.parametrize('entry', ['empty_directory', 'loose_file'])
def test_portable_bundle_keeps_its_complete_receipt_inventory_requirement(tmp_path, entry):
    root, _ = fixture(tmp_path / 'project')
    if entry == 'empty_directory':
        empty_history_directory(root)
    else:
        put(root, RECEIPTS_ROOT + '/retained.json', b'unclaimed history is not portable proof')
    before = inventory(root)
    with no_write_attempts():
        snapshot = InspectionSnapshot(root, None)
        assert not snapshot.model.force_provenance
        snapshot.verify_current()
        with pytest.raises(BundleError) as caught:
            prepare_project_bundle(root)
    assert caught.value.reason == ('bundle_receipt_completion_missing' if entry == 'empty_directory'
                                    else 'bundle_receipt_path_invalid')
    assert inventory(root) == before


@pytest.mark.parametrize('entry', ['symlink', 'canonical_file'])
def test_local_observation_preserves_receipt_path_safety(tmp_path, entry):
    root, _ = fixture(tmp_path / 'project')
    parent = root / RECEIPTS_ROOT
    parent.mkdir(parents=True)
    foreign = tmp_path / 'foreign'
    foreign.write_bytes(b'unclaimed bytes')
    if entry == 'symlink':
        (parent / 'retained.json').symlink_to(foreign)
    else:
        (parent / sha256(b'claimed-transaction').hexdigest()).write_bytes(b'not a directory')
    with no_write_attempts(), pytest.raises((BundleError, SafetyViolation)):
        InspectionSnapshot(root, None)
    assert foreign.read_bytes() == b'unclaimed bytes'
