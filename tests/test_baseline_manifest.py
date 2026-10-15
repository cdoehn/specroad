"""Byte-backed Baseline preparation and the existing semantic model-root contract."""
from dataclasses import FrozenInstanceError, replace
from hashlib import sha256
import json

import pytest

from specroad.archive import BaselineManifest, SnapshotObjectStore, build_baseline_manifest
from specroad.graph.closure_inputs import ClosureBindings, artifact_node, resource_node
from specroad.graph.relations import SourceRelations
from specroad.graph.scope_closure import resolve_scope_closure
from specroad.graph.scope_descriptors import ScopeDescriptor
from specroad.graph.scope_hash import fingerprint_scope
from specroad.graph.scope_inputs import ScopeResource, ScopeSeedInputs
from specroad.graph.scope_seeds import resolve_scope_seeds
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.model.configuration import ProjectConfiguration
from specroad.model.errors import ModelError
from specroad.model.attachments import AttachmentDescriptor
from specroad.model.manifest_resources import project_json_resource
from specroad.model.model_manifest import ProjectReadBinding
from specroad.model.semantic_configuration import semantic_configuration
from specroad.profiles import ProfileResource, compose_profiles
from specroad.security import ProjectBoundary
from support.artifacts import artifact_bytes
from support.closure import observe
from support.model import configuration_value
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.profiles import encoded, profile_data
from support.read_only import inventory, make_project, no_write_attempts
from support.relations import artifact, aid, edge
from support.scopes import descriptor


def baseline_inputs(*, values=None, configuration=None, scope=None, attachment=b'\x00\xff\r\n',
                    profile_changes=None, rule_value=True, reverse=False):
    """Owned complete test inventory; empty usage/review observations are fixture facts."""
    cfg = ProjectConfiguration(configuration_value() if configuration is None else configuration)
    core = ProfileResource(encoded(profile_data(profile_id='core')))
    product = ProfileResource(encoded(profile_data(profile_id='product', **(profile_changes or {}))))
    profile = compose_profiles([core, product], core_key=core.key, project_profiles=[product.key])
    payloads = {'profile:core': ('profiles/core.json', core.source_bytes),
        'profile:product': ('profiles/product.json', product.source_bytes),
        'rule:check': ('rules/check.json', encoded({'schema_version': '0.2.0',
            'rule_id': 'check', 'version': '1.0.0', 'value': rule_value})),
        'mapping:exchange': ('mappings/exchange.json', encoded({'schema_version': '0.2.0',
            'mapping_id': 'exchange', 'version': '2.0.0', 'fields': {'source': 'title'}}))}
    binding = ProjectReadBinding('sample', '/test/baseline-source', (1, 2))
    resources = []
    for identity, (path, raw) in payloads.items():
        data = project_json_resource(cfg, path, raw, binding).data
        resources.append(ScopeResource(identity, data['kind'], data['sha256'], data['version'], True))
    declarations, attachments, uses = {}, {}, {}
    if attachment is not None:
        record = AttachmentDescriptor('attachments/manual.bin', 'application/octet-stream',
                                      len(attachment), sha256(attachment).hexdigest())
        resources.append(ScopeResource('attachment:manual', 'attachment', record.sha256))
        declarations['attachment:manual'] = record
        attachments[record.path] = attachment
        uses[artifact_node(aid())] = [resource_node('attachment:manual')]
    if values is None:
        values = [artifact(relations=[edge('depends_on', aid(number=2))]), artifact(number=2, revision=3)]
    records = [SourceRelations(artifact_bytes(value)) for value in values]
    if reverse:
        records.reverse(); resources.reverse(); payloads = dict(reversed(list(payloads.items())))
    inputs = ScopeSeedInputs(cfg, records, resources)
    dependencies = observe(inputs, uses=uses, attachments=declarations)
    seeds = resolve_scope_seeds(ScopeDescriptor(scope or descriptor()), inputs)
    closure = resolve_scope_closure(seeds, dependencies)
    return dict(configuration=cfg, binding=binding, closure=closure, dependencies=dependencies,
                baseline_kind='working', effective_profile=profile,
                resource_payloads=payloads, attachment_payloads=attachments)


def built(**changes):
    inputs = baseline_inputs(); inputs.update(changes)
    return build_baseline_manifest(**inputs)


def object_bytes(result, role):
    entry = next(item for item in result.data['manifest'] if item['role'] == role)
    return next(item.content for item in result.objects if item.reference.path == entry['object_path'])


