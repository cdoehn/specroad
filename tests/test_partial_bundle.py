"""15.c.W: native partial selection, exact bytes and real weak-target bindings."""
from hashlib import sha256
import json
import os
from unittest.mock import patch

import pytest

from specroad.authoring._inspection_snapshot import InspectionSnapshot
from specroad.bundles import BundleError, prepare_partial_bundle, prepare_project_bundle
from specroad.bundles import partial as service
from specroad.graph.boundary_validation import validate_boundary_references
from specroad.graph.relations import SourceRelations
from specroad.graph.scope_descriptors import ScopeDescriptor
from specroad.model.attachments import AttachmentDescriptor
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.model.manifest_resources import project_json_resource
from specroad.model.model_manifest import ModelManifest
from specroad.model.paths import artifact_path
from specroad.model.semantic_configuration import semantic_configuration
from support.domain import domain_value, relation
from support.inspection import inspection_project
from support.model import put
from support.read_only import inventory, no_write_attempts
from support.records import record_value, ref
from support.scopes import descriptor


def edge(kind, target, number):
    value = {**relation(kind, target), 'relation_id': 'REL-' + str(number).zfill(26)}
    if kind == 'contains':
        value['position'] = 0
    return value


def save(root, value):
    path = artifact_path(value['artifact_type'], value['id'], 'SR')
    put(root, path, canonical_json_bytes(value))
    return path


def scope(kind='document', identity=None, **options):
    identity = identity or ref('DOC' if kind == 'document' else 'REL')
    return ScopeDescriptor(descriptor(kind, {kind + '_id': identity}, boundary_policy='partial', **options))


def project(root, kind='document', weak='duplicates'):
    outside = domain_value('requirement', id=ref('REQ', '1'), statement='Outside the selection.')
    requirement = domain_value('requirement', relations=[edge(weak, outside['id'], 4)])
    if kind == 'document':
        seed = record_value('document', relations=[edge('contains', ref('SEC'), 1)])
        extra = [record_value('section', relations=[edge('contains', ref('BLOCK'), 2)]),
                 record_value('content_block', block_kind='artifact_ref', payload={'render_mode': 'full'},
                              relations=[edge('references', requirement['id'], 3)])]
    else:
        seed = domain_value('release')
        requirement['relations'].append(edge('scheduled_for', seed['id'], 3))
        extra = []
    values = [seed, *extra, requirement, outside, domain_value('goal')]
    inspection_project(root, artifacts=values)
    from test_exchange_export import mapping
    put(root, 'mappings/inactive.json', mapping().source_bytes)
    return values


def records(bundle):
    return [SourceRelations(raw, path=p) for p, raw in bundle.files.items() if p.startswith('spec/')]


def independent_root(root, bundle):
    """Materialize fixture bytes, then assemble their root without the selector."""
    root.mkdir()
    for path, raw in bundle.files.items():
        put(root, path, raw)
    native = InspectionSnapshot(root, None, include_archive_objects=True).model
    resources = list(native.resources)
    resources.extend(project_json_resource(native.configuration, d.path, d.content, native.binding)
                     for d in native.documents)
    # Independently project the actual payload inventory using 10.9. The older
    # generic assembler supports only project/specification/explicit scopes;
    # do not reuse the generator's selection or its asserted model-root hash.
    rows = [r.data for r in resources]
    value = {
        'project_id': native.configuration.project_id,
        'scope_descriptor': bundle.manifest['scope_descriptor'],
        'artifacts': sorted((r for r in rows if r['kind'] == 'artifact'), key=lambda r: r['id'].encode()),
        'resources': sorted((r for r in rows if r['kind'] not in ('artifact', 'attachment', 'archive')),
                            key=lambda r: (r['id'].encode(), r['version'].encode(), r['kind'])),
        'attachments': sorted((r for r in rows if r['kind'] == 'attachment'), key=lambda r: r['path'].encode()),
        'boundary_references': bundle.manifest['boundary_references'],
        'configuration_sha256': canonical_json_sha256(semantic_configuration(native.configuration)),
        'profile_sha256': native.profile.sha256,
    }
    archives = sorted((r for r in rows if r['kind'] == 'archive'), key=lambda r: r['path'].encode())
    if archives:
        value['archive_objects'] = archives
    return ModelManifest({'model_manifest_version': 'model-manifest-v1', **value,
                          'scope_sha256': canonical_json_sha256(value)})


