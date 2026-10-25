"""15.b.W: actual project closure and exact portable bytes, without extraction."""
from base64 import b64decode
from hashlib import sha256
from io import BytesIO
import json
import os
from unittest.mock import patch
from zipfile import ZipFile

import pytest

from specroad.authoring._inspection_snapshot import InspectionSnapshot
from specroad.bundles import BundleError, prepare_project_bundle
from specroad.bundles import project as service
from specroad.cli.application import dispatch_result
from specroad.model.attachments import AttachmentDescriptor
from specroad.model.canonical import canonical_json_bytes
from specroad.model.paths import artifact_path
from support.domain import domain_value
from support.inspection import inspection_project
from support.model import put
from support.read_only import inventory, no_write_attempts
from support.records import record_value
from support.scopes import descriptor


def project(root):
    """Native model, including a control artifact and an actual binary attachment."""
    content = b'\x00\xffattachment bytes\r\n'
    attachment = AttachmentDescriptor('attachments/owned.bin', 'application/octet-stream',
                                      len(content), sha256(content).hexdigest())
    values = [domain_value('goal'), domain_value('requirement'),
              record_value('proposal'), record_value('document')]
    inspection_project(root, artifacts=values)
    evidence = record_value('evidence', attachments=[attachment.data])
    put(root, artifact_path('evidence', evidence['id'], 'SR'), canonical_json_bytes(evidence))
    put(root, attachment.path, content)
    # A real passive mapping, including an inactive resource, belongs to project.
    from test_exchange_export import mapping
    put(root, 'mappings/export.json', mapping().source_bytes)
    return InspectionSnapshot(root, None, include_archive_objects=True)


def test_complete_project_preserves_native_bytes_controls_and_model_root(tmp_path):
    root = tmp_path / 'source'
    snapshot = project(root)
    before = inventory(root)
    with no_write_attempts():
        bundle = prepare_project_bundle(root)
    assert inventory(root) == before
    assert bundle.files == snapshot.raw
    native = snapshot.model.manifest(snapshot.model.artifacts, descriptor('project'))
    manifest = bundle.manifest
    assert manifest['bundle_kind'] == 'project' and manifest['read_only'] is False
    assert manifest['scope_descriptor'] == descriptor('project')
    assert manifest['origin_model_root_sha256'] == manifest['bundle_model_root_sha256'] == native.sha256
    assert manifest['configuration_sha256'] == native.data['configuration_sha256']
    assert manifest['profile_sha256'] == native.data['profile_sha256']
    assert manifest['boundary_references'] == manifest['excluded_contents'] == []
    assert manifest['idempotency_scope'] == 'portable'
    assert any(p.startswith('spec/proposals/') for p in bundle.files)
    assert not bundle.project_verified and not bundle.write_authorized
    with ZipFile(BytesIO(bundle.source_bytes)) as archive:
        assert archive.testzip() is None
        assert set(archive.namelist()) == set(snapshot.raw) | {'bundle-manifest.json'}
        assert all(archive.read(path) == raw for path, raw in snapshot.raw.items())


def test_fresh_initialized_project_keeps_all_language_package_sources(tmp_path):
    root = tmp_path / 'project'
    result = dispatch_result(['init', str(root)])
    assert result.exit_code == 0, result.as_dict()
    before = inventory(root)
    with no_write_attempts():
        bundle = prepare_project_bundle(root)
    assert inventory(root) == before
    assert len([p for p in bundle.files if p.startswith('profiles/language-data/packages/')]) == 9
    assert {item['path']: (root / item['path']).read_bytes()
            for item in result.as_dict()['result']['files']} == bundle.files
    assert not any(p.startswith('.specroad/') for p in bundle.files)


def test_relocated_payload_reopens_as_complete_normal_project(tmp_path):
    root = tmp_path / 'source'; project(root)
    bundle = prepare_project_bundle(root)
    target = tmp_path / 'relocated'; target.mkdir()
    # Independent fixture materialization, not the not-yet-implemented extractor.
    for name, raw in bundle.files.items():
        put(target, name, raw)
    put(target, 'bundle-manifest.json', bundle.manifest_bytes)
    reopened = InspectionSnapshot(target, None, include_archive_objects=True)
    native = reopened.model.manifest(reopened.model.artifacts, descriptor('project'))
    assert native.sha256 == bundle.manifest['bundle_model_root_sha256']
    assert reopened.raw == bundle.files
    assert prepare_project_bundle(target).source_bytes == bundle.source_bytes


