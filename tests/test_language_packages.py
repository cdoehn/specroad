"""Metadata/label package contracts; translated display text is not an oracle."""
from dataclasses import FrozenInstanceError
from hashlib import sha256
from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from specroad.model.errors import ModelError
from specroad.model.content_language import ContentLanguage
from specroad.model.language_packages import (LanguagePackage, LanguagePackageError,
    range_matches, select_language_packages)
from specroad.storage.language_packages import (bundled_package_index, load_bundled_package,
    packages_for_language, minimum_language_corpus)
from specroad.cli.language_labels import label_for, labels_for_locale
from specroad.model.requirement import prepare_requirement
from specroad.model.audit import Actor, UtcTimestamp
from specroad.model.identity_values import ArtifactIdentity
from support.portable import build_distribution, files_under

IDS = ('de', 'en', 'hi', 'id', 'pt', 'es', 'ru', 'ja', 'zh-Hans')
KEYS = tuple(k + '@1.0.0' for k in IDS)
MINIMUM = ('en-US', 'en-IN', 'hi-IN', 'id-ID', 'pt-BR', 'es-MX', 'ru-RU',
           'ja-JP', 'de-DE', 'zh-Hans-CN', 'cmn-Hans-CN')
TEXT = 'e\u0301 é 日本語 हिन्दी 中文 العربية اردو \u2067rtl\u2069'


def package_data(**changes):
    value = {'package_id': 'example', 'version': '1.0.0', 'language_ranges': ['en'],
             'labels': {}, 'literal_rules': [], 'capabilities': ['metadata', 'labels']}
    value.update(changes)
    return value


def encoded(value):
    return json.dumps(value, ensure_ascii=False).encode('utf-8')


def draft_for(language, text=TEXT):
    return prepare_requirement({'title': 'Example', 'requirement_kind': 'functional',
        'language': language, 'normative_force': 'may', 'statement': text,
        'priority': 'low', 'criticality': 'normal'},
        identity=ArtifactIdentity('SR-REQ-'+'0'*26, 'random128-v1', 'requirement', 'SR'),
        actor=Actor('human','author'), planned_at=UtcTimestamp('2026-09-17T00:00:00Z'))


