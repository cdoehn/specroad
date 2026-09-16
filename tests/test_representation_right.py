"""Read-only snapshot failures, original text and portable behavior; no layout."""

from dataclasses import FrozenInstanceError
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

from specroad.model.canonical import canonical_object_sha256
from specroad.model.errors import ModelError
from specroad.model.paths import artifact_path
from specroad.model.representation import NormalizationCandidate, normal_json_bytes
from specroad.security import SafetyViolation
from specroad.storage.generated import GeneratedView
from specroad.storage.project import ProjectSource
from specroad.storage.representation import (prepare_normalization, prepare_normalizations,
                                             check_normalization_current)
from support.artifacts import artifact_bytes
from support.domain import domain_value
from support.files import tree_state
from support.model import configuration_file, put
from support.portable import build_distribution
from support.processes import run_core
from support.records import record_value

RAW = b'{"schema_version":"0.2.0","x":1}'
PATH = 'profiles/example.json'


class RepresentationRightTests(unittest.TestCase):
    def test_original_text_utf8_bytes_are_not_normalized(self):
        for text in ('é', 'e\u0301', 'é e\u0301', ' a\r\nb\rc\n ', '\t\x00\u2028\u2029', 'العربية 😀 汉字'):
            raw = json.dumps({'text': text}, ensure_ascii=True).encode()
            candidate = NormalizationCandidate(PATH, raw)
            with self.subTest(text=text):
                self.assertEqual(candidate.normalized_data['text'].encode('utf-8'), text.encode('utf-8'))
                self.assertEqual(candidate.source_bytes, raw)

    def test_two_original_unicode_forms_remain_semantically_distinct(self):
        first = NormalizationCandidate(PATH, '{"x":"é"}'.encode())
        second = NormalizationCandidate(PATH, '{"x":"e\u0301"}'.encode())
        self.assertNotEqual(first.value_sha256, second.value_sha256)

    def test_negative_zero_booleans_and_array_order_are_not_rewritten_as_fields(self):
        import math
        candidate = NormalizationCandidate(PATH, b'{"a":[true,1,false,0,null,-0.0,3,2]}')
        value = candidate.normalized_data['a']
        self.assertIs(value[0], True); self.assertIs(value[2], False)
        self.assertIsNone(value[4]); self.assertEqual(math.copysign(1, value[5]), -1)
        self.assertEqual(value[-2:], [3,2])

    def test_source_precondition_rejects_even_semantically_identical_new_bytes(self):
        candidate = NormalizationCandidate(PATH, RAW)
        candidate.require_current(RAW)
        with self.assertRaises(ModelError) as caught: candidate.require_current(b' '+RAW)
        self.assertEqual(caught.exception.reason, 'representation_source_changed')
        self.assertEqual(caught.exception.path, PATH)

    def test_source_precondition_requires_actual_bytes(self):
        candidate = NormalizationCandidate(PATH, RAW)
        for data in (RAW.decode(), bytearray(RAW), None):
            with self.assertRaises(ModelError): candidate.require_current(data)

    def test_batch_is_complete_deterministic_and_read_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); configuration_file(root)
            for path in (PATH, 'rules/r.json'): put(root, path, RAW)
            before=tree_state(root); source=ProjectSource(root)
            candidates=prepare_normalizations(source, ['rules/r.json', PATH])
            self.assertEqual({c.path for c in candidates}, {PATH,'rules/r.json'})
            self.assertEqual(candidates, prepare_normalizations(source, [PATH,'rules/r.json']))
            self.assertEqual(tree_state(root), before)

    def test_batch_duplicates_are_rejected_before_resource_reads(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); configuration_file(root); source=ProjectSource(root)
            with mock.patch.object(source, 'read_normative') as read:
                with self.assertRaises(ModelError): prepare_normalizations(source, [PATH,PATH])
                read.assert_not_called()

    def test_invalid_batch_inputs_are_not_interpreted_as_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); configuration_file(root); source=ProjectSource(root)
            for paths in (PATH, b'paths', {'a': PATH}, None, [False], ['../x.json']):
                with self.subTest(kind=type(paths).__name__), self.assertRaises(ModelError):
                    prepare_normalizations(source, paths)

    def test_batch_does_not_return_partial_success_for_missing_or_bad_resource(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); configuration_file(root); put(root,PATH,RAW)
            put(root,'rules/invalid.json',b'{invalid'); before=tree_state(root)
            for bad in ('rules/invalid.json','rules/missing.json'):
                with self.subTest(bad=bad), self.assertRaises((ModelError,FileNotFoundError)):
                    prepare_normalizations(ProjectSource(root), [PATH,bad])
                self.assertEqual(tree_state(root),before)

    def test_observed_single_file_change_is_rejected_before_return(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); configuration_file(root); put(root,PATH,RAW)
            source=ProjectSource(root); original=source.read_normative; count=0
            def changed(path, **kwargs):
                nonlocal count
                data=original(path,**kwargs);count+=1
                if count==1: put(root,PATH,b' '+RAW)
                return data
            with mock.patch.object(source,'read_normative',side_effect=changed):
                with self.assertRaises(ModelError) as caught: prepare_normalization(source,PATH)
            self.assertEqual(caught.exception.reason,'representation_source_changed')
            self.assertEqual((root/PATH).read_bytes(),b' '+RAW)

    def test_earlier_batch_member_is_rechecked_after_later_reads(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);configuration_file(root);put(root,PATH,RAW);put(root,'rules/r.json',RAW)
            source=ProjectSource(root);original=source.read_normative
            def changed(path, **kwargs):
                data=original(path,**kwargs)
                if path=='rules/r.json':put(root,PATH,b' '+RAW)
                return data
            with mock.patch.object(source,'read_normative',side_effect=changed):
                with self.assertRaises(ModelError) as caught:
                    prepare_normalizations(source,[PATH,'rules/r.json'])
            self.assertEqual(caught.exception.reason,'representation_source_changed')

    def test_stale_candidate_does_not_overwrite_current_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);configuration_file(root);put(root,PATH,RAW);source=ProjectSource(root)
            candidate=prepare_normalization(source,PATH);put(root,PATH,b' '+RAW);before=tree_state(root)
            with self.assertRaises(ModelError):check_normalization_current(source,candidate)
            self.assertEqual(tree_state(root),before)

    def test_newly_terminal_proposal_is_not_formatable_via_an_old_candidate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);configuration_file(root);value=record_value('proposal')
            path=artifact_path('proposal',value['id'],'SR');put(root,path,artifact_bytes(value))
            source=ProjectSource(root);candidate=prepare_normalization(source,path)
            value.update(proposal_status='rejected',maturity='rejected');put(root,path,artifact_bytes(value))
            with self.assertRaises(ModelError) as caught:check_normalization_current(source,candidate)
            self.assertEqual(caught.exception.reason,'protected_original_resource')

    def test_missing_unknown_and_mismatched_special_statuses_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);configuration_file(root)
            for kind,field in [('proposal','proposal_status'),('evidence','evidence_state'),('baseline','baseline_state'),('relation_review','review_state')]:
                for status in (None,'unknown'):
                    value=record_value(kind)
                    if status is None:value.pop(field)
                    else:value[field]=status
                    path=artifact_path(kind,value['id'],'SR');put(root,path,artifact_bytes(value))
                    with self.subTest(kind=kind,status=status),self.assertRaises(ModelError):
                        prepare_normalization(ProjectSource(root),path)
            value=record_value('proposal',proposal_status='applied',maturity='draft')
            put(root,path:=artifact_path('proposal',value['id'],'SR'),artifact_bytes(value))
            with self.assertRaises(ModelError):prepare_normalization(ProjectSource(root),path)

    def test_all_active_proposal_states_preserve_control_and_content_metadata(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);configuration_file(root)
            for status,maturity in [('draft','draft'),('validated','proposed'),('checked','proposed'),('in_review','in_review'),('approved','approved')]:
                value=record_value('proposal',proposal_status=status,maturity=maturity)
                path=artifact_path('proposal',value['id'],'SR');put(root,path,artifact_bytes(value))
                with self.subTest(status=status):
                    self.assertEqual(prepare_normalization(ProjectSource(root),path).normalized_data,value)

    def test_path_and_artifact_identity_cannot_be_disguised(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);configuration_file(root);value=domain_value()
            path='spec/requirements/'+value['id'].replace('-GOAL-','-REQ-')+'.json'
            put(root,path,artifact_bytes(value))
            with self.assertRaises(ModelError):prepare_normalization(ProjectSource(root),path)

    def test_custom_generated_directory_is_also_excluded(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);configuration_file(root,generated_path='out/reports');put(root,'out/reports/data.json',RAW)
            source=ProjectSource(root)
            with self.assertRaises(ModelError):prepare_normalization(source,'out/reports/data.json')
            with self.assertRaises(ModelError):source.read_normative('out/reports/data.json')

    def test_configuration_changes_are_not_silently_adopted(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);configuration_file(root);put(root,PATH,RAW);source=ProjectSource(root)
            configuration_file(root,project_id='other')
            with self.assertRaises(ModelError):prepare_normalization(source,PATH)
            with self.assertRaises(ModelError):prepare_normalizations(source,[])

    def test_symlink_source_is_not_followed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);configuration_file(root);put(root,'profiles/real.json',RAW)
            (root/PATH).symlink_to('real.json');before=tree_state(root)
            with self.assertRaises(SafetyViolation):prepare_normalization(ProjectSource(root),PATH)
            self.assertEqual(tree_state(root),before)

    def test_unsafe_paths_are_rejected_without_writes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);configuration_file(root);source=ProjectSource(root);before=tree_state(root)
            for path in ('../p.json','/tmp/p.json','profiles/../p.json','.git/config','profiles\\p.json'):
                with self.subTest(path=path),self.assertRaises(ModelError):prepare_normalization(source,path)
            self.assertEqual(tree_state(root),before)

    def test_future_schema_version_is_not_silently_normalized(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);configuration_file(root);put(root,PATH,b'{"schema_version":"99.0.0"}')
            before=tree_state(root)
            with self.assertRaises(ModelError):prepare_normalization(ProjectSource(root),PATH)
            self.assertEqual(tree_state(root),before)

    def test_nested_original_values_and_extensions_are_preserved(self):
        value=domain_value('requirement',extensions={'org.example.data':{'z':[3,2,1],'text':'e\u0301\r\n'}})
        candidate=NormalizationCandidate(PATH,artifact_bytes(value))
        self.assertEqual(candidate.normalized_data,value)
        self.assertEqual(canonical_object_sha256(candidate.source_bytes),candidate.value_sha256)

    def test_invalid_surrogates_or_deep_json_fail_without_partial_candidates(self):
        for raw in (b'{"x":"\\ud800"}', b'{"x":'+b'['*2000+b'0'+b']'*2000+b'}'):
            with self.assertRaises(ModelError):normal_json_bytes(raw)

    def test_generated_role_cannot_be_changed_by_payload_metadata(self):
        view=GeneratedView(b'{"generated":false,"normative":true}',format='json')
        self.assertFalse(view.normative);self.assertTrue(view.generated)
        with self.assertRaises(FrozenInstanceError):view.content=b'{}'
        self.assertEqual(json.loads(view.content)['data'],{'generated':False,'normative':True})

    def test_helpers_work_without_site_packages(self):
        with tempfile.TemporaryDirectory() as temporary:
            process=run_core("from specroad.model.representation import NormalizationCandidate; "
                             "from specroad.storage.generated import GeneratedView; "
                             "c=NormalizationCandidate('rules/r.json',b'{\\\"n\\\":1}'); "
                             "assert c.normalized_data=={'n':1}; "
                             "assert not GeneratedView(c.source_bytes,format='json').normative",temporary)
            self.assertEqual(process.returncode,0,process.stderr)

    def test_moved_portable_module_and_zipapp_retain_behavior(self):
        # Both distributions execute the same isolated Core operation, without
        # asserting any generated human text, key order or visible label.
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);distribution=root/'build';build_distribution(distribution)
            moved=root/'moved';distribution.rename(moved)
            code=("import sys;sys.path.insert(0,sys.argv[1]); "
                  "from specroad.model.representation import NormalizationCandidate; "
                  "from specroad.storage.generated import GeneratedView; "
                  "c=NormalizationCandidate('rules/r.json',b'{\\\"x\\\":true}'); "
                  "assert c.normalized_data=={'x':True}; "
                  "assert not GeneratedView(c.source_bytes,format='json').normative")
            # Use the standard library process runner with explicitly isolated
            # CPython and the moved package path, not the development checkout.
            import subprocess
            for path in (moved/'module',moved/'specroad.pyz'):
                process=subprocess.run([sys.executable,'-I','-S','-B','-c',code,str(path)],
                                       cwd=root,stdin=subprocess.DEVNULL,capture_output=True)
                self.assertEqual(process.returncode,0,process.stderr)
