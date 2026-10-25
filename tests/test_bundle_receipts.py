"""15.g.W: real completed writes, verified transfer, and historical retry."""
from hashlib import sha256
import json
import os
import shutil
from unittest.mock import patch

import pytest

from specroad.authoring._inspection_snapshot import InspectionSnapshot
from specroad.bundles import (BundleContainer, BundleError, prepare_project_bundle,
    create_project_bundle, prepare_partial_bundle, verify_bundle)
from specroad.bundles.container import encode_bundle
from specroad.bundles.extraction import extract_bundle
from specroad.changes import (prepare_publication_check, project_lock, begin_building_journal,
    stage_building_journal, CommittingJournal, finalize_committing_journal,
    cleanup_completed_transaction, resolve_normative_request, bind_plan_authoring,
    prepare_authoring_request, RequestReceipt, ReceiptError, request_receipt_path,
    read_transaction_completion)
from specroad.changes.receipt_values import transaction_receipt_path, completion_marker_path
from specroad.cli.application import dispatch_result, execute_request
from specroad.graph.scope_descriptors import ScopeDescriptor
from specroad.model.canonical import canonical_json_bytes
from specroad.model.paths import artifact_path
from specroad.storage.project import ProjectSource
from support.committing import publish
from support.folds import goal, create, edit
from support.inspection import inspection_project
from support.model import put
from support.publication import ALLOW
from support.read_only import no_write_attempts, inventory
from support.records import record_value
from support.scopes import descriptor
from support.targets import ACTOR, TIME, POLICY, plan

TRANSACTION = 'bundle-transfer-transaction'
PROOF = '.specroad/recovery/bundle-bootstrap/journal.json'


def completed(root, *, request_id='portable-request', transaction_id=TRANSACTION, existing=False):
    model = (InspectionSnapshot(root, None, include_archive_objects=True).model if existing else
             inspection_project(root, artifacts=[goal()]))
    artifact = goal(9, revision=1, created_at=TIME, updated_at=TIME, created_by=ACTOR, updated_by=ACTOR)
    operations = [edit(model.artifacts[0], 'Later state')] if existing else [create(artifact)]
    selected = plan(model, operations, request_id=request_id)
    check = prepare_publication_check(selected, model, policy=POLICY)
    with project_lock(root, kind='writer', command='change apply', project_id='sample',
                      request_id=request_id, transaction_id=transaction_id) as held:
        building = begin_building_journal(check, held_lock=held, transaction_id=transaction_id, authority=ALLOW)
        ready = stage_building_journal(check, building, held_lock=held, authority=ALLOW)
        publish(check, ready, held)
        journal = CommittingJournal((root / ready.path).read_bytes())
        finalize_committing_journal(check, journal, held_lock=held, authority=ALLOW)
        outcome = cleanup_completed_transaction(check, transaction_id, held_lock=held, authority=ALLOW)
        assert outcome.data['cleanup_completed']
    return selected, check


def receipts(root):
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for name in ('.specroad/requests', '.specroad/transactions/receipts')
            for p in (root / name).rglob('*.json')}


def retry(root, selected):
    return resolve_normative_request(ProjectSource(root), bind_plan_authoring(selected)).data


def transfer(tmp_path):
    origin, target = tmp_path / 'origin', tmp_path / 'transferred'
    selected, check = completed(origin)
    bundle = prepare_project_bundle(origin)
    extract_bundle(bundle.source_bytes, target, expected_sha256=bundle.sha256)
    return origin, target, selected, check, bundle


def rebound(bundle, files, **changes):
    metadata = {k: v for k, v in bundle.manifest.items() if k != 'entries'}
    return encode_bundle({**metadata, **changes}, files)