class LanguagePackageWorkTests(unittest.TestCase):
    def test_nine_explicit_distribution_packages(self):
        entries = bundled_package_index()
        self.assertEqual([e['package_id'] for e in entries], list(IDS))
        self.assertEqual({e['version'] for e in entries}, {'1.0.0'})

    def test_each_package_matches_byte_binding(self):
        for key in KEYS:
            with self.subTest(key=key):
                package = load_bundled_package(key)
                self.assertEqual(package.sha256, sha256(package.source_bytes).hexdigest())
                self.assertEqual(package.key, key)

    def test_minimum_corpus_is_separate_from_allowlist(self):
        self.assertEqual(minimum_language_corpus()['minimum_tags'], list(MINIMUM))
        self.assertEqual(draft_for('fr-CA').data['language'], 'fr-CA')

    def test_all_minimum_tags_select_metadata(self):
        for tag in MINIMUM:
            with self.subTest(tag=tag):
                result = packages_for_language(tag, activated=KEYS)
                self.assertEqual(len(result.packages), 1)
                self.assertEqual(result.language, tag)
                self.assertEqual(result.as_dict()['labels'], 'available')

    def test_all_minimum_tags_support_unmodified_utf8(self):
        with patch('locale.setlocale', side_effect=AssertionError('No host locale')):
            for tag in MINIMUM:
                with self.subTest(tag=tag):
                    self.assertEqual(draft_for(tag).data['statement'], TEXT)

    def test_additional_tags_remain_metadata_without_a_pack(self):
        for tag in minimum_language_corpus()['additional_tags']:
            with self.subTest(tag=tag):
                result = packages_for_language(tag, activated=KEYS)
                self.assertEqual(result.packages, ())
                self.assertEqual(draft_for(tag).data['statement'], TEXT)

    def test_chinese_package_has_two_distinct_ranges(self):
        p = load_bundled_package('zh-Hans@1.0.0')
        self.assertEqual(p.language_ranges, ('zh-Hans', 'cmn-Hans'))
        self.assertNotEqual(draft_for('zh-Hans-CN').data['language'], draft_for('cmn-Hans-CN').data['language'])

    def test_no_inferred_chinese_script(self):
        for tag in ('zh', 'zh-CN', 'cmn', 'zh-Hant'):
            self.assertEqual(packages_for_language(tag, activated=KEYS).packages, ())

    def test_no_automatic_activation_or_io(self):
        with patch('specroad.storage.language_packages._read', side_effect=AssertionError('No IO')):
            result = packages_for_language('de-DE')
        self.assertEqual(result.packages, ())

    def test_only_matching_activated_package_is_read(self):
        import specroad.storage.language_packages as storage
        old_read = storage._read
        seen = []
        def read(filename):
            seen.append(filename)
            if filename not in ('packages.json','packages/en.json'):
                raise AssertionError('Unrelated package loaded')
            return old_read(filename)
        with patch.object(storage, '_read', side_effect=read):
            self.assertEqual(len(packages_for_language('en-IN', activated=KEYS).packages), 1)
        self.assertEqual(seen, ['packages.json','packages/en.json'])

    def test_explicit_missing_package_is_unavailable(self):
        result = packages_for_language('fr', activated=['fr@1.0.0'])
        self.assertEqual(result.unavailable, ('fr@1.0.0',))
        self.assertEqual(result.as_dict()['labels'], 'not_available')
        self.assertEqual(draft_for('fr').data['language'], 'fr')

    def test_no_linguistic_capability_is_claimed(self):
        report = packages_for_language('en', activated=KEYS).as_dict()
        self.assertEqual((report['lint'],report['detector'],report['metadata_policy']),
                         ('not_available','not_available','not_evaluated'))
        for key in KEYS:
            self.assertEqual(load_bundled_package(key).data['literal_rules'], [])

    def test_unknown_package_version_is_not_silently_upgraded(self):
        with self.assertRaises(LanguagePackageError): load_bundled_package('en@2.0.0')
        self.assertEqual(packages_for_language('en',activated=['en@2.0.0']).packages, ())

    def test_only_six_declared_fields(self):
        p = load_bundled_package('de@1.0.0')
        self.assertEqual(set(p.data), {'package_id','version','language_ranges','labels','literal_rules','capabilities'})

    def test_package_is_immutable(self):
        p = load_bundled_package('de@1.0.0')
        with self.assertRaises(FrozenInstanceError): p.version = '2.0.0'

    def test_returned_data_is_detached(self):
        p = load_bundled_package('en@1.0.0'); before = p.source_bytes
        p.data['labels'].clear(); p.binding()['language_ranges'].append('*')
        self.assertEqual(p.source_bytes, before)
        self.assertEqual(p.language_ranges, ('en',))

    def test_basic_range_boundaries(self):
        self.assertTrue(range_matches('en', 'en-US'))
        self.assertFalse(range_matches('en', 'enm'))
        self.assertFalse(range_matches('en-US', 'en'))

    def test_basic_range_case_insensitive(self):
        self.assertTrue(range_matches('EN', 'eN-uS'))

    def test_no_language_alias_expansion(self):
        self.assertFalse(range_matches('zh', 'cmn-Hans-CN'))
        self.assertFalse(range_matches('he', 'iw'))

    def test_wildcard_accepts_valid_private_and_unknown_tags(self):
        for tag in ('x-project','zzzz','und'):
            self.assertTrue(range_matches('*', tag))

    def test_unknown_label_falls_back_to_exact_enum(self):
        self.assertEqual(label_for('not_started',domain='implementation_status',packages=[load_bundled_package('de@1.0.0')]), 'not_started')
        self.assertEqual(label_for('future_enum',domain='unknown'), 'future_enum')

    def test_labels_are_not_a_text_interpreter(self):
        p = LanguagePackage(encoded(package_data(labels={'normative_force': {'must': 'os.system("touch owned")'}})))
        with tempfile.TemporaryDirectory() as tmp:
            before = files_under(Path(tmp))
            label_for('must',domain='normative_force',packages=[p])
            self.assertEqual(files_under(Path(tmp)),before)
        self.assertEqual(draft_for('en',text='should must darf').data['normative_force'], 'may')

    def test_display_locale_is_not_requirement_language(self):
        before = draft_for('hi-IN').data
        packages = labels_for_locale('de-DE',activated=KEYS)
        self.assertEqual(tuple(p.package_id for p in packages), ('de',))
        self.assertEqual(draft_for('hi-IN').data, before)

    def test_language_and_direction_do_not_imply_each_other(self):
        self.assertEqual(ContentLanguage('ar').text_direction, 'auto')
        self.assertEqual(ContentLanguage('en','rtl').language, 'en')
        self.assertEqual(ContentLanguage('ja','ltr').text_direction, 'ltr')

    def test_direction_metadata_preserves_original_tag(self):
        self.assertEqual(ContentLanguage('EN-us').as_dict()['language'], 'EN-us')

    def test_direction_is_never_a_detection_result(self):
        value = ContentLanguage('ur-IN','rtl').as_dict()
        self.assertFalse(value['language_detected']); self.assertFalse(value['direction_detected'])
        self.assertIsNone(ContentLanguage().language)

    def test_invalid_direction_is_rejected(self):
        for value in ('RTL','',None,True,'right-to-left'):
            with self.assertRaises(ModelError): ContentLanguage('en',value)

    def test_invalid_language_not_made_valid_by_wildcard(self):
        with self.assertRaises(ModelError): range_matches('*','en_US')

    def test_callbacks_and_import_paths_cannot_be_fields(self):
        for key in ('callback','import_path','module','command'):
            with self.assertRaises(ModelError): LanguagePackage(encoded(package_data(**{key:'os.system'})))

    def test_no_network_for_pack_loading(self):
        with patch('socket.socket',side_effect=AssertionError('Network forbidden')):
            self.assertEqual(packages_for_language('ja',activated=KEYS).packages[0].package_id,'ja')

    def test_pure_selection_preserves_explicit_order(self):
        a=LanguagePackage(encoded(package_data(package_id='broad',language_ranges=['*'])))
        b=LanguagePackage(encoded(package_data(package_id='english')))
        self.assertEqual(select_language_packages('en',[b,a]),(b,a))

    def test_relocatable_distributions_ship_same_package_bytes(self):
        expected=[load_bundled_package(key).sha256 for key in KEYS]
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); build_distribution(root/'dist'); (root/'dist').rename(root/'moved')
            script=('import sys,json;sys.path.insert(0,sys.argv[1]);'
                    'from specroad.storage.language_packages import bundled_package_index,load_bundled_package;'
                    'print(json.dumps([load_bundled_package(e["package_id"]+"@"+e["version"]).sha256 for e in bundled_package_index()]))')
            for target in (root/'moved/module',root/'moved/specroad.pyz'):
                proc=subprocess.run([sys.executable,'-I','-B','-c',script,str(target)],cwd=root,
                    stdin=subprocess.DEVNULL,capture_output=True,check=True)
                self.assertEqual(json.loads(proc.stdout),expected)
