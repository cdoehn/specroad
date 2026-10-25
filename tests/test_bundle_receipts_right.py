"""15.g.R: preserved history, honest exclusions, and unchanged retry contracts."""
import json
import os
from unittest.mock import patch

import pytest

from specroad.bundles import (BundleError, prepare_project_bundle,
    prepare_partial_bundle, create_project_bundle, verify_bundle)
from specroad.bundles.extraction import extract_bundle
from specroad.changes import (RequestIdConflict, prepare_authoring_request,
    resolve_normative_request, cleanup_completed_transaction)
from specroad.changes.receipt_values import transaction_receipt_path, completion_marker_path
from specroad.graph.scope_descriptors import ScopeDescriptor
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.model.paths import artifact_path
from specroad.storage.project import ProjectSource
from support.folds import goal, edit
from support.model import put
from support.publication import ALLOW, TRANSACTION as MULTI_TRANSACTION
from support.read_only import inventory, no_write_attempts
from support.receipts import published, finish
from support.records import record_value
from support.scopes import descriptor
from support.targets import ACTOR
from test_bundle_receipts import (TRANSACTION, completed, receipts, retry, transfer,
    rebound, request_receipt_path)


def document_scope(root):
    document = record_value('document')
    put(root, artifact_path('document', document['id'], 'SR'), canonical_json_bytes(document))
    return ScopeDescriptor(descriptor('document', {'document_id': document['id']},
                                     boundary_policy='partial'))


@pytest.mark.parametrize('mixed', [False, True])
@pytest.mark.parametrize('mode', ['project', 'excluded', 'partial', 'publish'])
def test_whole_imported_receipt_group_cannot_disappear_on_reexport(tmp_path, mixed, mode):
    origin = tmp_path / 'origin'; completed(origin)
    if mixed:
        completed(origin, request_id='later-request', transaction_id='later-transaction', existing=True)
    scope = document_scope(origin)
    bundle = prepare_project_bundle(origin)
    target = tmp_path / 'target'; extract_bundle(bundle.source_bytes, target)
    (target / request_receipt_path('portable-request')).unlink()
    transaction = target / transaction_receipt_path(TRANSACTION)
    transaction.unlink(); (target / completion_marker_path(TRANSACTION)).unlink()
    transaction.parent.rmdir()
    # Remaining groups are complete: a closure-only scan would silently lose
    # the removed group, or certify an empty history when it was the only one.
    assert len(receipts(target)) == (3 if mixed else 0)
    before = inventory(target)
    with no_write_attempts():
        if mode == 'publish':
            outcome = create_project_bundle(target, output='generated/lost.zip')
            assert outcome.exit_code == 6 and outcome.result is None
        else:
            with pytest.raises(BundleError) as error:
                if mode == 'partial': prepare_partial_bundle(target, scope)
                else: prepare_project_bundle(target, exclude_operational_receipts=mode == 'excluded')
            assert error.value.exit_code == 6
    assert inventory(target) == before and not (target / 'generated').exists()


@pytest.mark.parametrize('kind', ['project', 'partial'])
@pytest.mark.parametrize('part', ['request', 'transaction', 'committed'])
def test_excluded_receipts_cannot_be_relabelled_as_other_content(tmp_path, kind, part):
    origin = tmp_path / 'origin'; completed(origin)
    scope = document_scope(origin)
    bundle = (prepare_project_bundle(origin, exclude_operational_receipts=True)
              if kind == 'project' else prepare_partial_bundle(origin, scope))
    path = {'request': request_receipt_path('portable-request'),
            'transaction': transaction_receipt_path(TRANSACTION),
            'committed': completion_marker_path(TRANSACTION)}[part]
    # A consistent re-encoded ZIP must not turn a known omitted receipt into
    # archive optimization or normative partial-scope provenance.
    raw = rebound(bundle, bundle.files,
        excluded_contents=[{'path': path, 'reason': 'unreferenced_archive_object'
                            if kind == 'project' else 'outside_scope'}],
        idempotency_scope='portable' if kind == 'project' else 'local_only')
    before = inventory(origin)
    with no_write_attempts():
        for consume in (lambda: verify_bundle(raw), lambda: extract_bundle(raw, tmp_path / 'target')):
            with pytest.raises(BundleError) as error: consume()
            assert error.value.exit_code == 3 and error.value.code == 'SRV002'
    assert inventory(origin) == before and not (tmp_path / 'target').exists()