def test_representation_bytes_are_retained_without_changing_semantic_root(tmp_path):
    root = tmp_path / 'source'; snapshot = project(root)
    first = prepare_project_bundle(root)
    path = next(p for p in snapshot.raw if p.startswith('spec/goals/'))
    raw = json.dumps(json.loads(snapshot.raw[path]), indent=4).encode() + b'\n'
    put(root, path, raw)
    second = prepare_project_bundle(root)
    assert second.files[path] == raw and second.sha256 != first.sha256
    assert first.manifest['bundle_model_root_sha256'] == second.manifest['bundle_model_root_sha256']


def test_host_location_creation_order_and_mtime_do_not_change_bundle(tmp_path):
    root = tmp_path / 'source'; snapshot = project(root)
    first = prepare_project_bundle(root)
    other = tmp_path / 'other'; other.mkdir()
    for name, raw in reversed(list(snapshot.raw.items())):
        put(other, name, raw)
        os.utime(other / name, (1000, 1000))
    assert prepare_project_bundle(other).source_bytes == first.source_bytes


def test_unrelated_repository_cache_generated_and_previous_manifest_are_not_payload(tmp_path):
    root = tmp_path / 'source'; project(root)
    first = prepare_project_bundle(root)
    for path in ('.git/config', '.codex/settings.json', '.env', 'README.md',
                 'generated/report.json', '.specroad/cache/arbitrary.bin'):
        put(root, path, b'local-only bytes')
    put(root, 'bundle-manifest.json', first.manifest_bytes)
    before = inventory(root)
    with no_write_attempts():
        second = prepare_project_bundle(root)
    assert inventory(root) == before
    assert second.source_bytes == first.source_bytes


def baseline_project(root):
    from test_baseline_creation import project as native_project, plan_for
    model = native_project(root, bundled=True)
    plan = plan_for(model)
    op = plan.data['operations'][0]
    # A saved native snapshot's exact record and objects, without running a
    # transaction or inventing a completed receipt history in this fixture.
    put(root, artifact_path('baseline', op['record']['id'], 'SR'), canonical_json_bytes(op['record']))
    for obj in op['objects']:
        put(root, obj['path'], b64decode(obj['bytes_base64']))
    return op


def test_baselines_keep_every_referenced_historical_object(tmp_path):
    root = tmp_path / 'source'; op = baseline_project(root)
    bundle = prepare_project_bundle(root)
    paths = {row['object_path'] for row in op['record']['manifest']}
    assert paths and paths <= bundle.files.keys()
    assert all(bundle.files[obj['path']] == b64decode(obj['bytes_base64']) for obj in op['objects'])
    assert artifact_path('baseline', op['record']['id'], 'SR') in bundle.files


def test_unreferenced_archive_optimization_is_explicit_and_not_a_model_change(tmp_path):
    root = tmp_path / 'source'; project(root)
    first = prepare_project_bundle(root)
    content = b'unreferenced old object'
    digest = sha256(content).hexdigest()
    path = 'archive/objects/' + digest[:2] + '/' + digest
    put(root, path, content)
    second = prepare_project_bundle(root)
    assert path not in second.files
    assert second.manifest['excluded_contents'] == [{'path': path, 'reason': 'unreferenced_archive_object'}]
    assert second.manifest['bundle_model_root_sha256'] == first.manifest['bundle_model_root_sha256']


@pytest.mark.parametrize('kind', ['attachment', 'archive', 'profile', 'registry'])
def test_missing_required_payload_never_becomes_a_closed_bundle(tmp_path, kind):
    root = tmp_path / 'source'
    if kind == 'archive':
        op = baseline_project(root); path = op['objects'][0]['path']
    else:
        snapshot = project(root)
        path = {'attachment': 'attachments/owned.bin', 'profile': 'profiles/core.json',
                'registry': snapshot.registry_path}[kind]
    (root / path).unlink()
    before = inventory(root)
    with no_write_attempts(), pytest.raises(BundleError):
        prepare_project_bundle(root)
    assert inventory(root) == before


@pytest.mark.parametrize('path', ['.specroad/requests/item.json', '.specroad/transactions/receipts/item/transaction.json'])
def test_nonempty_receipt_history_is_not_silently_omitted(tmp_path, path):
    root = tmp_path / 'source'; project(root)
    put(root, path, b'opaque history is not a verified empty receipt set')
    before = inventory(root)
    with no_write_attempts(), pytest.raises(BundleError) as failure:
        prepare_project_bundle(root)
    assert failure.value.reason == 'bundle_receipt_path_invalid'
    assert failure.value.exit_code == 3 and inventory(root) == before


