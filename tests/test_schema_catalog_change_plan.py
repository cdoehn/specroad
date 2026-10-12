"""Public catalog inventory and isolated Change Plan field contracts."""
import copy
from dataclasses import replace
import hashlib
import unittest

from specroad.changes import ChangeOperation, ChangePlan, ChangePlanError, prepare_change_plan
from specroad.changes.operation_registry import OPERATION_TYPES, operation_schema
from specroad.changes.schema import change_plan_schema
from specroad.cli.application import dispatch_result, execute_request
from specroad.cli.commands import builtin_registry
from specroad.cli.request_schema import request_schema
from specroad.cli.result_schemas import result_json_schema
from specroad.model.artifact_schemas import artifact_common_schema
from specroad.model.artifact_types import artifact_types
from specroad.model.canonical import canonical_json_bytes
from specroad.model.configuration_schema import configuration_json_schema
from specroad.model.domain_schemas import DOMAIN_TYPES, domain_schema
from specroad.model.errors import ModelError
from specroad.model.record_schemas import RECORD_TYPES, record_schema
from specroad.model.schema_catalog import SchemaCatalog, SchemaLookupError, SchemaResource
from support.change_plans import document, operation, result
from support.domain import domain_value
from support.records import record_value


CHANGE_PLAN_ID = 'urn:specroad:schema:1.2.0:change-plan'


