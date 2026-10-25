"""15.d.W: owned-byte model verification and a project-free, nonwriting CLI."""
from hashlib import sha256
import json
from unittest.mock import patch

import pytest

from specroad.bundles import (BundleContainer, BundleError, encode_bundle, prepare_project_bundle,
                              verify_bundle, verify_bundle_file)
from specroad.bundles import verification_command as command
from specroad.cli.application import dispatch_result
from specroad.cli.result_schemas import validate_result_document
from specroad.model.canonical import canonical_json_bytes
from support.domain import domain_value
from support.model import put
from support.read_only import inventory, no_write_attempts
from support.relations import edge
from test_project_bundle import project, baseline_project


def bundle(root):
    project(root)
    return prepare_project_bundle(root)


def rebind(original, files=None, **metadata):
    value = original.manifest
    value.pop('entries')
    return encode_bundle({**value, **metadata}, original.files if files is None else files)


@pytest.mark.parametrize('kind', ['project', 'baseline', 'initialized'])
@pytest.mark.parametrize('external', [False, True])
def test_native_complete_inventory_is_verified_using_only_owned_bytes(tmp_path, kind, external):
    root = tmp_path / 'source'
    if kind == 'project':
        project(root)
    elif kind == 'baseline':
        baseline_project(root)
    else:
        assert dispatch_result(['init', str(root)]).exit_code == 0
    original = prepare_project_bundle(root)
    # Any attempted origin or distribution fallback read is forbidden. Data
    # from the original root is deliberately unavailable to the pure reader.
    with no_write_attempts(), patch('specroad.security.ProjectBoundary.read_bytes', side_effect=AssertionError):
        result = verify_bundle(original.source_bytes, expected_sha256=original.sha256 if external else None)
    validate_result_document('bundle-verify-v1', result)
    assert result['file'] == {'sha256': original.sha256, 'size': len(original.source_bytes)}
    assert result['manifest'] == original.manifest
    assert result['container_verified'] and result['closure_verified'] and result['model_root_verified']
    assert result['external_hash_verified'] is external
    assert result['validation_scope'] == 'closed_project_payload_model'
    assert not any(result[k] for k in ('creator_authenticated', 'write_authorized',
                                      'approval_granted', 'full_semantic_validation'))


@pytest.mark.parametrize('mode', ['cli_absolute', 'cli_relative', 'direct', 'structured'])
def test_explicit_file_without_project_is_verified_without_any_write(tmp_path, mode):
    original = bundle(tmp_path / 'source')
    target = tmp_path / 'input'; target.mkdir()
    filename = target / 'input.zip'; filename.write_bytes(original.source_bytes)
    # An invalid nearby configuration/operational state must never be read.
    put(target, 'specroad.json', b'not a project')
    put(target, '.specroad/locks/writer.json', b'not a usable lock')
    before = inventory(tmp_path)
    with no_write_attempts(), patch('specroad.cli.project_selection.select_project', side_effect=AssertionError):
        if mode == 'direct':
            result = verify_bundle_file(filename, expected_sha256=original.sha256)
        elif mode == 'structured':
            from specroad.cli.application import execute_request
            result = execute_request({'command_id': 'bundle.verify',
                'arguments': {'file': str(filename)}, 'options': {'--expected-sha256': original.sha256}}, cwd=target).result
        else:
            result = dispatch_result(['bundle', 'verify', filename.name if mode == 'cli_relative' else str(filename),
                                      '--expected-sha256', original.sha256], cwd=target)
    assert result.exit_code == 0, result.as_dict()
    value = result.as_dict()
    assert value['project'] is None and value['summary']['complete']
    assert value['result']['external_hash_verified'] is True
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('field', ['origin_model_root_sha256', 'bundle_model_root_sha256',
                                  'configuration_sha256', 'profile_sha256'])