@pytest.mark.parametrize('kind', ['document', 'release'])
@pytest.mark.parametrize('weak', ['duplicates', 'conflicts_with'])
def test_exact_native_selection_roots_and_omitted_weak_target(tmp_path, kind, weak):
    root = tmp_path / 'origin'
    values = project(root, kind, weak)
    original = InspectionSnapshot(root, None, include_archive_objects=True)
    before = inventory(root)
    selection = scope(kind)
    with no_write_attempts():
        bundle = prepare_partial_bundle(root, selection)
    assert inventory(root) == before
    expected = {v['id'] for v in values[:-2]}
    assert {r.identity.id for r in records(bundle)} == expected
    manifest = bundle.manifest
    assert manifest['bundle_kind'] == 'partial' and manifest['read_only'] is True
    assert manifest['idempotency_scope'] == 'local_only'
    assert manifest['scope_descriptor'] == selection.data
    assert manifest['boundary_references'] == [{
        'source_id': ref('REQ'), 'relation_id': 'REL-' + '4'.zfill(26),
        'relation_type': weak, 'target_id': ref('REQ', '1'), 'target_type': 'requirement',
        'reason': 'boundary_policy_partial', 'origin_target_sha256': canonical_json_sha256(values[-2])}]
    assert set(bundle.files) == {'specroad.json', 'profiles/core.json', original.registry_path,
        *(artifact_path(v['artifact_type'], v['id'], 'SR') for v in values[:-2])}
    assert all(raw == original.raw[p] for p, raw in bundle.files.items())
    assert manifest['excluded_contents'] == [{'path': p, 'reason': 'outside_scope'}
        for p in sorted(set(original.raw) - set(bundle.files), key=lambda p: p.encode())]
    assert manifest['origin_model_root_sha256'] == original.model.manifest(
        original.model.artifacts, descriptor('project')).sha256
    rebuilt = independent_root(tmp_path / 'partial', bundle)
    assert rebuilt.sha256 == manifest['bundle_model_root_sha256'] != manifest['origin_model_root_sha256']
    assert rebuilt.data['configuration_sha256'] == manifest['configuration_sha256']
    assert rebuilt.data['profile_sha256'] == manifest['profile_sha256']
    check = validate_boundary_references(records(bundle), manifest['boundary_references'],
        descriptor=selection, origin_sources=[SourceRelations(d.content) for d in original.model.documents])
    assert check.origin_hashes_verified
    assert not bundle.project_verified and not bundle.write_authorized


def test_release_seeds_include_milestones_scheduled_members_and_tasks(tmp_path):
    root = tmp_path / 'origin'; values = project(root, 'release')
    milestone = domain_value('milestone', relations=[edge('part_of', ref('REL'), 5)])
    task = domain_value('task', relations=[edge('part_of', milestone['id'], 6)])
    scheduled = domain_value('capability', relations=[edge('scheduled_for', milestone['id'], 7)])
    unrelated = domain_value('task', id=ref('TASK', '1'))
    for value in (milestone, task, scheduled, unrelated):
        save(root, value)
    bundle = prepare_partial_bundle(root, scope('release'))
    assert {r.identity.id for r in records(bundle)} == {
        values[0]['id'], ref('REQ'), milestone['id'], task['id'], scheduled['id']}
    assert independent_root(tmp_path / 'partial', bundle).sha256 == bundle.manifest['bundle_model_root_sha256']