def test_complete_history_is_byte_exact_separate_and_verified_without_writes(tmp_path):
    root = tmp_path / 'origin'; completed(root)
    raw = receipts(root)
    assert len(raw) == 3
    native = InspectionSnapshot(root, None, include_archive_objects=True)
    before = inventory(root)
    with no_write_attempts():
        bundle = prepare_project_bundle(root)
        result = verify_bundle(bundle.source_bytes, expected_sha256=bundle.sha256)
    assert inventory(root) == before
    assert bundle.files == {**native.raw, **raw}
    assert result['manifest']['idempotency_scope'] == 'portable'
    assert result['model_root_verified'] and result['closure_verified']
    assert not result['creator_authenticated'] and not result['write_authorized']
    assert not result['approval_granted'] and not result['full_semantic_validation']
    assert bundle.manifest['bundle_model_root_sha256'] == native.model.manifest(
        native.model.artifacts, descriptor('project')).sha256
    entries = {e['path']: e for e in bundle.manifest['entries']}
    for path, value in raw.items():
        assert entries[path]['size'] == len(value) and entries[path]['sha256'] == sha256(value).hexdigest()
    assert not any(p.startswith(('.specroad/locks', '.specroad/recovery')) for p in bundle.files)


def test_retry_after_native_transfer_reuses_exact_result_and_ids_without_writes(tmp_path):
    origin, target, selected, _, bundle = transfer(tmp_path)
    saved = RequestReceipt((origin / request_receipt_path('portable-request')).read_bytes()).data
    before = inventory(target)
    assert origin.stat().st_ino != target.stat().st_ino
    with no_write_attempts():
        first, second = retry(target, selected), retry(target, selected)
        completion = read_transaction_completion(ProjectSource(target), TRANSACTION).data
    assert first == second and first['action'] == 'replay'
    assert first['original_request'] == saved and first['result_object'] == saved['result_object']
    assert first['created_ids'] == saved['created_ids'] == [goal(9)['id']]
    assert first['normative_writes'] == 0 and not first['write_authorized']
    assert completion['receipt_verified'] and completion['cleanup_completed']
    assert not completion['current_target_verified'] and not completion['write_authorized']
    assert inventory(target) == before and receipts(target) == receipts(origin)
    assert prepare_project_bundle(target).source_bytes == bundle.source_bytes


def test_reexported_history_survives_another_native_transfer(tmp_path):
    origin, target, selected, _, original = transfer(tmp_path)
    next_bundle = prepare_project_bundle(target)
    assert next_bundle.source_bytes == original.source_bytes
    third = tmp_path / 'third'; extract_bundle(next_bundle.source_bytes, third)
    before = inventory(third)
    with no_write_attempts():
        assert retry(third, selected)['original_request'] == retry(origin, selected)['original_request']
    assert inventory(third) == before


@pytest.mark.parametrize('mode', ['direct', 'cli', 'structured'])
@pytest.mark.parametrize('empty', [False, True])
def test_explicit_exclusion_publishes_only_local_idempotency(tmp_path, mode, empty):
    root = tmp_path / 'origin'
    if empty:
        inspection_project(root)
    else:
        selected, _ = completed(root)
    raw = receipts(root); before = inventory(root)
    options = {'--project': str(root), '--scope': 'project', '--output': 'generated/local.zip',
               '--exclude-operational-receipts': True}
    if mode == 'direct':
        result = create_project_bundle(root, output='generated/local.zip', exclude_operational_receipts=True)
    elif mode == 'cli':
        result = dispatch_result(['bundle', 'create', '--project', str(root), '--scope', 'project',
                                  '--output', 'generated/local.zip', '--exclude-operational-receipts'])
    else:
        result = execute_request({'command_id': 'bundle.create', 'options': options}).result
    assert result.exit_code == 0, result.as_dict()
    bundle = BundleContainer((root / 'generated/local.zip').read_bytes())
    assert bundle.manifest['idempotency_scope'] == 'local_only'
    assert bundle.manifest['excluded_contents'] == [
        {'path': p, 'reason': 'operational_receipts_excluded'} for p in sorted(raw)]
    assert not any(p.startswith('.specroad/') for p in bundle.files)
    assert tuple(e for e in inventory(root) if not e[0].startswith('generated')) == before
    assert verify_bundle(bundle.source_bytes)['model_root_verified']
    target = tmp_path / 'target'; extract_bundle(bundle.source_bytes, target)
    if not empty:
        target_before = inventory(target)
        with no_write_attempts():
            outcome = retry(target, selected)
        assert outcome['action'] == 'new_request' and not outcome['write_authorized']
        assert inventory(target) == target_before


