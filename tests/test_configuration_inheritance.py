"""Parent-chain behavior and canonical configuration bindings over owned records."""
from hashlib import sha256
import json
import unittest

from specroad.configurations import resolve_configuration
from specroad.graph.relations import SourceRelations
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.model.errors import ModelError
from support.artifacts import artifact_bytes
from support.records import record_value, ref, srx


def configuration(token='0', **changes):
    value = record_value('configuration', id=ref('CFG', token), name='Configuration ' + token)
    value.update(changes)
    return value


def sources(*values):
    return [SourceRelations(artifact_bytes(value)) for value in values]


def resolve(*values, selected=None):
    return resolve_configuration(sources(*values), values[-1]['id'] if selected is None else selected)


class ConfigurationInheritanceWorkTests(unittest.TestCase):
    def test_root_manifest_binds_identity_revision_full_value_hash_and_selection(self):
        root = configuration()
        result = resolve(root)
        expected = {'manifest_version': 'effective-configuration-v1', 'configuration_id': root['id'],
                    'configurations': [{'id': root['id'], 'revision': 1,
                                        'sha256': canonical_json_sha256(root)}],
                    'dimensions': root['dimensions'], 'effective_values': {'platform': 'linux'}}
        self.assertEqual(result.manifest, expected)
        self.assertEqual(result.sha256, sha256(canonical_json_bytes(expected)).hexdigest())

    def test_child_inherits_the_parents_declared_dimensions_and_selection(self):
        root = configuration(selection={'platform': 'windows'})
        child = configuration('1', parent=root['id'], dimensions=[], selection={})
        result = resolve(root, child)
        self.assertEqual(result.effective_values, {'platform': 'windows'})
        self.assertEqual(result.dimensions, root['dimensions'])
        self.assertEqual(result.configuration_id, child['id'])
        self.assertEqual(result.validation_scope, 'supplied_configuration_chain_only')

    def test_child_overrides_a_parent_selection(self):
        root = configuration()
        child = configuration('1', parent=root['id'], dimensions=[], selection={'platform': 'windows'})
        self.assertEqual(resolve(root, child).effective_values, {'platform': 'windows'})

    def test_three_levels_combine_new_dimensions_and_child_overrides(self):
        root = configuration()
        middle = configuration('1', parent=root['id'], dimensions=[
            {'name': 'edition', 'allowed_values': ['basic', 'pro'], 'default': 'basic'}],
            selection={'platform': 'windows'})
        child = configuration('2', parent=middle['id'], dimensions=[
            {'name': 'debug', 'allowed_values': [False, True]}],
            selection={'edition': 'pro', 'debug': False})
        result = resolve(root, middle, child)
        self.assertEqual(result.effective_values, {'platform': 'windows', 'edition': 'pro', 'debug': False})
        self.assertEqual([entry['id'] for entry in result.manifest['configurations']],
                         [root['id'], middle['id'], child['id']])

    def test_missing_selection_after_the_chain_uses_the_original_default(self):
        root = configuration(selection={})
        child = configuration('1', parent=root['id'], dimensions=[], selection={})
        self.assertEqual(resolve(root, child).effective_values, {'platform': 'linux'})

    def test_child_selection_has_priority_over_an_inherited_default(self):
        root = configuration(selection={})
        child = configuration('1', parent=root['id'], dimensions=[], selection={'platform': 'windows'})
        self.assertEqual(resolve(root, child).effective_values, {'platform': 'windows'})

    def test_child_can_add_a_dimension_with_its_own_default(self):
        root = configuration()
        child = configuration('1', parent=root['id'], dimensions=[
            {'name': 'edition', 'allowed_values': ['basic', 'pro'], 'default': 'pro'}], selection={})
        self.assertEqual(resolve(root, child).effective_values, {'platform': 'linux', 'edition': 'pro'})

    def test_explicit_null_survives_an_inherited_non_null_default(self):
        root = configuration(dimensions=[{'name': 'mode', 'allowed_values': ['auto', None], 'default': 'auto'}],
                             selection={})
        child = configuration('1', parent=root['id'], dimensions=[], selection={'mode': None})
        self.assertEqual(resolve(root, child).effective_values, {'mode': None})

    def test_boolean_override_is_not_replaced_by_parent_truthiness(self):
        root = configuration(dimensions=[{'name': 'enabled', 'allowed_values': [False, True]}],
                             selection={'enabled': True})
        child = configuration('1', parent=root['id'], dimensions=[], selection={'enabled': False})
        self.assertIs(resolve(root, child).effective_values['enabled'], False)

    def test_identical_inherited_dimension_declaration_does_not_duplicate_it(self):
        root = configuration()
        child = configuration('1', parent=root['id'], selection={'platform': 'windows'})
        result = resolve(root, child)
        self.assertEqual(result.dimensions, root['dimensions'])
        self.assertEqual(result.effective_values, {'platform': 'windows'})

    def test_changed_inherited_allowed_values_are_rejected(self):
        root = configuration()
        child = configuration('1', parent=root['id'], dimensions=[
            {'name': 'platform', 'allowed_values': ['linux'], 'default': 'linux'}], selection={})
        with self.assertRaises(ModelError) as caught:
            resolve(root, child)
        self.assertEqual(caught.exception.reason, 'inherited_dimension_changed')

    def test_changed_or_removed_inherited_default_is_rejected(self):
        root = configuration()
        for include_default in (False, True):
            dimension = {'name': 'platform', 'allowed_values': ['linux', 'windows']}
            if include_default:
                dimension['default'] = 'windows'
            child = configuration('1', parent=root['id'], dimensions=[dimension], selection={})
            with self.subTest(default=include_default), self.assertRaises(ModelError) as caught:
                resolve(root, child)
            self.assertEqual(caught.exception.reason, 'inherited_dimension_changed')

    def test_unknown_inherited_selection_is_rejected(self):
        root = configuration()
        child = configuration('1', parent=root['id'], dimensions=[], selection={'unknown': 'value'})
        with self.assertRaises(ModelError) as caught:
            resolve(root, child)
        self.assertEqual(caught.exception.reason, 'unknown_dimension')

    def test_invalid_inherited_value_is_rejected(self):
        root = configuration()
        child = configuration('1', parent=root['id'], dimensions=[], selection={'platform': 'other'})
        with self.assertRaises(ModelError) as caught:
            resolve(root, child)
        self.assertEqual(caught.exception.reason, 'invalid_dimension_selection')

    def test_inherited_boolean_is_not_a_numeric_value(self):
        root = configuration(dimensions=[{'name': 'choice', 'allowed_values': [1]}], selection={'choice': 1})
        child = configuration('1', parent=root['id'], dimensions=[], selection={'choice': True})
        with self.assertRaises(ModelError) as caught:
            resolve(root, child)
        self.assertEqual(caught.exception.reason, 'invalid_dimension_selection')

    def test_new_dimension_needs_a_selection_or_default_at_the_end(self):
        root = configuration()
        child = configuration('1', parent=root['id'], dimensions=[{'name': 'edition', 'allowed_values': ['pro']}],
                              selection={})
        with self.assertRaises(ModelError) as caught:
            resolve(root, child)
        self.assertEqual(caught.exception.reason, 'missing_dimension_selection')

    def test_missing_parent_cannot_be_replaced_by_root_defaults(self):
        child = configuration('1', parent=ref('CFG'))
        with self.assertRaises(ModelError) as caught:
            resolve(child)
        self.assertEqual(caught.exception.reason, 'configuration_parent_missing')
        self.assertEqual(caught.exception.pointer, '/parent')

    def test_parent_list_cannot_choose_one_arbitrary_configuration(self):
        child = configuration('1', parent=[ref('CFG'), ref('CFG', '2')])
        with self.assertRaises(ModelError) as caught:
            resolve(child)
        self.assertEqual(caught.exception.pointer, '/parent')

    def test_parent_reference_cannot_address_a_document(self):
        child = configuration('1', parent=ref('DOC'))
        with self.assertRaises(ModelError) as caught:
            resolve(child)
        self.assertEqual(caught.exception.pointer, '/parent')

    def test_parent_from_a_different_project_prefix_is_rejected(self):
        root = configuration(id='XX-CFG-' + '0' * 26)
        child = configuration('1', parent=root['id'], dimensions=[], selection={})
        with self.assertRaises(ModelError) as caught:
            resolve(root, child)
        self.assertEqual(caught.exception.reason, 'configuration_parent_project_mismatch')

    def test_self_parent_is_rejected(self):
        root = configuration(parent=ref('CFG'))
        with self.assertRaises(ModelError) as caught:
            resolve(root)
        self.assertEqual(caught.exception.reason, 'configuration_self_parent')

    def test_two_node_cycle_terminates_without_effective_values(self):
        first = configuration(parent=ref('CFG', '1'))
        second = configuration('1', parent=first['id'])
        with self.assertRaises(ModelError) as caught:
            resolve(first, second)
        self.assertEqual(caught.exception.reason, 'configuration_parent_cycle')

    def test_root_configuration_cannot_have_applicability(self):
        root = configuration(applicability=srx())
        with self.assertRaises(ModelError) as caught:
            resolve(root)
        self.assertEqual(caught.exception.reason, 'unknown_field')
        self.assertEqual(caught.exception.pointer, '/applicability')

    def test_child_configuration_cannot_have_applicability(self):
        root = configuration()
        child = configuration('1', parent=root['id'], dimensions=[], selection={}, applicability=srx())
        with self.assertRaises(ModelError) as caught:
            resolve(root, child)
        self.assertEqual(caught.exception.reason, 'unknown_field')
        self.assertEqual(caught.exception.pointer, '/applicability')

    def test_inventory_order_does_not_change_the_chain_or_hash(self):
        root = configuration()
        child = configuration('1', parent=root['id'], dimensions=[], selection={})
        forward = resolve(root, child)
        reverse = resolve(child, root, selected=child['id'])
        self.assertEqual(forward.data, reverse.data)
        self.assertEqual(forward.manifest, reverse.manifest)
        self.assertEqual(forward.sha256, reverse.sha256)

    def test_unrelated_configuration_is_not_part_of_the_effective_hash(self):
        root = configuration()
        child = configuration('1', parent=root['id'], dimensions=[], selection={})
        unrelated = configuration('2', selection={'platform': 'windows'})
        self.assertEqual(resolve(root, child).sha256,
                         resolve(unrelated, root, child).sha256)

    def test_parent_revision_and_full_record_hash_are_bound(self):
        root = configuration()
        child = configuration('1', parent=root['id'], dimensions=[], selection={})
        original = resolve(root, child)
        for changed in (dict(root, revision=2), dict(root, title='Changed normative title')):
            result = resolve(changed, child)
            self.assertEqual(result.effective_values, original.effective_values)
            self.assertNotEqual(result.sha256, original.sha256)
            self.assertEqual(result.manifest['configurations'][0]['sha256'], canonical_json_sha256(changed))

    def test_selected_child_revision_is_bound(self):
        root = configuration()
        child = configuration('1', parent=root['id'], dimensions=[], selection={})
        self.assertNotEqual(resolve(root, child).sha256, resolve(root, dict(child, revision=2)).sha256)

    def test_changed_selection_changes_the_effective_configuration_hash(self):
        root = configuration()
        child = configuration('1', parent=root['id'], dimensions=[], selection={})
        changed = dict(child, selection={'platform': 'windows'})
        self.assertNotEqual(resolve(root, child).sha256, resolve(root, changed).sha256)

    def test_json_representation_does_not_change_the_canonical_hash(self):
        value = configuration()
        compact = SourceRelations(artifact_bytes(value))
        indented = SourceRelations(json.dumps(value, indent=4, sort_keys=True).encode())
        first = resolve_configuration([compact], value['id'])
        second = resolve_configuration([indented], value['id'])
        self.assertEqual(first.sha256, second.sha256)
        self.assertEqual(first.manifest, second.manifest)
        self.assertNotEqual(first.source_sha256, second.source_sha256)

    def test_local_source_path_is_not_an_effective_hash_input(self):
        value = configuration()
        first = SourceRelations(artifact_bytes(value), path='one/configuration.json')
        second = SourceRelations(artifact_bytes(value), path='another/configuration.json')
        self.assertEqual(resolve_configuration([first], value['id']).sha256,
                         resolve_configuration([second], value['id']).sha256)

    def test_manifest_is_detached_and_sources_stay_byte_identical(self):
        root = configuration(selection={})
        child = configuration('1', parent=root['id'], dimensions=[], selection={})
        records = sources(root, child)
        before = [record.source_bytes for record in records]
        result = resolve_configuration(records, child['id'])
        manifest, digest = result.manifest, result.sha256
        result.manifest['configurations'].clear()
        result.manifest['dimensions'][0]['allowed_values'].clear()
        result.manifest['effective_values']['platform'] = 'windows'
        self.assertEqual(result.manifest, manifest)
        self.assertEqual(result.sha256, digest)
        self.assertEqual([record.source_bytes for record in records], before)
        self.assertEqual(records[0].data['selection'], {})

    def test_manifest_dimensions_have_deterministic_name_order(self):
        root = configuration(dimensions=[{'name': 'z', 'allowed_values': [1], 'default': 1},
                                         {'name': 'a', 'allowed_values': [2], 'default': 2}], selection={})
        result = resolve(root)
        self.assertEqual([value['name'] for value in result.dimensions], ['z', 'a'])
        self.assertEqual([value['name'] for value in result.manifest['dimensions']], ['a', 'z'])
