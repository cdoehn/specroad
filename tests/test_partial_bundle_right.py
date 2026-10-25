"""15.c.R: original configuration context, native scope and guarded publication."""
from hashlib import sha256
import json
from unittest.mock import patch

import pytest

from specroad.authoring._inspection_snapshot import InspectionSnapshot
from specroad.bundles import (BundleContainer, BundleError, create_partial_bundle,
                             prepare_partial_bundle, prepare_project_bundle)
from specroad.bundles import partial as service, publication
from specroad.cli.application import dispatch_result, execute_request
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.model.model_manifest import ModelManifest
from specroad.model.paths import artifact_path
from specroad.model.semantic_configuration import semantic_configuration
from support.domain import domain_value
from support.model import put
from support.read_only import inventory, no_write_attempts
from support.records import record_value, ref, srx
from support.srx import binary, expression_document, field, literal
from test_partial_bundle import edge, independent_root, project, records, save, scope


def configured(root, kind='document', child=True):
    values = project(root, kind)
    parent = record_value('configuration')
    chain = [parent]
    if child:
        chain.append(record_value('configuration', id=ref('CFG', '1'), name='Child',
                                  parent=parent['id'], dimensions=[], selection={}))
    unrelated = record_value('configuration', id=ref('CFG', '2'), name='Other')
    for value in (*chain, unrelated):
        save(root, value)
    return values, chain, unrelated


def config_oracle(root, bundle, chain):
    # Resolve this synthetic chain independently from its transported bytes.
    # The fixture inherits one dimension unchanged; later selections override it.
    actual = [json.loads(bundle.files[artifact_path('configuration', v['id'], 'SR')]) for v in chain]
    selected = {}
    for value in actual:
        selected.update(value['selection'])
    effective = {'manifest_version': 'effective-configuration-v1', 'configuration_id': actual[-1]['id'],
                 'configurations': [{'id': v['id'], 'revision': v['revision'],
                                     'sha256': canonical_json_sha256(v)} for v in actual],
                 'dimensions': actual[0]['dimensions'], 'effective_values': selected}
    configuration = InspectionSnapshot(root, None).model.configuration
    return canonical_json_sha256({
        'project_configuration_sha256': canonical_json_sha256(semantic_configuration(configuration)),
        'selected_configuration_sha256': canonical_json_sha256(effective)})


def root_oracle(root, bundle, members, configuration_hash):
    # The independent W oracle reads actual files, without calling export_scope.
    # Only explicit fixture members enter the model; transported context does not.
    data = independent_root(root, bundle).data
    data['artifacts'] = [v for v in data['artifacts'] if v['id'] in members]
    assert {v['id'] for v in data['artifacts']} == set(members)
    data['configuration_sha256'] = configuration_hash
    data['scope_sha256'] = canonical_json_sha256({k: v for k, v in data.items()
                                                if k not in ('scope_sha256', 'model_manifest_version')})
    return ModelManifest(data).sha256


def configuration_resources(root, configuration):
    """Configuration -> source -> evidence -> attachment, all native schemas."""
    raw = b'original evidence for a configuration dependency'
    path = 'attachments/configuration.bin'
    evidence = record_value('evidence', attachments=[{'path': path, 'size': len(raw),
        'media_type': 'application/octet-stream', 'sha256': sha256(raw).hexdigest()}])
    source = record_value('source', relations=[edge('references', evidence['id'], 11)])
    configuration['relations'].append(edge('derived_from', source['id'], 10))
    for value in (source, evidence, configuration):
        save(root, value)
    put(root, path, raw)
    return (source, evidence), path, raw


