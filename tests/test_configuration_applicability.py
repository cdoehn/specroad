"""Applicability classifications and restricted SRX context behavior."""
from dataclasses import FrozenInstanceError
from hashlib import sha256
import unittest

from specroad.configurations import (ApplicabilityResult, evaluate_applicability,
                                     resolve_configuration)
from specroad.graph.relations import SourceRelations
from specroad.model.errors import ModelError
from specroad.srx import SrxError
from support.artifacts import artifact_bytes
from support.records import record_value, ref
from support.srx import binary, expression_document, field, literal, quantifier


def source(expression=None, **changes):
    value = record_value('document', title='Control', tags=['safety'])
    if expression is not None:
        value['applicability'] = expression_document(expression)
    value.update(changes)
    return SourceRelations(artifact_bytes(value), path='spec/documents/control.json')


def configuration(platform='linux'):
    value = record_value('configuration', selection={'platform': platform})
    return resolve_configuration([SourceRelations(artifact_bytes(value))], value['id'])


def platform_condition(platform):
    return binary('eq', field('/effective_values/platform', 'configuration'), literal(platform))


class ConfigurationApplicabilityWorkTests(unittest.TestCase):
    def test_unconditional_artifact_without_configuration_is_applicable(self):
        result = evaluate_applicability(source())
        self.assertEqual(result.status, 'applicable')
        self.assertEqual(result.reason, 'unconditional')
        self.assertIsNone(result.configuration_id)
        self.assertIsNone(result.configuration_sha256)

    def test_unconditional_artifact_with_configuration_is_applicable(self):
        selected = configuration()
        result = evaluate_applicability(source(), selected)
        self.assertEqual(result.status, 'applicable')
        self.assertEqual(result.configuration_id, selected.configuration_id)
        self.assertEqual(result.configuration_sha256, selected.sha256)

    def test_conditional_artifact_without_configuration_is_potential(self):
        result = evaluate_applicability(source(platform_condition('linux')))
        self.assertEqual(result.status, 'potentially_applicable')
        self.assertEqual(result.reason, 'no_configuration')

    def test_literal_true_without_configuration_remains_potential(self):
        self.assertEqual(evaluate_applicability(source(literal(True))).status, 'potentially_applicable')

    def test_literal_false_without_configuration_remains_potential(self):
        self.assertEqual(evaluate_applicability(source(literal(False))).status, 'potentially_applicable')

    def test_no_configuration_does_not_evaluate_runtime_operands(self):
        expression = binary('divide', literal(1), literal(0))
        self.assertEqual(evaluate_applicability(source(expression)).status, 'potentially_applicable')

    def test_matching_configuration_selects_the_artifact(self):
        result = evaluate_applicability(source(platform_condition('linux')), configuration())
        self.assertEqual((result.status, result.reason), ('applicable', 'condition_true'))

    def test_nonmatching_configuration_excludes_the_artifact(self):
        result = evaluate_applicability(source(platform_condition('windows')), configuration())
        self.assertEqual((result.status, result.reason), ('excluded', 'condition_false'))

    def test_literal_boolean_results_remain_distinct(self):
        for value, status in ((True, 'applicable'), (False, 'excluded')):
            with self.subTest(value=value):
                self.assertEqual(evaluate_applicability(source(literal(value)), configuration()).status, status)

    def test_parent_chain_override_drives_the_condition(self):
        root = record_value('configuration')
        child = record_value('configuration', id=ref('CFG', '1'), name='Windows', parent=root['id'],
                             dimensions=[], selection={'platform': 'windows'})
        selected = resolve_configuration([SourceRelations(artifact_bytes(v)) for v in (root, child)], child['id'])
        result = evaluate_applicability(source(platform_condition('windows')), selected)
        self.assertEqual(result.status, 'applicable')
        self.assertEqual(result.configuration_id, child['id'])
        self.assertEqual(result.configuration_sha256, selected.sha256)

    def test_configuration_context_contains_only_the_normative_projection(self):
        selected = configuration()
        expected = {'configuration_id': selected.configuration_id, 'effective_values': {'platform': 'linux'}}
        expression = binary('eq', field('', 'configuration'), literal(expected))
        self.assertEqual(evaluate_applicability(source(expression), selected).status, 'applicable')

    def test_constant_artifact_metadata_is_available(self):
        expression = {'op': 'and', 'args': [binary('eq', field('/title'), literal('Control')),
                       binary('eq', field('/artifact_type'), literal('document')),
                       binary('contains', field('/tags'), literal('safety'))]}
        self.assertEqual(evaluate_applicability(source(expression), configuration()).status, 'applicable')

    def test_optional_metadata_existence_is_a_boolean_condition(self):
        expression = {'op': 'exists', 'arg': field('/owner')}
        self.assertEqual(evaluate_applicability(source(expression), configuration()).status, 'excluded')
        self.assertEqual(evaluate_applicability(source(expression, owner='engineering'), configuration()).status,
                         'applicable')

    def test_quantifier_item_is_bound_to_passive_metadata_values(self):
        expression = quantifier('any', field('/tags'), binary('eq', field('', 'item'), literal('safety')))
        self.assertEqual(evaluate_applicability(source(expression), configuration()).status, 'applicable')

    def test_whole_artifact_projection_excludes_relations_and_applicability(self):
        base = source().data
        del base['relations']
        # Document purpose/audience/render policy are content, not common metadata.
        for name in ('purpose', 'audience', 'document_role', 'render_policy'):
            del base[name]
        expression = binary('eq', field(''), literal(base))
        self.assertEqual(evaluate_applicability(source(expression), configuration()).status, 'applicable')

    def test_expression_shaped_literal_data_does_not_request_graph_access(self):
        value = {'op': 'has_relation', 'direction': 'outgoing', 'types': '*'}
        expression = binary('eq', literal(value), literal(value))
        self.assertEqual(evaluate_applicability(source(expression), configuration()).status, 'applicable')

    def test_nonboolean_end_values_are_errors_not_truthiness(self):
        for value in (None, 0, 1, '', 'true', [], {}):
            with self.subTest(value=value), self.assertRaises(ModelError) as caught:
                evaluate_applicability(source(literal(value)), configuration())
            self.assertEqual(caught.exception.reason, 'invalid_applicability')
            self.assertIsInstance(caught.exception.__cause__, SrxError)
            self.assertEqual(caught.exception.__cause__.expected, 'boolean')

    def test_missing_end_value_is_not_false(self):
        with self.assertRaises(ModelError) as caught:
            evaluate_applicability(source(field('/effective_values/unknown', 'configuration')), configuration())
        self.assertEqual(caught.exception.reason, 'invalid_applicability')
        self.assertEqual(caught.exception.__cause__.actual, 'missing')

    def test_operand_type_error_is_not_exclusion(self):
        with self.assertRaises(ModelError) as caught:
            evaluate_applicability(source({'op': 'not', 'arg': literal('false')}), configuration())
        self.assertEqual(caught.exception.reason, 'invalid_applicability')

    def test_project_context_access_is_forbidden(self):
        with self.assertRaises(ModelError) as caught:
            evaluate_applicability(source({'op': 'exists', 'arg': field('/statistics', 'project')}), configuration())
        self.assertEqual(caught.exception.__cause__.reason, 'applicability_context_forbidden')

    def test_relations_context_access_is_forbidden(self):
        with self.assertRaises(ModelError) as caught:
            evaluate_applicability(source(binary('eq', field('', 'relations'), literal([]))), configuration())
        self.assertEqual(caught.exception.__cause__.reason, 'applicability_context_forbidden')

    def test_graph_operations_are_forbidden(self):
        node = {'op': 'has_relation', 'direction': 'outgoing', 'types': '*'}
        with self.assertRaises(ModelError) as caught:
            evaluate_applicability(source(node), configuration())
        self.assertEqual(caught.exception.__cause__.reason, 'applicability_graph_forbidden')

    def test_relation_fields_cannot_be_reached_through_artifact(self):
        with self.assertRaises(ModelError) as caught:
            evaluate_applicability(source({'op': 'exists', 'arg': field('/relations')}), configuration())
        self.assertEqual(caught.exception.__cause__.reason, 'applicability_field_forbidden')

    def test_computed_verification_result_is_not_constant_metadata(self):
        with self.assertRaises(ModelError) as caught:
            evaluate_applicability(source({'op': 'exists', 'arg': field('/verification_result')},
                                          verification_result='passed'), configuration())
        self.assertEqual(caught.exception.__cause__.reason, 'applicability_field_forbidden')

    def test_configuration_record_metadata_is_not_exposed_as_configuration_context(self):
        with self.assertRaises(ModelError) as caught:
            evaluate_applicability(source({'op': 'exists', 'arg': field('/name', 'configuration')}), configuration())
        self.assertEqual(caught.exception.__cause__.reason, 'applicability_field_forbidden')

    def test_forbidden_access_in_a_short_circuited_branch_is_rejected(self):
        node = {'op': 'or', 'args': [literal(True), {'op': 'exists', 'arg': field('', 'project')}]}
        with self.assertRaises(ModelError) as caught:
            evaluate_applicability(source(node), configuration())
        self.assertEqual(caught.exception.__cause__.reason, 'applicability_context_forbidden')

    def test_missing_configuration_does_not_bypass_static_access_restrictions(self):
        with self.assertRaises(ModelError) as caught:
            evaluate_applicability(source({'op': 'exists', 'arg': field('', 'project')}))
        self.assertEqual(caught.exception.__cause__.reason, 'applicability_context_forbidden')

    def test_unknown_language_version_is_rejected_without_a_configuration(self):
        value = expression_document(literal(True)); value['version'] = '2.0'
        with self.assertRaises(ModelError) as caught:
            evaluate_applicability(source(applicability=value))
        self.assertEqual(caught.exception.__cause__.reason, 'unsupported_version')

    def test_configuration_artifact_cannot_be_conditional(self):
        value = record_value('configuration', applicability=expression_document(literal(True)))
        with self.assertRaises(ModelError) as caught:
            evaluate_applicability(SourceRelations(artifact_bytes(value)), configuration())
        self.assertEqual(caught.exception.reason, 'configuration_applicability_forbidden')
        self.assertEqual(caught.exception.pointer, '/applicability')

    def test_configuration_must_be_an_effective_configuration(self):
        for selected in (False, {}, ref('CFG'), record_value('configuration')):
            with self.subTest(selected=selected), self.assertRaises(ModelError) as caught:
                evaluate_applicability(source(), selected)
            self.assertEqual(caught.exception.reason, 'effective_configuration_required')

    def test_artifact_must_supply_original_source_bytes(self):
        for value in (None, {}, source().data, source().source_bytes):
            with self.subTest(value=type(value).__name__), self.assertRaises(ModelError) as caught:
                evaluate_applicability(value)
            self.assertEqual(caught.exception.reason, 'applicability_source_required')

    def test_result_is_frozen_and_its_projection_is_detached(self):
        result = evaluate_applicability(source(platform_condition('linux')), configuration())
        with self.assertRaises(FrozenInstanceError):
            result.status = 'excluded'
        result.data['status'] = 'excluded'
        self.assertEqual(result.status, 'applicable')

    def test_original_bytes_and_configuration_values_are_preserved(self):
        record, selected = source(platform_condition('linux')), configuration()
        raw, config = record.source_bytes, selected.data
        result = evaluate_applicability(record, selected)
        self.assertEqual(record.source_bytes, raw)
        self.assertEqual(selected.data, config)
        self.assertEqual(result.source_sha256, sha256(raw).hexdigest())
        self.assertEqual(result.artifact_id, record.identity.id)

    def test_error_preserves_source_location_and_expression_pointer(self):
        with self.assertRaises(ModelError) as caught:
            evaluate_applicability(source(field('/effective_values/unknown', 'configuration')), configuration())
        self.assertEqual(caught.exception.path, 'spec/documents/control.json')
        self.assertEqual(caught.exception.pointer, '/applicability/expression')

    def test_source_projection_mutation_does_not_change_the_condition(self):
        record = source(platform_condition('linux'))
        record.data['applicability']['expression'] = literal(False)
        self.assertEqual(evaluate_applicability(record, configuration()).status, 'applicable')

    def test_separate_configuration_decisions_are_not_cached_by_artifact_id(self):
        record = source(platform_condition('linux'))
        self.assertEqual(evaluate_applicability(record, configuration('linux')).status, 'applicable')
        self.assertEqual(evaluate_applicability(record, configuration('windows')).status, 'excluded')

    def test_direct_result_construction_uses_the_same_validation(self):
        record, selected = source(platform_condition('linux')), configuration()
        self.assertEqual(ApplicabilityResult(record, selected).data, evaluate_applicability(record, selected).data)
        self.assertEqual(ApplicabilityResult(record, selected).validation_scope,
                         'supplied_artifact_applicability_only')
