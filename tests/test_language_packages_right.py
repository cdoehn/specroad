"""Host independence and corrupt/ambiguous package contracts, not label wording."""
from hashlib import sha256
from pathlib import Path
from dataclasses import FrozenInstanceError
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from specroad.model.errors import ModelError
from specroad.model.canonical import canonical_json_sha256
from specroad.model.language_packages import (LanguagePackage, LanguagePackageError, package_key,
    parse_package_key, validate_ranges, coalesce_packages, select_language_packages)
from specroad.model.content_language import ContentLanguage
from specroad.storage.language_packages import (load_bundled_package, packages_for_language,
    bundled_package_index, PackageSelection, minimum_language_corpus)
from specroad.cli.language_labels import label_for
from support.portable import build_distribution, copy_source_fixture, files_under
from test_language_packages import package_data, encoded, draft_for, KEYS, TEXT

ROOT = Path(__file__).resolve().parents[1]


class LanguagePackageRightTests(unittest.TestCase):
    def test_semver_versions_preserved_without_range_resolution(self):
        for version in ('0.0.0','1.0.0','1.2.3-alpha.0','1.2.3-rc.1+build.01','2.0.0+ABC'):
            with self.subTest(version=version):
                self.assertEqual(parse_package_key(package_key('demo', version)), ('demo',version))

    def test_invalid_semver_rejected(self):
        for version in ('01.0.0','1.0','v1.0.0','1.0.0-01','1.0.0-','1.0.0+','1.0.0+a..b','1.0.0\n',1):
            with self.subTest(version=version), self.assertRaises(ModelError): package_key('en',version)

    def test_invalid_package_keys_never_become_paths(self):
        for key in ('../en@1.0.0','en/x@1.0.0','en@1.0.0@x','en','',None,True):
            with self.subTest(key=key), self.assertRaises(ModelError): parse_package_key(key)

    def test_no_custom_bytes_decode_executed(self):
        class Malicious(bytes):
            def decode(self, *args, **kwargs): raise AssertionError('custom decode executed')
        with self.assertRaises(LanguagePackageError): LanguagePackage(Malicious(b'{}'))

    def test_doubled_keys_and_trailing_bytes_rejected(self):
        raw = encoded(package_data())
        for data in (b'{"package_id":"one","package_id":"two"}', raw+b'{}', b'\xef\xbb\xbf'+raw):
            with self.assertRaises(ModelError): LanguagePackage(data)

    def test_invalid_unicode_is_not_corrected(self):
        for data in (b'{"labels":"\xff"}', encoded(package_data()).replace(b'"labels": {}', b'"labels":{"x":{"x":"\\ud800"}}')):
            with self.assertRaises(ModelError): LanguagePackage(data)

    def test_lint_and_detection_not_declared_by_package(self):
        for capability in ('lint','detector','translation','passed','os.system',{},True):
            with self.subTest(capability=capability), self.assertRaises(ModelError):
                LanguagePackage(encoded(package_data(capabilities=['metadata',capability])))

    def test_nonempty_literal_rules_fail_explicitly_not_silently_ignored(self):
        with self.assertRaises(LanguagePackageError) as caught:
            LanguagePackage(encoded(package_data(literal_rules=[{'callback':'os.system'}])))
        self.assertEqual(caught.exception.reason,'literal_rule_invalid')

    def test_bad_labels_shape_not_executed(self):
        for labels in ([],None,{'domain':[]},{'domain':{'value':{'callback':'run'}}}):
            with self.assertRaises(ModelError): LanguagePackage(encoded(package_data(labels=labels)))

    def test_capability_missing_for_nonempty_labels(self):
        with self.assertRaises(ModelError):
            LanguagePackage(encoded(package_data(labels={'maturity':{'draft':'example'}},capabilities=['metadata'])))

    def test_ranges_reject_extended_wildcards_and_duplicate_case(self):
        for ranges in ([],['en-*'],['*-US'],['en','EN'],['en_US'],['en-abcdefghi'],[None]):
            with self.subTest(ranges=ranges), self.assertRaises(ModelError): validate_ranges(ranges)

    def test_basic_range_is_not_required_to_be_a_registered_tag(self):
        self.assertEqual(validate_ranges(['i','en-a','zzzz']), ('i','en-a','zzzz'))

    def test_identical_identity_and_hash_collapse(self):
        p=load_bundled_package('en@1.0.0'); duplicate=LanguagePackage(p.source_bytes)
        self.assertEqual(coalesce_packages([p,duplicate]),(p,))
        self.assertEqual(select_language_packages('en-US',[p,duplicate]),(p,))

    def test_same_identity_different_bytes_is_conflict(self):
        p=LanguagePackage(encoded(package_data()))
        other=LanguagePackage(encoded(package_data(labels={'maturity':{'draft':'different'}})))
        with self.assertRaises(LanguagePackageError) as caught: coalesce_packages([p,other])
        self.assertEqual(caught.exception.reason,'package_identity_conflict')

    def test_same_values_different_resource_hash_not_silently_collapsed(self):
        p=LanguagePackage(encoded(package_data()))
        q=LanguagePackage(p.source_bytes+b'\n')
        with self.assertRaises(LanguagePackageError): coalesce_packages([p,q])

    def test_conflicting_label_sources_rejected_before_lookup(self):
        p=LanguagePackage(encoded(package_data()))
        q=LanguagePackage(p.source_bytes+b' ')
        with self.assertRaises(LanguagePackageError): label_for('must',domain='normative_force',packages=[p,q])

    def test_duplicate_activation_is_stable_and_loaded_once(self):
        import specroad.storage.language_packages as storage
        old=storage._read; reads=[]
        def read(path): reads.append(path); return old(path)
        with patch.object(storage,'_read',side_effect=read):
            result=packages_for_language('en',activated=['en@1.0.0']*3)
        self.assertEqual(len(result.packages),1)
        self.assertEqual(reads.count('packages/en.json'),1)

    def test_duplicate_missing_activation_is_not_multiple_failures(self):
        result=packages_for_language('fr',activated=['fr@1.0.0']*3)
        self.assertEqual(result.unavailable,('fr@1.0.0',))

    def test_corrupt_matching_package_hash_fails(self):
        import specroad.storage.language_packages as storage
        old=storage._read
        def read(path): return old(path)+b'\n' if path=='packages/en.json' else old(path)
        with patch.object(storage,'_read',side_effect=read), self.assertRaises(LanguagePackageError):
            packages_for_language('en',activated=KEYS)

    def test_absent_matching_package_does_not_use_another_package(self):
        from importlib.resources import files
        root=files('specroad.language_data')
        class Source:
            def joinpath(self,path):
                if path=='packages/en.json': raise FileNotFoundError(path)
                return root.joinpath(path)
        with patch('specroad.storage.language_packages.files',return_value=Source()), self.assertRaises(LanguagePackageError):
            load_bundled_package('en@1.0.0')

    def test_unrelated_package_is_not_opened_even_if_unreadable(self):
        import specroad.storage.language_packages as storage
        old=storage._read
        def read(path):
            if path=='packages/ja.json': raise AssertionError('unrelated package read')
            return old(path)
        with patch.object(storage,'_read',side_effect=read):
            self.assertEqual(packages_for_language('de',activated=KEYS).packages[0].package_id,'de')

    def test_index_forbids_traversal_and_absolute_paths(self):
        index={'format_version':1,'packages':list(bundled_package_index())}
        for path in ('../en.json','/tmp/en.json','packages/../en.json','packages\\en.json'):
            index['packages'][0]['filename']=path
            with patch('specroad.storage.language_packages._read',return_value=encoded(index)), self.assertRaises(ModelError):
                bundled_package_index()

    def test_index_rejects_duplicate_ids(self):
        entries=list(bundled_package_index());entries.append(dict(entries[0]))
        with patch('specroad.storage.language_packages._read',return_value=encoded({'format_version':1,'packages':entries})), self.assertRaises(ModelError):
            bundled_package_index()

    def test_index_rejects_unknown_fields_and_boolean_version(self):
        for value in ({'format_version':True,'packages':[]},{'format_version':1,'packages':[],'callback':'x'}):
            with patch('specroad.storage.language_packages._read',return_value=encoded(value)), self.assertRaises(ModelError):
                bundled_package_index()

    def test_index_hash_must_be_full_lowercase(self):
        entries=list(bundled_package_index());entries[0]['sha256']='x'*64
        with patch('specroad.storage.language_packages._read',return_value=encoded({'format_version':1,'packages':entries})), self.assertRaises(ModelError):
            bundled_package_index()

    def test_no_cached_index_is_shared_with_callers(self):
        entries=bundled_package_index();entries[0]['language_ranges'].append('*')
        self.assertEqual(bundled_package_index()[0]['language_ranges'],['de'])

    def test_source_ranges_must_match_the_index(self):
        import specroad.storage.language_packages as storage
        old=storage._read
        def read(path):
            raw=old(path)
            if path=='packages.json':
                value=json.loads(raw);value['packages'][0]['language_ranges']=['en'];return encoded(value)
            return raw
        with patch.object(storage,'_read',side_effect=read), self.assertRaises(LanguagePackageError):
            load_bundled_package('de@1.0.0')

    def test_selection_rejects_nonmatching_content_language(self):
        with self.assertRaises(ModelError): PackageSelection('de',(load_bundled_package('en@1.0.0'),),())

    def test_selection_rejects_simultaneous_available_and_missing(self):
        with self.assertRaises(ModelError): PackageSelection('en',(load_bundled_package('en@1.0.0'),),('en@1.0.0',))

    def test_selection_input_and_report_are_detached(self):
        packs=[load_bundled_package('en@1.0.0')]; missing=['other@1.0.0']
        result=PackageSelection('en',packs,missing);packs.clear();missing.clear()
        report=result.as_dict();report['packages'].clear();report['unavailable'].clear()
        self.assertEqual(len(result.packages),1);self.assertEqual(result.unavailable,('other@1.0.0',))
        with self.assertRaises(FrozenInstanceError): result.language='de'

    def test_source_text_and_unicode_normalization_are_preserved(self):
        self.assertNotEqual(canonical_json_sha256(draft_for('de',text='é').data),canonical_json_sha256(draft_for('de',text='e\u0301').data))
        self.assertEqual(draft_for('ar').data['statement'],TEXT)
        self.assertEqual(ContentLanguage('ar').text_direction,'auto')

    def test_model_hash_ignores_package_read_and_display_choices(self):
        before=draft_for('hi-IN').data;expected=canonical_json_sha256(before)
        for tag in ('de-DE','ja-JP','ar','zh-Hans-CN'):
            result=packages_for_language(tag,activated=KEYS)
            label_for('must',domain='normative_force',packages=result.packages)
            self.assertEqual(canonical_json_sha256(before),expected)
        self.assertEqual(draft_for('hi-IN').data,before)

    def test_locale_and_timezone_changes_leave_values_and_hashes_identical(self):
        script='''import sys,json,locale,time
sys.path[:0]=[sys.argv[1]+"/src",sys.argv[1]+"/tests"]
from test_language_packages import draft_for,KEYS
from specroad.model.canonical import canonical_json_sha256
from specroad.storage.language_packages import packages_for_language
locale.setlocale=lambda *a,**k: (_ for _ in ()).throw(RuntimeError("host locale must not be used"))
if hasattr(time,"tzset"): time.tzset()
d=draft_for("hi-IN").data
print(json.dumps({"model":d,"hash":canonical_json_sha256(d),"packages":packages_for_language("hi-IN",activated=KEYS).as_dict()},ensure_ascii=True))
'''
        expected=None
        with tempfile.TemporaryDirectory() as tmp:
            for loc,tz in (('C','UTC0'),('C.UTF-8','JST-9'),('tr_TR.not-installed','EST5EDT')):
                env=dict(os.environ);env.update(LANG=loc,LC_ALL=loc,TZ=tz)
                result=subprocess.run([sys.executable,'-I','-B','-c',script,str(ROOT)],cwd=tmp,env=env,
                                      stdin=subprocess.DEVNULL,capture_output=True,check=True)
                observed=json.loads(result.stdout)
                if expected is None: expected=observed
                self.assertEqual(observed,expected)

    def test_label_resource_changes_build_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=copy_source_fixture(root/'src')
            first,_=build_distribution(root/'first',source)
            p=source/'specroad/language_data/packages/en.json';p.write_bytes(p.read_bytes()+b'\n')
            second,_=build_distribution(root/'second',source)
            self.assertNotEqual((first/'specroad/_build.py').read_bytes(),(second/'specroad/_build.py').read_bytes())

    def test_omitted_labels_return_exact_enum_without_english_translation(self):
        self.assertEqual(label_for('must_not',domain='normative_force'), 'must_not')
        p=LanguagePackage(encoded(package_data(labels={})))
        self.assertEqual(label_for('must_not',domain='normative_force',packages=[p]), 'must_not')

    def test_language_selection_is_not_cli_locale(self):
        result=packages_for_language('ar',activated=KEYS)
        self.assertEqual(result.as_dict()['language'],'ar')
        self.assertEqual(result.packages,())
        self.assertEqual(result.as_dict()['content_support'],'utf8')

    def test_malformed_corpus_is_not_silently_used(self):
        for data in ({'format_version':1,'minimum_tags':[],'additional_tags':['ar']},
                     {'format_version':1,'minimum_tags':['en','EN'],'additional_tags':['ar']}):
            with patch('specroad.storage.language_packages._read',return_value=encoded(data)), self.assertRaises(ModelError):
                minimum_language_corpus()

    def test_invalid_activated_sequence_and_entries_rejected(self):
        for active in ('en@1.0.0',{},[None],['en@'],[True]):
            with self.assertRaises(ModelError): packages_for_language('en',activated=active)
