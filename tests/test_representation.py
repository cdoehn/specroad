"""Values, immutability and source boundaries; no pretty/layout/header oracles."""

from dataclasses import FrozenInstanceError
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from specroad.model.canonical import canonical_object_sha256
from specroad.model.errors import ModelError
from specroad.model.paths import artifact_path
from specroad.model.representation import NormalizationCandidate, normal_json_bytes
from specroad.storage.generated import GeneratedView
from specroad.storage.json_reader import JsonResource, configuration_schema
from specroad.storage.json_syntax import parse_json_object
from specroad.storage.project import ProjectSource
from specroad.storage.representation import prepare_normalization
from support.artifacts import artifact_bytes
from support.domain import domain_value
from support.files import tree_state
from support.model import configuration_file, configuration_value, put
from support.records import record_value


class RepresentationWorkTests(unittest.TestCase):
    def test_values_and_audit_fields_survive_normalization(self):
        value = domain_value('requirement', revision=17, statement='a\r\nb\n e\u0301 😀  ')
        raw = artifact_bytes(value)
        self.assertEqual(parse_json_object(normal_json_bytes(raw)), value)

    def test_full_value_hash_is_unchanged(self):
        raw = b'{ "revision": 3, "values": [true,1,1.0,-0.0,null] }\r\n'
        self.assertEqual(canonical_object_sha256(raw), canonical_object_sha256(normal_json_bytes(raw)))

    def test_byte_bindings_are_independent_of_value_hash(self):
        raw = b' { "b": 2, "a": 1 } '
        candidate = NormalizationCandidate('profiles/p.json', raw)
        self.assertEqual(candidate.expected_byte_sha256, sha256(raw).hexdigest())
        self.assertEqual(candidate.result_byte_sha256, sha256(candidate.normalized_bytes).hexdigest())
        self.assertEqual(candidate.value_sha256, canonical_object_sha256(raw))

    def test_candidate_keeps_exact_source_bytes(self):
        raw = b' {"x":"\\u0061","n":1.00} \r\n'
        self.assertEqual(NormalizationCandidate('rules/r.json', raw).source_bytes, raw)

    def test_repeated_normalization_has_no_further_change(self):
        first = NormalizationCandidate('profiles/p.json', b'{"x":1}')
        second = NormalizationCandidate(first.path, first.normalized_bytes)
        self.assertTrue(first.change_required)
        self.assertFalse(second.change_required)
        self.assertEqual(first.value_sha256, second.value_sha256)

    def test_returned_values_are_independent(self):
        candidate = NormalizationCandidate('rules/r.json', b'{"x":[1]}')
        candidate.source_data['x'].clear(); candidate.normalized_data['x'].append(2)
        self.assertEqual(candidate.source_data, {'x': [1]})
        self.assertEqual(candidate.normalized_data, {'x': [1]})

    def test_candidate_is_immutable(self):
        candidate = NormalizationCandidate('rules/r.json', b'{}')
        with self.assertRaises(FrozenInstanceError): candidate.path = 'other.json'

    def test_invalid_json_is_not_repaired(self):
        for raw in (b'{"x":1,"x":2}', b'{} {}', b'[1]', b'{"x":NaN}', b'\xef\xbb\xbf{}'):
            with self.subTest(raw=raw), self.assertRaises(ModelError): normal_json_bytes(raw)

    def test_lossy_numbers_are_not_repaired(self):
        for token in ('1.0000000000000001', '9007199254740993', '1e-400'):
            with self.subTest(token=token), self.assertRaises(ModelError):
                normal_json_bytes(('{"n":' + token + '}').encode())

    def test_config_normalization_is_read_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); value = configuration_file(root); source = ProjectSource(root)
            before = tree_state(root); candidate = prepare_normalization(source, 'specroad.json')
            self.assertEqual(candidate.normalized_data, value)
            self.assertEqual(tree_state(root), before)

    def test_current_artifact_can_be_proposed_without_changing_revision(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); configuration_file(root)
            value = domain_value('requirement', revision=9)
            path = artifact_path('requirement', value['id'], 'SR'); put(root, path, artifact_bytes(value))
            before = tree_state(root); candidate = prepare_normalization(ProjectSource(root), path)
            self.assertEqual(candidate.normalized_data, value)
            self.assertEqual(tree_state(root), before)

    def test_profile_rule_mapping_syntax_is_preserved_not_fully_approved(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); configuration_file(root)
            raw = b'{"schema_version":"0.2.0","opaque":{"x":[false,0]}}'
            for path in ('profiles/p.json', 'rules/r.json', 'mappings/m.json'):
                put(root, path, raw)
                self.assertEqual(prepare_normalization(ProjectSource(root), path).normalized_data,
                                 parse_json_object(raw))

    def test_excluded_paths_are_rejected_before_payload_read(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); configuration_file(root); source = ProjectSource(root)
            for path in ('generated/x.json', 'attachments/a.json', 'archive/objects/aa/'+'a'*64,
                         '.specroad/cache/x.json', 'unmanaged/x.json'):
                with self.subTest(path=path), mock.patch.object(source, 'read_normative') as read:
                    with self.assertRaises(ModelError): prepare_normalization(source, path)
                    read.assert_not_called()

    def test_recorded_evidence_reviews_and_sealed_baselines_are_protected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); configuration_file(root)
            for kind in ('evidence', 'relation_review', 'baseline'):
                value = record_value(kind); path = artifact_path(kind, value['id'], 'SR')
                put(root, path, artifact_bytes(value)); before = tree_state(root)
                with self.subTest(kind=kind), self.assertRaises(ModelError) as caught:
                    prepare_normalization(ProjectSource(root), path)
                self.assertEqual(caught.exception.reason, 'protected_original_resource')
                self.assertEqual(tree_state(root), before)

    def test_terminal_proposals_are_protected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); configuration_file(root)
            for status, maturity in [('applied','approved'),('rejected','rejected'),('stale','retired')]:
                value = record_value('proposal', proposal_status=status, maturity=maturity)
                path = artifact_path('proposal', value['id'], 'SR'); put(root, path, artifact_bytes(value))
                with self.subTest(status=status), self.assertRaises(ModelError) as caught:
                    prepare_normalization(ProjectSource(root), path)
                self.assertEqual(caught.exception.reason, 'protected_original_resource')

    def test_draft_proposal_remains_formatable(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); configuration_file(root); value = record_value('proposal')
            path = artifact_path('proposal', value['id'], 'SR'); put(root, path, artifact_bytes(value))
            self.assertEqual(prepare_normalization(ProjectSource(root), path).normalized_data, value)

    def test_generated_views_have_no_normative_role_and_keep_payload(self):
        for format in ('json', 'markdown', 'html', 'text'):
            raw = b'{"revision":5}' if format == 'json' else 'text\r\n e\u0301'.encode()
            view = GeneratedView(raw, format=format)
            self.assertTrue(view.generated); self.assertFalse(view.normative)
            self.assertEqual(view.payload_bytes, raw)

    def test_generated_json_keeps_selected_data_in_separate_envelope(self):
        value = configuration_value(); view = GeneratedView(artifact_bytes(value), format='json')
        result = parse_json_object(view.content)
        self.assertEqual(result['data'], value)
        self.assertIs(result['normative'], False)
        self.assertIs(result['generated'], True)

    def test_generated_path_cannot_be_read_as_normative_even_with_valid_config_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); value = configuration_file(root)
            put(root, 'generated/edited.json', artifact_bytes(value)); source = ProjectSource(root)
            before = tree_state(root)
            with self.assertRaises(ModelError): source.read_normative('generated/edited.json')
            with self.assertRaises(ModelError): prepare_normalization(source, 'generated/edited.json')
            self.assertEqual(tree_state(root), before)

    def test_generated_envelope_is_not_a_canonical_configuration(self):
        view = GeneratedView(artifact_bytes(configuration_value()), format='json')
        with self.assertRaises(ModelError): JsonResource(view.content, configuration_schema())

    def test_generated_object_cannot_be_passed_as_normative_bytes(self):
        view = GeneratedView(b'{}', format='json')
        with self.assertRaises(ModelError): normal_json_bytes(view)
        with self.assertRaises(ModelError): JsonResource(view, configuration_schema())

    def test_unsupported_generated_format_and_invalid_utf8_fail(self):
        with self.assertRaises(ModelError): GeneratedView(b'text', format='pdf')
        with self.assertRaises(ModelError): GeneratedView(b'\xff', format='markdown')
        with self.assertRaises(ModelError): GeneratedView(b'{"a":1,"a":2}', format='json')