def test_canonical_zip_inventory_does_not_validate_forged_native_bindings(tmp_path, field):
    original = bundle(tmp_path / 'source')
    fields = {field: 'a' * 64}
    if field.endswith('model_root_sha256'):
        fields.update(origin_model_root_sha256='a' * 64, bundle_model_root_sha256='a' * 64)
    raw = rebind(original, **fields)
    assert BundleContainer(raw).files == original.files
    with no_write_attempts(), pytest.raises(BundleError) as failure:
        verify_bundle(raw)
    assert (failure.value.exit_code, failure.value.code) == (3, 'SRV060')


@pytest.mark.parametrize('change', ['statement', 'dangling_relation', 'type', 'malformed_type', 'path',
                                   'attachment', 'registry', 'profile', 'missing_package'])
def test_recomputed_transport_hashes_cannot_hide_invalid_payload_models(tmp_path, change):
    root = tmp_path / 'source'
    if change == 'missing_package':
        assert dispatch_result(['init', str(root)]).exit_code == 0
        original = prepare_project_bundle(root)
    else:
        original = bundle(root)
    files = original.files
    goal = next((p for p in files if p.startswith('spec/goals/')), None)
    if change in ('statement', 'dangling_relation', 'type', 'malformed_type'):
        value = json.loads(files[goal])
        if change == 'statement':
            del value['statement']
        elif change == 'dangling_relation':
            value['relations'] = [edge('depends_on', domain_value('need')['id'])]
        else:
            value['artifact_type'] = 'need' if change == 'type' else []
        files[goal] = canonical_json_bytes(value)
    elif change == 'path':
        files[goal.replace('goals/', 'needs/')] = files.pop(goal)
    elif change == 'attachment':
        files['attachments/owned.bin'] = b'changed attachment'
    else:
        path = next(p for p in files if (p.endswith('registry.txt') if change == 'registry'
                    else p == 'profiles/core.json' if change == 'profile'
                    else p.startswith('profiles/language-data/packages/')))
        del files[path]
    raw = rebind(original, files)
    BundleContainer(raw)  # Transport inventory and actual bytes agree.
    with no_write_attempts(), pytest.raises(BundleError) as failure:
        verify_bundle(raw)
    assert failure.value.exit_code == 3


@pytest.mark.parametrize('extra', ['.env', '.specroad/locks/writer.json',
                                  'generated/file.json', 'README.md', 'attachments/orphan.bin'])
def test_additional_nonmodel_payload_is_not_silently_ignored(tmp_path, extra):
    original = bundle(tmp_path / 'source')
    raw = rebind(original, {**original.files, extra: b'not a native input'})
    BundleContainer(raw)
    with no_write_attempts(), pytest.raises(BundleError) as failure:
        verify_bundle(raw)
    assert failure.value.exit_code in (3, 7)


@pytest.mark.parametrize('external', [False, True])
def test_consistent_replacement_has_a_distinct_external_binding(tmp_path, external):
    root = tmp_path / 'source'; first = bundle(root)
    path = next(p for p in first.files if p.startswith('spec/goals/'))
    value = json.loads(first.files[path]); value['statement'] = 'Changed but valid goal.'
    put(root, path, canonical_json_bytes(value))
    second = prepare_project_bundle(root)
    assert first.sha256 != second.sha256
    assert first.manifest['bundle_model_root_sha256'] != second.manifest['bundle_model_root_sha256']
    if external:
        with no_write_attempts(), pytest.raises(BundleError) as failure:
            verify_bundle(second.source_bytes, expected_sha256=first.sha256)
        assert failure.value.code == 'SRV060' and failure.value.exit_code == 3
    else:
        with no_write_attempts():
            value = verify_bundle(second.source_bytes)
        assert value['external_hash_verified'] is False and value['creator_authenticated'] is False


def test_formatting_changes_zip_hash_but_preserves_the_semantic_model(tmp_path):
    original = bundle(tmp_path / 'source')
    files = original.files
    path = next(p for p in files if p.startswith('spec/goals/'))
    files[path] = json.dumps(json.loads(files[path]), indent=4).encode() + b'\n'
    raw = rebind(original, files)
    result = verify_bundle(raw)
    assert result['file']['sha256'] != original.sha256
    assert result['manifest']['bundle_model_root_sha256'] == original.manifest['bundle_model_root_sha256']