@pytest.mark.parametrize('kind', ['document', 'release'])
@pytest.mark.parametrize('child', [False, True])
def test_original_chain_bytes_are_context_not_extra_model_members(tmp_path, kind, child):
    root = tmp_path / 'origin'; values, chain, other = configured(root, kind, child)
    for value in chain:
        put(root, artifact_path('configuration', value['id'], 'SR'),
            json.dumps(value, indent=3).encode() + b'\n')
    selection = scope(kind, configuration_id=chain[-1]['id'])
    before = inventory(root)
    with no_write_attempts():
        bundle = prepare_partial_bundle(root, selection)
    assert inventory(root) == before
    members = {v['id'] for v in values[:-2]}
    assert {r.identity.id for r in records(bundle)} == members | {v['id'] for v in chain}
    native = InspectionSnapshot(root, None)
    assert set(bundle.files) == {'specroad.json', 'profiles/core.json', native.registry_path,
        *(artifact_path(v['artifact_type'], v['id'], 'SR') for v in (*values[:-2], *chain))}
    assert all(raw == native.raw[p] for p, raw in bundle.files.items())
    config_hash = config_oracle(root, bundle, chain)
    assert bundle.manifest['configuration_sha256'] == config_hash
    assert bundle.manifest['bundle_model_root_sha256'] == root_oracle(tmp_path / 'oracle', bundle, members, config_hash)
    assert bundle.manifest['origin_model_root_sha256'] == prepare_project_bundle(root).manifest['bundle_model_root_sha256']
    assert bundle.manifest['origin_model_root_sha256'] != bundle.manifest['bundle_model_root_sha256']
    assert bundle.manifest['read_only'] is True and bundle.manifest['bundle_kind'] == 'partial'
    assert bundle.manifest['idempotency_scope'] == 'local_only'
    assert bundle.manifest['scope_descriptor'] == selection.data
    excluded = {v['path'] for v in bundle.manifest['excluded_contents']}
    assert not excluded.intersection(bundle.files)
    assert artifact_path('configuration', other['id'], 'SR') in excluded


@pytest.mark.parametrize('kind', ['document', 'release'])
@pytest.mark.parametrize('change', ['parent_content', 'parent_revision', 'formatting', 'unrelated'])
def test_parent_and_transport_changes_have_distinct_hash_domains(tmp_path, kind, change):
    root = tmp_path / 'origin'; _, chain, other = configured(root, kind)
    selection = scope(kind, configuration_id=chain[-1]['id'])
    first = prepare_partial_bundle(root, selection)
    value = other if change == 'unrelated' else chain[0]
    path = artifact_path('configuration', value['id'], 'SR')
    if change == 'formatting':
        put(root, path, json.dumps(value, indent=4).encode() + b'\n')
    else:
        if change == 'parent_revision':
            value['revision'] += 1
        else:
            value['title'] += ' changed without changing selection'
        save(root, value)
    second = prepare_partial_bundle(root, selection)
    assert first.sha256 != second.sha256
    for key in ('configuration_sha256', 'bundle_model_root_sha256'):
        assert (first.manifest[key] == second.manifest[key]) == (change in ('formatting', 'unrelated'))
    assert (first.manifest['origin_model_root_sha256'] == second.manifest['origin_model_root_sha256']) == (change == 'formatting')
    assert (first.files == second.files) == (change == 'unrelated')
    assert second.manifest['configuration_sha256'] == config_oracle(root, second, chain)


@pytest.mark.parametrize('kind', ['document', 'release'])
def test_inherited_child_override_selects_anchor_without_changing_unconfigured_scope(tmp_path, kind):
    root = tmp_path / 'origin'; values, chain, _ = configured(root, kind)
    values[0]['applicability'] = expression_document(
        binary('eq', field('/effective_values/platform', 'configuration'), literal('windows')))
    save(root, values[0])
    chain[-1]['selection'] = {'platform': 'windows'}; save(root, chain[-1])
    before = inventory(root)
    with no_write_attempts():
        selected = prepare_partial_bundle(root, scope(kind, configuration_id=chain[-1]['id']))
        unconfigured = prepare_partial_bundle(root, scope(kind))
        with pytest.raises(BundleError) as error:
            prepare_partial_bundle(root, scope(kind, configuration_id=chain[0]['id']))
    assert error.value.reason == 'bundle_partial_anchor_excluded' and error.value.exit_code == 3
    assert selected.manifest['configuration_sha256'] == config_oracle(root, selected, chain)
    assert {r.identity.id for r in records(unconfigured)} == {v['id'] for v in values[:-2]}
    assert inventory(root) == before