def test_working_manifest_binds_the_actual_precreation_model_root():
    args = baseline_inputs(); result = build_baseline_manifest(**args)
    records = {name: project_json_resource(args['configuration'], path, raw, args['binding'])
               for name, (path, raw) in args['resource_payloads'].items()}
    expected = fingerprint_scope(args['configuration'], args['binding'], args['closure'],
        args['dependencies'], effective_profile=args['effective_profile'].data, resource_records=records)
    assert result.model_root_sha256 == expected.sha256
    assert result.data['model_manifest'] == expected.data
    assert object_bytes(result, 'model_manifest') == expected.canonical_bytes
    assert result.data['scope_sha256'] == expected.scope_sha256
    assert result.data['scope_descriptor'] == descriptor()
    assert {r['artifact_type'] for r in result.data['manifest'] if r['role'] == 'artifact'} == {'requirement'}


@pytest.mark.parametrize('kind', ['working', 'release'])
def test_both_baseline_kinds_are_inert_data_without_publication_or_release_authority(kind):
    result = built(baseline_kind=kind)
    assert result.data['baseline_kind'] == kind
    assert result.assurance == {'validation_scope': 'supplied_scope_and_object_bytes',
        'project_completeness_verified': False, 'atomic_snapshot': False,
        'full_validation_passed': False, 'write_authorized': False, 'release_authorized': False}


@pytest.mark.parametrize('kind', ['Working', '', 'draft', None, True])
def test_unknown_baseline_kind_is_rejected(kind):
    with pytest.raises(ModelError) as caught: built(baseline_kind=kind)
    assert caught.value.reason == 'baseline_kind_invalid'


def test_every_manifest_row_has_exact_retained_bytes_hash_length_and_object_path():
    args = baseline_inputs(); result = build_baseline_manifest(**args)
    objects = {item.reference.path: item.content for item in result.objects}
    assert len(objects) == len(result.objects)
    assert set(objects) == {row['object_path'] for row in result.data['manifest']}
    assert {r['role'] for r in result.data['manifest']} == {
        'artifact', 'profile', 'rule', 'mapping', 'attachment',
        'semantic_configuration', 'effective_profile', 'model_manifest'}
    for row in result.data['manifest']:
        raw = objects[row['object_path']]; digest = sha256(raw).hexdigest()
        assert (row['size'], row['sha256']) == (len(raw), digest)
        assert row['object_path'] == 'archive/objects/' + digest[:2] + '/' + digest
        if row['role'] != 'attachment': assert canonical_json_bytes(json.loads(raw)) == raw
    assert object_bytes(result, 'attachment') == b'\x00\xff\r\n'
    artifacts = {row['id']: row for row in result.data['manifest'] if row['role'] == 'artifact'}
    assert artifacts[aid(number=2)]['revision'] == 3
    assert artifacts[aid()]['source_path'] == 'spec/requirements/' + aid() + '.json'
    assert artifacts[aid()]['media_type'] == 'application/json'


def test_effective_configuration_profile_chain_versions_and_schema_are_retained():
    args = baseline_inputs(); result = build_baseline_manifest(**args); data = result.data
    assert data['schema_version'] == '0.2.0' and data['tool_version'] == '0.2.0.dev0'
    assert data['profiles'] == args['effective_profile'].data['profiles']
    assert [p['profile_id'] for p in data['profiles']] == ['core', 'product']
    assert object_bytes(result, 'semantic_configuration') == canonical_json_bytes(
        semantic_configuration(args['configuration']))
    assert object_bytes(result, 'effective_profile') == args['effective_profile'].canonical_bytes
    assert data['configuration_hash'] == sha256(object_bytes(result, 'semantic_configuration')).hexdigest()
    assert data['profile_sha256'] == sha256(object_bytes(result, 'effective_profile')).hexdigest()
    resources = {row['role']: row for row in data['manifest'] if row['role'] in ('rule', 'mapping')}
    assert (resources['rule']['id'], resources['rule']['version']) == ('check', '1.0.0')
    assert (resources['mapping']['id'], resources['mapping']['version']) == ('exchange', '2.0.0')


def test_preparation_is_pure_and_does_not_modify_any_project_or_create_a_baseline(tmp_path):
    project = tmp_path / 'project'; project.mkdir(); make_project(project)
    args = baseline_inputs(); before = inventory(tmp_path)
    with no_write_attempts(): result = build_baseline_manifest(**args)
    assert inventory(tmp_path) == before
    assert not result.assurance['write_authorized']


