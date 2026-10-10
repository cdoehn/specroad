"""Machine schema fidelity, closed lookup and passive metadata regression tests."""
import copy
from dataclasses import FrozenInstanceError, replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from specroad.cli.application import dispatch_result, execute_request
from specroad.cli.commands import builtin_registry
from specroad.cli.contracts import CommandProtocol, PositionalSpec
from specroad.cli.registry import CommandRegistry, CommandUsageError
from specroad.cli.request_schema import request_schema
from specroad.cli.requests import CommandRequest
from specroad.cli.results import CommandResult, ResultContractError
from specroad.cli.result_schemas import result_json_schema, validate_result_document
from specroad.model._schema import validate_builtin
from specroad.model.artifact_schemas import artifact_common_schema, validate_common_fields
from specroad.model.canonical import canonical_json_bytes
from specroad.model.configuration import ProjectConfiguration
from specroad.model.configuration_schema import SCHEMA_ID, configuration_json_schema
from specroad.model.domain_schemas import domain_schema, validate_domain_fields
from specroad.model.errors import ModelError
from specroad.model.schema_catalog import SchemaCatalog, SchemaLookupError, SchemaResource
from support import run_core
from support.artifacts import common_artifact
from support.domain import domain_value
from support.model import configuration_value


class SchemaCatalogRobustnessTests(unittest.TestCase):
    def setUp(self):
        self.catalog = SchemaCatalog()

    def test_complete_schema_retains_every_annotation_value(self):
        schema = configuration_json_schema()
        actual = self.catalog.show(SCHEMA_ID)['schema']
        self.assertEqual(actual, schema)
        self.assertIn('description', actual)
        self.assertEqual(actual['properties']['srx_policy']['properties']['decimal_precision']['default'], 34)

    def test_request_examples_remain_executable_input_contracts(self):
        for command in builtin_registry().commands:
            schema = request_schema(command)
            actual = self.catalog.get(schema['$id']).schema
            self.assertEqual(actual['examples'], [command.protocol.example.as_dict()])
            for example in actual['examples']:
                self.catalog.validate(schema['$id'], example)
                with tempfile.TemporaryDirectory() as tmp:
                    self.assertEqual(execute_request(example, cwd=Path(tmp)).result.exit_code, 0)

    def test_requirement_enum_and_examples_have_no_obligation_default(self):
        field = self.catalog.get(domain_schema('requirement')['$id']).schema['properties']['normative_force']
        self.assertEqual(set(field['enum']), {'must','must_not','should','may'})
        self.assertEqual(set(field['examples']), set(field['enum']))
        self.assertNotIn('default', field)

    def test_missing_normative_force_still_fails_without_input_mutation(self):
        value = domain_value('requirement'); value.pop('normative_force'); before = copy.deepcopy(value)
        with self.assertRaises(ModelError): self.catalog.validate(domain_schema('requirement')['$id'], value)
        with self.assertRaises(ModelError): validate_domain_fields(value)
        self.assertEqual(value, before)

    def test_missing_configuration_defaults_are_not_inserted(self):
        value = configuration_value(); value['srx_policy'] = {}; value['transaction_policy'] = {}
        value['validation_policy'] = {}; before = copy.deepcopy(value)
        self.catalog.validate(SCHEMA_ID, value)
        self.assertEqual(ProjectConfiguration(value).data, before)
        self.assertEqual(value, before)

    def test_annotated_defaults_do_not_accept_wrong_values(self):
        value = configuration_value(); value['srx_policy'] = {'decimal_precision': 0}
        for checker in (lambda: self.catalog.validate(SCHEMA_ID, value), lambda: ProjectConfiguration(value)):
            with self.assertRaises(ModelError): checker()

    def test_request_default_is_a_valid_value_not_a_silent_request_rewrite(self):
        command = builtin_registry().resolve('schema.list'); schema = request_schema(command)
        field = schema['properties']['options']['properties']['--format']
        validate_builtin(field['default'], field)
        value = {'command_id': 'schema.list'}; self.catalog.validate(schema['$id'], value)
        self.assertEqual(value, {'command_id': 'schema.list'})

    def test_omitted_boolean_flag_is_not_an_accepted_explicit_false(self):
        command = builtin_registry().resolve('schema.list'); schema = request_schema(command)
        self.assertNotIn('default', schema['properties']['options']['properties']['--quiet'])
        value = {'command_id': 'schema.list', 'options': {'--quiet': False}}
        with self.assertRaises(ModelError): self.catalog.validate(schema['$id'], value)
        self.assertEqual(execute_request(value).result.exit_code, 2)

    def test_deprecated_legacy_branch_still_reads_existing_identity(self):
        schema = artifact_common_schema('goal')
        actual = self.catalog.get(schema['$id']).schema
        branch = next(x for x in actual['anyOf'] if x['properties']['id_scheme']['const']=='legacy-sequential-v1')
        self.assertIs(branch['properties']['id_scheme']['deprecated'], True)
        value = common_artifact('goal','GOAL'); value['id_scheme'] = 'legacy-sequential-v1'; value['id'] = 'SR-GOAL-0001'
        validate_common_fields(value); self.catalog.validate(schema['$id'], value)
        self.assertEqual(value['id'], 'SR-GOAL-0001')

    def test_deprecation_does_not_alias_legacy_and_random_identity(self):
        value = common_artifact('goal', 'GOAL'); value['id_scheme'] = 'legacy-sequential-v1'
        with self.assertRaises(ModelError): self.catalog.validate(artifact_common_schema('goal')['$id'], value)

    def test_annotation_containing_schema_like_code_stays_passive(self):
        inert = {'$ref': 'https://invalid.test/private', 'shell': 'never execute', 'unknownAssertion': False}
        schema = {'type': 'object', 'properties': {'optional': {'default': inert}}, 'examples': [inert]}
        value = {}; validate_builtin(value, schema); self.assertEqual(value, {})

    def test_read_write_annotations_do_not_erase_fields(self):
        schema = {'type': 'object', 'properties': {'a': {'readOnly': True}, 'b': {'writeOnly': True}}}
        value = {'a': 1, 'b': 2}; validate_builtin(value, schema); self.assertEqual(value, {'a': 1, 'b': 2})

    def test_malformed_annotations_do_not_turn_into_assertions_or_success(self):
        for annotation in ({'examples': {}}, {'deprecated': 'true'}, {'readOnly': 1}, {'description': []}):
            with self.assertRaises(ValueError): validate_builtin(None, annotation)

    def test_unknown_assertions_fail_even_in_unselected_branch(self):
        schema = {'anyOf': [True, {'inventedAssertion': True}]}
        with self.assertRaises(ValueError): validate_builtin('x', schema)

    def test_remote_reference_in_schema_is_never_resolved(self):
        schema = configuration_json_schema(); schema['properties']['x'] = {'$ref': 'https://invalid.test/schema'}
        with self.assertRaises(SchemaLookupError): SchemaResource.capture(schema,'0.2.0','configuration')

    def test_local_definitions_are_included_and_missing_definitions_fail(self):
        schema = artifact_common_schema('goal'); self.assertIn('actor', schema['$defs'])
        schema['$defs'].pop('actor')
        with self.assertRaises(SchemaLookupError): SchemaResource.capture(schema,'0.2.0','artifact')

    def test_cyclic_schema_reference_is_rejected_not_followed(self):
        schema = configuration_json_schema(); schema['$defs']={'cycle':{'$ref':'#/$defs/cycle'}}
        with self.assertRaises(SchemaLookupError): SchemaResource.capture(schema,'0.2.0','configuration')

    def test_physical_schema_cycle_is_rejected(self):
        schema = configuration_json_schema(); schema['properties']['cycle'] = schema
        with self.assertRaises(SchemaLookupError): SchemaResource.capture(schema,'0.2.0','configuration')

    def test_metadata_identity_scope_and_bytes_cannot_disagree(self):
        resource = self.catalog.get(SCHEMA_ID)
        for changes in ({'schema_id': 'other'}, {'validation_scope': 'full_approval'}, {'_encoded': b'{}'}):
            with self.assertRaises(SchemaLookupError): replace(resource, **changes)

    def test_invalid_versions_categories_and_stability_fail_closed(self):
        resource = self.catalog.get(SCHEMA_ID)
        for changes in ({'version':'latest'}, {'version':3}, {'category':'invented'}, {'stability':'approved'}):
            with self.assertRaises(SchemaLookupError): replace(resource, **changes)

    def test_noncanonical_or_duplicate_key_resource_bytes_are_rejected(self):
        resource = self.catalog.get(SCHEMA_ID)
        variants = [json.dumps(resource.schema, indent=2).encode(), b'{"$id":"a","$id":"b"}']
        for raw in variants:
            with self.assertRaises(SchemaLookupError): replace(resource, _encoded=raw)

    def test_resource_metadata_is_immutable_and_schema_access_is_detached(self):
        resource = self.catalog.get(SCHEMA_ID)
        with self.assertRaises(FrozenInstanceError): resource.version = '9.9.9'
        value = resource.schema; value.clear(); self.assertEqual(resource.schema['$id'], SCHEMA_ID)

    def test_hash_includes_annotations_but_not_dictionary_order(self):
        original = configuration_json_schema(); changed = copy.deepcopy(original)
        changed['description'] = 'Other passive annotation'
        one=SchemaResource.capture(original,'0.2.0','configuration'); two=SchemaResource.capture(changed,'0.2.0','configuration')
        self.assertNotEqual(one.metadata()['sha256'], two.metadata()['sha256'])
        reversed_schema = dict(reversed(list(original.items())))
        self.assertEqual(one.metadata(), SchemaResource.capture(reversed_schema,'0.2.0','configuration').metadata())

    def test_old_unknown_version_does_not_fall_forward_to_latest(self):
        for version in ('0.1.0','0.2.1','999.0.0','latest'):
            with self.assertRaises(SchemaLookupError): self.catalog.get(SCHEMA_ID.replace('0.2.0',version))

    def test_returned_metadata_and_default_objects_do_not_poison_next_lookup(self):
        first=self.catalog.show(SCHEMA_ID); expected=copy.deepcopy(first)
        first['metadata']['sha256']='0'*64
        first['schema']['properties']['srx_policy']['properties']['decimal_precision']['default']=999
        self.assertEqual(self.catalog.show(SCHEMA_ID), expected)

    def test_registry_order_does_not_change_catalog_or_schema_examples(self):
        registry = builtin_registry()
        reverse = SchemaCatalog(CommandRegistry(tuple(reversed(registry.commands))))
        self.assertEqual(reverse.list(), self.catalog.list())
        for item in self.catalog.list()['schemas']:
            self.assertEqual(reverse.show(item['schema_id']), self.catalog.show(item['schema_id']))

    def test_schema_description_does_not_invoke_described_command(self):
        calls=[]; base=builtin_registry().resolve('schema.show')
        command=replace(base, command_id='fixture.inspect', words=('fixture','inspect'),
            handler=lambda i: calls.append(i) or 0, positionals=(),
            protocol=CommandProtocol('schema-document-v1', {'command_id':'fixture.inspect'}))
        catalog=SchemaCatalog(CommandRegistry((command,)))
        schema_id='urn:specroad:schema:1.0.0:request:fixture.inspect'
        catalog.list(); catalog.get(schema_id); catalog.validate(schema_id, {'command_id':'fixture.inspect'})
        self.assertEqual(calls, [])

    def test_multi_positional_dependencies_match_actual_request_binding(self):
        base=builtin_registry().resolve('schema.show')
        command=replace(base, command_id='fixture.inspect', words=('fixture','inspect'),
            handler=lambda i:0, positionals=(PositionalSpec('first',False),PositionalSpec('second',False)),
            protocol=CommandProtocol('schema-document-v1', {'command_id':'fixture.inspect'}))
        registry=CommandRegistry((command,)); catalog=SchemaCatalog(registry); schema_id=request_schema(command)['$id']
        invalid={'command_id':'fixture.inspect','arguments':{'second':'b'}}
        with self.assertRaises(ModelError): catalog.validate(schema_id,invalid)
        with self.assertRaises(CommandUsageError): registry.bind_request(CommandRequest.from_mapping(invalid))
        valid={'command_id':'fixture.inspect','arguments':{'first':'a','second':'b'}}
        catalog.validate(schema_id,valid); registry.bind_request(CommandRequest.from_mapping(valid))

    def test_dependent_required_is_conditional_and_rejects_malformed_vocabulary(self):
        schema={'dependentRequired':{'b':['a']}}
        validate_builtin({}, schema); validate_builtin({'a':1,'b':2},schema)
        with self.assertRaises(ModelError): validate_builtin({'b':2},schema)
        for dependency in (True, {'b':'a'}, {'b':['a','a']}):
            with self.assertRaises(ValueError): validate_builtin({}, {'dependentRequired':dependency})

    def test_request_schema_rejects_unknown_option_before_handler(self):
        command=builtin_registry().resolve('schema.list'); value={'command_id':command.command_id,'options':{'--invented':True}}
        with self.assertRaises(ModelError): self.catalog.validate(request_schema(command)['$id'],value)
        self.assertEqual(execute_request(value).result.exit_code,2)

    def test_nested_work_schema_does_not_claim_a_resume_engine(self):
        data=dispatch_result(['command','describe','version']).as_dict()['result']
        data['work']['continuation_supported']=True
        with self.assertRaises(ModelError): self.catalog.validate('command-description-v1',data)
        data=dispatch_result(['capabilities']).as_dict()['result']; data['semantic']['work']['engine_available']=True
        with self.assertRaises(ModelError): self.catalog.validate('capabilities-v1',data)

    def test_nested_runtime_limit_types_remain_a_data_contract(self):
        data=dispatch_result(['capabilities']).as_dict()['result']
        data['runtime']['limits']['process_cpu_seconds']['soft']['value']='unlimited'
        with self.assertRaises(ModelError): self.catalog.validate('capabilities-v1',data)

    def test_missing_known_nested_contract_fields_are_rejected(self):
        data=dispatch_result(['command','describe','schema.show']).as_dict()['result']
        data['stdout'].pop('result_schema')
        with self.assertRaises(ModelError): self.catalog.validate('command-description-v1',data)

    def test_future_formats_and_unsupported_sarif_commands_stay_unavailable(self):
        data=dispatch_result(['capabilities']).as_dict()['result']['semantic']
        self.assertEqual(data['exchange_formats'],[])
        self.assertEqual(dispatch_result(['schema','list','--format=sarif']).exit_code,2)
        for name in ('reqif-v1','csv-mapping-v1','ndjson-v1'):
            with self.assertRaises(SchemaLookupError): self.catalog.get(name)

    def test_catalog_retrieval_does_not_grant_lifecycle_or_write_approval(self):
        schema=domain_schema('milestone'); value=domain_value('milestone'); value['relations']=[]
        self.catalog.validate(schema['$id'],value)  # Structural data remain well formed.
        with self.assertRaises(ModelError): validate_domain_fields(value)  # Local relation condition still required.
        self.assertEqual(self.catalog.get(schema['$id']).validation_scope,'domain_fields_only')

    def test_locale_and_timezone_do_not_change_schema_document_bytes(self):
        import os
        before=canonical_json_bytes(self.catalog.list())
        for settings in ({'LANG':'C','LC_ALL':'C','TZ':'UTC'}, {'LANG':'tr_TR.UTF-8','LC_ALL':'tr_TR.UTF-8','TZ':'Pacific/Auckland'}):
            with patch.dict(os.environ,settings):
                self.assertEqual(canonical_json_bytes(SchemaCatalog().list()), before)

    def test_schema_commands_reject_project_reads_network_and_subprocesses(self):
        body=r'''
import os
from pathlib import Path
from specroad.cli.application import dispatch_result
from specroad.model.schema_catalog import SchemaCatalog
# Ordinary imports may discover distribution modules. Warm this bounded trusted
# set before auditing calls; no project tree or user file is ever an input.
SchemaCatalog().list()
root=str(Path.cwd())
def guard(event,args):
    if event in {'subprocess.Popen','os.system','socket.connect','socket.getaddrinfo','os.scandir'}:
        raise AssertionError(event)
    if event=='open':
        path,mode,flags=args
        if isinstance(path,str) and os.path.abspath(path).startswith(root+os.sep):
            raise AssertionError('project access')
        if isinstance(flags,int) and flags & (os.O_CREAT|os.O_WRONLY|os.O_RDWR|os.O_TRUNC):
            raise AssertionError('write')
sys.addaudithook(guard)
assert dispatch_result(['schema','list']).exit_code==0
assert dispatch_result(['schema','show','json-envelope-v2']).exit_code==0
assert dispatch_result(['schema','show','urn:specroad:schema:1.2.0:change-plan']).exit_code==0
assert dispatch_result(['schema','show','urn:specroad:schema:1.1.0:change-plan']).exit_code==2
assert dispatch_result(['schema','show','https://invalid.test/schema']).exit_code==2
'''
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp)/'specroad.json').write_bytes(b'bad')
            result=run_core(body,tmp); self.assertEqual(result.returncode,0,result.stderr)

    def test_an_invalid_producer_result_cannot_be_published_as_success(self):
        with patch('specroad.runtime.identity.version_info',return_value={'invented':True}):
            outcome=dispatch_result(['version'])
        self.assertNotEqual(outcome.exit_code,0); self.assertIsNone(outcome.result)

    def test_every_full_document_itself_obeys_catalog_result_contract(self):
        for row in self.catalog.list()['schemas']:
            validate_result_document('schema-document-v1',self.catalog.show(row['schema_id']))
        validate_result_document('schema-catalog-v1',self.catalog.list())

    def test_reference_schema_objects_can_be_inspected_without_resolving_files(self):
        schema=self.catalog.get(artifact_common_schema('goal')['$id']).schema
        self.assertEqual(schema['properties']['created_by']['$ref'],'#/$defs/actor')
        self.assertEqual(schema['$defs']['actor']['additionalProperties'],False)
        value=common_artifact('goal','GOAL'); value['created_by']['actor_type']='invented'
        with self.assertRaises(ModelError): self.catalog.validate(schema['$id'],value)

    def test_valid_but_mismatched_version_and_category_are_rejected(self):
        resource=self.catalog.get(SCHEMA_ID)
        for changes in ({'version':'9.9.9'}, {'category':'request'}):
            with self.assertRaises(SchemaLookupError): replace(resource,**changes)

    def test_schema_id_and_declared_scope_must_agree(self):
        schema=configuration_json_schema(); schema['x-specroad-validation-scope']='full_approval'
        with self.assertRaises(SchemaLookupError): SchemaResource.capture(schema,'0.2.0','configuration')