@pytest.mark.parametrize('kind', ['document', 'release'])
@pytest.mark.parametrize('reached', [False, True])
def test_context_edges_expand_only_when_configuration_is_a_real_member(tmp_path, kind, reached):
    root = tmp_path / 'origin'; values, chain, other = configured(root, kind)
    dependency = domain_value('component')
    chain[-1]['relations'] = [edge('depends_on', dependency['id'], 8), edge('duplicates', other['id'], 9)]
    resource_members, attachment_path, attachment = configuration_resources(root, chain[-1])
    if reached:
        values[-3]['relations'].append(edge('depends_on', chain[-1]['id'], 7))
        save(root, values[-3])
    for value in (dependency, chain[-1]):
        save(root, value)
    bundle = prepare_partial_bundle(root, scope(kind, configuration_id=chain[-1]['id']))
    members = {v['id'] for v in values[:-2]}
    if reached:
        members |= {chain[-1]['id'], dependency['id'], *(v['id'] for v in resource_members)}
    assert {r.identity.id for r in records(bundle)} == members | {v['id'] for v in chain}
    assert (attachment_path in bundle.files) == reached
    if reached:
        assert bundle.files[attachment_path] == attachment
    boundaries = bundle.manifest['boundary_references']
    assert len(boundaries) == (2 if reached else 1)
    config_boundaries = [b for b in boundaries if b['source_id'] == chain[-1]['id']]
    assert bool(config_boundaries) == reached
    if reached:
        assert config_boundaries[0]['origin_target_sha256'] == canonical_json_sha256(other)
    config_hash = config_oracle(root, bundle, chain)
    assert bundle.manifest['bundle_model_root_sha256'] == root_oracle(tmp_path / 'oracle', bundle, members, config_hash)


@pytest.mark.parametrize('reached', [False, True])
def test_missing_target_of_configuration_is_invalid_even_when_context_only(tmp_path, reached):
    root = tmp_path / 'origin'; values, chain, _ = configured(root)
    chain[-1]['relations'] = [edge('depends_on', ref('COMP'), 8)]
    save(root, chain[-1])
    if reached:
        values[-3]['relations'].append(edge('depends_on', chain[-1]['id'], 7)); save(root, values[-3])
    before = inventory(root)
    with no_write_attempts(), pytest.raises(BundleError) as error:
        prepare_partial_bundle(root, scope(configuration_id=chain[-1]['id']))
    assert error.value.exit_code == 3 and inventory(root) == before


@pytest.mark.parametrize('reached', [False, True])
def test_missing_configuration_attachment_cannot_hide_in_context(tmp_path, reached):
    root = tmp_path / 'origin'; values, chain, _ = configured(root)
    _, attachment_path, _ = configuration_resources(root, chain[-1])
    if reached:
        values[-3]['relations'].append(edge('depends_on', chain[-1]['id'], 7)); save(root, values[-3])
    selection = scope(configuration_id=chain[-1]['id'])
    with no_write_attempts():
        assert (attachment_path in prepare_partial_bundle(root, selection).files) == reached
    (root / attachment_path).unlink()
    before = inventory(root)
    with no_write_attempts(), pytest.raises(BundleError) as error:
        prepare_partial_bundle(root, selection)
    assert error.value.exit_code == 5 and error.value.reason == 'bundle_project_io'
    assert isinstance(error.value.__cause__, FileNotFoundError) and inventory(root) == before


@pytest.mark.parametrize('kind', ['document', 'release'])
@pytest.mark.parametrize('fault', ['missing_configuration', 'missing_parent', 'parent_cycle', 'dimension',
                                 'selection', 'missing_anchor', 'excluded_anchor', 'excluded_dependency'])
def test_invalid_configuration_or_required_selection_fails_before_output(tmp_path, kind, fault):
    root = tmp_path / 'origin'; values, chain, _ = configured(root, kind)
    selected, anchor = chain[-1]['id'], values[0]['id']
    if fault == 'missing_configuration':
        selected = ref('CFG', '3')
    elif fault == 'missing_parent':
        (root / artifact_path('configuration', chain[0]['id'], 'SR')).unlink()
    elif fault == 'parent_cycle':
        chain[0]['parent'] = chain[-1]['id']; save(root, chain[0])
    elif fault == 'dimension':
        chain[-1]['dimensions'] = [{'name': 'platform', 'allowed_values': ['other']}]; save(root, chain[-1])
    elif fault == 'selection':
        chain[-1]['selection'] = {'platform': 'other'}; save(root, chain[-1])
    elif fault == 'missing_anchor':
        anchor = ref('DOC' if kind == 'document' else 'REL', '3')
    else:
        value = values[0] if fault == 'excluded_anchor' else values[-2]
        value['applicability'] = srx(); value['applicability']['expression']['value'] = False
        save(root, value)
        if fault == 'excluded_dependency':
            values[-3]['relations'].append(edge('depends_on', value['id'], 7)); save(root, values[-3])
    before = inventory(root)
    with no_write_attempts():
        result = create_partial_bundle(root, scope(kind, anchor, configuration_id=selected), output='generated/partial.zip')
    assert result.exit_code == 3 and result.result is None, result.as_dict()
    assert inventory(root) == before


