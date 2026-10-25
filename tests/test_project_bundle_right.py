"""15.b.R: complete generated ZIPs, exact retained inputs and fail-closed publication."""
from hashlib import sha256
import json
import os
from unittest.mock import patch

import pytest

from specroad.bundles import BundleContainer, BundleError, create_project_bundle, prepare_project_bundle
from specroad.bundles import project as service, publication
from specroad.cli.application import dispatch_result, execute_request
from specroad.cli.commands import builtin_registry
from specroad.cli.result_schemas import validate_result_document
from specroad.model.canonical import canonical_json_bytes
from specroad.model.paths import artifact_path
from support.domain import domain_value
from support.model import put
from support.read_only import inventory, no_write_attempts
from support.records import record_value
from support.scopes import descriptor
from test_project_bundle import project, baseline_project


def create(root, output='generated/bundles/project.zip', **options):
    return create_project_bundle(root, output=output, **options)


def test_cli_registry_declares_implemented_project_and_partial_creation():
    command = builtin_registry().resolve('bundle.create')
    assert command.command_class.value == 'generated_output'
    assert command.preflight_profile.value == 'project_read'
    assert command.effect_scope.value == 'external_output'
    assert next(o for o in command.options if o.flag == '--scope').choices == ('project', 'document', 'release')
    assert not any(o.flag in ('--profile', '--exclude-operational-receipts') for o in command.options)
    result = dispatch_result(['command', 'describe', 'bundle.create'])
    assert result.exit_code == 0, result.as_dict()
    schema = dispatch_result(['schema', 'show', 'bundle-create-v1'])
    assert schema.exit_code == 0, schema.as_dict()


@pytest.mark.parametrize('mode', ['cli', 'structured', 'direct'])
def test_creation_publishes_exact_complete_bytes_and_only_generated_output(tmp_path, mode):
    root = tmp_path / 'project'; snapshot = project(root)
    expected = prepare_project_bundle(root)
    before = inventory(root)
    options = {'--project': str(root), '--scope': 'project', '--output': 'generated/bundle.zip', '--format': 'json'}
    if mode == 'cli':
        result = dispatch_result(['bundle', 'create', *(item for pair in options.items() for item in pair)])
    elif mode == 'structured':
        result = execute_request({'command_id': 'bundle.create', 'options': options}).result
    else:
        result = create(root, options['--output'])
    assert result.exit_code == 0, result.as_dict()
    data = result.as_dict()['result']
    validate_result_document('bundle-create-v1', data)
    raw = (root / options['--output']).read_bytes()
    assert raw == expected.source_bytes
    bundle = BundleContainer(raw, expected_sha256=data['file']['sha256'])
    assert bundle.files == snapshot.raw and data['manifest'] == bundle.manifest
    assert data['file'] == {'path': options['--output'], 'size': len(raw), 'sha256': sha256(raw).hexdigest()}
    assert data['manifest']['scope_descriptor'] == descriptor('project')
    assert data['generated'] and data['source_bytes_rechecked']
    assert not any(data[k] for k in ('normative', 'atomic_snapshot', 'full_semantic_validation',
                                    'approval_granted', 'write_authorized'))
    assert tuple(r for r in inventory(root) if not r[0].startswith('generated')) == before
    assert sorted(p.name for p in (root / 'generated').iterdir()) == ['bundle.zip']


def test_explicit_external_output_is_relocatable_and_does_not_mutate_source(tmp_path):
    root = tmp_path / 'project'; project(root)
    before = inventory(root)
    outputs = []
    for name in ('first', 'second'):
        destination = tmp_path / name; destination.mkdir()
        result = create(root, 'nested/project.zip', output_root=str(destination))
        assert result.exit_code == 0, result.as_dict()
        outputs.append((destination / 'nested/project.zip').read_bytes())
        assert not (destination / '.specroad').exists()
    assert outputs[0] == outputs[1] and inventory(root) == before


def test_initialization_language_packages_and_baseline_objects_survive_publication(tmp_path):
    initialized = tmp_path / 'initialized'
    assert dispatch_result(['init', str(initialized)]).exit_code == 0
    result = create(initialized)
    assert result.exit_code == 0, result.as_dict()
    bundle = BundleContainer((initialized / 'generated/bundles/project.zip').read_bytes())
    assert len([p for p in bundle.files if p.startswith('profiles/language-data/packages/')]) == 9
    root = tmp_path / 'baseline'; op = baseline_project(root)
    result = create(root)
    assert result.exit_code == 0, result.as_dict()
    bundle = BundleContainer((root / 'generated/bundles/project.zip').read_bytes())
    assert all(bundle.files[e['path']] == (root / e['path']).read_bytes() for e in op['objects'])


