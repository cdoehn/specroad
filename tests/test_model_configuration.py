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
