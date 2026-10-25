"""Self-description claims are checked against executable Core boundaries."""

import json
from pathlib import Path
import tempfile
import unittest

from specroad.cli.application import dispatch_result, execute_request
from specroad.cli.capabilities import capabilities
from specroad.cli.commands import builtin_registry
from specroad.cli.registry import CommandRegistry
from specroad.cli.results import CommandResult, sarif_document
from specroad.model.artifact_schemas import validate_common_fields
from specroad.model.errors import ModelError
from specroad.model.schema_catalog import SchemaCatalog, SchemaLookupError
from specroad.runtime.identity import version_info
from specroad.srx import EvaluationContext, SrxError, SrxProgram, evaluate, parse_program
from support.artifacts import common_artifact
from support.portable import build_distribution, files_under
from support.processes import run_python
from support.records import record_value
from support.srx import binary, field, literal, roots


class CapabilityScopeTests(unittest.TestCase):
    def test_advertised_srx_versions_execute_through_the_public_library(self):
        semantic = capabilities(builtin_registry())['semantic']
        self.assertIn('python.srx.evaluate', semantic['capability_ids'])
        self.assertEqual(semantic['supported_versions']['srx'], ['1.0'])
        for version in semantic['supported_versions']['srx']:
            document = {'language': 'srx', 'version': version,
                        'expression': binary('add', field('/count'), literal(3))}
            context = EvaluationContext(roots({'count': 2}), rule_id='capability-proof')
            for program in (SrxProgram(document, rule_id='capability-proof'),
                            parse_program(json.dumps(document).encode(), rule_id='capability-proof')):
                self.assertEqual(evaluate(program, context), 5)

    def test_unadvertised_srx_versions_remain_structured_failures(self):
        versions = capabilities(builtin_registry())['semantic']['supported_versions']['srx']
        for version in ('0.9', '1.0.0', '1.1', '2.0', 'latest', 1, True, None):
            with self.subTest(version=version):
                self.assertNotIn(version, versions)
                document = {'language': 'srx', 'version': version, 'expression': literal(True)}
                with self.assertRaises(SrxError) as caught:
                    SrxProgram(document, rule_id='bad-version')
                self.assertEqual(caught.exception.reason, 'unsupported_version')
                self.assertEqual(caught.exception.pointer, '/version')
                self.assertEqual(caught.exception.expected, versions[0])

    def test_library_support_does_not_register_product_commands(self):
        semantic = capabilities(builtin_registry())['semantic']
        actual_ids = {command['command_id'] for command in semantic['commands']}
        advertised_cli = {key[4:] for key in semantic['capability_ids'] if key.startswith('cli.')}
        self.assertEqual(advertised_cli, actual_ids)
        self.assertTrue({'query', 'diff', 'validate'} <= actual_ids)
        for command in ('srx.evaluate', 'proposal.create', 'proposal.apply'):
            with self.subTest(command=command):
                self.assertNotIn(command, actual_ids)
                self.assertEqual(dispatch_result(command.split('.')).exit_code, 2)
                self.assertEqual(dispatch_result(['command', 'describe', command]).exit_code, 2)
                self.assertEqual(execute_request({'command_id': command}).result.exit_code, 2)

    def test_library_claim_survives_an_empty_command_registry(self):
        semantic = capabilities(CommandRegistry(()))['semantic']
        self.assertEqual(semantic['commands'], [])
        self.assertEqual(semantic['command_groups'], [])
        self.assertEqual(semantic['output_formats'], [])
        self.assertEqual(semantic['capability_ids'], ['python.srx.evaluate', 'python.structured-request'])
        self.assertEqual(semantic['supported_versions']['srx'], ['1.0'])

    def test_proposal_record_schema_is_not_an_executable_proposal_workflow(self):
        schema_id = 'urn:specroad:schema:0.2.0:artifact-record:proposal'
        result = dispatch_result(['schema', 'show', schema_id]).as_dict()
        self.assertEqual(result['result']['metadata']['validation_scope'], 'record_fields_only')
        self.assertEqual(result['result']['schema']['$id'], schema_id)
        SchemaCatalog().validate(schema_id, record_value('proposal'))
        semantic = capabilities(builtin_registry())['semantic']
        self.assertEqual(semantic['supported_versions']['proposal'], [])
        self.assertNotIn('proposal', semantic['command_groups'])
        self.assertEqual(semantic['exchange_formats'], ['csv', 'ndjson', 'reqif', 'reqifz'])
        without_export = CommandRegistry(tuple(command for command in builtin_registry().commands
                                               if command.command_id != 'export'))
        self.assertEqual(capabilities(without_export)['semantic']['exchange_formats'], [])

    def test_library_versions_do_not_invent_schema_catalog_ids(self):
        catalog = SchemaCatalog()
        for schema_id in ('srx', 'srx-1.0', 'urn:specroad:schema:1.0:srx',
                          'urn:specroad:schema:1.0.0:request:srx.evaluate'):
            with self.subTest(schema_id=schema_id):
                with self.assertRaises(SchemaLookupError):
                    catalog.get(schema_id)
                self.assertEqual(dispatch_result(['schema', 'show', schema_id]).exit_code, 2)

    def test_schema_and_output_format_versions_do_not_enable_other_model_versions(self):
        identity = version_info()
        self.assertEqual(identity['supported_schema_versions'], ['0.2.0'])
        for version in ('0.1.0', '0.2.1', '1.0', '1.0.0', '1.2.0', '2.0.0'):
            with self.subTest(version=version):
                self.assertNotIn(version, identity['supported_schema_versions'])
                with self.assertRaises(ModelError) as caught:
                    validate_common_fields(common_artifact(schema_version=version))
                self.assertEqual(caught.exception.reason, 'unsupported_schema_version')
                self.assertEqual(caught.exception.highest_supported, '0.2.0')

    def test_library_sarif_serializer_is_distinct_from_active_cli_formats(self):
        document = sarif_document(CommandResult('fixture'))
        self.assertIn(document['version'], version_info()['supported_output_format_versions']['sarif'])
        semantic = capabilities(builtin_registry())['semantic']
        self.assertNotIn('sarif', semantic['output_formats'])
        for command in builtin_registry().commands:
            request = command.protocol.example.as_dict()
            request['options'] = {**request.get('options', {}), '--format': 'sarif'}
            with self.subTest(command=command.command_id):
                self.assertEqual(execute_request(request).result.exit_code, 2)

    def test_portable_srx_capability_executes_without_project_or_external_packages(self):
        body = '''
import sys
sys.path.insert(0, sys.argv[1])
from specroad.cli.application import dispatch_result
from specroad.srx import SrxProgram, EvaluationContext, evaluate
result = dispatch_result(['capabilities', '--format=json'])
assert result.exit_code == 0
semantic = result.as_dict()['result']['semantic']
assert semantic['supported_versions']['srx'] == ['1.0']
assert 'python.srx.evaluate' in semantic['capability_ids']
program = SrxProgram({'language': 'srx', 'version': semantic['supported_versions']['srx'][0],
    'expression': {'op': 'field', 'context': 'artifact', 'pointer': '/value'}}, rule_id='portable')
context = EvaluationContext({'artifact': {'value': [3, True, None]}, 'configuration': None,
    'project': {}, 'relations': []}, rule_id='portable')
assert evaluate(program, context) == [3, True, None]
assert 'cli.query' in semantic['capability_ids']
assert dispatch_result(['query']).exit_code == 3
'''
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            targets = build_distribution(root / 'build')
            project = root / 'project'; project.mkdir()
            (project / 'specroad.json').write_bytes(b'not valid JSON')
            before = files_under(root)
            for target in targets:
                with self.subTest(target=target.name):
                    result = run_python(['-I', '-S', '-B', '-c', body, str(target)], project)
                    self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(files_under(root), before)