def test_later_strong_reachability_makes_a_weak_target_internal(tmp_path):
    root = tmp_path / 'origin'; values = project(root)
    requirement = values[-3]
    requirement['relations'].append(edge('depends_on', values[-2]['id'], 5))
    save(root, requirement)
    bundle = prepare_partial_bundle(root, scope())
    assert values[-2]['id'] in {r.identity.id for r in records(bundle)}
    assert bundle.manifest['boundary_references'] == []


@pytest.mark.parametrize('kind', ['document', 'release'])
def test_scope_that_reaches_every_artifact_stays_read_only_partial(tmp_path, kind):
    root = tmp_path / 'origin'
    value = record_value('document') if kind == 'document' else domain_value('release')
    inspection_project(root, artifacts=[value])
    bundle = prepare_partial_bundle(root, scope(kind))
    full = prepare_project_bundle(root)
    assert bundle.files == full.files
    assert bundle.manifest['excluded_contents'] == bundle.manifest['boundary_references'] == []
    assert bundle.manifest['bundle_kind'] == 'partial' and bundle.manifest['read_only'] is True
    assert bundle.manifest['idempotency_scope'] == 'local_only'
    assert bundle.manifest['bundle_model_root_sha256'] != full.manifest['bundle_model_root_sha256']


def test_selected_attachment_keeps_exact_binary_bytes_and_omits_unselected_attachment(tmp_path):
    root = tmp_path / 'origin'; project(root)
    selected = b'\x00\xff selected\r\n'; omitted = b'outside bytes'
    for index, raw in enumerate((selected, omitted)):
        attachment = AttachmentDescriptor('attachments/' + str(index) + '.bin',
            'application/octet-stream', len(raw), sha256(raw).hexdigest())
        value = record_value('evidence', id=ref('EVD', str(index)), attachments=[attachment.data])
        save(root, value); put(root, attachment.path, raw)
    save(root, record_value('content_block', block_kind='artifact_ref', payload={'render_mode': 'full'},
                           relations=[edge('references', ref('EVD'), 3)]))
    bundle = prepare_partial_bundle(root, scope())
    assert bundle.files['attachments/0.bin'] == selected
    assert 'attachments/1.bin' not in bundle.files
    assert {'path': 'attachments/1.bin', 'reason': 'outside_scope'} in bundle.manifest['excluded_contents']
    assert independent_root(tmp_path / 'partial', bundle).sha256 == bundle.manifest['bundle_model_root_sha256']


def test_referenced_baseline_keeps_objects_while_unreferenced_archive_is_declared(tmp_path):
    from test_project_bundle import baseline_project
    root = tmp_path / 'origin'; op = baseline_project(root)
    document = record_value('document', relations=[edge('contains', ref('SEC'), 8)])
    save(root, document)
    save(root, record_value('section', relations=[edge('contains', ref('BLOCK'), 9)]))
    save(root, record_value('content_block', block_kind='artifact_ref', payload={'render_mode': 'full'},
                           relations=[edge('references', op['record']['id'], 10)]))
    raw = b'unreferenced object'; digest = sha256(raw).hexdigest()
    extra = 'archive/objects/' + digest[:2] + '/' + digest
    put(root, extra, raw)
    bundle = prepare_partial_bundle(root, scope())
    assert {row['object_path'] for row in op['record']['manifest']} <= bundle.files.keys()
    assert extra not in bundle.files
    assert {'path': extra, 'reason': 'unreferenced_archive_object'} in bundle.manifest['excluded_contents']
    assert independent_root(tmp_path / 'partial', bundle).sha256 == bundle.manifest['bundle_model_root_sha256']