def test_retained_objects_round_trip_through_the_actual_external_store(tmp_path):
    project = tmp_path / 'project'; project.mkdir(); make_project(project)
    root = tmp_path / 'store'; root.mkdir(mode=0o700)
    store = SnapshotObjectStore(root, protected_roots=(ProjectBoundary(project),))
    before = inventory(project); result = built()
    for item in result.objects:
        ref = store.put(item)
        assert store.get(ref) == item.content
    assert inventory(project) == before
    assert len(list((root / 'archive/objects').glob('*/*'))) == len(result.objects)


def test_identical_content_can_have_two_logical_roles_but_one_object():
    args = baseline_inputs(); raw = canonical_json_bytes(args['dependencies'].inventory.records[0].data)
    result = build_baseline_manifest(**baseline_inputs(attachment=raw))
    rows = [row for row in result.data['manifest'] if row['sha256'] == sha256(raw).hexdigest()]
    assert {row['role'] for row in rows} == {'artifact', 'attachment'}
    assert len({row['object_path'] for row in rows}) == 1
    assert sum(item.content == raw for item in result.objects) == 1


def test_manifest_and_object_order_are_independent_of_inventory_iteration():
    a = build_baseline_manifest(**baseline_inputs()); b = build_baseline_manifest(**baseline_inputs(reverse=True))
    assert a.canonical_bytes == b.canonical_bytes and a.objects == b.objects


def test_owned_manifest_survives_mutation_of_original_and_returned_containers():
    args = baseline_inputs(); result = build_baseline_manifest(**args); before = result.canonical_bytes
    args['resource_payloads'].clear(); args['attachment_payloads'].clear()
    result.data['manifest'].clear(); result.assurance['write_authorized'] = True
    assert result.canonical_bytes == before and not result.assurance['write_authorized']
    with pytest.raises(FrozenInstanceError): result.objects = ()
    with pytest.raises(TypeError): BaselineManifest()


@pytest.mark.parametrize('change', ['artifact', 'revision', 'rule', 'attachment', 'configuration', 'profile'])
def test_every_semantic_input_changes_the_bound_model_root(change):
    args = baseline_inputs(); before = build_baseline_manifest(**args)
    if change == 'artifact': other = baseline_inputs(values=[artifact(title='Changed'), artifact(number=2, revision=3)])
    elif change == 'revision': other = baseline_inputs(values=[artifact(revision=2), artifact(number=2, revision=3)])
    elif change == 'rule': other = baseline_inputs(rule_value=False)
    elif change == 'attachment': other = baseline_inputs(attachment=b'new bytes')
    elif change == 'configuration': other = baseline_inputs(configuration=configuration_value(validation_policy={'fail_on': 'warning'}))
    else: other = baseline_inputs(profile_changes={'severity_overrides': {'product:lint': 'warning'}})
    assert before.model_root_sha256 != build_baseline_manifest(**other).model_root_sha256


@pytest.mark.parametrize('name', ['profile:core', 'profile:product', 'rule:check', 'mapping:exchange'])
def test_missing_selected_resource_bytes_cannot_produce_a_partial_manifest(name):
    args = baseline_inputs(); del args['resource_payloads'][name]
    with pytest.raises(ModelError) as caught: build_baseline_manifest(**args)
    assert caught.value.reason == 'baseline_resource_payload_set_mismatch'


def test_extra_unselected_resource_payload_is_rejected():
    args = baseline_inputs(); args['resource_payloads']['unknown'] = args['resource_payloads']['rule:check']
    with pytest.raises(ModelError) as caught: build_baseline_manifest(**args)
    assert caught.value.reason == 'baseline_resource_payload_set_mismatch'


@pytest.mark.parametrize('change', ['missing', 'extra', 'changed'])
def test_attachment_payloads_must_match_the_exact_declared_scope(change):
    args = baseline_inputs()
    if change == 'missing': args['attachment_payloads'].clear()
    elif change == 'extra': args['attachment_payloads']['attachments/unselected.bin'] = b'extra'
    else: args['attachment_payloads']['attachments/manual.bin'] = b'wrong'
    with pytest.raises(ModelError) as caught: build_baseline_manifest(**args)
    assert caught.value.reason == ('baseline_attachment_binding_mismatch' if change == 'changed'
                                   else 'baseline_attachment_payload_set_mismatch')