def test_explicitly_empty_receipt_directories_are_checked_and_accepted(tmp_path):
    root = tmp_path / 'source'; project(root)
    first = prepare_project_bundle(root)
    for name in ('.specroad/requests', '.specroad/transactions/receipts'):
        (root / name).mkdir(parents=True)
    assert prepare_project_bundle(root).source_bytes == first.source_bytes


@pytest.mark.parametrize('path', ['.specroad/transactions/active/journal.json', '.specroad/locks/writer.json',
                                  '.specroad/tmp/staging.json'])
def test_unresolved_state_refuses_without_writes(tmp_path, path):
    root = tmp_path / 'source'; project(root)
    put(root, path, b'not a portable successful state')
    before = inventory(root)
    with no_write_attempts(), pytest.raises(BundleError) as failure:
        prepare_project_bundle(root)
    assert failure.value.exit_code == 5 and inventory(root) == before


@pytest.mark.parametrize('path', ['profiles/core.json', 'attachments/owned.bin', '.specroad/requests'])
def test_source_links_are_not_followed(tmp_path, path):
    root = tmp_path / 'source'; project(root)
    outside = tmp_path / 'outside'; outside.mkdir()
    target = root / path
    if target.exists():
        target.unlink()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.symlink_to(outside)
    with no_write_attempts(), pytest.raises(BundleError) as failure:
        prepare_project_bundle(root)
    assert failure.value.exit_code == 7


@pytest.mark.parametrize('change', ['artifact', 'new_artifact', 'archive', 'receipt', 'transaction'])
def test_changes_during_encoding_cannot_return_stale_success(tmp_path, change):
    root = tmp_path / 'source'; project(root)
    encode = service.encode_bundle

    def changed(*args):
        raw = encode(*args)
        if change == 'artifact':
            path = artifact_path('goal', domain_value('goal')['id'], 'SR')
            put(root, path, (root / path).read_bytes() + b' ')
        elif change == 'new_artifact':
            value = domain_value('need')
            put(root, artifact_path('need', value['id'], 'SR'), canonical_json_bytes(value))
        elif change == 'archive':
            digest = sha256(b'extra').hexdigest()
            put(root, 'archive/objects/' + digest[:2] + '/' + digest, b'extra')
        elif change == 'receipt':
            put(root, '.specroad/requests/new.json', b'{}')
        else:
            put(root, '.specroad/transactions/active/journal.json', b'{}')
        return raw

    with patch.object(service, 'encode_bundle', changed), pytest.raises(BundleError) as failure:
        prepare_project_bundle(root)
    assert failure.value.exit_code in (5, 6)


def test_partial_marker_cannot_be_promoted_even_when_payload_has_closed_project_shape(tmp_path):
    root = tmp_path / 'source'; project(root)
    full = prepare_project_bundle(root)
    marker = full.manifest
    marker.update(bundle_kind='partial', read_only=True, idempotency_scope='local_only',
                  scope_descriptor=descriptor('document', {'document_id': record_value('document')['id']},
                                              boundary_policy='partial'))
    put(root, 'bundle-manifest.json', canonical_json_bytes(marker))
    before = inventory(root)
    with no_write_attempts(), pytest.raises(BundleError) as failure:
        prepare_project_bundle(root)
    assert failure.value.reason == 'bundle_partial_project_source' and failure.value.exit_code == 7
    assert inventory(root) == before


def test_invalid_native_artifact_fields_are_not_hidden_by_valid_container_hashes(tmp_path):
    root = tmp_path / 'source'; project(root)
    value = domain_value('goal'); value.pop('statement')
    put(root, artifact_path('goal', value['id'], 'SR'), canonical_json_bytes(value))
    with no_write_attempts(), pytest.raises(BundleError) as failure:
        prepare_project_bundle(root)
    assert failure.value.exit_code == 3


def test_missing_relation_target_cannot_become_an_empty_boundary_list(tmp_path):
    from support.relations import edge
    root = tmp_path / 'source'; project(root)
    value = domain_value('goal')
    value['relations'] = [edge('depends_on', domain_value('need')['id'])]
    put(root, artifact_path('goal', value['id'], 'SR'), canonical_json_bytes(value))
    with no_write_attempts(), pytest.raises(BundleError):
        prepare_project_bundle(root)
