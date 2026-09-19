"""Scope integrity and data-only diff/impact, never console or document text."""
from copy import deepcopy
import json
from dataclasses import replace
import unittest

from specroad.graph.comparison import ComparisonInputs, field_diff, compare_artifacts, direct_impact
from specroad.graph.scope_hash import fingerprint_scope
from specroad.graph.scope_closure import resolve_scope_closure
from specroad.graph.scope_descriptors import ScopeDescriptor
from specroad.graph.scope_seeds import resolve_scope_seeds
from specroad.graph.scope_inputs import ScopeResource
from specroad.graph.relations import SourceRelations
from specroad.model.canonical import canonical_json_sha256
from specroad.model.configuration import ProjectConfiguration
from specroad.model.model_manifest import ProjectReadBinding, ManifestResource, assemble_model_manifest
from specroad.model.errors import ModelError
from support.artifacts import artifact_bytes
from support.relations import artifact, aid, edge, rid
from support.scopes import inputs, descriptor
from support.closure import observe, selected
from support.model import configuration_value


def snapshot(*values, project_id='sample'):
    return ComparisonInputs(project_id, [SourceRelations(artifact_bytes(value)) for value in values])


def resolved(inventory, *, kind='explicit', policy='closed', identities=None):
    selector = {'artifact_ids': [aid()] if identities is None else identities, 'resource_ids': []} if kind == 'explicit' else {}
    seeds = resolve_scope_seeds(ScopeDescriptor(descriptor(kind, selector, boundary_policy=policy)), inventory)
    bindings = observe(inventory)
    return resolve_scope_closure(seeds, bindings), bindings


def fingerprint(inventory, *, kind='explicit', policy='closed', profile=None, binding=None):
    closure, bindings = resolved(inventory, kind=kind, policy=policy)
    return fingerprint_scope(ProjectConfiguration(configuration_value()),
        binding or ProjectReadBinding('sample', '/test-only/project', (1, 2)),
        closure, bindings, effective_profile={} if profile is None else profile)