def test_changed_resource_bytes_cannot_reuse_the_old_scope_identity():
    args = baseline_inputs(); path, raw = args['resource_payloads']['rule:check']
    data = json.loads(raw); data['value'] = False
    args['resource_payloads']['rule:check'] = path, encoded(data)
    with pytest.raises(ModelError) as caught: build_baseline_manifest(**args)
    assert caught.value.reason == 'baseline_resource_binding_mismatch'


def test_effective_profile_is_recomposed_from_actual_profile_bytes():
    args = baseline_inputs(); other = baseline_inputs(profile_changes={'severity_overrides': {'product:lint': 'warning'}})
    args['effective_profile'] = other['effective_profile']
    with pytest.raises(ModelError) as caught: build_baseline_manifest(**args)
    assert caught.value.reason == 'baseline_effective_profile_mismatch'


def test_stale_closure_is_rejected_instead_of_hashing_incomplete_membership():
    args = baseline_inputs(); args['closure'] = replace(args['closure'], artifact_ids=(aid(),))
    with pytest.raises(ModelError) as caught: build_baseline_manifest(**args)
    assert caught.value.reason == 'scope_closure_observation_stale'


def test_partial_scope_retains_boundary_hash_without_materializing_the_omitted_target():
    values = [artifact(relations=[edge('duplicates', aid(number=2))]), artifact(number=2)]
    scope = descriptor('explicit', {'artifact_ids': [aid()],
        'resource_ids': ['mapping:exchange', 'profile:core', 'profile:product', 'rule:check']}, boundary_policy='partial')
    result = build_baseline_manifest(**baseline_inputs(values=values, scope=scope))
    assert [r['id'] for r in result.data['manifest'] if r['role'] == 'artifact'] == [aid()]
    boundary = result.data['boundary_references'][0]
    assert boundary['target_id'] == aid(number=2)
    assert boundary['origin_target_sha256'] == canonical_json_sha256(values[1])


def test_same_semantic_json_with_other_formatting_has_the_same_snapshot_objects():
    args = baseline_inputs(); a = build_baseline_manifest(**args)
    args['resource_payloads'] = {k: (path, json.dumps(json.loads(raw), sort_keys=True).encode())
                                for k, (path, raw) in args['resource_payloads'].items()}
    b = build_baseline_manifest(**args)
    assert a.canonical_bytes == b.canonical_bytes and a.objects == b.objects


@pytest.mark.parametrize('mode', ['core', 'pyz'])
def test_baseline_manifest_runs_in_an_isolated_core_or_portable_distribution(tmp_path, mode):
    core = encoded(profile_data(profile_id='core'))
    body = '''from specroad.archive import build_baseline_manifest
from specroad.graph.closure_inputs import ClosureBindings, resource_node
from specroad.graph.scope_inputs import ScopeSeedInputs, ScopeResource
from specroad.graph.scope_seeds import resolve_scope_seeds
from specroad.graph.scope_closure import resolve_scope_closure
from specroad.graph.scope_descriptors import ScopeDescriptor
from specroad.model.configuration import ProjectConfiguration
from specroad.model.model_manifest import ProjectReadBinding
from specroad.profiles import ProfileResource, compose_profiles
'''
    body += 'configuration=ProjectConfiguration(' + repr(configuration_value()) + ')\n'
    body += 'core=ProfileResource(' + repr(core) + ')\n'
    body += '''inputs=ScopeSeedInputs(configuration, [], [ScopeResource('core', 'profile', core.sha256, core.version, True)])
dependencies=ClosureBindings(inputs, uses={resource_node('core'):()}, current_reviews={})
'''
    body += 'seeds=resolve_scope_seeds(ScopeDescriptor(' + repr(descriptor()) + '), inputs)\n'
    body += '''result=build_baseline_manifest(configuration, ProjectReadBinding('sample','/inert', (1,2)),
 resolve_scope_closure(seeds, dependencies), dependencies, baseline_kind='working',
 effective_profile=compose_profiles([core],core_key=core.key),
 resource_payloads={'core':('profiles/core.json',core.source_bytes)}, attachment_payloads={})
assert len(result.objects)==4 and result.data['baseline_kind']=='working'
assert not result.assurance['write_authorized']
'''
    if mode == 'core': result = run_core(body, tmp_path, capture=True)
    else:
        _, package = build_distribution(tmp_path / 'distribution')
        result = run_python(['-I', '-S', '-B', '-c', 'import sys;sys.path.insert(0,' + repr(str(package)) + ')\n' + body],
                            tmp_path, capture=True)
    assert result.returncode == 0, result.stderr
