"""Precreation identity, original-byte scope binding and nonsemantic run data."""
from dataclasses import replace
import time

import pytest

from specroad.archive import build_baseline_manifest
from specroad.graph.closure_inputs import ClosureBindings
from specroad.graph.relations import SourceRelations
from specroad.graph.scope_closure import resolve_scope_closure
from specroad.graph.scope_descriptors import ScopeDescriptor
from specroad.graph.scope_inputs import ScopeSeedInputs
from specroad.graph.scope_seeds import resolve_scope_seeds
from specroad.model.canonical import canonical_json_bytes
from specroad.model.errors import ModelError
from specroad.model.model_manifest import ProjectReadBinding
from support.artifacts import artifact_bytes
from support.closure import source
from support.model import configuration_value
from support.relations import artifact, aid
from support.scopes import descriptor
from test_baseline_manifest import baseline_inputs


def test_planned_baseline_identity_is_bound_outside_its_precreation_model_root():
    args = baseline_inputs()
    first = build_baseline_manifest(**args, baseline_id=aid('baseline'))
    second = build_baseline_manifest(**args, baseline_id=aid('baseline', 2))
    unnamed = build_baseline_manifest(**args)
    assert first.data['baseline_id'] == aid('baseline')
    assert second.data['baseline_id'] == aid('baseline', 2)
    assert first.sha256 != second.sha256
    assert first.model_root_sha256 == second.model_root_sha256 == unnamed.model_root_sha256
    assert first.data['model_manifest'] == unnamed.data['model_manifest']
    assert first.objects == second.objects == unnamed.objects
    assert all(row.get('id') != aid('baseline') for row in first.data['manifest'])


@pytest.mark.parametrize('selected', [False, True])
def test_new_baseline_cannot_already_exist_even_outside_the_selected_scope(selected):
    existing = source('baseline')
    scope = (descriptor('explicit', {'artifact_ids': sorted([aid(), existing['id']]),
        'resource_ids': ['mapping:exchange', 'profile:core', 'profile:product', 'rule:check']})
        if selected else None)
    args = baseline_inputs(values=[artifact(), existing])
    if selected:
        prior = args['dependencies']
        inputs = ScopeSeedInputs(args['configuration'], prior.inventory.records,
            prior.inventory.resources, archive_bindings={existing['id']: ()})
        dependencies = ClosureBindings(inputs, uses=dict(prior.uses),
            current_reviews=dict(prior.current_reviews), attachments=dict(prior.attachments))
        seeds = resolve_scope_seeds(ScopeDescriptor(scope), inputs)
        args.update(dependencies=dependencies, closure=resolve_scope_closure(seeds, dependencies))
    with pytest.raises(ModelError) as caught:
        build_baseline_manifest(**args, baseline_id=existing['id'])
    assert caught.value.reason == 'baseline_identity_already_present'


def test_different_prior_baseline_control_does_not_enter_specification_snapshot():
    existing = source('baseline')
    args = baseline_inputs(values=[artifact(), existing])
    result = build_baseline_manifest(**args, baseline_id=aid('baseline', 2))
    assert {r['id'] for r in result.data['manifest'] if r['role'] == 'artifact'} == {aid()}
    assert result.data['baseline_id'] == aid('baseline', 2)


@pytest.mark.parametrize('identity', [aid(), 'other-BAS-0001', '../baseline', True, ''])
def test_planned_identity_must_be_a_baseline_in_this_project(identity):
    with pytest.raises(ModelError): build_baseline_manifest(**baseline_inputs(), baseline_id=identity)


@pytest.mark.parametrize('root,inode', [('/elsewhere/project', (8, 9)), ('/container/source', (11, 15))])
def test_local_runtime_paths_and_inode_bindings_do_not_change_portable_bytes(root, inode):
    args = baseline_inputs(); first = build_baseline_manifest(**args)
    args['binding'] = ProjectReadBinding('sample', root, inode)
    second = build_baseline_manifest(**args)
    assert first.canonical_bytes == second.canonical_bytes and first.objects == second.objects


@pytest.mark.parametrize('change', [
    {'default_locale': 'en-US'}, {'generated_path': 'output'},
    {'transaction_policy': {'auto_recover': False}},
    {'resource_limits': {'model_bytes': 99999, 'relation_count': 33}},
])
def test_display_and_operational_configuration_are_not_semantic_snapshot_inputs(change):
    a = build_baseline_manifest(**baseline_inputs())
    b = build_baseline_manifest(**baseline_inputs(configuration=configuration_value(**change)))
    assert a.canonical_bytes == b.canonical_bytes and a.objects == b.objects


def test_runtime_clock_and_timezone_do_not_affect_manifest_or_model_root(monkeypatch):
    args = baseline_inputs(); first = build_baseline_manifest(**args)
    monkeypatch.setenv('TZ', 'Pacific/Honolulu')
    monkeypatch.setattr(time, 'time', lambda: 0)
    second = build_baseline_manifest(**args)
    assert first.canonical_bytes == second.canonical_bytes