@pytest.mark.parametrize('options', [
    {}, {'--scope': 'project'}, {'--output': 'generated/project.zip'},
    {'--scope': 'project', '--output': 'generated/project.zip', '--configuration': 'SR-CFG-0001'},
    {'--scope': 'document', '--output': 'generated/project.zip'},
    {'--scope': 'release', '--output': 'generated/project.zip'},
    {'--scope': 'project', '--output': 'generated/project.zip', '--exclude-operational-receipts': True},
    {'--scope': 'project', '--output': 'generated/project.zip', '--profile': 'ai-runtime'},
])
def test_invalid_or_unimplemented_selections_fail_without_writes(tmp_path, options):
    root = tmp_path / 'project'; project(root); before = inventory(root)
    with no_write_attempts():
        result = execute_request({'command_id': 'bundle.create', 'options': {'--project': str(root), **options}}).result
    assert result.exit_code == 2, result.as_dict()
    assert inventory(root) == before


@pytest.mark.parametrize('output', ['specroad.json', 'spec/goals/overwrite.json', '.specroad/out.zip',
                                  'generated', '../outside.zip', '/absolute.zip', 'generated/../out.zip',
                                  'generated/.git/config', 'generated/NUL.zip'])
def test_unsafe_or_normative_destinations_are_refused_without_writes(tmp_path, output):
    root = tmp_path / 'project'; project(root); before = inventory(root)
    with no_write_attempts():
        result = create(root, output)
    assert result.exit_code == 7, result.as_dict()
    assert inventory(root) == before


@pytest.mark.parametrize('kind', ['source', 'ancestor', 'nested', 'other_project', 'symlink'])
def test_external_output_root_must_be_separate_and_canonical(tmp_path, kind):
    root = tmp_path / 'project'; project(root)
    if kind == 'source':
        destination = root
    elif kind == 'ancestor':
        destination = tmp_path
    elif kind == 'nested':
        destination = root / 'sub'; destination.mkdir()
    elif kind == 'other_project':
        destination = tmp_path / 'other'; project(destination)
    else:
        real = tmp_path / 'real'; real.mkdir()
        destination = tmp_path / 'alias'; destination.symlink_to(real, target_is_directory=True)
    before = inventory(root)
    with no_write_attempts():
        result = create(root, 'out.zip', output_root=str(destination))
    assert result.exit_code == 7, result.as_dict()
    assert inventory(root) == before


@pytest.mark.parametrize('kind', ['file', 'directory', 'symlink', 'fifo', 'leaf_case', 'parent_case', 'nested_project'])
def test_existing_or_unsafe_output_is_never_replaced(tmp_path, kind):
    root = tmp_path / 'project'; project(root)
    output = root / 'generated/sub/project.zip'; output.parent.mkdir(parents=True)
    if kind == 'file':
        output.write_bytes(b'keep')
    elif kind == 'directory':
        output.mkdir()
    elif kind == 'symlink':
        output.symlink_to(tmp_path / 'unopened')
    elif kind == 'fifo':
        os.mkfifo(output)
    elif kind == 'leaf_case':
        output.with_name('PROJECT.ZIP').write_bytes(b'keep')
    elif kind == 'parent_case':
        (root / 'generated/Sub').mkdir()
    else:
        put(root, 'generated/sub/specroad.json', b'{}')
    with no_write_attempts():
        result = create(root, 'generated/sub/project.zip')
    assert result.exit_code == (6 if kind in ('file', 'directory', 'symlink', 'fifo') else 7), result.as_dict()
    if kind == 'file':
        assert output.read_bytes() == b'keep'
    assert not list((root / 'generated/sub').glob('.specroad-bundle-*'))


@pytest.mark.parametrize('path', ['.specroad/transactions/active/journal.json', '.specroad/locks/writer.json',
                                 '.specroad/tmp/staging.json', '.specroad/requests/item.json',
                                 '.specroad/transactions/receipts/item/transaction.json'])
def test_unresolved_or_unverified_history_prevents_normal_completion(tmp_path, path):
    root = tmp_path / 'project'; project(root); put(root, path, b'{}')
    before = inventory(root)
    with no_write_attempts():
        result = create(root)
    assert result.exit_code == 5 and inventory(root) == before, result.as_dict()
    assert result.as_dict()['result'] is None and not result.complete


@pytest.mark.parametrize('kind', ['attachment', 'archive', 'profile', 'registry', 'language_package'])
def test_missing_required_source_never_publishes_a_zip(tmp_path, kind):
    root = tmp_path / 'project'
    if kind == 'archive':
        path = baseline_project(root)['objects'][0]['path']
    elif kind == 'language_package':
        assert dispatch_result(['init', str(root)]).exit_code == 0
        path = next(p.relative_to(root).as_posix() for p in (root / 'profiles/language-data/packages').glob('*.json'))
    else:
        snapshot = project(root)
        path = {'attachment': 'attachments/owned.bin', 'profile': 'profiles/core.json',
                'registry': snapshot.registry_path}[kind]
    (root / path).unlink(); before = inventory(root)
    with no_write_attempts():
        result = create(root)
    assert result.exit_code in (3, 5) and inventory(root) == before, result.as_dict()
    assert not (root / 'generated/bundles/project.zip').exists()


@pytest.mark.parametrize('change', ['artifact', 'missing_attachment', 'new_artifact', 'receipt', 'transaction',
                                   'archive', 'root_manifest'])
