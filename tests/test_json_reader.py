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


class JsonReaderRightTests(unittest.TestCase):
    def test_lossy_numbers_are_never_silently_rounded(self):
        for token in ('9007199254740993','1000000000000000128','1.0000000000000001',
                      '0.1234567890123456789','1e-400','1e400','-1e400'):
            with self.subTest(token=token), self.assertRaises(ModelError) as caught:
                parse_json_object(('{"payload":['+token+']}').encode(), path='profiles/a.json')
            self.assertEqual(caught.exception.pointer,'/payload/0')
            self.assertEqual(caught.exception.path,'profiles/a.json')

    def test_exact_roundtrip_uses_decimal_spelling_not_float_expansion(self):
        for token in ('0.1','0.3000','1e23','100000000000000000000000','9007199254740992',
                      '9007199254740994','1e-300','5e-324','-0','-0.0','1.7976931348623157e308'):
            with self.subTest(token=token):
                value=parse_json_object(('{"n":'+token+'}').encode())['n']
                self.assertEqual(float(value),float(token))
        self.assertIs(type(parse_json_object(b'{"n":2}')['n']),int)
        self.assertIs(type(parse_json_object(b'{"n":2.0}')['n']),float)

    def test_decimal_context_cannot_change_number_acceptance(self):
        from decimal import localcontext, Inexact, Rounded
        raw=b'{"n":0.1234567890123456}'
        with localcontext() as context:
            context.prec=2;context.traps[Inexact]=True;context.traps[Rounded]=True
            self.assertEqual(parse_json_object(raw)['n'],0.1234567890123456)
            with self.assertRaises(ModelError):parse_json_object(b'{"n":0.123456789012345678}')
            self.assertEqual(context.prec,2)

    def test_duplicate_unescaped_keys_report_the_nested_json_pointer(self):
        raw=b'{"payload":[{"a/b~":1,"a\\u002fb~":2}]}'
        with self.assertRaises(ModelError) as caught:parse_json_object(raw)
        self.assertEqual(caught.exception.pointer,'/payload/0/a~1b~0')
        self.assertEqual(caught.exception.reason,'duplicate_key')

    def test_nonfinite_literals_have_nested_locations(self):
        for token in ('NaN','Infinity','-Infinity','1e999'):
            with self.subTest(token=token),self.assertRaises(ModelError) as caught:
                parse_json_object(('{"nested":{"n":'+token+'}}').encode())
            self.assertEqual(caught.exception.reason,'nonfinite_number')
            self.assertEqual(caught.exception.pointer,'/nested/n')

    def test_invalid_utf8_after_multibyte_prefix_has_a_byte_offset(self):
        prefix='{"文字":"'.encode('utf-8')
        with self.assertRaises(ModelError) as caught:parse_json_object(prefix+b'\xff"}')
        self.assertEqual(caught.exception.position,len(prefix))

    def test_number_syntax_and_trailing_documents_are_not_repaired(self):
        for raw in (b'{"n":01}',b'{"n":+1}',b'{"n":1.}',b'{"n":.1}',b'{"n":1e}',
                    b'{}\n{}',b'{}\0',b'{"a":1,}',b'/*comment*/{}'):
            with self.subTest(raw=raw),self.assertRaises(ModelError):parse_json_object(raw)

    def test_invalid_json_never_calls_the_resource_validator(self):
        called=[]
        schema=ResourceSchema('fixture',PathClass.PROFILE,{'schema_version','x'},set(),
                              validator=lambda value:called.append(value))
        for raw in (b'{"schema_version":"0.2.0","x":1,"x":2}',
                    b'{"schema_version":"0.2.0","x":1.0000000000000001}',
                    b'{"schema_version":"0.2.0","x":"\\ud800"}'):
            with self.assertRaises(ModelError):JsonResource(raw,schema)
        self.assertEqual(called,[])

    def test_closed_descriptor_owns_sets_and_orders_versions_numerically(self):
        fields={'schema_version','title'};required={'title'};versions=['0.10.0','0.2.0']
        schema=ResourceSchema('fixture',PathClass.PROFILE,fields,required,versions)
        fields.add('extra');required.clear();versions.clear()
        self.assertEqual(schema.supported_versions,('0.2.0','0.10.0'))
        with self.assertRaises(ModelError) as caught:JsonResource(b'{"schema_version":"0.3.0","title":"x"}',schema)
        self.assertEqual(caught.exception.highest_supported,'0.10.0')
        with self.assertRaises(ModelError):JsonResource(b'{"schema_version":"0.2.0","title":"x","extra":1}',schema)

    def test_malformed_trusted_descriptors_are_rejected(self):
        for versions in ([],['future'],['01.2.0'],['0.2.0','0.2.0'],['0.2.0',2]):
            with self.subTest(versions=versions),self.assertRaises(ValueError):
                ResourceSchema('fixture',PathClass.PROFILE,{'schema_version'},set(),versions)
        with self.assertRaises(ValueError):ResourceSchema('fixture',PathClass.PROFILE,{'schema_version'},set(),validator='shell')
        with self.assertRaises(ValueError):ResourceSchema('fixture',PathClass.PROFILE,{'schema_version'},{'missing'})

    def test_request_shape_and_duplicates_are_validated_before_reads(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);configuration_file(root);source=ProjectSource(root)
            for case, requests in enumerate(('profiles/a.json',None,{},[('profiles/a.json',)],[(42,PROFILE)],
                             [('profiles/a.json',object())],[('profiles/a.json',PROFILE)]*2)):
                with self.subTest(case=case),self.assertRaises(ModelError):read_resources(source,requests)

    def test_empty_resource_request_still_checks_the_configuration_binding(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);configuration_file(root);source=ProjectSource(root)
            self.assertEqual(read_resources(source,[]),())
            configuration_file(root,project_name='Changed')
            with self.assertRaises(ModelError):read_resources(source,[])

    def test_configuration_change_during_validation_cannot_publish_a_resource(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);configuration_file(root);source=ProjectSource(root)
            put(root,'profiles/a.json',b'{"schema_version":"0.2.0","title":"a"}')
            def changed(value):configuration_file(root,project_name='Concurrent edit')
            schema=ResourceSchema('fixture',PathClass.PROFILE,PROFILE.allowed_fields,PROFILE.required_fields,validator=changed)
            with self.assertRaises(ModelError) as caught:read_resource(source,'profiles/a.json',schema)
            self.assertEqual(caught.exception.reason,'configuration_changed')

    def test_direct_configuration_api_rejects_lossy_integer_values(self):
        from specroad.model import ProjectConfiguration
        value=configuration_value();value['extensions']={'test.number':9007199254740993}
        with self.assertRaises(ModelError):ProjectConfiguration(value)
        value['extensions']['test.number']=9007199254740994
        self.assertEqual(ProjectConfiguration(value).data['extensions']['test.number'],9007199254740994)

    def test_deep_input_is_a_controlled_rejection_not_a_partial_model(self):
        raw=b'{"value":'+b'['*2500+b'0'+b']'*2500+b'}'
        with self.assertRaises(ModelError):parse_json_object(raw)

    def test_malformed_input_never_becomes_diagnostic_source_content(self):
        secret='PRIVATE-TEST-DATA-717171'
        with self.assertRaises(ModelError) as caught:
            parse_json_object(('{"value":"'+secret+'",}').encode(),path='profiles/a.json')
        diagnostic=caught.exception.diagnostic()
        self.assertEqual(set(diagnostic),{'reason','path','pointer','position','line','column','highest_supported'})
        self.assertEqual(diagnostic['reason'],'invalid_json')
        self.assertNotIn(secret,json.dumps(diagnostic))

    def test_loaded_set_keeps_order_and_data_ownership(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);configuration_file(root)
            for name in ('a','b'):put(root,'profiles/'+name+'.json',json.dumps({'schema_version':'0.2.0','title':name}).encode())
            result=read_resources(ProjectSource(root),[(f'profiles/{name}.json',PROFILE) for name in ('b','a')])
            self.assertEqual(tuple(item.data['title'] for item in result),('b','a'))
            result[0].data['title']='modified'
            self.assertEqual(result[0].data['title'],'b')

    def test_registry_binding_rejects_nonexistent_dates(self):
        from specroad.model import ProjectConfiguration
        for day in ('2026-02-30','2026-13-01','0000-01-01'):
            value=configuration_value();value['language_registry']={'registry_id':'iana-language-subtags',
                'registry_version':day,'path':'profiles/language-data/iana.txt','sha256':'a'*64}
            with self.subTest(day=day),self.assertRaises(ModelError):ProjectConfiguration(value)