@pytest.mark.parametrize('kind', ['document', 'release'])
def test_partial_provider_gap_is_not_reported_as_verified(tmp_path, kind):
    from test_partial_bundle import project as partial_project, scope
    from specroad.bundles import prepare_partial_bundle
    root = tmp_path / 'source'; partial_project(root, kind)
    original = prepare_partial_bundle(root, scope(kind))
    with no_write_attempts(), pytest.raises(BundleError) as failure:
        verify_bundle(original.source_bytes)
    assert failure.value.reason == 'bundle_partial_verification_provider_required'
    assert failure.value.exit_code == 5


@pytest.mark.parametrize('path', ['.specroad/requests/item.json', '.specroad/transactions/receipts/item/transaction.json'])
def test_unimplemented_receipt_verification_is_not_claimed(tmp_path, path):
    original = bundle(tmp_path / 'source')
    raw = rebind(original, {**original.files, path: b'{}'})
    with no_write_attempts(), pytest.raises(BundleError) as failure:
        verify_bundle(raw)
    assert failure.value.reason == 'bundle_portable_receipt_provider_required'
    assert failure.value.exit_code == 5


@pytest.mark.parametrize('kind', ['missing', 'directory', 'symlink', 'invalid_zip', 'wrong_hash'])
def test_file_failure_never_creates_an_output_or_success_result(tmp_path, kind):
    original = bundle(tmp_path / 'source')
    path = tmp_path / 'input.zip'
    if kind == 'directory':
        path.mkdir()
    elif kind == 'symlink':
        target = tmp_path / 'target.zip'; target.write_bytes(original.source_bytes)
        path.symlink_to(target)
    elif kind != 'missing':
        path.write_bytes(b'not a ZIP' if kind == 'invalid_zip' else original.source_bytes)
    before = inventory(tmp_path)
    with no_write_attempts():
        result = verify_bundle_file(path, expected_sha256='a' * 64 if kind == 'wrong_hash' else None)
    assert result.exit_code == {'missing': 5, 'directory': 7, 'symlink': 7, 'invalid_zip': 3, 'wrong_hash': 3}[kind]
    assert result.as_dict()['result'] is None
    assert inventory(tmp_path) == before


def test_changed_input_after_verification_cannot_return_stale_success(tmp_path):
    original = bundle(tmp_path / 'source')
    path = tmp_path / 'input.zip'; path.write_bytes(original.source_bytes)
    verify = command.verify_bundle
    def changed(raw, **options):
        result = verify(raw, **options)
        path.write_bytes(b'changed by a concurrent actor')
        return result
    with patch.object(command, 'verify_bundle', changed):
        result = verify_bundle_file(path)
    assert result.exit_code == 6 and result.as_dict()['result'] is None
    assert path.read_bytes() == b'changed by a concurrent actor'


@pytest.mark.parametrize('arguments', [[], ['--project', 'other'], ['--output', 'output.zip'], ['--profile', 'core']])
def test_unimplemented_options_and_missing_file_fail_before_file_read(tmp_path, arguments):
    before = inventory(tmp_path)
    with no_write_attempts():
        result = dispatch_result(['bundle', 'verify', *arguments], cwd=tmp_path)
    assert result.exit_code == 2 and inventory(tmp_path) == before


def test_result_contract_rejects_invented_authority_and_missing_evidence(tmp_path):
    result = verify_bundle(bundle(tmp_path / 'source').source_bytes)
    validate_result_document('bundle-verify-v1', result)
    for field in ('creator_authenticated', 'approval_granted', 'write_authorized'):
        with pytest.raises(ValueError):
            validate_result_document('bundle-verify-v1', {**result, field: True})
    del result['model_root_verified']
    with pytest.raises(ValueError):
        validate_result_document('bundle-verify-v1', result)
