"""Project schema and path behavior, never documentation or terminal appearance."""

from pathlib import Path
import tempfile
import unittest

from specroad.model import ProjectConfiguration, PathClass, ModelError, artifact_path, classify_path
from specroad.storage import ProjectSource
from support.model import configuration_value, configuration_file, put


class ConfigurationWorkTests(unittest.TestCase):
    def test_required_fields_and_unknown_fields_are_rejected(self):
        for field in configuration_value():
            with self.subTest(field=field):
                value = configuration_value(); value.pop(field)
                with self.assertRaises(ModelError):
                    ProjectConfiguration(value)
        with self.assertRaises(ModelError):
            ProjectConfiguration(configuration_value(unknown=True))

    def test_prefix_boundaries(self):
        for value in ('AB', 'A0', 'ABCDEFG8'):
            self.assertEqual(ProjectConfiguration(configuration_value(id_prefix=value)).id_prefix, value)
        for value in ('A', 'abcdefgh', 'ABCDEFGHI', '0A', 'A-', '../AB', True, ['AB']):
            with self.subTest(value=value), self.assertRaises(ModelError):
                ProjectConfiguration(configuration_value(id_prefix=value))

    def test_configuration_owns_its_nested_data(self):
        original = configuration_value()
        config = ProjectConfiguration(original)
        original['managed_paths'].clear()
        copy = config.data; copy['validation_policy']['fail_on'] = 'info'
        self.assertEqual(config.data, configuration_value())

    def test_unsupported_version_reports_highest_reader(self):
        with self.assertRaises(ModelError) as caught:
            ProjectConfiguration(configuration_value(schema_version='99.0.0'))
        self.assertEqual(caught.exception.highest_supported, '0.2.0')

    def test_configuration_is_required_at_the_selected_root(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaises(FileNotFoundError): ProjectSource(root)
            child=root/'child';child.mkdir();configuration_file(child)
            with self.assertRaises(FileNotFoundError): ProjectSource(root)
            self.assertEqual(ProjectSource(child).configuration.project_id, 'sample')

    def test_explicit_resource_load_excludes_non_normative_data(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);configuration_file(root)
            path='spec/requirements/SR-REQ-0001.json';put(root,path,b'{"schema_version":"0.2.0"}')
            put(root,'generated/changed.json',b'invalid');put(root,'.specroad/cache/index.json',b'invalid')
            source=ProjectSource(root)
            self.assertEqual(dict(source.load_resources([path])), {path:(root/path).read_bytes()})
            for name in ('generated/changed.json','.specroad/cache/index.json'):
                with self.assertRaises(ModelError): source.read_normative(name)

    def test_payload_requires_an_explicit_reference(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);configuration_file(root);put(root,'attachments/input.bin',b'payload')
            source=ProjectSource(root)
            with self.assertRaises(ModelError): source.read_normative('attachments/input.bin')
            self.assertEqual(source.read_normative('attachments/input.bin', referenced_payloads=('attachments/input.bin',)),b'payload')

    def test_artifact_address_binds_type_and_project_prefix(self):
        self.assertEqual(artifact_path('requirement','SR-REQ-0001','SR'),'spec/requirements/SR-REQ-0001.json')
        self.assertEqual(artifact_path('goal','SR-GOAL-'+'0'*26,'SR'),'spec/goals/SR-GOAL-'+'0'*26+'.json')
        for kind, identity in [('requirement','XX-REQ-0001'),('goal','SR-REQ-0001'),('unknown','SR-REQ-0001'),('goal','SR-GOAL-../x')]:
            with self.subTest(identity=identity),self.assertRaises(ModelError): artifact_path(kind,identity,'SR')

    def test_standard_path_classes_are_disjoint(self):
        config=ProjectConfiguration(configuration_value())
        rows={'specroad.json':PathClass.CONFIGURATION,'spec/requirements/SR-REQ-0001.json':PathClass.ARTIFACT,
              'profiles/core.json':PathClass.PROFILE,'rules/check.json':PathClass.RULE,'mappings/csv.json':PathClass.MAPPING,
              'attachments/input':PathClass.ATTACHMENT,'generated/a.json':PathClass.GENERATED,
              '.specroad/cache/a':PathClass.CACHE,'.specroad/recovery/a':PathClass.RECOVERY,
              '.specroad/transactions/staging/a':PathClass.RECOVERY,
              '.specroad/transactions/receipts/a':PathClass.RECEIPT,'.specroad/requests/a':PathClass.RECEIPT,
              '.specroad/locks/a':PathClass.OPERATIONAL,'src/main.py':PathClass.UNMANAGED}
        for path,kind in rows.items():
            with self.subTest(path=path): self.assertEqual(classify_path(path,config),kind)

    def test_write_authorization_never_writes_and_rejects_escapes(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);configuration_file(root);before=(root/'specroad.json').read_bytes()
            source=ProjectSource(root)
            self.assertEqual(source.require_write_target('spec/requirements/SR-REQ-0001.json'),PathClass.ARTIFACT)
            for name in ('../outside.json','/tmp/out.json','specification/a.json','generated/a.json','.specroad/cache/a'):
                with self.subTest(path=name),self.assertRaises(ModelError): source.require_write_target(name)
            self.assertEqual(list(root.iterdir()),[root/'specroad.json'])
            self.assertEqual((root/'specroad.json').read_bytes(),before)

    def test_configuration_paths_cannot_mix_generated_and_normative_classes(self):
        for generated in ('spec', 'spec/reports', '.specroad', 'profiles/core', '../out'):
            with self.subTest(generated=generated),self.assertRaises(ModelError):
                ProjectConfiguration(configuration_value(generated_path=generated))
        for managed in (['.specroad'], ['generated'], ['specroad.json'], ['spec','SPEC'],['../out']):
            with self.subTest(managed=managed),self.assertRaises(ModelError):
                ProjectConfiguration(configuration_value(managed_paths=managed))

    def test_invalid_value_types_are_not_coerced(self):
        for key,value in [('project_id',[]),('project_name',' '),('profiles','core'),('managed_paths','spec'),('validation_policy',[]),('extensions',[]),('generated_path',False)]:
            with self.subTest(key=key),self.assertRaises(ModelError):
                ProjectConfiguration(configuration_value(**{key:value}))


class ConfigurationRightTests(unittest.TestCase):
    def test_standard_addresses_cover_all_declared_types(self):
        types = [('goal','goals','GOAL'),('need','needs','NEED'),('capability','capabilities','CAP'),
                 ('requirement','requirements','REQ'),('scenario','scenarios','SCN'),('decision','decisions','DEC'),
                 ('risk','risks','RISK'),('assumption','assumptions','ASM'),('component','components','COMP'),
                 ('interface','interfaces','IFC'),('source','sources','SRC'),('verification','verifications','VER'),
                 ('test','tests','TEST'),('evidence','evidence','EVD'),('release','releases','REL'),
                 ('milestone','milestones','MS'),('task','tasks','TASK'),('term','terms','TERM'),
                 ('proposal','proposals','PROP'),('baseline','baselines','BASE'),('issue','issues','ISSUE'),
                 ('document','documents','DOC'),('section','sections','SEC'),('content_block','content-blocks','BLOCK'),
                 ('view','views','VIEW'),('code_ref','code-refs','CODE'),('relation_review','relation-reviews','RREV'),
                 ('configuration','configurations','CFG')]
        config=ProjectConfiguration(configuration_value())
        for kind,directory,prefix in types:
            identity='SR-'+prefix+'-'+'0'*26
            path='spec/'+directory+'/'+identity+'.json'
            with self.subTest(kind=kind):
                self.assertEqual(artifact_path(kind,identity,'SR'),path)
                self.assertEqual(classify_path(path,config),PathClass.ARTIFACT)

    def test_custom_generated_directory_and_managed_subtrees(self):
        config=ProjectConfiguration(configuration_value(generated_path='build/docs',managed_paths=['spec/requirements']))
        self.assertEqual(classify_path('build/docs/a.json',config),PathClass.GENERATED)
        self.assertEqual(classify_path('spec/goals/SR-GOAL-0001.json',config),PathClass.UNMANAGED)
        self.assertEqual(classify_path('spec/requirements-other/a.json',config),PathClass.UNMANAGED)

    def test_archive_addresses_require_a_consistent_hash_shard(self):
        config=ProjectConfiguration(configuration_value());token='ab'+'0'*62
        self.assertEqual(classify_path('archive/objects/ab/'+token,config),PathClass.ARCHIVE_OBJECT)
        self.assertEqual(classify_path('archive/objects/cd/'+token,config),PathClass.UNMANAGED)

    def test_duplicate_paths_and_scalar_path_sequences_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);configuration_file(root);source=ProjectSource(root)
            for paths in (['specroad.json','specroad.json'],'specroad.json',[True],None):
                with self.subTest(paths=paths),self.assertRaises(ModelError): source.load_resources(paths)

    def test_payload_reference_is_not_a_substring_permission(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);configuration_file(root);put(root,'attachments/a',b'a');source=ProjectSource(root)
            with self.assertRaises(ModelError): source.read_normative('attachments/a',referenced_payloads='attachments/abc')

    def test_changed_configuration_invalidates_reads_and_write_authorization(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);configuration_file(root);put(root,'profiles/a.json');source=ProjectSource(root)
            configuration_file(root,project_id='replacement')
            for operation in (lambda:source.read_normative('profiles/a.json'),lambda:source.require_write_target('profiles/b.json'),lambda:source.load_resources([])):
                with self.assertRaises(ModelError) as caught: operation()
                self.assertEqual(caught.exception.reason,'configuration_changed')

    def test_foreign_project_identity_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);configuration_file(root)
            with self.assertRaises(ModelError):ProjectSource(root,expected_project_id='other')
            self.assertEqual(ProjectSource(root,expected_project_id='sample').configuration.project_id,'sample')

    def test_nested_roots_and_symlinks_are_rejected_for_read_and_write(self):
        from specroad.security import SafetyViolation
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);configuration_file(root);source=ProjectSource(root)
            nested=root/'profiles';nested.mkdir();configuration_file(nested);put(root,'profiles/a.json')
            with self.assertRaises(SafetyViolation):source.read_normative('profiles/a.json')
            with self.assertRaises(ModelError):source.require_write_target('profiles/new.json')
            real=root/'real';real.mkdir();(root/'rules').symlink_to(real,target_is_directory=True)
            put(root,'real/a.json')
            with self.assertRaises(SafetyViolation):source.read_normative('rules/a.json')
            with self.assertRaises(ModelError):source.require_write_target('rules/new.json')
            self.assertFalse((real/'new.json').exists())

    def test_generated_and_recovery_changes_do_not_change_loaded_resource_set(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);configuration_file(root);put(root,'rules/a.json',b'{"schema_version":"0.2.0"}')
            source=ProjectSource(root);before=source.load_resources(['specroad.json','rules/a.json'])
            for path in ('generated/a.json','.specroad/transactions/live','.specroad/requests/done','attachments/not-referenced','archive/objects/bad'):
                put(root,path,b'not JSON')
            self.assertEqual(source.load_resources(['rules/a.json','specroad.json']),before)

    def test_policy_declarations_validate_without_resolving_or_executing(self):
        value=configuration_value(profiles=['core@0.2.0'],language_packages=['de@1.0.0'],
                                  transaction_policy={'auto_recover':True,'retain_receipts':True},
                                  srx_policy={'numeric_policy_version':'srx-decimal-v1','decimal_precision':1000},
                                  resource_limits={'model_bytes':1})
        self.assertEqual(ProjectConfiguration(value).data,value)
        for changes in ({'profiles':['../../plugin']},{'transaction_policy':{'retain_receipts':False}},
                        {'validation_policy':{'fail_on':'never'}},{'srx_policy':{'decimal_precision':True}},
                        {'resource_limits':{'model_bytes':False}},{'validation_policy':{'unexpected':True}}):
            with self.subTest(changes=changes),self.assertRaises(ModelError):ProjectConfiguration(configuration_value(**changes))

    def test_registry_binding_is_managed_and_no_file_is_invented(self):
        registry={'registry_id':'iana-language-subtags','registry_version':'2026-01-01',
                  'path':'profiles/language-data/registry.txt','sha256':'0'*64}
        self.assertEqual(ProjectConfiguration(configuration_value(language_registry=registry)).data['language_registry'],registry)
        for path in ('../registry','generated/registry','attachments/registry'):
            with self.subTest(path=path),self.assertRaises(ModelError):
                ProjectConfiguration(configuration_value(language_registry=dict(registry,path=path)))

    def test_unsafe_portable_names_are_rejected(self):
        config=ProjectConfiguration(configuration_value())
        for path in ('spec/../a','spec//a','spec/./a','spec/a\\b','C:/a','profiles/CON.json','profiles/a.','profiles/a ','profiles/*.json','.git/config'):
            with self.subTest(path=path),self.assertRaises(ModelError):classify_path(path,config)