class SchemaCatalogChangePlanTests(unittest.TestCase):
    def setUp(self):
        self.catalog = SchemaCatalog()

    def assert_unknown(self, schema_id):
        with self.assertRaises(SchemaLookupError) as caught:
            self.catalog.get(schema_id)
        self.assertEqual(caught.exception.reason, 'unknown_schema_id')
        outcomes = (
            dispatch_result(['schema', 'show', schema_id, '--format=json']),
            execute_request({'command_id': 'schema.show',
                             'arguments': {'schema_id': schema_id}}).result,
        )
        for outcome in outcomes:
            self.assertEqual(outcome.exit_code, 2)
            self.assertIsNone(outcome.result)
            self.assertIsNone(outcome.project)

    def test_public_factory_inventory_equals_retrievable_catalog(self):
        schemas = [artifact_common_schema(item.artifact_type) for item in artifact_types()]
        schemas += [domain_schema(kind) for kind in DOMAIN_TYPES]
        schemas += [record_schema(kind) for kind in RECORD_TYPES]
        schemas += [configuration_json_schema(), change_plan_schema()]
        schemas += [request_schema(command) for command in builtin_registry().commands]
        schemas += [result_json_schema(name) for name in (
            'json-envelope-v2', 'help-v1', 'version-info-v1', 'command-description-v1',
            'capabilities-v1', 'schema-catalog-v1', 'schema-document-v1', 'sarif-specroad-v1',
            'environment-v1', 'work-evaluation-v1', 'project-init-v1', 'project-inspect-v1', 'artifact-show-v1', 'artifact-trace-v1', 'artifact-why-v1',
        )]
        expected = {schema['$id']: schema for schema in schemas}
        self.assertEqual(len(expected), len(schemas))
        rows = self.catalog.list()['schemas']
        self.assertEqual({row['schema_id'] for row in rows}, set(expected))
        self.assertEqual(len(rows), len(expected))
        for row in rows:
            with self.subTest(schema_id=row['schema_id']):
                actual = self.catalog.show(row['schema_id'])
                self.assertEqual(actual['schema'], expected[row['schema_id']])
                self.assertEqual(actual['metadata'], row)
                self.assertEqual(row['sha256'], hashlib.sha256(
                    canonical_json_bytes(expected[row['schema_id']])).hexdigest())

    def test_change_plan_versions_do_not_alias_model_or_latest_versions(self):
        for version in ('0.2.0', '1.0.0', '1.1.0', '1.2', '1.2.00', '01.2.0',
                        '1.2.1', '2.0.0', 'latest'):
            with self.subTest(version=version):
                self.assert_unknown('urn:specroad:schema:' + version + ':change-plan')
        resource = self.catalog.get(CHANGE_PLAN_ID)
        self.assertEqual(resource.version, '1.2.0')
        self.assertEqual(resource.schema['properties']['format_version']['const'], '1.2.0')
        self.assertEqual(resource.schema['properties']['metadata_policy_version']['const'],
                         'change-metadata-v1')

    def test_change_plan_ids_are_not_normalized_or_resolved(self):
        for schema_id in ('change-plan', 'change-plan-v1', CHANGE_PLAN_ID.upper(),
                          ' ' + CHANGE_PLAN_ID, CHANGE_PLAN_ID + '\n',
                          CHANGE_PLAN_ID + '#', CHANGE_PLAN_ID + ':create',
                          CHANGE_PLAN_ID.replace('change-plan', 'change_plan'),
                          'file:///tmp/' + CHANGE_PLAN_ID,
                          'https://invalid.test/' + CHANGE_PLAN_ID):
            with self.subTest(schema_id=schema_id):
                self.assert_unknown(schema_id)

    def test_typed_schema_id_does_not_invoke_caller_conversion(self):
        class ForeignString(str):
            def __hash__(self):
                raise AssertionError('Caller hash must not run')

            def __str__(self):
                raise AssertionError('Caller conversion must not run')

        for value in (ForeignString(CHANGE_PLAN_ID), [CHANGE_PLAN_ID],
                      {'schema_id': CHANGE_PLAN_ID}, CHANGE_PLAN_ID.encode()):
            with self.assertRaises(SchemaLookupError) as caught:
                self.catalog.get(value)
            self.assertEqual(caught.exception.reason, 'unknown_schema_id')

    def test_nested_return_values_cannot_poison_readers_or_validation(self):
        resource = self.catalog.get(CHANGE_PLAN_ID)
        other_reader = SchemaCatalog()
        expected = self.catalog.show(CHANGE_PLAN_ID)
        catalog_before = self.catalog.list()
        views = (
            resource.schema,
            self.catalog.show(CHANGE_PLAN_ID)['schema'],
            dispatch_result(['schema', 'show', CHANGE_PLAN_ID]).as_dict()['result']['schema'],
            execute_request({'command_id': 'schema.show',
                'arguments': {'schema_id': CHANGE_PLAN_ID}}).result.as_dict()['result']['schema'],
            change_plan_schema(),
        )
        for view in views:
            view['required'].clear()
            view['properties']['operations']['items']['anyOf'][0]['properties']['op']['const'] = 'execute'
            view['$defs'].clear()
        listing = self.catalog.list()
        listing['schemas'].clear()
        listing['categories']['exchange'] = 0
        resource.metadata()['sha256'] = '0' * 64
        self.assertEqual(self.catalog.list(), catalog_before)
        self.assertEqual(self.catalog.show(CHANGE_PLAN_ID), expected)
        self.assertEqual(other_reader.show(CHANGE_PLAN_ID), expected)
        self.assertEqual(SchemaCatalog().show(CHANGE_PLAN_ID), expected)
        self.assertEqual(resource.schema, expected['schema'])
        self.assertEqual(change_plan_schema(), expected['schema'])
        plan = prepare_change_plan(document())
        original = plan.data
        for validator in (resource.validate, lambda value: self.catalog.validate(CHANGE_PLAN_ID, value)):
            value = copy.deepcopy(original)
            validator(value)
            self.assertEqual(value, original)
            value['operations'][0]['op'] = 'execute'
            invalid = copy.deepcopy(value)
            with self.assertRaises(ModelError):
                validator(value)
            self.assertEqual(value, invalid)
        self.assertEqual(ChangePlan(plan.canonical_bytes).data, original)

    def test_all_typed_operations_retain_their_field_boundaries(self):
        operations = [operation(kind) for kind in OPERATION_TYPES]
        results = [result(domain_value()), result(record_value('evidence')),
                   result(record_value('relation_review')),
                   result(record_value('proposal', proposal_status='validated',
                       maturity='proposed', content_sha256='b' * 64))]
        plan = prepare_change_plan(document(operations, results))
        self.catalog.validate(CHANGE_PLAN_ID, plan.data)
        self.assertEqual(ChangePlan(plan.canonical_bytes).data, plan.data)
        branches = self.catalog.get(CHANGE_PLAN_ID).schema['properties']['operations']['items']['anyOf']
        self.assertEqual({branch['properties']['op']['const'] for branch in branches}, set(OPERATION_TYPES))
        self.assertEqual(len(branches), len(OPERATION_TYPES))
        for index, op in enumerate(operations):
            with self.subTest(kind=op['op']):
                self.assertIn(operation_schema(op['op']), branches)
                self.assertEqual(ChangeOperation(op).data, op)
                for invalid in ({**op, 'unexpected': True}, {k: v for k, v in op.items() if k != 'op'}):
                    value = plan.data
                    value['operations'][index] = invalid
                    before = copy.deepcopy(value)
                    with self.assertRaises(ModelError):
                        self.catalog.validate(CHANGE_PLAN_ID, value)
                    with self.assertRaises(ChangePlanError):
                        ChangeOperation(invalid)
                    self.assertEqual(value, before)

    def test_change_plan_resource_rejects_metadata_and_reference_mismatches(self):
        resource = self.catalog.get(CHANGE_PLAN_ID)
        for metadata in ({'version': '0.2.0'}, {'version': '1.2.1'},
                         {'category': 'artifact'}, {'validation_scope': 'full_approval'}):
            with self.assertRaises(SchemaLookupError) as caught:
                replace(resource, **metadata)
            self.assertEqual(caught.exception.reason, 'invalid_schema_resource')
        schema = resource.schema
        schema['properties']['actor'] = {'$ref': 'https://invalid.test/actor'}
        with self.assertRaises(SchemaLookupError) as caught:
            SchemaResource.capture(schema, '1.2.0', 'exchange')
        self.assertEqual(caught.exception.reason, 'invalid_schema_resource')

    def test_embedded_and_future_contracts_do_not_create_catalog_entries(self):
        for schema_id in ('urn:specroad:schema:1.2.0:change-operation:create',
                          'urn:specroad:schema:1.0.0:request:change.apply',
                          'urn:specroad:schema:1.0.0:transaction-receipt',
                          'urn:specroad:schema:1.0:srx', 'diagnostic-v1',
                          'language-policy-v1', 'reqif-mapping-v1'):
            with self.subTest(schema_id=schema_id):
                self.assert_unknown(schema_id)

    def test_empty_command_registry_preserves_change_plan_resource(self):
        from specroad.cli.registry import CommandRegistry

        catalog = SchemaCatalog(CommandRegistry(()))
        self.assertEqual(catalog.list()['categories']['request'], 0)
        self.assertEqual(catalog.show(CHANGE_PLAN_ID), self.catalog.show(CHANGE_PLAN_ID))
        catalog.validate(CHANGE_PLAN_ID, prepare_change_plan(document()).data)
