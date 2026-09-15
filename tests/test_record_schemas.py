"""Behavioral contracts for passive records, not document output or human claims."""

import copy
from dataclasses import FrozenInstanceError
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from specroad.model.errors import ModelError
from specroad.model.record_schemas import record_schema, validate_record_fields, require_generic_mutation
from specroad.model.paths import artifact_path
from specroad.security import SafetyViolation
from specroad.storage.record_artifact import RecordArtifact, read_record_artifact
from specroad.storage.project import ProjectSource
from support.artifacts import artifact_bytes
from support.files import temporary_project, tree_state
from support.model import configuration_file, put
from support.portable import build_distribution
from support.records import PREFIXES, record_value, block_value, ref

ROOT = Path(__file__).resolve().parents[1]


class RecordWorkTests(unittest.TestCase):
    def load(self, value, **kwargs):
        return RecordArtifact(artifact_bytes(value), **kwargs)

    def test_all_fourteen_record_types_are_readable(self):
        for kind in PREFIXES:
            with self.subTest(kind=kind):
                value = record_value(kind); loaded = self.load(value)
                self.assertEqual(loaded.data, value)
                self.assertEqual(loaded.validation_scope, 'record_fields_only')
                self.assertEqual(loaded.artifact_type, kind)
                self.assertEqual(loaded.id, value['id'])

    def test_minimum_required_fields_are_not_synthesized(self):
        required = {
            'source': ('source_kind', 'locator', 'captured_at'),
            'verification': ('method', 'subjects', 'preconditions', 'procedure', 'oracle', 'evidence_kinds', 'evidence_slots', 'dimensions', 'configuration_policy'),
            'test': ('test_identity', 'test_type', 'oracle'),
            'evidence': ('result', 'produced_at', 'producer', 'tool', 'environment', 'subjects', 'origin', 'run_context', 'evidence_state'),
            'baseline': ('baseline_kind', 'baseline_state', 'scope_descriptor', 'manifest', 'model_root_sha256'),
            'proposal': ('proposal_status', 'content_revision', 'content_sha256', 'control_history', 'base', 'change_plan', 'rationale'),
            'issue': ('description', 'issue_status', 'owner'),
            'document': ('purpose', 'audience', 'language', 'document_role', 'render_policy'),
            'section': ('title',), 'content_block': ('block_kind', 'payload'),
            'view': ('scope_descriptor', 'filter', 'columns', 'sort', 'grouping', 'relation_projections', 'formats'),
            'code_ref': ('path', 'reference_kind', 'file_sha256'),
            'relation_review': ('relation_id', 'relation_content_sha256', 'source_context_sha256', 'target_context_sha256', 'reviewer', 'decision', 'review_state'),
            'configuration': ('name', 'dimensions', 'selection'),
        }
        for kind, fields in required.items():
            for field in fields:
                value = record_value(kind); value.pop(field)
                with self.subTest(kind=kind, field=field), self.assertRaises(ModelError): self.load(value)

    def test_common_envelope_is_required_for_every_record(self):
        for kind in PREFIXES:
            for field in ('id', 'schema_version', 'revision', 'created_by', 'relations', 'extensions'):
                value = record_value(kind); value.pop(field)
                with self.subTest(kind=kind, field=field), self.assertRaises(ModelError): self.load(value)

    def test_per_type_fields_are_closed(self):
        for kind in PREFIXES:
            for field in ('verification_result', 'execution_status', 'arbitrary'):
                with self.subTest(kind=kind, field=field), self.assertRaises(ModelError):
                    self.load(record_value(kind, **{field: 'passed'}))

    def test_loaded_record_does_not_infer_success(self):
        for result in ('failed', 'passed', 'incomplete', 'skipped'):
            loaded = self.load(record_value('evidence', result=result))
            self.assertEqual(loaded.data['result'], result)
            self.assertNotIn('verification_result', loaded.data)
            self.assertEqual(loaded.validation_scope, 'record_fields_only')

    def test_all_verification_methods_are_data_only(self):
        for method in ('inspection', 'review', 'analysis', 'simulation', 'automated_test', 'manual_test', 'formal_proof', 'monitoring', 'audit', 'measurement'):
            with self.subTest(method=method):
                self.assertEqual(self.load(record_value('verification', method=method)).data['method'], method)
        with self.assertRaises(ModelError): self.load(record_value('verification', method='shell'))

    def test_reference_types_and_identity_grammars_are_checked(self):
        for target in ('Title of another requirement', 'SR-TASK-xyz', True, None):
            with self.subTest(target=str(target)), self.assertRaises(ModelError):
                self.load(record_value('verification', subjects=[target]))
        value = record_value('verification', subjects=['SR-REQ-0001', ref('TASK')])
        self.assertEqual(self.load(value).data, value)

    def test_evidence_subjects_require_revision_and_hash_bindings(self):
        for field in ('artifact_id', 'revision', 'artifact_sha256', 'verification_context_sha256'):
            value = record_value('evidence'); value['subjects'][0].pop(field)
            with self.subTest(field=field), self.assertRaises(ModelError): self.load(value)
        value = record_value('evidence'); value['subjects'][0]['revision'] = True
        with self.assertRaises(ModelError): self.load(value)

    def test_all_evidence_origins_are_preserved_without_trust(self):
        for origin in ('recorded_manual', 'imported_junit', 'imported_sarif', 'imported_generic', 'generated_internal'):
            value = record_value('evidence', origin=origin)
            self.assertEqual(self.load(value).data, value)
        with self.assertRaises(ModelError): self.load(record_value('evidence', origin='trusted'))

    def test_unbound_evidence_requires_a_reason(self):
        for changes in ({'run_context': None}, {'run_context': None, 'unbound_reason': ''}):
            with self.subTest(changes=str(changes)), self.assertRaises(ModelError):
                self.load(record_value('evidence', **changes))
        value = record_value('evidence', run_context=None, unbound_reason='Legacy producer supplied no run binding.')
        self.assertEqual(self.load(value).data, value)

    def test_run_context_is_closed_and_test_reference_typed(self):
        for changes in ({'test_id': ref('REQ')}, {'run_id': ''}, {'check_id': 'invalid space'}, {'subject_state_sha256': 'f' * 63}, {'extra': True}):
            value = record_value('evidence'); value['run_context'].update(changes)
            with self.subTest(changes=str(changes)), self.assertRaises(ModelError): self.load(value)

    def test_producer_including_monitoring_is_not_an_approval(self):
        for kind in ('human', 'tool', 'ci', 'monitoring', 'ai'):
            value = record_value('evidence', producer={'producer_type': kind, 'producer_id': 'synthetic'})
            self.assertEqual(self.load(value).data['producer'], value['producer'])
        with self.assertRaises(ModelError): self.load(record_value('evidence', producer={'producer_type': 'trusted', 'producer_id': 'x'}))

    def test_special_status_and_maturity_are_coupled(self):
        for kind, field, status in (('evidence', 'evidence_state', 'recorded'), ('baseline', 'baseline_state', 'sealed'), ('relation_review', 'review_state', 'recorded')):
            for maturity in ('draft', 'proposed', 'retired'):
                with self.subTest(kind=kind, maturity=maturity), self.assertRaises(ModelError):
                    self.load(record_value(kind, maturity=maturity))
            with self.subTest(kind=kind), self.assertRaises(ModelError): self.load(record_value(kind, **{field: 'draft'}))
            self.assertEqual(self.load(record_value(kind)).data[field], status)

    def test_every_recorded_proposal_status_remains_readable(self):
        for status, maturity in {'draft': 'draft', 'validated': 'proposed', 'checked': 'proposed', 'in_review': 'in_review', 'approved': 'approved', 'applied': 'approved', 'rejected': 'rejected', 'stale': 'retired'}.items():
            value = record_value('proposal', proposal_status=status, maturity=maturity)
            self.assertEqual(self.load(value).data, value)
            value['maturity'] = 'superseded'
            with self.subTest(status=status), self.assertRaises(ModelError): self.load(value)

    def test_schemas_never_enable_generic_special_mutations(self):
        for kind in ('evidence', 'baseline', 'relation_review', 'proposal'):
            self.load(record_value(kind))
            for operation in ('create', 'patch', 'lifecycle'):
                with self.subTest(kind=kind, operation=operation), self.assertRaises(ModelError) as caught:
                    require_generic_mutation(kind, operation)
                self.assertEqual(caught.exception.reason, 'specialized_operation_required')

    def test_normal_record_routing_is_not_a_write(self):
        with temporary_project() as root:
            before = tree_state(root)
            for kind in ('source', 'document', 'section', 'view', 'code_ref', 'configuration', 'verification', 'test', 'issue', 'content_block'):
                self.assertIsNone(require_generic_mutation(kind, 'create'))
            self.assertEqual(tree_state(root), before)
        with self.assertRaises(ModelError): require_generic_mutation('document', 'execute')

    def test_source_approval_needs_hash_or_excerpt(self):
        with self.assertRaises(ModelError): self.load(record_value('source', maturity='approved'))
        for extra in ({'content_sha256': 'a' * 64}, {'excerpt': 'Unmodified source excerpt.'}):
            value = record_value('source', maturity='approved', **extra)
            self.assertEqual(self.load(value).data, value)

    def test_test_identity_has_one_external_or_local_form(self):
        for identity in ({'external_id': 'suite/test'}, {'path': 'tests/example.py'}):
            self.assertEqual(self.load(record_value('test', test_identity=identity)).data['test_identity'], identity)
        for identity in ({}, {'external_id': 'x', 'path': 'test.py'}, {'path': '/tmp/test.py'}, {'external_id': ''}):
            with self.subTest(identity=str(identity)), self.assertRaises(ModelError): self.load(record_value('test', test_identity=identity))

    def test_seven_block_payloads_are_readable(self):
        for kind in ('prose', 'artifact_ref', 'query', 'table', 'admonition', 'page_break', 'include_document'):
            value = block_value(kind)
            with self.subTest(kind=kind): self.assertEqual(self.load(value).data, value)

    def test_block_payloads_do_not_mix_variants(self):
        for kind in ('prose', 'artifact_ref', 'query', 'table', 'admonition', 'page_break', 'include_document'):
            value = block_value(kind); value['payload']['unknown'] = 'data'
            with self.subTest(kind=kind), self.assertRaises(ModelError): self.load(value)
        value = block_value('page_break'); value['payload'] = {'markdown': 'incorrect'}
        with self.assertRaises(ModelError): self.load(value)

    def test_bad_document_roles_and_render_policy_types_fail(self):
        for field, bad in (('document_role', 'primary'), ('audience', []), ('purpose', ''), ('render_policy', 'code')):
            with self.subTest(field=field), self.assertRaises(ModelError): self.load(record_value('document', **{field: bad}))

    def test_section_parent_is_not_fabricated_from_its_own_file(self):
        value = record_value('section')
        self.assertEqual(self.load(value).data['relations'], [])
        self.assertNotIn('parent', self.load(value).data)
        self.assertEqual(self.load(value).validation_scope, 'record_fields_only')

    def test_hash_fields_reject_malformed_digests(self):
        for kind, field in (('code_ref', 'file_sha256'), ('source', 'content_sha256'), ('baseline', 'model_root_sha256'), ('proposal', 'content_sha256'), ('relation_review', 'relation_content_sha256')):
            for bad in ('A' * 64, '0' * 63, '0' * 64 + '\n', True, None):
                with self.subTest(kind=kind, field=field, bad=str(bad)), self.assertRaises(ModelError): self.load(record_value(kind, **{field: bad}))

    def test_code_paths_are_lexically_safe_without_loading_targets(self):
        for bad in ('../outside', '/etc/passwd', 'x/../../y', 'C:\\data', '.git/config', 'a//b', 'a/./b', 'NUL.txt'):
            with self.subTest(bad=bad), self.assertRaises(ModelError): self.load(record_value('code_ref', path=bad))
        self.assertEqual(self.load(record_value('code_ref', path='src/missing.py')).data['path'], 'src/missing.py')

    def test_evidence_attachments_are_bound_but_not_opened(self):
        attachment = {'path': 'attachments/not-present.bin', 'media_type': 'application/octet-stream', 'size': 12, 'sha256': 'f' * 64}
        value = record_value('evidence', attachments=[attachment]); self.assertEqual(self.load(value).data, value)
        for field, bad in (('path', '../outside'), ('size', -1), ('size', True), ('sha256', 'bad'), ('media_type', '')):
            changed = dict(attachment, **{field: bad})
            with self.subTest(field=field), self.assertRaises(ModelError): self.load(record_value('evidence', attachments=[changed]))

    def test_relation_reviews_require_a_human_declaration(self):
        for actor_type in ('ai', 'tool', 'ci', 'monitoring'):
            with self.subTest(actor_type=actor_type), self.assertRaises(ModelError):
                self.load(record_value('relation_review', reviewer={'actor_type': actor_type, 'actor_id': 'synthetic'}))
        for decision in ('confirmed', 'rejected'):
            self.assertEqual(self.load(record_value('relation_review', decision=decision)).data['decision'], decision)

    def test_configuration_fields_do_not_resolve_a_parent(self):
        value = record_value('configuration', dimensions=[], selection={'inherited': 'value'}, parent=ref('CFG', '1'))
        self.assertEqual(self.load(value).data, value)
        with self.assertRaises(ModelError): self.load(record_value('configuration', applicability={'op': 'literal', 'value': True}))
        with self.assertRaises(ModelError): self.load(record_value('configuration', parent=ref('REQ')))

    def test_identity_and_expected_type_remain_bound(self):
        for kind in PREFIXES:
            with self.subTest(kind=kind), self.assertRaises(ModelError): self.load(record_value(kind, id=ref('TASK')))
        with self.assertRaises(ModelError): self.load(record_value('document'), expected_type='source')
        with self.assertRaises(ModelError): record_schema('goal')
        with self.assertRaises(ModelError): record_schema('missing')

    def test_original_json_bytes_are_preserved(self):
        value = record_value('document', title='Äpfel 東京')
        raw = ('\n' + json.dumps(value, ensure_ascii=False, indent=3) + '\r\n').encode('utf-8')
        record = RecordArtifact(raw)
        self.assertEqual(record.source_bytes, raw); self.assertEqual(record.data, value)
        with self.assertRaises(FrozenInstanceError): record.id = 'different'

    def test_returned_data_and_schemas_are_detached(self):
        original = record_value('evidence'); record = self.load(original)
        changed = record.data; changed['subjects'][0]['revision'] = 88
        self.assertEqual(record.data, original)
        first = record_schema('evidence'); first['$defs']['producer']['properties']['producer_id'] = False
        self.assertEqual(self.load(original).data, original)
        self.assertNotEqual(first, record_schema('evidence'))

    def test_invalid_input_does_not_change_source_objects(self):
        for kind in PREFIXES:
            value = record_value(kind, arbitrary='invalid'); before = copy.deepcopy(value)
            with self.subTest(kind=kind), self.assertRaises(ModelError): validate_record_fields(value)
            self.assertEqual(value, before)

    def test_reader_does_not_run_code_network_or_referenced_files(self):
        value = record_value('document', render_policy={'command': 'untrusted', 'url': 'https://invalid.test/'})
        with mock.patch('subprocess.run', side_effect=AssertionError('unexpected execution')), mock.patch.object(socket, 'socket', side_effect=AssertionError('unexpected network')), mock.patch.object(Path, 'read_bytes', side_effect=AssertionError('unexpected file read')):
            self.assertEqual(self.load(value).data, value)
            self.load(record_value('code_ref', path='not-present.py'))
            self.load(record_value('baseline'))

    def test_bound_reader_keeps_project_bytes_unchanged(self):
        with temporary_project({}) as root:
            configuration_file(root); value = record_value('document')
            name = artifact_path('document', value['id'], 'SR'); raw = artifact_bytes(value)
            put(root, name, raw); source = ProjectSource(root); before = tree_state(root)
            loaded = read_record_artifact(source, name, expected_type='document')
            self.assertEqual(loaded.source_bytes, raw); self.assertEqual(loaded.path, name)
            self.assertEqual(tree_state(root), before)

    def test_bound_reader_rejects_mismatched_file_identity(self):
        with temporary_project({}) as root:
            configuration_file(root); value = record_value('document')
            name = artifact_path('document', ref('DOC', '1'), 'SR'); put(root, name, artifact_bytes(value))
            before = tree_state(root)
            with self.assertRaises(ModelError): read_record_artifact(ProjectSource(root), name)
            self.assertEqual(tree_state(root), before)

    def test_bound_reader_rejects_symlink_and_changed_configuration(self):
        with temporary_project({}) as root:
            configuration_file(root); value = record_value('document')
            name = artifact_path('document', value['id'], 'SR'); path = put(root, name, artifact_bytes(value))
            source = ProjectSource(root)
            (root/'copy').write_bytes(path.read_bytes()); path.unlink(); path.symlink_to(root/'copy')
            with self.assertRaises(SafetyViolation): read_record_artifact(source, name)
            path.unlink(); path.write_bytes(artifact_bytes(value)); configuration_file(root, project_name='changed')
            with self.assertRaises(ModelError): read_record_artifact(source, name)

    def test_schemas_are_available_in_relocated_core_distributions(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); build_distribution(root/'build'); (root/'build').rename(root/'moved')
            program = "import sys,json;sys.path.insert(0,sys.argv[1]);from specroad.storage.record_artifact import RecordArtifact;v=json.load(sys.stdin);[(lambda r,x:(r.data==x or sys.exit(3)))(RecordArtifact(json.dumps(x).encode()),x) for x in v]"
            raw = json.dumps([record_value(kind) for kind in PREFIXES]).encode()
            for distribution in (root/'moved/module', root/'moved/specroad.pyz'):
                result = subprocess.run([sys.executable, '-I', '-S', '-B', '-c', program, str(distribution)], input=raw, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                self.assertEqual(result.returncode, 0, result.stderr.decode())