def test_changes_after_preparation_are_rechecked_before_any_output(tmp_path, change):
    root = tmp_path / 'project'; project(root)
    original = publication._prepare
    def changed(*args):
        prepared = original(*args)
        if change == 'artifact':
            path = artifact_path('goal', domain_value('goal')['id'], 'SR')
            put(root, path, (root / path).read_bytes() + b' ')
        elif change == 'missing_attachment':
            (root / 'attachments/owned.bin').unlink()
        elif change == 'new_artifact':
            value = domain_value('need')
            put(root, artifact_path('need', value['id'], 'SR'), canonical_json_bytes(value))
        elif change == 'receipt':
            put(root, '.specroad/requests/new.json', b'{}')
        elif change == 'transaction':
            put(root, '.specroad/transactions/new/journal.json', b'{}')
        elif change == 'archive':
            digest = sha256(b'extra').hexdigest()
            put(root, 'archive/objects/' + digest[:2] + '/' + digest, b'extra')
        else:
            put(root, 'bundle-manifest.json', prepared[0].manifest_bytes)
        return prepared
    with patch.object(publication, '_prepare', changed):
        result = create(root)
    assert result.exit_code in (5, 6), result.as_dict()
    assert not (root / 'generated').exists()


@pytest.mark.parametrize('change', ['source', 'target', 'private_image', 'directory', 'transaction'])
def test_changes_at_final_publication_boundary_cannot_claim_success(tmp_path, change):
    root = tmp_path / 'project'; project(root)
    original = publication._write_new
    target = root / 'generated/bundles/project.zip'
    def changed(parent, name, raw):
        identity = original(parent, name, raw)
        if change == 'source':
            put(root, 'attachments/owned.bin', b'changed source')
        elif change == 'target':
            target.write_bytes(b'competing output')
        elif change == 'private_image':
            (target.parent / name).write_bytes(b'changed private image')
        elif change == 'directory':
            target.parent.rename(target.parent.with_name('old'))
            target.parent.mkdir()
        else:
            put(root, '.specroad/transactions/new/journal.json', b'{}')
        return identity
    with patch.object(publication, '_write_new', changed):
        result = create(root)
    assert result.exit_code in (5, 6), result.as_dict()
    assert result.as_dict()['result'] is None
    if change == 'target':
        assert target.read_bytes() == b'competing output'
    else:
        assert not target.exists()
    assert list((root / 'generated').rglob('.specroad-bundle-*.tmp'))


@pytest.mark.parametrize('fault', ['write', 'link', 'after_link'])
def test_io_failure_preserves_actual_images_and_never_returns_completion(tmp_path, fault):
    root = tmp_path / 'project'; project(root)
    before = inventory(root)
    original = publication.replace_bound_image
    if fault == 'write':
        target_patch = patch.object(publication, '_write_new', side_effect=OSError('disk full'))
    elif fault == 'link':
        target_patch = patch('specroad.changes._publication_io.os.link', side_effect=OSError('link failed'))
    else:
        def failed(*args, **kwargs):
            original(*args, **kwargs)
            raise OSError('sync failed after actual publication')
        target_patch = patch.object(publication, 'replace_bound_image', failed)
    with target_patch:
        result = create(root)
    assert result.exit_code == 5 and not result.complete, result.as_dict()
    assert result.as_dict()['result'] is None
    target = root / 'generated/bundles/project.zip'
    if fault == 'after_link':
        BundleContainer(target.read_bytes())
    else:
        assert not target.exists()
    assert tuple(r for r in inventory(root) if not r[0].startswith('generated')) == before


def test_partial_source_marker_remains_a_write_free_rejection(tmp_path):
    root = tmp_path / 'project'; project(root)
    marker = prepare_project_bundle(root).manifest
    marker.update(bundle_kind='partial', read_only=True, idempotency_scope='local_only',
        scope_descriptor=descriptor('document', {'document_id': record_value('document')['id']},
                                    boundary_policy='partial'))
    put(root, 'bundle-manifest.json', canonical_json_bytes(marker)); before = inventory(root)
    with no_write_attempts():
        result = create(root)
    assert result.exit_code == 7 and inventory(root) == before, result.as_dict()


@pytest.mark.parametrize('change', ['omitted_resource', 'metadata'])
def test_self_consistent_container_cannot_replace_complete_selected_source(tmp_path, change):
    root = tmp_path / 'project'; project(root)
    original = service.encode_bundle
    def incomplete(metadata, payloads):
        metadata, payloads = dict(metadata), dict(payloads)
        if change == 'omitted_resource':
            payloads.pop('mappings/export.json')
        else:
            metadata['profile_sha256'] = 'f' * 64
        return original(metadata, payloads)
    with patch.object(service, 'encode_bundle', incomplete), no_write_attempts():
        with pytest.raises(BundleError) as failure:
            prepare_project_bundle(root)
        result = create(root)
    assert failure.value.exit_code == result.exit_code == 3
    assert failure.value.code == 'SRV060'
    assert not (root / 'generated').exists()