class ScopeComparisonTests(unittest.TestCase):
    def test_scope_hash_binds_transitive_members(self):
        one = inputs(artifact(relations=[edge('depends_on', aid(number=2))]), artifact(number=2))
        two = inputs(artifact(relations=[edge('depends_on', aid(number=2))]), artifact(number=2, title='Changed'))
        self.assertNotEqual(fingerprint(one).scope_sha256, fingerprint(two).scope_sha256)

    def test_scope_hash_ignores_unselected_unconnected_artifact(self):
        one = inputs(artifact(), artifact(number=2))
        two = inputs(artifact(), artifact(number=2, title='Unselected change'))
        self.assertEqual(fingerprint(one).sha256, fingerprint(two).sha256)

    def test_scope_hash_preserves_existing_manifest_contract(self):
        inventory = inputs(artifact()); closure, bindings = resolved(inventory)
        binding = ProjectReadBinding('sample', '/test-only/project', (1, 2))
        cfg = ProjectConfiguration(configuration_value())
        resources = [ManifestResource(binding, {'kind': 'artifact', 'id': aid(),
            'artifact_type': 'requirement', 'revision': 1, 'sha256': canonical_json_sha256(artifact())})]
        old = assemble_model_manifest(cfg, binding, resources,
            scope_descriptor=closure.seeds.descriptor.data, effective_profile={})
        new = fingerprint_scope(cfg, binding, closure, bindings, effective_profile={})
        self.assertEqual(new.canonical_bytes, old.canonical_bytes)

    def test_project_roots_and_inodes_are_not_semantic(self):
        inventory = inputs(artifact())
        one = fingerprint(inventory, binding=ProjectReadBinding('sample', '/a', (1, 2)))
        two = fingerprint(inventory, binding=ProjectReadBinding('sample', '/b', (3, 4)))
        self.assertEqual(one.sha256, two.sha256)

    def test_effective_profile_is_bound(self):
        inventory = inputs(artifact())
        self.assertNotEqual(fingerprint(inventory).sha256, fingerprint(inventory, profile={'rule': True}).sha256)

    def test_boundary_target_hash_changes_partial_scope_hash(self):
        one = inputs(artifact(relations=[edge('duplicates', aid(number=2))]), artifact(number=2))
        two = inputs(artifact(relations=[edge('duplicates', aid(number=2))]), artifact(number=2, title='New'))
        self.assertNotEqual(fingerprint(one, policy='partial').scope_sha256,
                            fingerprint(two, policy='partial').scope_sha256)

    def test_boundary_policy_is_hashed_even_without_weak_edges(self):
        inventory = inputs(artifact())
        self.assertNotEqual(fingerprint(inventory).scope_sha256, fingerprint(inventory, policy='partial').scope_sha256)

    def test_source_iteration_order_is_not_semantic(self):
        self.assertEqual(fingerprint(inputs(artifact(), artifact(number=2)), kind='project').sha256,
                         fingerprint(inputs(artifact(number=2), artifact()), kind='project').sha256)

    def test_original_formatting_is_not_semantic(self):
        from specroad.graph.scope_inputs import ScopeSeedInputs
        value = artifact()
        a = inputs(value)
        b = ScopeSeedInputs(ProjectConfiguration(configuration_value()),
            [SourceRelations(json.dumps(value, indent=4, sort_keys=True).encode())])
        self.assertEqual(fingerprint(a).sha256, fingerprint(b).sha256)

    def test_artifact_revision_is_bound(self):
        self.assertNotEqual(fingerprint(inputs(artifact())).sha256,
                            fingerprint(inputs(artifact(revision=2))).sha256)

    def test_descriptor_kind_is_bound(self):
        inventory = inputs(artifact())
        self.assertNotEqual(fingerprint(inventory, kind='project').sha256,
                            fingerprint(inventory, kind='specification').sha256)

    def test_selected_resource_identity_version_and_hash_are_bound(self):
        resource = ScopeResource('opaque-profile', 'profile', 'a'*64, '1', True)
        inventory = inputs(artifact(), resources=[resource]); closure, bindings = resolved(inventory, kind='project')
        cfg = ProjectConfiguration(configuration_value()); binding = ProjectReadBinding('sample', '/test', (1, 2))
        record = ManifestResource(binding, {'kind':'profile', 'id':'profile', 'version':'1', 'sha256':'a'*64})
        result = fingerprint_scope(cfg, binding, closure, bindings, effective_profile={},
                                   resource_records={'opaque-profile':record})
        self.assertEqual(result.data['resources'], [record.data])

    def test_result_is_detached_and_not_a_write_authorization(self):
        result = fingerprint(inputs(artifact())); digest = result.sha256
        result.data['artifacts'].clear()
        self.assertEqual(result.sha256, digest)
        self.assertFalse(result.atomic_snapshot)
        self.assertFalse(result.profile_composition_verified)

    def test_scope_hash_is_sha256_of_the_defined_scope_projection(self):
        result = fingerprint(inputs(artifact()))
        value = result.data; del value['scope_sha256']; del value['model_manifest_version']
        self.assertEqual(result.scope_sha256, canonical_json_sha256(value))

    def test_scalar_nested_field_delta_is_structured(self):
        data = field_diff({'x': {'value': 2}}, {'x': {'value': 3}}).data
        self.assertEqual(data['changes'][0]['pointer'], '/x/value')
        self.assertEqual((data['changes'][0]['before'], data['changes'][0]['after']), (2, 3))

    def test_missing_and_null_are_different(self):
        item = field_diff({}, {'x': None}).data['changes'][0]
        self.assertFalse(item['before_present']); self.assertTrue(item['after_present'])
        self.assertEqual(item['operation'], 'add')

    def test_removal_is_explicit(self):
        item = field_diff({'x': None}, {}).data['changes'][0]
        self.assertEqual(item['operation'], 'remove'); self.assertFalse(item['after_present'])

    def test_json_pointer_escapes_slash_and_tilde(self):
        item = field_diff({'a/b': {'~x': 1}}, {'a/b': {'~x': 2}}).data['changes'][0]
        self.assertEqual(item['pointer'], '/a~1b/~0x')

    def test_object_key_order_and_equal_jcs_numbers_are_not_changes(self):
        self.assertFalse(field_diff({'a': 1, 'b': -0.0}, {'b': 0, 'a': 1.0}).data['changed'])

    def test_boolean_is_not_integer(self):
        self.assertTrue(field_diff({'a': True}, {'a': 1}).data['changed'])

    def test_array_order_is_data_and_arrays_are_atomic(self):
        items = field_diff({'x': [1, 2]}, {'x': [2, 1]}).data['changes']
        self.assertEqual(len(items), 1); self.assertEqual(items[0]['pointer'], '/x')

    def test_text_is_never_interpreted_as_a_timing_constraint(self):
        item = field_diff({'statement': 'within 10 ms'}, {'statement': 'within 5 ms'}).data['changes'][0]
        self.assertEqual(item['category'], 'text_changed')

    def test_field_results_do_not_modify_inputs(self):
        before = {'x': [1]}; after = {'x': [2]}; saved = deepcopy((before, after))
        result = field_diff(before, after); result.data['changes'][0]['after'].append(3)
        self.assertEqual((before, after), saved)
        self.assertEqual(result.data['changes'][0]['after'], [2])

    def test_new_artifact_is_added(self):
        result = compare_artifacts(snapshot(), snapshot(artifact())).data
        self.assertEqual(result['changes'][0]['change_kind'], 'added')

    def test_missing_artifact_is_removed_not_assumed_retired(self):
        result = compare_artifacts(snapshot(artifact()), snapshot()).data
        self.assertEqual(result['changes'][0]['change_kind'], 'removed')

    def test_changed_artifact_has_bound_before_and_after_values(self):
        result = compare_artifacts(snapshot(artifact()), snapshot(artifact(title='New'))).data
        change = result['changes'][0]
        self.assertEqual(change['change_kind'], 'modified')
        self.assertNotEqual(change['before_sha256'], change['after_sha256'])

    def test_unchanged_set_has_no_changes(self):
        one = snapshot(artifact(), artifact(number=2))
        two = snapshot(artifact(number=2), artifact())
        self.assertFalse(compare_artifacts(one, two).data['changed'])

    def test_different_projects_are_not_silently_compared(self):
        with self.assertRaises(ModelError):
            compare_artifacts(snapshot(artifact()), snapshot(artifact(), project_id='other'))

    def test_changed_id_prefix_is_not_treated_as_same_project(self):
        with self.assertRaises(ModelError):
            compare_artifacts(snapshot(artifact()), snapshot(artifact(project='AB')))

    def test_direct_impact_includes_both_directions(self):
        inventory = inputs(artifact(relations=[edge('depends_on', aid(number=2))]),
                           artifact(number=2, relations=[edge('refines', aid(number=3), number=2)]), artifact(number=3))
        result = direct_impact(aid(number=2), inventory.references).data
        self.assertEqual({g['relation_type'] for g in result['groups']}, {'depends_on', 'refines'})
        self.assertEqual({c['direction'] for g in result['groups'] for c in g['connections']}, {'incoming', 'outgoing'})

    def test_direct_impact_does_not_include_transitive_only_nodes(self):
        inventory = inputs(artifact(relations=[edge('depends_on', aid(number=2))]),
                           artifact(number=2, relations=[edge('depends_on', aid(number=3), number=2)]), artifact(number=3))
        result = direct_impact(aid(), inventory.references).data
        self.assertEqual(result['groups'][0]['artifact_ids'], [aid(number=2)])
        self.assertFalse(result['transitive'])

    def test_multiple_relations_keep_all_relation_ids(self):
        inventory = inputs(artifact(relations=[edge('depends_on', aid(number=2)),
                                               edge('depends_on', aid(number=2), number=2)]), artifact(number=2))
        group = direct_impact(aid(), inventory.references).data['groups'][0]
        self.assertEqual(group['artifact_ids'], [aid(number=2)])
        self.assertEqual([c['relation_id'] for c in group['connections']], [rid(), rid(2)])

    def test_isolated_node_has_complete_empty_direct_impact(self):
        self.assertEqual(direct_impact(aid(), inputs(artifact()).references).data['groups'], [])

    def test_unknown_impact_target_is_error(self):
        with self.assertRaises(ModelError): direct_impact(aid(number=2), inputs(artifact()).references)

    def test_supersedes_reverse_keeps_its_stored_identity(self):
        inventory = inputs(artifact(relations=[edge('supersedes', aid(number=2))]), artifact(number=2))
        group = direct_impact(aid(number=2), inventory.references).data['groups'][0]
        self.assertEqual(group['relation_type'], 'supersedes')
        self.assertEqual(group['connections'][0]['relation_id'], rid())

    def test_symmetric_relationship_is_seen_from_both_ends(self):
        inventory = inputs(artifact(relations=[edge('duplicates', aid(number=2))]), artifact(number=2))
        one = direct_impact(aid(), inventory.references).data
        two = direct_impact(aid(number=2), inventory.references).data
        self.assertEqual(one['groups'][0]['connections'][0]['relation_id'], two['groups'][0]['connections'][0]['relation_id'])
