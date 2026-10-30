"""Schema contracts and real command effects, not help/docs or presentation."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from specroad.cli.application import dispatch_result, execute_request
from specroad.cli.commands import builtin_registry
from specroad.cli.results import CommandResult, FailureKind, serialize_result, sarif_document
from specroad.changes import ChangePlan, ChangePlanError, prepare_change_plan
from specroad.changes.schema import change_plan_schema
from specroad.model.schema_catalog import SchemaCatalog, SchemaLookupError
from specroad.model.artifact_types import artifact_types
from specroad.model.artifact_schemas import artifact_common_schema, validate_common_fields
from specroad.model.domain_schemas import DOMAIN_TYPES, domain_schema, validate_domain_fields
from specroad.model.record_schemas import RECORD_TYPES, record_schema, validate_record_fields
from specroad.model.configuration import ProjectConfiguration
from specroad.model.configuration_schema import SCHEMA_ID, configuration_json_schema
from specroad.model.errors import ModelError
from specroad.model.canonical import canonical_json_bytes
from support.artifacts import common_artifact
from support.domain import domain_value
from support.records import record_value
from support.model import configuration_value
from support.change_plans import document as change_plan_document
from support.portable import build_distribution, files_under
from support.processes import run_core, run_python


class SchemaCatalogWorkTests(unittest.TestCase):
    def setUp(self):
        self.catalog = SchemaCatalog()

    def test_list_has_unique_sorted_versioned_ids(self):
        rows = self.catalog.list()['schemas']; ids = [r['schema_id'] for r in rows]
        self.assertEqual(ids, sorted(set(ids)))
        for row in rows:
            self.assertRegex(row['version'], r'^\d+\.\d+\.\d+$')
            self.assertEqual(row['stability'], 'experimental')
            self.assertEqual(len(row['sha256']), 64)

    def test_all_common_artifact_resources_are_present(self):
        for item in artifact_types():
            self.assertEqual(self.catalog.get(item.schema_id).schema, artifact_common_schema(item.artifact_type))

    def test_all_domain_resources_are_present(self):
        for kind in DOMAIN_TYPES:
            schema = domain_schema(kind)
            self.assertEqual(self.catalog.get(schema['$id']).schema, schema)

    def test_all_record_resources_are_present(self):
        for kind in RECORD_TYPES:
            schema = record_schema(kind)
            self.assertEqual(self.catalog.get(schema['$id']).schema, schema)

    def test_configuration_resource_matches_used_field_contract(self):
        self.assertEqual(self.catalog.get(SCHEMA_ID).schema, configuration_json_schema())
        value = configuration_value(); self.catalog.validate(SCHEMA_ID, value)
        self.assertEqual(ProjectConfiguration(value).data, value)

    def test_missing_mapping_resources_are_not_advertised(self):
        self.assertEqual(self.catalog.list()['categories']['mapping'], 0)
        with self.assertRaises(SchemaLookupError): self.catalog.get('reqif-mapping-v1')

    def test_category_counts_cover_every_entry(self):
        data = self.catalog.list()
        self.assertEqual(sum(data['categories'].values()), len(data['schemas']))
        self.assertEqual(data['categories']['artifact'], 56)
        self.assertEqual(data['categories']['configuration'], 1)
        self.assertEqual(data['categories']['exchange'], 2)

    def test_change_plan_resource_is_the_existing_structural_contract(self):
        schema_id = 'urn:specroad:schema:1.2.0:change-plan'
        rows = [row for row in self.catalog.list()['schemas'] if row['schema_id'] == schema_id]
        self.assertEqual(len(rows), 1)
        resource = self.catalog.get(schema_id)
        self.assertEqual(resource.metadata(), rows[0])
        self.assertEqual(resource.version, '1.2.0')
        self.assertEqual(resource.category, 'exchange')
        self.assertEqual(resource.validation_scope, 'change_plan_fields_only')
        self.assertEqual(resource.schema, change_plan_schema())

    def test_change_plan_cli_and_structured_lookup_return_the_same_schema(self):
        schema_id = 'urn:specroad:schema:1.2.0:change-plan'
        listed = dispatch_result(['schema', 'list', '--format=json'])
        self.assertEqual(listed.exit_code, 0)
        self.assertIn(schema_id, [row['schema_id'] for row in listed.as_dict()['result']['schemas']])
        outcomes = (dispatch_result(['schema', 'show', schema_id, '--format=json']),
                    execute_request({'command_id': 'schema.show',
                                     'arguments': {'schema_id': schema_id}}).result)
        for outcome in outcomes:
            self.assertEqual(outcome.exit_code, 0)
            self.assertIsNone(outcome.project)
            self.assertEqual(outcome.as_dict()['result'], self.catalog.show(schema_id))

    def test_change_plan_catalog_validates_real_positive_and_negative_fields(self):
        schema_id = 'urn:specroad:schema:1.2.0:change-plan'
        plan = prepare_change_plan(change_plan_document())
        self.catalog.validate(schema_id, plan.data)
        self.assertEqual(ChangePlan(plan.canonical_bytes).data, plan.data)
        for name, value in (('format_version', '1.0.0'), ('metadata_policy_version', 'invented'),
                            ('operations', [{'op': 'execute', 'command': 'never'}]),
                            ('actor', {'actor_type': 'invented', 'actor_id': 'x'})):
            with self.subTest(field=name):
                invalid = plan.data; invalid[name] = value
                with self.assertRaises(ModelError):
                    self.catalog.validate(schema_id, invalid)
                with self.assertRaises(ChangePlanError):
                    ChangePlan(canonical_json_bytes(invalid))

    def test_change_plan_field_schema_does_not_replace_integrity_checks(self):
        value = prepare_change_plan(change_plan_document()).data
        value['change_plan_sha256'] = '0' * 64
        self.catalog.validate('urn:specroad:schema:1.2.0:change-plan', value)
        with self.assertRaises(ChangePlanError) as caught:
            ChangePlan(canonical_json_bytes(value))
        self.assertEqual(caught.exception.reason, 'change_plan_hash_mismatch')
        self.assertEqual(dispatch_result(['change', 'apply']).exit_code, 2)

    def test_hash_binds_the_full_jcs_schema_not_a_local_path(self):
        for item in self.catalog.list()['schemas']:
            schema = self.catalog.get(item['schema_id']).schema
            self.assertEqual(item['sha256'], hashlib.sha256(canonical_json_bytes(schema)).hexdigest())

    def test_list_and_show_metadata_agree_for_every_resource(self):
        for row in self.catalog.list()['schemas']:
            document = self.catalog.show(row['schema_id'])
            self.assertEqual(document['metadata'], row)
            self.assertEqual(document['schema']['$id'], row['schema_id'])

    def test_common_field_acceptance_matches_the_existing_validator(self):
        for item in artifact_types():
            value = common_artifact(item.artifact_type, item.prefix)
            validate_common_fields(value); self.catalog.validate(item.schema_id, value)
            value['revision'] = 0
            with self.assertRaises(ModelError): validate_common_fields(value)
            with self.assertRaises(ModelError): self.catalog.validate(item.schema_id, value)

    def test_domain_field_acceptance_matches_the_existing_validator(self):
        for kind in DOMAIN_TYPES:
            value = domain_value(kind); schema_id = domain_schema(kind)['$id']
            validate_domain_fields(value); self.catalog.validate(schema_id, value)
            value['revision'] = False
            with self.assertRaises(ModelError): validate_domain_fields(value)
            with self.assertRaises(ModelError): self.catalog.validate(schema_id, value)

    def test_record_field_acceptance_matches_the_existing_validator(self):
        for kind in RECORD_TYPES:
            value = record_value(kind); schema_id = record_schema(kind)['$id']
            validate_record_fields(value); self.catalog.validate(schema_id, value)
            value['unexpected_top_level'] = 42
            with self.assertRaises(ModelError): validate_record_fields(value)
            with self.assertRaises(ModelError): self.catalog.validate(schema_id, value)

    def test_request_schema_is_the_command_description_schema(self):
        for command in builtin_registry().commands:
            outcome = dispatch_result(['command', 'describe', command.command_id])
            self.assertEqual(outcome.exit_code, 0, (command.command_id, outcome.as_dict()))
            description = outcome.as_dict()['result']
            schema = description['request_schema']
            self.assertEqual(self.catalog.get(schema['$id']).schema, schema)
            self.catalog.validate(schema['$id'], command.protocol.example.as_dict())

    def test_every_builtin_has_a_real_retrievable_result_contract(self):
        for command in builtin_registry().commands:
            with tempfile.TemporaryDirectory() as tmp:
                from support.inspection import command_example_inputs
                with command_example_inputs(Path(tmp), command) as request:
                    self.catalog.validate("urn:specroad:schema:1.0.0:request:" + command.command_id, request)
                    outcome = execute_request(request, cwd=Path(tmp)).result
            self.assertEqual(outcome.exit_code, 0, (command.command_id, outcome.as_dict()))
            self.catalog.validate(command.protocol.result_schema, outcome.as_dict()['result'])

    def test_envelope_schema_accepts_success_and_failure(self):
        for outcome in (CommandResult('fixture'), CommandResult.failed('fixture', FailureKind.MODEL)):
            self.catalog.validate('json-envelope-v2', json.loads(serialize_result(outcome)))

    def test_envelope_schema_rejects_wrong_status(self):
        value = CommandResult('fixture').as_dict(); value['status'] = 'invented'
        with self.assertRaises(ModelError): self.catalog.validate('json-envelope-v2', value)

    def test_local_sarif_projection_is_not_a_full_external_standard_schema(self):
        self.catalog.validate('sarif-specroad-v1', sarif_document(CommandResult('fixture')))
        resource = self.catalog.get('sarif-specroad-v1')
        self.assertEqual(resource.validation_scope, 'sarif_projection_only')
        with self.assertRaises(SchemaLookupError):
            self.catalog.get('https://docs.oasis-open.org/sarif/sarif/v2.1.0/cos02/schemas/sarif-schema-2.1.0.json')

    def test_unknown_ids_and_foreign_types_are_rejected_without_coercion(self):
        for value in (None, True, 1, [], {}, '', 'requirement', 'json-envelope-v3'):
            with self.assertRaises(SchemaLookupError): self.catalog.get(value)

    def test_lookup_is_exact_and_does_not_fetch_paths_or_urls(self):
        for value in ('../../secret', '/etc/passwd', 'file:///tmp/data', 'https://example.invalid/schema',
                      ' json-envelope-v2', 'JSON-ENVELOPE-V2', 'json-envelope-v2\0'):
            result = dispatch_result(['schema', 'show', value])
            self.assertEqual(result.exit_code, 2)
            self.assertIsNone(result.result)

    def test_cli_list_returns_catalog_in_standard_envelope(self):
        result = dispatch_result(['schema', 'list', '--format=json'])
        data = json.loads(serialize_result(result))
        self.assertEqual(data['format_version'], '2.0.0')
        self.assertEqual(data['result'], self.catalog.list()); self.assertIsNone(data['project'])

    def test_cli_show_returns_schema_not_a_stub(self):
        result = dispatch_result(['schema', 'show', 'json-envelope-v2', '--format=json'])
        data = json.loads(serialize_result(result))['result']
        self.assertEqual(data, self.catalog.show('json-envelope-v2'))
        self.assertIn('diagnostics', data['schema']['properties'])

    def test_structured_and_cli_requests_share_results(self):
        request = {'command_id': 'schema.show', 'arguments': {'schema_id': SCHEMA_ID}}
        a = execute_request(request).result.as_dict()['result']
        b = dispatch_result(['schema', 'show', SCHEMA_ID]).as_dict()['result']
        self.assertEqual(a, b)

    def test_invalid_cli_forms_never_succeed(self):
        for argv in (['schema'], ['schema', 'show'], ['schema', 'list', 'extra'],
                     ['schema', 'show', SCHEMA_ID, 'extra'], ['schema', 'list', '--project', '/tmp']):
            self.assertEqual(dispatch_result(argv).exit_code, 2)

    def test_modified_return_values_do_not_change_future_reads(self):
        first = self.catalog.show(SCHEMA_ID); original = copy.deepcopy(first)
        first['schema']['required'].clear(); first['metadata']['version'] = '999'
        self.assertEqual(self.catalog.show(SCHEMA_ID), original)

    def test_caller_inputs_are_not_changed_by_validation(self):
        value = domain_value('requirement'); before = copy.deepcopy(value)
        self.catalog.validate(domain_schema('requirement')['$id'], value)
        self.assertEqual(value, before)

    def test_presentation_flags_do_not_change_schema_payloads(self):
        plain = dispatch_result(['schema', 'list']).as_dict()['result']
        fancy = dispatch_result(['schema', 'list', '--quiet', '--no-color', '--format=json']).as_dict()['result']
        self.assertEqual(plain, fancy)

    def test_bad_project_and_user_files_are_not_read_or_rewritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root/'specroad.json').write_bytes(b'broken')
            (root/'private').write_bytes(b'do not open')
            before = files_under(root)
            for argv in (['schema', 'list'], ['schema', 'show', SCHEMA_ID]):
                self.assertEqual(dispatch_result(argv, cwd=root).exit_code, 0)
            self.assertEqual(files_under(root), before)

    def test_bootstrap_does_not_need_a_current_working_directory(self):
        with patch('pathlib.Path.cwd', side_effect=FileNotFoundError):
            self.assertEqual(dispatch_result(['schema', 'list']).exit_code, 0)
            self.assertEqual(dispatch_result(['schema', 'show', SCHEMA_ID]).exit_code, 0)

    def test_common_layer_is_explicitly_not_a_full_artifact_validator(self):
        resource = self.catalog.get(artifact_common_schema('term')['$id'])
        self.assertEqual(resource.validation_scope, 'common_fields_only')
        self.assertEqual(resource.schema['x-specroad-validation-scope'], resource.validation_scope)

    def test_schema_resources_work_after_portable_distribution_move(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); build_distribution(root/'build'); (root/'build').rename(root/'moved')
            project = root/'project'; project.mkdir(); (project/'specroad.json').write_bytes(b'bad')
            before = files_under(root); snapshots = []
            for target in (root/'moved/module', root/'moved/specroad.pyz'):
                run = run_python(['-I','-S','-B',str(target),'schema','list','--format=json'],project,capture=True)
                self.assertEqual(run.returncode, 0, run.stderr)
                snapshots.append(json.loads(run.stdout)['result'])
                for schema_id in (SCHEMA_ID, 'urn:specroad:schema:1.2.0:change-plan'):
                    show = run_python(['-I','-S','-B',str(target),'schema','show',schema_id,'--format=json'],project,capture=True)
                    self.assertEqual(show.returncode, 0, show.stderr)
                    self.assertEqual(json.loads(show.stdout)['result'], self.catalog.show(schema_id))
            self.assertEqual(snapshots[0], snapshots[1]); self.assertEqual(files_under(root), before)
