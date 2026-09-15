"""JSON bytes and typed-resource contracts; no pretty/output snapshots."""

from pathlib import Path
import json
import tempfile
import unittest

from specroad.model import ModelError, PathClass
from specroad.storage import ProjectSource
from specroad.storage.json_reader import (parse_json_object, ResourceSchema, JsonResource,
                                          configuration_schema, read_resource, read_resources)
from support.model import configuration_value, configuration_file, put

# A deliberately tiny trusted fixture schema, not a product profile schema.
PROFILE = ResourceSchema('fixture_profile',PathClass.PROFILE,
                         frozenset({'schema_version','title','payload'}),frozenset({'title'}))


class JsonReaderWorkTests(unittest.TestCase):
    def test_utf8_object_returns_its_original_values(self):
        value={'title':'中文 e\u0301 العربية','list':[1,True,None,{'x':'ñ'}]}
        self.assertEqual(parse_json_object(json.dumps(value,ensure_ascii=False).encode()),value)

    def test_invalid_utf8_is_rejected_with_a_position(self):
        with self.assertRaises(ModelError) as caught:parse_json_object(b'{"title":"\xff"}',path='profiles/a.json')
        self.assertEqual(caught.exception.reason,'invalid_utf8')
        self.assertEqual(caught.exception.position,10)
        self.assertEqual(caught.exception.path,'profiles/a.json')

    def test_syntax_errors_have_machine_readable_positions(self):
        raw=b'{\n  "a": }'
        with self.assertRaises(ModelError) as caught:parse_json_object(raw,path='profiles/a.json')
        error=caught.exception
        self.assertEqual((error.position,error.line,error.column),(9,2,8))
        self.assertEqual(error.path,'profiles/a.json')

    def test_only_one_object_is_accepted(self):
        for raw in (b'[]',b'null',b'true',b'1',b'"value"',b'{} {}',b'{} trailing',b''):
            with self.subTest(raw=raw),self.assertRaises(ModelError):parse_json_object(raw)

    def test_duplicates_and_nonfinite_numbers_are_rejected(self):
        for raw in (b'{"a":1,"a":2}',b'{"a":{"b":1,"b":2}}',b'{"a":NaN}',b'{"a":Infinity}',b'{"a":1e999}'):
            with self.subTest(raw=raw),self.assertRaises(ModelError):parse_json_object(raw)

    def test_closed_resource_schema_is_not_a_loose_object_loader(self):
        for value in ({'schema_version':'0.2.0'}, {'schema_version':'0.2.0','title':'x','extra':1}):
            with self.subTest(value=value),self.assertRaises(ModelError):JsonResource(json.dumps(value).encode(),PROFILE)

    def test_schema_versions_do_not_implicitly_upgrade(self):
        for version in ('0.1.0','0.2.1',0.2,None,['0.2.0']):
            with self.subTest(version=version),self.assertRaises(ModelError) as caught:
                JsonResource(json.dumps({'schema_version':version,'title':'x'}).encode(),PROFILE)
            self.assertEqual(caught.exception.highest_supported,'0.2.0')

    def test_typed_resource_retains_bytes_and_returns_owned_values(self):
        raw=b' {"schema_version":"0.2.0","title":"x","payload":{"a":[1]}}\r\n'
        resource=JsonResource(raw,PROFILE,path='profiles/a.json')
        copy=resource.data;copy['payload']['a'].append(2)
        self.assertEqual(resource.data['payload'],{'a':[1]})
        self.assertEqual(resource.source_bytes,raw)
        self.assertEqual((resource.kind,resource.schema_version),('fixture_profile','0.2.0'))

    def test_real_configuration_load_uses_the_closed_descriptor(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);value=configuration_file(root)
            resource=read_resource(ProjectSource(root),'specroad.json',configuration_schema())
            self.assertEqual(resource.data,value)
            configuration_file(root,unknown='value')
            with self.assertRaises(ModelError):ProjectSource(root)

    def test_resource_path_class_is_bound_before_file_read(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);configuration_file(root);put(root,'generated/a.json',b'{}')
            with self.assertRaises(ModelError):read_resource(ProjectSource(root),'generated/a.json',PROFILE)

    def test_failed_resource_set_has_no_partial_file_effects(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);configuration_file(root)
            put(root,'profiles/a.json',b'{"schema_version":"0.2.0","title":"a"}')
            put(root,'profiles/b.json',b'invalid')
            before={p.relative_to(root).as_posix():p.read_bytes() for p in root.rglob('*') if p.is_file()}
            with self.assertRaises(ModelError):read_resources(ProjectSource(root),[('profiles/a.json',PROFILE),('profiles/b.json',PROFILE)])
            self.assertEqual({p.relative_to(root).as_posix():p.read_bytes() for p in root.rglob('*') if p.is_file()},before)

    def test_unpaired_surrogates_and_bom_are_rejected(self):
        for raw in (b'{"value":"\\ud800"}',b'{"\\udfff":1}',b'\xef\xbb\xbf{}'):
            with self.subTest(raw=raw),self.assertRaises(ModelError):parse_json_object(raw)
        self.assertEqual(parse_json_object(b'{"value":"\\ud83d\\ude00"}')['value'],'😀')