def test_initialized_language_packages_remain_bound_and_reconstructable(tmp_path):
    from specroad.cli.application import dispatch_result
    root = tmp_path / 'origin'
    assert dispatch_result(['init', str(root)]).exit_code == 0
    save(root, record_value('document'))
    original = InspectionSnapshot(root, None)
    bundle = prepare_partial_bundle(root, scope())
    expected = {p: raw for p, raw in original.raw.items() if p.startswith('profiles/language-data/packages/')}
    # Only packages configured into the effective profile are necessary for a
    # partial; unlike the full origin it does not include inactive packages.
    from specroad.model.language_package_values import LanguagePackage
    selected = {p.key for p in original.model.language_packages}
    expected = {p: raw for p, raw in expected.items() if LanguagePackage(raw).key in selected}
    assert expected and {p: raw for p, raw in bundle.files.items()
        if p.startswith('profiles/language-data/packages/')} == expected
    assert independent_root(tmp_path / 'partial', bundle).sha256 == bundle.manifest['bundle_model_root_sha256']


def test_original_representation_and_location_independent_bytes(tmp_path):
    root = tmp_path / 'origin'; values = project(root)
    first = prepare_partial_bundle(root, scope())
    path = artifact_path(values[0]['artifact_type'], values[0]['id'], 'SR')
    altered = json.dumps(values[0], indent=4).encode() + b'\n'
    put(root, path, altered)
    second = prepare_partial_bundle(root, scope())
    assert second.files[path] == altered and first.sha256 != second.sha256
    assert first.manifest['origin_model_root_sha256'] == second.manifest['origin_model_root_sha256']
    assert first.manifest['bundle_model_root_sha256'] == second.manifest['bundle_model_root_sha256']
    source = InspectionSnapshot(root, None)
    other = tmp_path / 'relocated'; other.mkdir()
    for name, raw in reversed(list(source.raw.items())):
        put(other, name, raw); os.utime(other / name, (1000, 1000))
    assert prepare_partial_bundle(other, scope()).source_bytes == second.source_bytes


@pytest.mark.parametrize('target', ['weak', 'unrelated'])
def test_omitted_source_changes_bind_the_origin_and_only_relevant_boundary(tmp_path, target):
    root = tmp_path / 'origin'; values = project(root)
    first = prepare_partial_bundle(root, scope())
    value = values[-2] if target == 'weak' else values[-1]
    value['statement'] = 'Changed outside statement.'
    save(root, value)
    second = prepare_partial_bundle(root, scope())
    assert first.files == second.files
    assert first.manifest['origin_model_root_sha256'] != second.manifest['origin_model_root_sha256']
    assert (first.manifest['bundle_model_root_sha256'] == second.manifest['bundle_model_root_sha256']) == (target == 'unrelated')
    if target == 'weak':
        assert second.manifest['boundary_references'][0]['origin_target_sha256'] == canonical_json_sha256(value)


@pytest.mark.parametrize('policy,kind', [('closed', 'document'), ('closed', 'release'),
                                      ('partial', 'project'), ('closed', 'project')])
def test_wrong_scope_is_not_silently_promoted_or_repaired(tmp_path, policy, kind):
    root = tmp_path / 'origin'; project(root)
    selector = {} if kind == 'project' else {kind + '_id': ref('DOC' if kind == 'document' else 'REL')}
    selection = ScopeDescriptor(descriptor(kind, selector, boundary_policy=policy))
    before = inventory(root)
    with no_write_attempts(), pytest.raises(BundleError) as failure:
        prepare_partial_bundle(root, selection)
    assert failure.value.exit_code == 3 and inventory(root) == before


def test_configuration_is_explicitly_refused_until_its_provider_is_implemented(tmp_path):
    root = tmp_path / 'origin'; project(root); save(root, record_value('configuration'))
    before = inventory(root)
    with no_write_attempts(), pytest.raises(BundleError) as failure:
        prepare_partial_bundle(root, scope(configuration_id=ref('CFG')))
    assert failure.value.reason == 'bundle_partial_configuration_provider_required'
    assert failure.value.exit_code == 2 and inventory(root) == before


@pytest.mark.parametrize('kind', ['document', 'release'])
def test_missing_seed_has_no_partial_success(tmp_path, kind):
    root = tmp_path / 'origin'; project(root, kind)
    with no_write_attempts(), pytest.raises(BundleError) as failure:
        prepare_partial_bundle(root, scope(kind, identity=ref('DOC' if kind == 'document' else 'REL', '2')))
    assert failure.value.exit_code == 3


