"""Observable literal policy and Term contracts, never human output snapshots."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from specroad.lint import Glossary, LiteralPolicy, LiteralLintError, lint_literals
from specroad.model.errors import ModelError
from specroad.model.domain_schemas import domain_schema, validate_domain_fields
from specroad.model.schema_catalog import SchemaCatalog
from specroad.storage.domain_artifact import DomainArtifact
from specroad.storage.project import ProjectSource
from specroad.storage.terms import read_term_artifact
from support.artifacts import artifact_bytes
from support.domain import domain_value
from support.literal_lint import term, policy_data, observe
from support.model import configuration_file, put
from support.portable import build_distribution


class LiteralWorkTests(unittest.TestCase):
    def test_minimum_term_fields_are_preserved(self):
        item = term(); data = item.data
        self.assertEqual(data['term'], 'Controller')
        self.assertEqual(data['forbidden_synonyms'], ['Magic box'])
        self.assertEqual(item.artifact_type, 'term')
        self.assertEqual(item.validation_scope, 'domain_fields_only')

    def test_every_term_mandatory_field_is_required(self):
        for field in ('term','definition','language','synonyms','forbidden_synonyms','owner','maturity'):
            value = term().data; value.pop(field)
            with self.subTest(field=field), self.assertRaises(ModelError):
                DomainArtifact(artifact_bytes(value), expected_type='term')

    def test_term_schema_in_catalog_is_the_real_validator(self):
        value = term().data; schema = domain_schema('term')
        resource = SchemaCatalog().get(schema['$id'])
        self.assertEqual(resource.schema, schema)
        resource.validate(value); validate_domain_fields(value)
        for name in ('synonyms','forbidden_synonyms'):
            bad = copy.deepcopy(value); bad[name] = 'not an array'
            with self.assertRaises(ModelError): resource.validate(bad)
            with self.assertRaises(ModelError): validate_domain_fields(bad)

    def test_empty_synonym_lists_are_allowed(self):
        item = term(synonyms=[], forbidden_synonyms=[])
        self.assertEqual(item.data['synonyms'], [])
        self.assertTrue(observe(terms=[item])['literal_checks_passed'])

    def test_term_texts_cannot_be_blank(self):
        for changes in ({'term':''}, {'definition':'  '}, {'synonyms':['']}, {'forbidden_synonyms':['  ']}):
            with self.subTest(changes=changes), self.assertRaises(ModelError): term(**changes)

    def test_valid_owner_shapes_are_preserved(self):
        for owner in ('engineering', {'actor_type':'human','actor_id':'test'}):
            self.assertEqual(term(owner=owner).data['owner'], owner)

    def test_unknown_top_level_term_fields_are_rejected(self):
        with self.assertRaises(ModelError): term(callback='evil.adapter')

    def test_term_keeps_original_bytes_and_detached_values(self):
        raw = json.dumps(term().data, ensure_ascii=True, indent=4).encode() + b'\n'
        item = DomainArtifact(raw, expected_type='term'); data = item.data
        data['synonyms'].append('MUTATED')
        self.assertEqual(item.source_bytes, raw)
        self.assertNotIn('MUTATED', item.data['synonyms'])

    def test_glossary_order_does_not_change_bound_content(self):
        a,b = term(), term(2, term='Monitor')
        self.assertEqual(Glossary([a,b]).sha256, Glossary([b,a]).sha256)
        self.assertEqual([t['id'] for t in Glossary([b,a]).terms], [a.id,b.id])

    def test_duplicate_ids_and_nontems_are_rejected(self):
        item=term()
        for records in ([item,item], [DomainArtifact(artifact_bytes(domain_value('goal')))], [item.data]):
            with self.subTest(kind=str(type(records[-1]))), self.assertRaises(LiteralLintError): Glossary(records)

    def test_declared_forbidden_synonym_is_diagnosed(self):
        report=observe('The Magic box works.')
        self.assertFalse(report['literal_checks_passed'])
        self.assertEqual([(d['code'],d['reason'],d['term_id']) for d in report['diagnostics']],
                         [('SRV053','forbidden_synonym','SR-TERM-0001')])

    def test_definition_and_allowed_synonyms_pass(self):
        for text in ('Controller works.', 'Control unit works.', 'A new unrelated technical word.'):
            self.assertTrue(observe(text)['literal_checks_passed'])

    def test_only_explicitly_selected_terms_are_checked(self):
        report=observe('Magic box', policy=policy_data(term_ids=[]))
        self.assertEqual(report['diagnostics'], [])
        self.assertEqual(report['checks']['forbidden_synonyms'], 'not_configured')

    def test_other_declared_language_is_not_silently_checked(self):
        report=observe('Magic box', language='en')
        self.assertEqual(report['diagnostics'], [])
        self.assertEqual(report['checks']['forbidden_synonyms'], 'not_applicable')

    def test_language_tag_case_does_not_rewrite_artifact(self):
        value=domain_value('requirement', language='DE-de', statement='Magic box')
        before=copy.deepcopy(value)
        report=lint_literals(value, glossary=Glossary([term()]), policy=LiteralPolicy.from_value(policy_data()))
        self.assertEqual(report['language'],'DE-de'); self.assertEqual(value,before)
        self.assertEqual(len(report['diagnostics']),1)

    def test_language_has_no_region_or_macrolanguage_fallback(self):
        for language, tagged in (('de','de-DE'),('cmn-Hans','zh-Hans')):
            report=observe('Magic box', language=language, terms=[term(language=tagged)],
                           policy=policy_data(language=language))
            self.assertEqual(report['diagnostics'],[])
            self.assertEqual(report['matched_term_ids'],[])

    def test_missing_configured_term_is_not_empty_success(self):
        with self.assertRaises(LiteralLintError) as caught: observe(terms=[])
        self.assertEqual(caught.exception.reason, 'literal_selected_term_missing')

    def test_exact_case_sensitive_substrings_only(self):
        self.assertTrue(observe('magic box')['literal_checks_passed'])
        self.assertFalse(observe('XMagic boxY')['literal_checks_passed'])

    def test_unicode_normalization_is_not_inferred(self):
        item=term(forbidden_synonyms=['café'])
        self.assertTrue(observe('cafe\u0301', terms=[item])['literal_checks_passed'])
        self.assertFalse(observe('café', terms=[item])['literal_checks_passed'])

    def test_matches_include_overlaps(self):
        report=observe('ababa', terms=[term(forbidden_synonyms=['aba'])])
        self.assertEqual([(d['start'],d['end']) for d in report['diagnostics']],[(0,3),(2,5)])

    def test_offsets_are_unicode_codepoints_not_bytes(self):
        report=observe('😀Magic box')
        finding=report['diagnostics'][0]
        self.assertEqual((finding['start'],finding['end'],finding['offset_unit']),(1,10,'unicode_codepoint'))

    def test_approved_core_placeholders_cannot_be_removed(self):
        report=observe('TBD TODO FIXME', maturity='approved', policy=policy_data(placeholders=[]))
        self.assertEqual({d['literal'] for d in report['diagnostics']},{'TBD','TODO','FIXME'})
        self.assertTrue(all(d['code']=='SRV033' and d['severity']=='error' for d in report['diagnostics']))

    def test_explicit_placeholder_is_scoped_to_declared_language(self):
        self.assertEqual(observe('OFFEN', maturity='approved')['diagnostics'][0]['reason'],'open_placeholder')
        report=observe('OFFEN', maturity='approved', language='en')
        self.assertEqual(report['diagnostics'],[])

    def test_core_placeholders_apply_even_if_optional_policy_language_does_not_match(self):
        self.assertEqual(observe('TODO', language='ja', maturity='approved')['diagnostics'][0]['code'],'SRV033')

    def test_draft_placeholders_do_not_claim_an_approval_violation(self):
        report=observe('TBD OFFEN')
        self.assertEqual(report['diagnostics'],[])
        self.assertEqual(report['checks']['approved_placeholders'],'not_applicable')

    def test_unselected_text_is_not_scanned(self):
        report=observe('Controller', rationale='TODO Magic box', maturity='approved')
        self.assertEqual(report['diagnostics'],[])
        self.assertEqual(report['checked_fields'],['/statement'])

    def test_explicit_nested_text_pointer_is_supported(self):
        data=policy_data(fields=['/extensions/demo.literal/~0x~1y/0'])
        report=observe('Controller',policy=data,extensions={'demo.literal':{'~x/y':['Magic box']}})
        self.assertEqual(report['diagnostics'][0]['pointer'],data['fields'][0])

    def test_missing_or_nontext_selection_fails_closed(self):
        for pointer in ('/missing','/revision','/relations'):
            with self.subTest(pointer=pointer),self.assertRaises(LiteralLintError):
                observe(policy=policy_data(fields=[pointer]))

    def test_invalid_policy_and_unknown_executable_fields_rejected(self):
        for change in ({'callback':'evil.adapter'},{'format_version':True},{'version':'latest'},
                       {'fields':[]},{'fields':['statement']},{'fields':['/a~2']},
                       {'fields':['/statement','/statement']},{'placeholders':['']},{'language':'de_DE'}):
            with self.subTest(change=change),self.assertRaises(ModelError): LiteralPolicy.from_value(policy_data(**change))

    def test_policy_keeps_its_own_data_and_bytes(self):
        data=policy_data(); raw=artifact_bytes(data); policy=LiteralPolicy(raw)
        data['placeholders'].append('Controller'); exposed=policy.data;exposed['fields'].clear()
        self.assertEqual(policy.source_bytes,raw)
        self.assertEqual(policy.data['fields'],['/statement'])

    def test_complete_report_is_reproducible_and_has_no_linguistic_success(self):
        a=observe('Controller should maybe be reliable.')
        b=observe('Controller should maybe be reliable.')
        self.assertEqual(a,b)
        self.assertTrue(all(v=='not_available' for v in a['linguistic_checks'].values()))
        self.assertFalse(a['approval_granted']);self.assertFalse(a['project_complete'])
        self.assertEqual(a['validation_scope'],'selected_literal_fields_only')

    def test_modal_words_do_not_infer_force_or_contradiction(self):
        for force in ('must','must_not','should','may'):
            report=observe('Es sollte nie und immer gehen.',normative_force=force)
            self.assertEqual(report['diagnostics'],[])
            self.assertEqual(report['linguistic_checks']['modality'],'not_available')

    def test_project_reader_preserves_bytes_and_side_effects(self):
        raw=artifact_bytes(term().data)
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);configuration_file(root);put(root,'spec/terms/SR-TERM-0001.json',raw)
            before={str(p.relative_to(root)):p.read_bytes() for p in root.rglob('*') if p.is_file()}
            item=read_term_artifact(ProjectSource(root),'spec/terms/SR-TERM-0001.json')
            self.assertEqual(item.source_bytes,raw)
            self.assertEqual(before,{str(p.relative_to(root)):p.read_bytes() for p in root.rglob('*') if p.is_file()})

    def test_portable_module_and_zipapp_can_evaluate_literals(self):
        item=term(); value=domain_value('requirement',statement='Magic box TODO',maturity='approved')
        rule=LiteralPolicy.from_value(policy_data())
        expected=lint_literals(value,glossary=Glossary([item]),policy=rule)
        code=('import sys,json;sys.path.insert(0,sys.argv[1]);from specroad.lint import Glossary,LiteralPolicy,lint_literals;'
              'from specroad.storage.domain_artifact import DomainArtifact;'
              'v=json.loads(sys.stdin.buffer.read());print(json.dumps(lint_literals(v[0],'
              'glossary=Glossary([DomainArtifact(json.dumps(v[1]).encode(),expected_type="term")]),'
              'policy=LiteralPolicy.from_value(v[2]))))')
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);module,archive=build_distribution(root/'out')
            m=root/'moved';a=root/'moved.pyz';module.rename(m);archive.rename(a)
            for source in (m,a):
                result=subprocess.run([sys.executable,'-I','-B','-c',code,str(source)],cwd=temp,
                    input=json.dumps([value,item.data,rule.data]).encode(),capture_output=True)
                self.assertEqual(result.returncode,0,result.stderr.decode())
                self.assertEqual(json.loads(result.stdout),expected)