def test_partial_explicitly_omits_completed_project_history(tmp_path):
    root = tmp_path / 'origin'; completed(root)
    document = record_value('document')
    put(root, artifact_path('document', document['id'], 'SR'), canonical_json_bytes(document))
    selected = ScopeDescriptor(descriptor('document', {'document_id': record_value('document')['id']},
                                          boundary_policy='partial'))
    before = inventory(root)
    with no_write_attempts():
        bundle = prepare_partial_bundle(root, selected)
        verify_bundle(bundle.source_bytes)
    assert bundle.manifest['read_only'] and bundle.manifest['idempotency_scope'] == 'local_only'
    assert not any(p.startswith('.specroad/') for p in bundle.files)
    assert {e['path'] for e in bundle.manifest['excluded_contents']
            if e['reason'] == 'operational_receipts_excluded'} == set(receipts(root))
    assert inventory(root) == before


def test_transaction_without_request_id_transports_its_completion_pair(tmp_path):
    root = tmp_path / 'origin'; completed(root, request_id=None)
    bundle = prepare_project_bundle(root)
    assert len(receipts(root)) == 2
    target = tmp_path / 'target'; extract_bundle(bundle.source_bytes, target)
    with no_write_attempts():
        value = read_transaction_completion(ProjectSource(target), TRANSACTION).data
    assert value['receipt_verified'] and value['request_id'] is None
    assert value['receipts']['request'] is None and not value['write_authorized']


@pytest.mark.parametrize('part', ['request', 'transaction', 'committed'])
def test_rebound_zip_missing_one_completion_link_is_rejected_before_extraction(tmp_path, part):
    root = tmp_path / 'origin'; completed(root); bundle = prepare_project_bundle(root)
    paths = {'request': request_receipt_path('portable-request'),
             'transaction': transaction_receipt_path(TRANSACTION), 'committed': completion_marker_path(TRANSACTION)}
    files = bundle.files; files.pop(paths[part])
    raw = rebound(bundle, files)
    with no_write_attempts(), pytest.raises(BundleError) as failure:
        extract_bundle(raw, tmp_path / 'target')
    assert failure.value.exit_code == 3 and failure.value.code == 'SRV060'
    assert not (tmp_path / 'target').exists()


@pytest.mark.parametrize('change', ['local_only', 'project_id', 'request_hash', 'created_ids', 'orphan_request'])
def test_invalid_operational_binding_cannot_be_hidden_by_rehashing_zip(tmp_path, change):
    root = tmp_path / 'origin'; completed(root); bundle = prepare_project_bundle(root)
    files, metadata = bundle.files, {}
    path = request_receipt_path('portable-request')
    value = json.loads(files[path])
    if change == 'local_only':
        metadata['idempotency_scope'] = 'local_only'
    elif change == 'orphan_request':
        files[request_receipt_path('other-request')] = files[path]
    else:
        if change == 'project_id': value['project_id'] = 'another-project'
        elif change == 'request_hash': value['operations_sha256'] = 'f' * 64
        else: value['created_ids'] = []
        files[path] = canonical_json_bytes(value)
    with no_write_attempts(), pytest.raises(BundleError) as failure:
        verify_bundle(rebound(bundle, files, **metadata))
    assert failure.value.exit_code == 3


@pytest.mark.parametrize('mode', ['plain_copy', 'copied_extraction', 'manual_payload', 'missing_proof'])
def test_receipt_replay_requires_native_root_bound_extraction(tmp_path, mode):
    origin, extracted, selected, _, bundle = transfer(tmp_path)
    target = tmp_path / 'copied'
    if mode in ('plain_copy', 'copied_extraction'):
        shutil.copytree(origin if mode == 'plain_copy' else extracted, target)
    elif mode == 'manual_payload':
        for path, raw in bundle.files.items(): put(target, path, raw)
        put(target, 'bundle-manifest.json', bundle.manifest_bytes)
    else:
        target = extracted
        (target / PROOF).unlink()
    before = inventory(target)
    with no_write_attempts(), pytest.raises(ReceiptError) as failure:
        retry(target, selected)
    assert failure.value.exit_code == 6 and inventory(target) == before