@pytest.mark.parametrize('fault', ['drop_parent', 'add_unrelated', 'replace_context', 'configuration_hash',
                                 'writable', 'project_kind', 'closed_scope'])
def test_codec_cannot_smuggle_payload_or_metadata_changes_into_generated_partial(tmp_path, fault):
    root = tmp_path / 'origin'; _, chain, other = configured(root)
    encode = service.encode_bundle
    def changed(metadata, payloads):
        metadata, payloads = dict(metadata), dict(payloads)
        parent = artifact_path('configuration', chain[0]['id'], 'SR')
        if fault == 'drop_parent':
            del payloads[parent]
        elif fault == 'add_unrelated':
            path = artifact_path('configuration', other['id'], 'SR')
            payloads[path] = (root / path).read_bytes()
            metadata['excluded_contents'] = [v for v in metadata['excluded_contents'] if v['path'] != path]
        elif fault == 'replace_context':
            payloads[parent] = json.dumps(chain[0], indent=3).encode()
        elif fault == 'configuration_hash':
            metadata['configuration_sha256'] = 'a' * 64
        elif fault == 'writable':
            metadata['read_only'] = False
        elif fault == 'project_kind':
            metadata['bundle_kind'] = 'project'
        else:
            metadata['scope_descriptor'] = {**metadata['scope_descriptor'], 'boundary_policy': 'closed'}
        return encode(metadata, payloads)
    before = inventory(root)
    with no_write_attempts(), patch.object(service, 'encode_bundle', changed), pytest.raises(BundleError) as error:
        prepare_partial_bundle(root, scope(configuration_id=chain[-1]['id']))
    assert error.value.exit_code == 3 and inventory(root) == before


@pytest.mark.parametrize('kind', ['document', 'release'])
@pytest.mark.parametrize('with_configuration', [False, True])
@pytest.mark.parametrize('mode', ['cli', 'structured', 'direct'])
def test_partial_publication_uses_the_same_original_bytes_and_readonly_contract(tmp_path, kind, with_configuration, mode):
    root = tmp_path / 'origin'; _, chain, _ = configured(root, kind)
    configuration = chain[-1]['id'] if with_configuration else None
    selection = scope(kind, configuration_id=configuration)
    expected = prepare_partial_bundle(root, selection)
    before = inventory(root)
    options = {'--project': str(root), '--scope': kind, '--' + kind: selection.data['selector'][kind + '_id'],
               '--output': 'generated/partial.zip', '--format': 'json'}
    if with_configuration:
        options['--configuration'] = configuration
    if mode == 'direct':
        result = create_partial_bundle(root, selection, output=options['--output'])
    elif mode == 'structured':
        result = execute_request({'command_id': 'bundle.create', 'options': options}).result
    else:
        result = dispatch_result(['bundle', 'create', *(s for pair in options.items() for s in pair)])
    assert result.exit_code == 0, result.as_dict()
    raw = (root / options['--output']).read_bytes()
    assert raw == expected.source_bytes
    assert result.as_dict()['result']['manifest'] == expected.manifest
    assert result.result['file'] == {'path': options['--output'], 'size': len(raw), 'sha256': sha256(raw).hexdigest()}
    assert result.result['source_bytes_rechecked']
    assert not any(result.result[k] for k in ('write_authorized', 'approval_granted', 'full_semantic_validation', 'atomic_snapshot'))
    assert tuple(r for r in inventory(root) if not r[0].startswith('generated')) == before
    assert sorted(p.name for p in (root / 'generated').iterdir()) == ['partial.zip']


@pytest.mark.parametrize('kind', ['document', 'release'])
def test_explicit_separate_output_retains_relocatable_partial_bytes(tmp_path, kind):
    root = tmp_path / 'origin'; _, chain, _ = configured(root, kind)
    destination = tmp_path / 'output'; destination.mkdir()
    selection = scope(kind, configuration_id=chain[-1]['id'])
    expected = prepare_partial_bundle(root, selection); before = inventory(root)
    result = create_partial_bundle(root, selection, output='nested/partial.zip', output_root=str(destination))
    assert result.exit_code == 0, result.as_dict()
    assert (destination / 'nested/partial.zip').read_bytes() == expected.source_bytes
    assert inventory(root) == before