@pytest.mark.parametrize('path', ['artifacts/goals/absent.json', '.specroad/requests',
    '.specroad/requests/not-a-request-hash.json', '.specroad/transactions/receipts',
    '.specroad/transactions/receipts/' + 'f' * 64 + '/unknown.json',
    '.specroad/requests/' + 'F' * 64 + '.json'])
def test_receipt_exclusion_requires_a_native_receipt_file_path(tmp_path, path):
    root = tmp_path / 'origin'; completed(root)
    bundle = prepare_project_bundle(root, exclude_operational_receipts=True)
    raw = rebound(bundle, bundle.files,
                  excluded_contents=[{'path': path, 'reason': 'operational_receipts_excluded'}])
    with no_write_attempts(), pytest.raises(BundleError) as error:
        extract_bundle(raw, tmp_path / 'target')
    assert error.value.exit_code == 3 and error.value.code == 'SRV002'
    assert not (tmp_path / 'target').exists()


@pytest.mark.parametrize('requestless', [False, True])
def test_model_root_is_independent_of_receipt_contents_and_exclusion(tmp_path, requestless):
    roots = [tmp_path / 'first', tmp_path / 'second']
    for index, root in enumerate(roots):
        completed(root, request_id=None if requestless else 'request-' + str(index),
                  transaction_id='transaction-' + str(index))
    before = [inventory(root) for root in roots]
    with no_write_attempts():
        included = [prepare_project_bundle(root) for root in roots]
        excluded = [prepare_project_bundle(root, exclude_operational_receipts=True) for root in roots]
        manifests = [verify_bundle(b.source_bytes)['manifest'] for b in included + excluded]
    assert [inventory(root) for root in roots] == before
    for field in ('origin_model_root_sha256', 'bundle_model_root_sha256',
                  'profile_sha256', 'configuration_sha256', 'scope_descriptor'):
        assert all(m[field] == manifests[0][field] for m in manifests)
    assert excluded[0].files == excluded[1].files
    assert included[0].files != included[1].files and included[0].sha256 != included[1].sha256
    for root, bundled, omitted in zip(roots, included, excluded):
        assert bundled.files == {**omitted.files, **receipts(root)}
        assert bundled.manifest['idempotency_scope'] == 'portable'
        assert omitted.manifest['idempotency_scope'] == 'local_only'
        assert {x['path'] for x in omitted.manifest['excluded_contents']} == set(receipts(root))
        assert not set(receipts(root)).intersection(omitted.files)


def multi_transfer(tmp_path):
    origin = tmp_path / 'origin'; a, b = goal(1), goal(2)
    with published(origin, artifacts=[a, b], operations=[edit(a, 'A'), edit(b, 'B')]) as (_, plan, check, held, journal):
        finish(check, held, journal)
        cleanup_completed_transaction(check, MULTI_TRANSACTION, held_lock=held, authority=ALLOW)
    bundle = prepare_project_bundle(origin); target = tmp_path / 'target'
    extract_bundle(bundle.source_bytes, target)
    return target, plan


@pytest.mark.parametrize('change', ['order', 'content', 'guard', 'remove'])
def test_transferred_request_conflict_retains_both_operation_hashes(tmp_path, change):
    target, selected = multi_transfer(tmp_path)
    original = selected.data['operations']; operations = json.loads(json.dumps(original))
    if change == 'order': operations.reverse()
    elif change == 'content': operations[0]['patch'][0]['value'] = 'Different'
    elif change == 'guard': operations[0]['expected_revision'] += 1
    else: operations.pop()
    request = prepare_authoring_request(command_id='change apply', actor=ACTOR,
                                        operations=operations, request_id='request-1')
    before = inventory(target)
    with no_write_attempts(), pytest.raises(RequestIdConflict) as error:
        resolve_normative_request(ProjectSource(target), request)
    diagnostic = error.value.diagnostic()
    assert error.value.exit_code == 6 and diagnostic['request_id'] == 'request-1'
    assert diagnostic['expected_operations_sha256'] == canonical_json_sha256(original)
    assert diagnostic['received_operations_sha256'] == canonical_json_sha256(operations)
    assert diagnostic['receipt_verified'] and diagnostic['existing_request_committed']
    assert not diagnostic['recovery_required'] and not diagnostic['normative_write_attempted']
    assert not diagnostic['mutation_possible'] and not diagnostic['write_authorized']
    assert inventory(target) == before