@pytest.mark.parametrize('weak', ['duplicates', 'depends_on'])
def test_missing_origin_target_is_never_replaced_by_a_hash_claim(tmp_path, weak):
    root = tmp_path / 'origin'; values = project(root, weak=weak)
    (root / artifact_path('requirement', values[-2]['id'], 'SR')).unlink()
    before = inventory(root)
    with no_write_attempts(), pytest.raises(BundleError) as failure:
        prepare_partial_bundle(root, scope())
    assert failure.value.exit_code == 3 and inventory(root) == before


def test_partial_origin_marker_cannot_be_promoted_even_if_payload_is_complete(tmp_path):
    root = tmp_path / 'origin'; inspection_project(root, artifacts=[record_value('document')])
    bundle = prepare_partial_bundle(root, scope())
    put(root, 'bundle-manifest.json', bundle.manifest_bytes)
    before = inventory(root)
    with no_write_attempts(), pytest.raises(BundleError):
        prepare_partial_bundle(root, scope())
    assert inventory(root) == before


@pytest.mark.parametrize('path', ['.specroad/requests/old.json', '.specroad/transactions/active/journal.json'])
def test_nonempty_history_or_unresolved_transaction_remains_outside_provider(tmp_path, path):
    root = tmp_path / 'origin'; project(root); put(root, path, b'unverified state')
    before = inventory(root)
    with no_write_attempts(), pytest.raises(BundleError) as failure:
        prepare_partial_bundle(root, scope())
    assert failure.value.exit_code == 5 and inventory(root) == before


def test_omitted_resource_link_is_not_followed(tmp_path):
    root = tmp_path / 'origin'; project(root)
    path = root / 'mappings/inactive.json'; raw = path.read_bytes(); path.unlink()
    outside = tmp_path / 'outside.json'; outside.write_bytes(raw); path.symlink_to(outside)
    with no_write_attempts(), pytest.raises(BundleError) as failure:
        prepare_partial_bundle(root, scope())
    assert failure.value.exit_code == 7 and outside.read_bytes() == raw


@pytest.mark.parametrize('change', ['selected', 'weak', 'unrelated', 'new', 'receipt'])
def test_original_observation_is_rechecked_after_encoding(tmp_path, change):
    root = tmp_path / 'origin'; values = project(root)
    encode = service.encode_bundle
    def changed(*args):
        result = encode(*args)
        if change == 'receipt':
            put(root, '.specroad/requests/late.json', b'new history')
        elif change == 'new':
            save(root, domain_value('risk'))
        else:
            value = values[0] if change == 'selected' else values[-2 if change == 'weak' else -1]
            value['title'] += ' changed'
            save(root, value)
        return result
    with patch.object(service, 'encode_bundle', changed), pytest.raises(BundleError) as failure:
        prepare_partial_bundle(root, scope())
    assert failure.value.exit_code == (5 if change == 'receipt' else 6)
    assert not (root / 'generated').exists()


@pytest.mark.parametrize('change', ['payload', 'metadata'])
def test_consistent_codec_output_cannot_drop_selected_bytes_or_rebind_origin(tmp_path, change):
    root = tmp_path / 'origin'; project(root)
    encode = service.encode_bundle
    def changed(metadata, payloads):
        metadata, payloads = dict(metadata), dict(payloads)
        if change == 'payload':
            del payloads[next(p for p in payloads if p.startswith('spec/sections/'))]
        else:
            metadata['origin_model_root_sha256'] = 'a' * 64
        return encode(metadata, payloads)
    before = inventory(root)
    with no_write_attempts(), patch.object(service, 'encode_bundle', changed), pytest.raises(BundleError) as failure:
        prepare_partial_bundle(root, scope())
    assert failure.value.code == 'SRV060' and inventory(root) == before