@pytest.mark.parametrize('part', ['request', 'transaction', 'committed'])
@pytest.mark.parametrize('change', ['remove', 'replace_inode', 'bytes'])
def test_changed_imported_completion_never_replays_or_becomes_new_request(tmp_path, part, change):
    _, target, selected, _, _ = transfer(tmp_path)
    paths = {'request': request_receipt_path('portable-request'),
             'transaction': transaction_receipt_path(TRANSACTION), 'committed': completion_marker_path(TRANSACTION)}
    path = target / paths[part]; raw = path.read_bytes()
    if change == 'remove':
        path.unlink()
    elif change == 'replace_inode':
        other = path.with_name('replacement'); other.write_bytes(raw); os.replace(other, path)
    else:
        path.write_bytes(raw + b' ')
    before = inventory(target)
    with no_write_attempts(), pytest.raises(ReceiptError):
        retry(target, selected)
    assert inventory(target) == before


def test_imported_history_never_supplies_original_live_publication_proof(tmp_path):
    _, target, _, check, _ = transfer(tmp_path)
    with no_write_attempts(), pytest.raises(ReceiptError) as failure:
        read_transaction_completion(ProjectSource(target), TRANSACTION, preflight=check)
    assert failure.value.exit_code == 6


def test_changed_retry_operations_remain_a_conflict_after_transfer(tmp_path):
    _, target, _, _, _ = transfer(tmp_path)
    request = prepare_authoring_request(command_id='change apply', actor=ACTOR,
                                        operations=[], request_id='portable-request')
    before = inventory(target)
    with no_write_attempts(), pytest.raises(ReceiptError) as failure:
        resolve_normative_request(ProjectSource(target), request)
    assert failure.value.exit_code == 6 and failure.value.reason == 'request_operations_conflict'
    assert inventory(target) == before


def test_historical_retry_does_not_freeze_the_live_normative_model(tmp_path):
    _, target, selected, _, _ = transfer(tmp_path)
    path = target / artifact_path('goal', goal()['id'], 'SR')
    value = json.loads(path.read_bytes()); value['statement'] = 'A later ordinary state'
    path.write_bytes(canonical_json_bytes(value))
    before = inventory(target)
    with no_write_attempts():
        assert retry(target, selected)['action'] == 'replay'
        assert not read_transaction_completion(ProjectSource(target), TRANSACTION).data['current_target_verified']
    assert inventory(target) == before


def test_imported_and_new_local_completions_share_the_next_portable_history(tmp_path):
    _, target, original, _, _ = transfer(tmp_path)
    later, _ = completed(target, request_id='later-request', transaction_id='later-transaction', existing=True)
    before = inventory(target)
    with no_write_attempts():
        bundle = prepare_project_bundle(target)
        assert retry(target, original)['action'] == retry(target, later)['action'] == 'replay'
    assert inventory(target) == before and len(receipts(target)) == 6
    third = tmp_path / 'third'; extract_bundle(bundle.source_bytes, third)
    transferred = inventory(third)
    with no_write_attempts():
        for selected in (original, later):
            assert retry(third, selected) == retry(target, selected)
    assert inventory(third) == transferred


@pytest.mark.parametrize('excluded', [False, True])
def test_receipt_bytes_are_rechecked_before_publishing_the_selected_bundle(tmp_path, excluded):
    from specroad.bundles import publication
    root = tmp_path / 'origin'; completed(root)
    original = publication._prepare
    def changed(*args, **kwargs):
        value = original(*args, **kwargs)
        path = root / request_receipt_path('portable-request')
        path.write_bytes(path.read_bytes() + b' ')
        return value
    with patch.object(publication, '_prepare', changed):
        result = create_project_bundle(root, output='generated/stale.zip', exclude_operational_receipts=excluded)
    assert result.exit_code == 6 and result.result is None
    assert not (root / 'generated').exists()
