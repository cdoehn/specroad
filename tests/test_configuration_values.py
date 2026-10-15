"""Behavior of effective product values, separate from specroad.json settings."""
from dataclasses import FrozenInstanceError
from hashlib import sha256
import unittest

from specroad.configurations import EffectiveConfiguration, resolve_configuration
from specroad.graph.relations import SourceRelations
from specroad.model.errors import ModelError
from support.artifacts import artifact_bytes
from support.records import record_value, ref


def source(**changes):
    return SourceRelations(artifact_bytes(record_value('configuration', **changes)))


class ConfigurationValuesWorkTests(unittest.TestCase):
    def test_explicit_root_selection_materializes_all_declared_dimensions(self):
        record = source(selection={'platform': 'windows'})
        result = resolve_configuration([record], record.identity.id)
        self.assertIs(type(result), EffectiveConfiguration)
        self.assertEqual(result.data, {
            'configuration_id': record.identity.id, 'configuration_revision': 1,
            'name': 'Linux', 'dimensions': record.data['dimensions'],
            'effective_values': {'platform': 'windows'}})

    def test_missing_selection_uses_declared_default_without_rewriting_source(self):
        record = source(selection={})
        before = record.source_bytes
        result = resolve_configuration([record], record.identity.id)
        self.assertEqual(result.effective_values, {'platform': 'linux'})
        self.assertEqual(record.source_bytes, before)
        self.assertEqual(record.data['selection'], {})
        self.assertEqual(result.source_sha256, sha256(before).hexdigest())

    def test_explicit_selection_overrides_default(self):
        record = source(selection={'platform': 'windows'})
        self.assertEqual(resolve_configuration([record], record.identity.id).effective_values,
                         {'platform': 'windows'})

    def test_multiple_dimensions_mix_explicit_selection_and_defaults(self):
        record = source(dimensions=[
            {'name': 'platform', 'allowed_values': ['linux', 'windows'], 'default': 'linux'},
            {'name': 'edition', 'allowed_values': ['basic', 'pro'], 'default': 'basic'},
            {'name': 'debug', 'allowed_values': [False, True]}],
            selection={'platform': 'windows', 'debug': False})
        self.assertEqual(resolve_configuration([record], record.identity.id).effective_values,
                         {'platform': 'windows', 'edition': 'basic', 'debug': False})

    def test_declared_dimension_without_default_uses_explicit_selection(self):
        record = source(dimensions=[{'name': 'level', 'allowed_values': [0, 1, 2]}], selection={'level': 0})
        self.assertEqual(resolve_configuration([record], record.identity.id).effective_values, {'level': 0})

    def test_empty_root_dimensions_resolve_to_empty_values(self):
        record = source(dimensions=[], selection={})
        self.assertEqual(resolve_configuration([record], record.identity.id).effective_values, {})

    def test_json_scalar_selections_keep_their_types_and_values(self):
        for value in ('', '東京', 0, 1.5, False, True, None):
            with self.subTest(value=value):
                record = source(dimensions=[{'name': 'choice', 'allowed_values': [value]}],
                                selection={'choice': value})
                actual = resolve_configuration([record], record.identity.id).effective_values['choice']
                self.assertIs(type(actual), type(value))
                self.assertEqual(actual, value)

    def test_falsy_defaults_are_materialized_by_presence(self):
        for value in (False, 0, '', None):
            with self.subTest(value=value):
                record = source(dimensions=[{'name': 'choice', 'allowed_values': [value], 'default': value}],
                                selection={})
                actual = resolve_configuration([record], record.identity.id).effective_values['choice']
                self.assertIs(type(actual), type(value))
                self.assertEqual(actual, value)

    def test_explicit_null_overrides_non_null_default(self):
        record = source(dimensions=[{'name': 'mode', 'allowed_values': ['auto', None], 'default': 'auto'}],
                        selection={'mode': None})
        self.assertEqual(resolve_configuration([record], record.identity.id).effective_values, {'mode': None})

    def test_named_configurations_keep_separate_selections_and_identifiers(self):
        first = source()
        second = source(id=ref('CFG', '1'), name='Windows', selection={'platform': 'windows'})
        records = [first, second]
        self.assertEqual(resolve_configuration(records, first.identity.id).effective_values, {'platform': 'linux'})
        result = resolve_configuration(records, second.identity.id)
        self.assertEqual(result.configuration_id, second.identity.id)
        self.assertEqual(result.effective_values, {'platform': 'windows'})

    def test_inventory_order_does_not_change_resolved_values(self):
        first = source()
        second = source(id=ref('CFG', '1'), name='Other')
        a = resolve_configuration([first, second], second.identity.id)
        b = resolve_configuration((second, first), second.identity.id)
        self.assertEqual(a.data, b.data)
        self.assertEqual(a.source_sha256, b.source_sha256)

    def test_duplicate_configuration_names_fail_before_a_result_is_returned(self):
        first = source()
        second = source(id=ref('CFG', '1'))
        with self.assertRaises(ModelError) as caught:
            resolve_configuration([first, second], first.identity.id)
        self.assertEqual(caught.exception.reason, 'duplicate_configuration_name')
        self.assertEqual(caught.exception.pointer, '/name')

    def test_duplicate_inventory_ids_are_not_silently_overwritten(self):
        record = source()
        with self.assertRaises(ModelError) as caught:
            resolve_configuration([record, record], record.identity.id)
        self.assertEqual(caught.exception.reason, 'duplicate_configuration_inventory_id')

    def test_unknown_id_never_chooses_the_only_available_configuration(self):
        with self.assertRaises(ModelError) as caught:
            resolve_configuration([source()], ref('CFG', '1'))
        self.assertEqual(caught.exception.reason, 'configuration_missing')

    def test_configuration_selection_is_explicit(self):
        for identifier in (None, '', False, []):
            with self.subTest(identifier=identifier), self.assertRaises(ModelError) as caught:
                resolve_configuration([source()], identifier)
            self.assertEqual(caught.exception.reason, 'configuration_id_required')

    def test_result_data_and_nested_dimensions_are_detached(self):
        record = source()
        result = resolve_configuration([record], record.identity.id)
        before = result.data
        result.data['effective_values']['platform'] = 'windows'
        result.dimensions[0]['allowed_values'].clear()
        result.effective_values.clear()
        self.assertEqual(result.data, before)
        self.assertEqual(record.data['dimensions'][0]['allowed_values'], ['linux', 'windows'])
        with self.assertRaises(FrozenInstanceError):
            result.configuration_id = ref('CFG', '1')

    def test_other_artifact_types_are_not_product_configurations(self):
        record = source()
        document = SourceRelations(artifact_bytes(record_value('document')))
        result = resolve_configuration([document, record], record.identity.id)
        self.assertEqual(result.effective_values, {'platform': 'linux'})
        with self.assertRaises(ModelError) as caught:
            resolve_configuration([document, record], document.identity.id)
        self.assertEqual(caught.exception.reason, 'configuration_missing')

    def test_inherited_configuration_needs_the_parent_resolver(self):
        parent = source()
        child = source(id=ref('CFG', '1'), name='Child', parent=parent.identity.id)
        with self.assertRaises(ModelError) as caught:
            resolve_configuration([child], child.identity.id)
        self.assertEqual(caught.exception.reason, 'configuration_parent_missing')
        self.assertEqual(caught.exception.pointer, '/parent')
        # 9.b supplies the previously unavailable parent resolver. Keep this
        # scenario's stable test identity while checking its new behavior.
        result = resolve_configuration([parent, child], child.identity.id)
        self.assertEqual(result.effective_values, {'platform': 'linux'})
        self.assertEqual(result.validation_scope, 'supplied_configuration_chain_only')

    def test_explicit_null_parent_is_a_root(self):
        record = source(parent=None)
        self.assertEqual(resolve_configuration([record], record.identity.id).effective_values, {'platform': 'linux'})

    def test_record_field_validation_rejects_unknown_dimension(self):
        record = source(selection={'platform': 'linux', 'unknown': 'value'})
        with self.assertRaises(ModelError) as caught:
            resolve_configuration([record], record.identity.id)
        self.assertEqual(caught.exception.reason, 'unknown_dimension')

    def test_record_field_validation_rejects_missing_selection_and_default(self):
        record = source(dimensions=[{'name': 'platform', 'allowed_values': ['linux']}], selection={})
        with self.assertRaises(ModelError) as caught:
            resolve_configuration([record], record.identity.id)
        self.assertEqual(caught.exception.reason, 'missing_dimension_selection')

    def test_result_scope_does_not_claim_project_coverage_or_a_configuration_hash(self):
        record = source()
        result = resolve_configuration([record], record.identity.id)
        self.assertEqual(result.validation_scope, 'supplied_root_configuration_only')
        self.assertEqual(set(result.data), {'configuration_id', 'configuration_revision', 'name',
                                           'dimensions', 'effective_values'})

    def test_input_requires_explicit_loaded_sources(self):
        for records in (None, 'project', {'configuration': source()}, [record_value('configuration')]):
            with self.subTest(kind=type(records).__name__), self.assertRaises(ModelError):
                resolve_configuration(records, ref('CFG'))

    def test_resolution_never_uses_a_forged_cached_record_identity(self):
        record = source()
        original = record.identity
        object.__setattr__(record, 'identity', source(id=ref('CFG', '1'), name='Other').identity)
        self.assertEqual(resolve_configuration([record], original.id).configuration_id, original.id)