@pytest.mark.parametrize('mode', ['key_order', 'actor', 'new_case', 'dry_run', 'absent_id'])
def test_transfer_preserves_native_retry_identity_and_non_authorization(tmp_path, mode):
    target, selected = multi_transfer(tmp_path)
    options = dict(command_id='change apply', actor=ACTOR, operations=selected.data['operations'],
                   request_id='request-1')
    if mode == 'key_order': options['operations'] = json.loads(json.dumps(options['operations'], sort_keys=True))
    elif mode == 'actor': options['actor'] = {'actor_type': 'human', 'actor_id': 'later-reader'}
    elif mode == 'new_case': options['request_id'] = 'Request-1'
    elif mode == 'dry_run': options['dry_run'] = True
    else: options['request_id'] = None
    before = inventory(target)
    with no_write_attempts():
        result = resolve_normative_request(ProjectSource(target), prepare_authoring_request(**options)).data
        if mode in ('key_order', 'actor'):
            saved = retry(target, selected)
            assert result == saved and result['original_request']['actor'] == ACTOR
        elif mode == 'new_case':
            assert result['action'] == 'new_request' and result['locked_recheck_required']
            assert result['result_object'] is None and not result['receipt_verified']
        else:
            assert result['action'] == 'not_applicable' and not result['locked_recheck_required']
            assert result['result_object'] is None and not result['receipt_verified']
    assert result['normative_writes'] == 0 and not result['write_authorized']
    assert not result['current_target_verified'] and not result['authenticity_verified']
    assert inventory(target) == before


@pytest.mark.parametrize('excluded', [False, True])
@pytest.mark.parametrize('change', ['group_removed', 'extra_file', 'directory_replaced'])
def test_receipt_namespace_changes_between_prepare_and_publish_are_conflicts(tmp_path, excluded, change):
    from specroad.bundles import publication
    root = tmp_path / 'origin'; completed(root)
    native = publication._prepare
    def changed(*args, **kwargs):
        result = native(*args, **kwargs)
        directory = (root / transaction_receipt_path(TRANSACTION)).parent
        if change == 'group_removed':
            for path in receipts(root): (root / path).unlink()
            directory.rmdir()
        elif change == 'extra_file':
            (root / '.specroad/requests/unknown.json').write_bytes(b'{}')
        else:
            moved = directory.with_name('moved'); directory.rename(moved); directory.mkdir()
            for file in moved.iterdir(): file.rename(directory / file.name)
            moved.rmdir()
        return result
    with patch.object(publication, '_prepare', changed):
        result = create_project_bundle(root, output='generated/stale.zip', exclude_operational_receipts=excluded)
    assert result.exit_code == 6 and result.result is None
    assert not (root / 'generated').exists()


@pytest.mark.parametrize('excluded', [False, True])
@pytest.mark.parametrize('kind', ['request_symlink', 'transaction_symlink', 'request_fifo'])
def test_unsafe_operational_files_are_never_bypassed_by_exclusion(tmp_path, excluded, kind):
    root = tmp_path / 'origin'; completed(root)
    path = root / (transaction_receipt_path(TRANSACTION) if kind == 'transaction_symlink'
                   else request_receipt_path('portable-request'))
    raw = path.read_bytes(); path.unlink()
    if kind == 'request_fifo': os.mkfifo(path)
    else:
        foreign = tmp_path / 'foreign.json'; foreign.write_bytes(raw); path.symlink_to(foreign)
    with no_write_attempts():
        result = create_project_bundle(root, output='generated/unsafe.zip', exclude_operational_receipts=excluded)
    assert result.exit_code == 7 and result.result is None
    assert not (root / 'generated').exists()
