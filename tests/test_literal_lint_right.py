"""Reference completeness, exact-language semantics, and boundary regressions."""
from concurrent.futures import ThreadPoolExecutor
import builtins
import copy
import itertools
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from specroad.lint import Glossary, LiteralPolicy, LiteralLintError, lint_literals
from specroad.model.canonical import canonical_json_sha256
from specroad.model.errors import ModelError
from specroad.security import SafetyViolation
from specroad.storage.domain_artifact import DomainArtifact
from specroad.storage.project import ProjectSource
from specroad.storage.terms import read_term_artifact
from support.artifacts import artifact_bytes, common_artifact
from support.domain import domain_value
from support.literal_lint import term, policy_data, observe
from support.model import configuration_file, put


def reference_policy(by='name', pointer='/extensions/test.refs/value', **changes):
    return policy_data(references=[{'pointer':pointer, 'by':by}], **changes)


def reference_result(value, *, by='name', terms=None, **changes):
    return observe(terms=terms, policy=reference_policy(by=by),
                   extensions={'test.refs':{'value':value}}, **changes)


class LiteralRightTests(unittest.TestCase):
    def test_explicit_term_name_and_allowed_synonym_are_resolved(self):
        for name in ('Controller', 'Control unit'):
            result=reference_result(name)
            self.assertEqual(result['diagnostics'],[])
            self.assertEqual(result['checks']['term_references'],'checked')

    def test_real_id_resolves_but_display_id_never_does(self):
        item=term(display_id='CONTROL')
        self.assertEqual(reference_result(item.id,by='id',terms=[item])['diagnostics'],[])
        for by in ('id','name'):
            result=reference_result('CONTROL',by=by,terms=[item])
            self.assertEqual(len(result['diagnostics']),1)

    def test_undefined_name_is_explicit_reference_not_unknown_prose(self):
        result=reference_result('Not defined')
        self.assertEqual(result['diagnostics'][0]['reason'],'undefined_term_reference')
        self.assertEqual(observe('Not defined')['diagnostics'],[])

    def test_unknown_well_formed_id_is_undefined(self):
        finding=reference_result('SR-TERM-0199',by='id')['diagnostics'][0]
        self.assertEqual(finding['reason'],'undefined_term_reference')
        self.assertEqual(finding['pointer'],'/extensions/test.refs/value')

    def test_reference_id_does_not_resolve_to_wrong_type(self):
        self.assertEqual(reference_result('SR-REQ-0001',by='id')['diagnostics'][0]['reason'],
                         'invalid_term_reference')

    def test_duplicate_names_are_ambiguous_not_chosen_by_file_order(self):
        a,b=term(),term(2)
        first=reference_result('Controller',terms=[a,b]); second=reference_result('Controller',terms=[b,a])
        self.assertEqual(first,second)
        self.assertEqual(first['diagnostics'][0]['reason'],'ambiguous_term_reference')
        self.assertEqual(first['diagnostics'][0]['candidate_ids'],['SR-TERM-0001','SR-TERM-0002'])

    def test_duplicate_alias_in_one_term_is_one_candidate(self):
        item=term(synonyms=['Controller','Controller'])
        self.assertEqual(reference_result('Controller',terms=[item])['diagnostics'],[])

    def test_alias_of_another_term_can_make_name_ambiguous(self):
        a,b=term(),term(2,term='Other',synonyms=['Controller'])
        self.assertEqual(reference_result('Controller',terms=[a,b])['diagnostics'][0]['reason'],'ambiguous_term_reference')

    def test_forbidden_synonym_is_not_an_allowed_reference_alias(self):
        self.assertEqual(reference_result('Magic box')['diagnostics'][0]['reason'],'undefined_term_reference')

    def test_reference_names_use_whole_exact_values(self):
        for value in (' Controller','controller','Controller subsystem','Control unit\n'):
            with self.subTest(value=value):
                self.assertEqual(reference_result(value)['diagnostics'][0]['reason'],'undefined_term_reference')

    def test_reference_language_is_not_translated(self):
        item=term(language='en',term='Controller')
        result=reference_result(item.id,by='id',terms=[item])
        self.assertEqual(result['diagnostics'][0]['reason'],'term_reference_language_mismatch')
        self.assertEqual(reference_result('Controller',terms=[item])['diagnostics'][0]['reason'],'undefined_term_reference')

    def test_inapplicable_language_does_not_claim_reference_check(self):
        result=reference_result('Not defined',language='ja')
        self.assertEqual(result['diagnostics'],[])
        self.assertEqual(result['checks']['term_references'],'not_applicable')
        self.assertIsNone(result['literal_checks_passed'])

    def test_absent_reference_field_is_diagnosed_not_silently_skipped(self):
        result=observe(policy=reference_policy())
        finding=result['diagnostics'][0]
        self.assertEqual(finding['reason'],'undefined_term_reference')
        self.assertIsNone(finding['start']);self.assertIsNone(finding['end']);self.assertIsNone(finding['literal'])

    def test_null_boolean_numbers_and_containers_are_not_names(self):
        for value in (None,False,1,[],{},'','  '):
            with self.subTest(value=value):
                self.assertEqual(reference_result(value)['diagnostics'][0]['reason'],'invalid_term_reference')

    def test_reference_pointers_can_address_array_items(self):
        result=observe(policy=reference_policy(pointer='/extensions/test.refs/0'),extensions={'test.refs':['Controller']})
        self.assertEqual(result['diagnostics'],[])

    def test_bad_reference_array_index_does_not_become_missing_success(self):
        with self.assertRaises(LiteralLintError) as caught:
            observe(policy=reference_policy(pointer='/extensions/test.refs/00'),extensions={'test.refs':['Controller']})
        self.assertEqual(caught.exception.reason,'literal_reference_access_error')

    def test_duplicate_and_executable_reference_declarations_fail(self):
        for entries in ([{'pointer':'/a','by':'guess'}], [{'pointer':'/a','by':False}],
                        [{'pointer':'/a','by':'name','callback':'evil'}], [{'pointer':'../a','by':'id'}],
                        [{'pointer':'/a','by':'name'},{'pointer':'/a','by':'id'}], ['name']):
            with self.subTest(entries=entries),self.assertRaises(LiteralLintError):
                LiteralPolicy.from_value(policy_data(references=entries))

    def test_more_than_a_display_page_of_references_are_all_checked(self):
        data={str(i):'Unknown '+str(i) for i in range(151)}
        refs=[{'pointer':'/extensions/test.refs/'+str(i),'by':'name'} for i in range(151)]
        result=observe(policy=policy_data(references=refs),extensions={'test.refs':data})
        self.assertEqual(len(result['diagnostics']),151)
        self.assertEqual({d['pointer'] for d in result['diagnostics']},{r['pointer'] for r in refs})

    def test_more_than_a_display_page_of_literal_hits_are_not_truncated(self):
        result=observe('x'*1001,terms=[term(forbidden_synonyms=['xx'])])
        self.assertEqual(len(result['diagnostics']),1000)
        self.assertEqual((result['diagnostics'][-1]['start'],result['diagnostics'][-1]['end']),(999,1001))

    def test_exact_matcher_agrees_with_independent_sliding_windows(self):
        patterns=['a','b','aa','ab','ba','bb','aba']
        for n in range(6):
            for text in map(''.join,itertools.product('ab',repeat=n)):
                result=observe(text,terms=[term(forbidden_synonyms=patterns)])
                expected=sorted((i,i+len(p),p) for p in patterns for i in range(len(text)-len(p)+1) if text[i:i+len(p)]==p)
                actual=sorted((d['start'],d['end'],d['literal']) for d in result['diagnostics'])
                self.assertEqual(actual,expected,(text,actual,expected))

    def test_term_literals_reject_nul_without_schema_weakening(self):
        with self.assertRaises(ModelError):
            term(forbidden_synonyms=["x\x00y"])

    def test_unicode_literal_vectors_preserve_original_positions(self):
        for prefix,literal in [('😀','café'),('e\u0301','東京'),('ع','नमस्ते'),('\n','x\ny')]:
            text=prefix+literal
            result=observe(text,terms=[term(forbidden_synonyms=[literal])])
            d=result['diagnostics'][0]
            self.assertEqual(text[d['start']:d['end']],literal)
            self.assertEqual(d['start'],len(prefix))

    def test_empty_applicable_work_is_not_reported_as_language_pass(self):
        result=observe(policy=policy_data(term_ids=[],placeholders=[]))
        self.assertIsNone(result['literal_checks_passed'])
        self.assertFalse(result['language_registry_checked'])
        self.assertFalse(result['language_detection_performed'])
        self.assertTrue(all(v=='not_available' for v in result['linguistic_checks'].values()))

    def test_statement_force_and_priority_do_not_trigger_linguistic_findings(self):
        statement='The box must and should maybe never always work. Контроллер.'
        for force in ('must','must_not','may','should'):
            for priority in ('mandatory','high','medium','low'):
                result=observe(statement,normative_force=force,priority=priority)
                self.assertEqual(result['diagnostics'],[])
                self.assertEqual(result['linguistic_checks']['contradiction'],'not_available')

    def test_core_placeholder_scan_does_not_normalize_case(self):
        self.assertEqual(observe('todo tbd fixme',maturity='approved')['diagnostics'],[])
        self.assertEqual({d['literal'] for d in observe('TODO TBD FIXME',maturity='approved')['diagnostics']},{'TODO','TBD','FIXME'})

    def test_repeated_placeholder_deduplicates_declarations_not_occurrences(self):
        result=observe('TODO TODO',maturity='approved',policy=policy_data(placeholders=['TODO']))
        self.assertEqual(len(result['diagnostics']),2)

    def test_nonapproved_maturities_do_not_produce_srv033(self):
        for maturity in ('draft','proposed','in_review','rejected','retired','superseded'):
            self.assertEqual(observe('TODO',maturity=maturity)['diagnostics'],[])

    def test_invalid_maturity_cannot_skip_approved_guard(self):
        with self.assertRaises(ModelError):observe('TODO',maturity='APPROVED')

    def test_absent_declared_language_does_not_default_from_locale(self):
        value=common_artifact('goal','GOAL',statement='TODO')
        with self.assertRaises(LiteralLintError) as caught:
            lint_literals(value,glossary=Glossary([term()]),policy=LiteralPolicy.from_value(policy_data()))
        self.assertEqual(caught.exception.reason,'literal_declared_language_required')

    def test_scope_is_explicit_not_arbitrary_recursive_text_discovery(self):
        result=observe('Controller',maturity='approved',title='TODO',
                       extensions={'test.literal':{'statement':'TODO Magic box'}})
        self.assertEqual(result['diagnostics'],[])
        self.assertFalse(result['project_complete'])

    def test_errors_do_not_mutate_caller_records(self):
        value=domain_value('requirement',statement='TODO');old=copy.deepcopy(value)
        with self.assertRaises(LiteralLintError):
            lint_literals(value,glossary=Glossary([]),policy=LiteralPolicy.from_value(policy_data()))
        self.assertEqual(value,old)

    def test_output_mutations_do_not_leak_to_future_calls(self):
        glossary=Glossary([term()]);rule=LiteralPolicy.from_value(policy_data());value=domain_value('requirement',statement='Magic box')
        first=lint_literals(value,glossary=glossary,policy=rule);expected=copy.deepcopy(first)
        first['diagnostics'][0]['candidate_ids'].append('FAKE');first['checked_fields'].clear()
        exposed=glossary.terms;exposed[0]['forbidden_synonyms'].clear()
        self.assertEqual(lint_literals(value,glossary=glossary,policy=rule),expected)

    def test_hashes_bind_terms_policy_and_actual_input(self):
        first=observe('Controller')
        second=observe('Controller  ')
        self.assertNotEqual(first['artifact_sha256'],second['artifact_sha256'])
        self.assertEqual(first['policy_sha256'],second['policy_sha256'])
        self.assertEqual(Glossary([term()]).sha256,canonical_json_sha256([term().data]))
        self.assertNotEqual(first['glossary_sha256'],observe(terms=[term(definition='Changed')])['glossary_sha256'])

    def test_concurrent_reuse_has_no_cross_call_binding(self):
        glossary=Glossary([term()]);rule=LiteralPolicy.from_value(policy_data())
        inputs=[domain_value('requirement',statement=s) for s in ['Controller','Magic box','TODO']*8]
        def run(v):return lint_literals(v,glossary=glossary,policy=rule)
        expected=[run(v) for v in inputs]
        with ThreadPoolExecutor(max_workers=4) as pool:self.assertEqual(list(pool.map(run,inputs)),expected)

    def test_locale_and_hash_randomization_do_not_change_literal_results(self):
        first=observe('Magic box TODO',maturity='approved')
        with patch.dict(os.environ,{'LANG':'tr_TR.UTF-8','LC_ALL':'ja_JP.UTF-8','TZ':'Asia/Tokyo'}):
            self.assertEqual(observe('Magic box TODO',maturity='approved'),first)

    def test_code_like_literals_cannot_open_or_execute(self):
        value=domain_value('requirement',statement="__import__('evil').run()")
        glossary=Glossary([term(forbidden_synonyms=["__import__('evil').run()"])]);rule=LiteralPolicy.from_value(policy_data())
        real_import=builtins.__import__;seen=[]
        def guarded(name,*args,**kwargs):
            seen.append(name)
            if name=='evil' or 'analyzer' in name:raise AssertionError('Unwanted dynamic import')
            return real_import(name,*args,**kwargs)
        with patch.object(builtins,'open',side_effect=AssertionError('No I/O')) as opened,\
             patch.object(os,'system',side_effect=AssertionError('No shell')) as system,\
             patch.object(subprocess,'Popen',side_effect=AssertionError('No process')) as spawned,\
             patch.object(builtins,'__import__',guarded):
            report=lint_literals(value,glossary=glossary,policy=rule)
        self.assertEqual(len(report['diagnostics']),1)
        opened.assert_not_called();system.assert_not_called();spawned.assert_not_called()
        self.assertNotIn('evil',seen)

    def test_foreign_conversion_hooks_are_not_executed(self):
        class Hostile(dict):
            def items(self):raise AssertionError('hook executed')
        with self.assertRaises(ModelError):LiteralPolicy.from_value(Hostile(policy_data()))
        with self.assertRaises(ModelError):
            lint_literals(Hostile(domain_value('requirement')),glossary=Glossary([term()]),policy=LiteralPolicy.from_value(policy_data()))

    def test_broken_policy_json_is_never_repaired(self):
        for raw in (b'{}{}',b'{"a":1,"a":2}',b'\xff',b'[]',b'\xef\xbb\xbf{}'):
            with self.subTest(raw=raw),self.assertRaises(ModelError):LiteralPolicy(raw)

    def test_result_order_is_severity_then_path_pointer_and_code(self):
        value=domain_value('requirement',statement='Magic box TODO',rationale='FIXME',maturity='approved')
        data=policy_data(fields=['/statement','/rationale'])
        a=lint_literals(value,glossary=Glossary([term()]),policy=LiteralPolicy.from_value(data),path='same.json')
        data['fields'].reverse()
        b=lint_literals(value,glossary=Glossary([term()]),policy=LiteralPolicy.from_value(data),path='same.json')
        self.assertEqual(a['diagnostics'],b['diagnostics'])
        self.assertEqual([d['code'] for d in a['diagnostics']],['SRV033','SRV033','SRV053'])

    def test_term_path_identity_and_project_prefix_are_bound(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);configuration_file(root);put(root,'spec/terms/SR-TERM-0002.json',artifact_bytes(term().data))
            with self.assertRaises(ModelError):read_term_artifact(ProjectSource(root),'spec/terms/SR-TERM-0002.json')

    def test_missing_term_never_falls_back_to_a_bundled_definition(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);configuration_file(root)
            with self.assertRaises((ModelError,SafetyViolation,OSError)):
                read_term_artifact(ProjectSource(root),'spec/terms/SR-TERM-0001.json')

    def test_symlink_and_wrong_path_classes_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);configuration_file(root)
            actual=put(root,'spec/terms/SR-TERM-0001.json',artifact_bytes(term().data))
            (root/'spec/terms/SR-TERM-0002.json').symlink_to(actual)
            put(root,'generated/t.json',artifact_bytes(term().data))
            for path in ('spec/terms/SR-TERM-0002.json','generated/t.json','../t.json'):
                with self.subTest(path=path),self.assertRaises((ModelError,SafetyViolation,OSError)):
                    read_term_artifact(ProjectSource(root),path)

    def test_reader_rechecks_changed_bytes_without_writing(self):
        raw=artifact_bytes(term().data);other=raw+b' '
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);configuration_file(root);p=put(root,'spec/terms/SR-TERM-0001.json',raw)
            source=ProjectSource(root);original=ProjectSource.read_normative;calls=[]
            def reader(obj,path):
                data=original(obj,path);calls.append(path)
                if len(calls)==1:p.write_bytes(other)
                return data
            with patch.object(ProjectSource,'read_normative',reader),self.assertRaises(ModelError) as caught:
                read_term_artifact(source,'spec/terms/SR-TERM-0001.json')
            self.assertEqual(caught.exception.reason,'term_changed_during_read')
            self.assertEqual(p.read_bytes(),other)

    def test_stale_project_configuration_cannot_be_used(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);configuration_file(root);put(root,'spec/terms/SR-TERM-0001.json',artifact_bytes(term().data))
            source=ProjectSource(root);configuration_file(root,project_name='Changed')
            with self.assertRaises(ModelError):read_term_artifact(source,'spec/terms/SR-TERM-0001.json')