def test_normative_artifact_audit_bytes_remain_part_of_the_model_root():
    args = baseline_inputs(); first = build_baseline_manifest(**args)
    values = [record.data for record in args['dependencies'].inventory.records]
    values[0]['updated_at'] = '2026-10-16T01:00:00Z'
    second = build_baseline_manifest(**baseline_inputs(values=values))
    assert first.model_root_sha256 != second.model_root_sha256
    assert first.data['configuration_hash'] == second.data['configuration_hash']


def test_tool_version_is_retained_as_metadata_without_changing_the_model_root(monkeypatch):
    import specroad.archive.baseline as module
    args = baseline_inputs(); first = build_baseline_manifest(**args)
    monkeypatch.setattr(module, '__version__', '0.2.0.dev1')
    second = build_baseline_manifest(**args)
    assert second.data['tool_version'] == '0.2.0.dev1' and first.sha256 != second.sha256
    assert first.model_root_sha256 == second.model_root_sha256 and first.objects == second.objects


@pytest.mark.parametrize('field', ['identity', 'relations', 'source_bytes'])
def test_derived_source_labels_cannot_override_the_owned_original_bytes(field):
    args = baseline_inputs(); record = args['dependencies'].inventory.records[0]
    if field == 'identity': changed = SourceRelations(artifact_bytes(artifact(number=9))).identity
    elif field == 'relations': changed = ()
    else: changed = artifact_bytes(artifact(number=9))
    object.__setattr__(record, field, changed)
    with pytest.raises(ModelError) as caught: build_baseline_manifest(**args)
    assert caught.value.reason == 'baseline_source_binding_mismatch'


def test_a_changed_inventory_fingerprint_is_not_accepted_as_current_scope():
    args = baseline_inputs(); object.__setattr__(args['dependencies'].inventory, 'fingerprint', '0' * 64)
    with pytest.raises(ModelError) as caught: build_baseline_manifest(**args)
    assert caught.value.reason == 'baseline_inventory_binding_mismatch'


def test_stale_active_profile_labels_are_detected_from_fresh_inventory_binding():
    args = baseline_inputs()
    resource = next(r for r in args['dependencies'].inventory.resources if r.resource_id == 'profile:core')
    object.__setattr__(resource, 'active', False)
    with pytest.raises(ModelError) as caught: build_baseline_manifest(**args)
    assert caught.value.reason == 'baseline_inventory_binding_mismatch'


def test_changed_dependency_binding_cannot_certify_the_same_closure():
    args = baseline_inputs(); object.__setattr__(args['dependencies'], 'fingerprint', '0' * 64)
    with pytest.raises(ModelError) as caught: build_baseline_manifest(**args)
    assert caught.value.reason == 'baseline_dependency_binding_mismatch'


def test_unknown_closure_resource_is_rejected_before_payload_lookup():
    args = baseline_inputs(); args['closure'] = replace(args['closure'], resource_ids=('unknown',))
    with pytest.raises(ModelError) as caught: build_baseline_manifest(**args)
    assert caught.value.reason == 'scope_closure_observation_stale'


@pytest.mark.parametrize('path', ['.specroad/receipts/fake.json', 'generated/fake.json', '.git/fake.json'])
def test_operational_or_git_payload_cannot_masquerade_as_a_model_resource(path):
    args = baseline_inputs(); _, raw = args['resource_payloads']['rule:check']
    args['resource_payloads']['rule:check'] = path, raw
    with pytest.raises(ModelError) as caught: build_baseline_manifest(**args)
    assert caught.value.reason in ('not_manifest_input', 'reserved_path')


def test_two_logical_resources_cannot_claim_the_same_source_path():
    args = baseline_inputs()
    path, _ = args['resource_payloads']['profile:core']; _, raw = args['resource_payloads']['profile:product']
    args['resource_payloads']['profile:product'] = path, raw
    with pytest.raises(ModelError) as caught: build_baseline_manifest(**args)
    assert caught.value.reason == 'baseline_resource_path_collision'


def test_artifact_bytes_in_a_profile_payload_cannot_be_mislabeled():
    args = baseline_inputs(); record = args['dependencies'].inventory.records[0]
    args['resource_payloads']['profile:core'] = 'spec/requirements/' + aid() + '.json', record.source_bytes
    with pytest.raises(ModelError) as caught: build_baseline_manifest(**args)
    assert caught.value.reason == 'baseline_resource_binding_mismatch'


def test_forged_effective_profile_merge_is_rejected_against_the_actual_composition():
    args = baseline_inputs(); value = args['effective_profile'].data
    value['merge']['severity_overrides']['product:forged'] = 'error'
    object.__setattr__(args['effective_profile'], '_encoded', canonical_json_bytes(value))
    with pytest.raises(ModelError) as caught: build_baseline_manifest(**args)
    assert caught.value.reason == 'baseline_effective_profile_mismatch'


@pytest.mark.parametrize('name', ['resource_payloads', 'attachment_payloads'])
@pytest.mark.parametrize('value', [None, [], 'payloads'])
def test_payload_inventories_must_be_explicit_mappings(name, value):
    args = baseline_inputs(); args[name] = value
    with pytest.raises(ModelError) as caught: build_baseline_manifest(**args)
    assert caught.value.reason == ('baseline_resource_payloads_required' if name == 'resource_payloads'
                                   else 'baseline_attachment_payloads_required')