@pytest.mark.parametrize('options', [
    {'--scope': 'project', '--document': ref('DOC')},
    {'--scope': 'project', '--release': ref('REL')},
    {'--scope': 'document', '--release': ref('REL')},
    {'--scope': 'release', '--document': ref('DOC')},
    {'--scope': 'document', '--document': ref('DOC'), '--release': ref('REL')},
    {'--scope': 'project', '--configuration': ref('CFG')},
])
def test_selector_combinations_are_usage_errors_without_writes(tmp_path, options):
    root = tmp_path / 'origin'; configured(root); before = inventory(root)
    with no_write_attempts():
        result = execute_request({'command_id': 'bundle.create', 'options': {
            '--project': str(root), '--output': 'generated/partial.zip', **options}}).result
    assert result.exit_code == 2 and inventory(root) == before, result.as_dict()


@pytest.mark.parametrize('options', [
    {'--document': ref('REL')}, {'--document': 'not-an-id'},
    {'--document': ref('DOC'), '--configuration': ref('DOC')},
])
def test_malformed_or_wrong_type_cli_identity_is_a_model_error(tmp_path, options):
    root = tmp_path / 'origin'; configured(root); before = inventory(root)
    with no_write_attempts():
        result = execute_request({'command_id': 'bundle.create', 'options': {
            '--project': str(root), '--scope': 'document', '--output': 'generated/partial.zip', **options}}).result
    assert result.exit_code == 3 and inventory(root) == before, result.as_dict()


@pytest.mark.parametrize('selector', [None, False, {}, 'project'])
def test_untyped_partial_request_cannot_fall_back_to_full_project(tmp_path, selector):
    root = tmp_path / 'origin'; configured(root); before = inventory(root)
    with no_write_attempts():
        result = create_partial_bundle(root, selector, output='generated/partial.zip')
    assert result.exit_code == 3 and inventory(root) == before, result.as_dict()


@pytest.mark.parametrize('fault', ['parent_link', 'output_link', 'traversal', 'collision', 'existing'])
def test_partial_safety_and_create_only_boundaries_do_not_change_other_bytes(tmp_path, fault):
    root = tmp_path / 'origin'; _, chain, _ = configured(root)
    output = 'generated/partial.zip'
    outside = tmp_path / 'outside'; outside.write_bytes(b'owned outside bytes')
    if fault == 'parent_link':
        path = root / artifact_path('configuration', chain[0]['id'], 'SR')
        path.unlink(); path.symlink_to(outside)
    elif fault == 'output_link':
        (root / 'generated').mkdir(); (root / output).symlink_to(outside)
    elif fault == 'traversal':
        output = 'generated/../outside.zip'
    elif fault == 'collision':
        put(root, 'generated/PARTIAL.zip', b'other file')
    else:
        put(root, output, b'other file')
    before = inventory(root)
    with no_write_attempts():
        result = create_partial_bundle(root, scope(configuration_id=chain[-1]['id']), output=output)
    assert result.exit_code == (6 if fault in ('existing', 'output_link') else 7), result.as_dict()
    assert inventory(root) == before and outside.read_bytes() == b'owned outside bytes'


@pytest.mark.parametrize('when', ['prepared', 'encoded', 'publishing'])
@pytest.mark.parametrize('change', ['parent', 'unrelated', 'new_configuration', 'receipt'])
def test_partial_publication_retains_original_observation_through_last_check(tmp_path, when, change):
    root = tmp_path / 'origin'; _, chain, other = configured(root)
    def mutate():
        if change == 'receipt':
            put(root, '.specroad/requests/new.json', b'new history')
        elif change == 'new_configuration':
            save(root, record_value('configuration', id=ref('CFG', '3'), name='New'))
        else:
            value = chain[0] if change == 'parent' else other
            value['title'] += ' changed'; save(root, value)
    if when == 'prepared':
        target, name = publication, '_prepare_partial'
    elif when == 'encoded':
        target, name = service, 'encode_bundle'
    else:
        target, name = publication, '_write_new'
    original = getattr(target, name)
    def changed(*args, **kwargs):
        result = original(*args, **kwargs); mutate(); return result
    with patch.object(target, name, changed):
        result = create_partial_bundle(root, scope(configuration_id=chain[-1]['id']), output='generated/partial.zip')
    assert result.exit_code == (5 if change == 'receipt' else 6), result.as_dict()
    assert result.result is None and not (root / 'generated/partial.zip').exists()
    if when == 'publishing':
        pending = list((root / 'generated').glob('.specroad-bundle-*.tmp'))
        assert len(pending) == 1
        assert BundleContainer(pending[0].read_bytes()).manifest['read_only'] is True
    else:
        assert not (root / 'generated').exists()
