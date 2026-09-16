"""Actual byte binding and complete current-resource sets, not presentation."""

from dataclasses import FrozenInstanceError
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from specroad.model.attachments import AttachmentDescriptor
from specroad.model.errors import ModelError
from specroad.model.hashes import canonical_json_sha256
from specroad.security import SafetyViolation
from specroad.storage.attachments import inspect_attachment, verify_attachment, verify_attachments, fingerprint_file
from specroad.storage.inventory import inventory_project
from specroad.storage.project import ProjectSource
from support.artifacts import artifact_bytes, common_artifact
from support.model import configuration_file, put
from support.portable import files_under


def descriptor(path='attachments/report.bin', content=b'\x00\xffsample', media='application/octet-stream'):
    return AttachmentDescriptor(path, media, len(content), sha256(content).hexdigest())


def evidence(root, descriptors, *, token='0' * 26):
    value = common_artifact('evidence', 'EVD', id='SR-EVD-' + token,
                            attachments=[item.data for item in descriptors])
    name = 'spec/evidence/' + value['id'] + '.json'
    put(root, name, artifact_bytes(value))
    return name


class ResourceWorkTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        configuration_file(self.root)
        self.source = ProjectSource(self.root)

    def test_inspect_binds_real_binary_bytes(self):
        content = b'\x00\xffsample'; item = descriptor(content=content)
        put(self.root, item.path, content)
        self.assertEqual(inspect_attachment(self.source, item.path, item.media_type), item)

    def test_empty_attachment_is_not_missing(self):
        item=descriptor(content=b'');put(self.root,item.path,b'')
        self.assertEqual(verify_attachment(self.source,item),item)

    def test_descriptor_requires_every_declared_field(self):
        original=descriptor().data
        for field in original:
            value=dict(original);value.pop(field)
            with self.subTest(field=field),self.assertRaises(ModelError):AttachmentDescriptor.from_data(value)

    def test_descriptor_rejects_unknown_fields(self):
        value=descriptor().data;value['shell']='do not execute'
        with self.assertRaises(ModelError):AttachmentDescriptor.from_data(value)

    def test_descriptor_rejects_bad_sizes_without_coercion(self):
        for size in (True,-1,1.0,'10',None):
            with self.subTest(size=size),self.assertRaises(ModelError):AttachmentDescriptor('attachments/a','text/plain',size,'0'*64)

    def test_descriptor_rejects_incomplete_or_uppercase_hashes(self):
        for value in ('A'*64,'x'*64,'f'*63,None):
            with self.subTest(value=value),self.assertRaises(ModelError):AttachmentDescriptor('attachments/a','text/plain',0,value)

    def test_descriptor_rejects_unsafe_relative_paths(self):
        for path in ('../a','/tmp/a','attachments/../a','attachments\\a','.git/config','attachments/CON'):
            with self.subTest(path=path),self.assertRaises(ModelError):descriptor(path)

    def test_descriptor_rejects_invalid_media_text(self):
        for media in ('',' ',None,'text/plain\nInjected: true','\ud800'):
            with self.subTest(media=repr(media)),self.assertRaises(ModelError):descriptor(media=media)

    def test_media_type_is_declared_not_guessed_from_suffix(self):
        item=descriptor('attachments/image.png',b'not a PNG','application/custom')
        put(self.root,item.path,b'not a PNG');self.assertEqual(verify_attachment(self.source,item),item)

    def test_declared_size_mismatch_is_an_error(self):
        item=descriptor();put(self.root,item.path,b'changed')
        with self.assertRaises(ModelError) as caught:verify_attachment(self.source,item)
        self.assertEqual(caught.exception.reason,'attachment_size_mismatch')

    def test_same_size_byte_tampering_is_an_error(self):
        item=descriptor(content=b'ab');put(self.root,item.path,b'cd')
        with self.assertRaises(ModelError) as caught:verify_attachment(self.source,item)
        self.assertEqual(caught.exception.reason,'attachment_hash_mismatch')

    def test_missing_payload_is_not_a_pass(self):
        with self.assertRaises(FileNotFoundError):verify_attachment(self.source,descriptor())

    def test_generated_and_operational_bytes_are_not_attachments(self):
        for path in ('generated/a','.specroad/cache/a','profiles/a.json','archive/objects/ab/'+'ab'*32):
            put(self.root,path,b'a')
            with self.subTest(path=path),self.assertRaises(ModelError):inspect_attachment(self.source,path,'text/plain')

    def test_external_symlink_is_not_read(self):
        outside=self.root/'secret';outside.write_bytes(b'secret');(self.root/'attachments').mkdir()
        (self.root/'attachments/a').symlink_to(outside)
        with self.assertRaises(SafetyViolation):inspect_attachment(self.source,'attachments/a','text/plain')
        self.assertEqual(outside.read_bytes(),b'secret')

    def test_internal_symlink_is_also_conservatively_rejected(self):
        put(self.root,'attachments/real',b'a');(self.root/'attachments/link').symlink_to('real')
        with self.assertRaises(SafetyViolation):inspect_attachment(self.source,'attachments/link','text/plain')

    def test_batch_verifies_complete_explicit_set(self):
        a=descriptor('attachments/a',b'a');b=descriptor('attachments/b',b'b')
        for item,content in ((a,b'a'),(b,b'b')):put(self.root,item.path,content)
        self.assertEqual(verify_attachments(self.source,(b,a)),(a,b))

    def test_batch_rejects_duplicate_paths(self):
        item=descriptor()
        with self.assertRaises(ModelError):verify_attachments(self.source,(item,item))

    def test_batch_missing_member_does_not_return_partial_result(self):
        item=descriptor();put(self.root,item.path,b'\x00\xffsample')
        with self.assertRaises(FileNotFoundError):verify_attachments(self.source,(item,descriptor('attachments/z')))

    def test_fingerprinting_is_blockwise_and_independent_of_chunk_size(self):
        content=b'abc\x00\xff'*20000;put(self.root,'attachments/a',content)
        from specroad.storage import attachments
        sizes=[];real_read=attachments.os.read
        def reading(fd,size):sizes.append(size);return real_read(fd,size)
        with patch.object(attachments.os,'read',side_effect=reading):
            result=fingerprint_file(self.source.boundary,'attachments/a',block_size=127)
        self.assertGreater(len(sizes),2);self.assertLessEqual(max(sizes),127)
        self.assertEqual(result.size,len(content));self.assertEqual(result.sha256,sha256(content).hexdigest())
        self.assertEqual(result,fingerprint_file(self.source.boundary,'attachments/a'))

    def test_minimal_project_inventory_includes_configuration(self):
        result=inventory_project(self.source)
        self.assertEqual([entry.path for entry in result.entries],['specroad.json'])
        self.assertFalse(result.atomic_snapshot)
        self.assertEqual(result.entries[0].sha256,sha256((self.root/'specroad.json').read_bytes()).hexdigest())

    def test_inventory_covers_all_normative_json_trees(self):
        artifact=common_artifact();path='spec/goals/'+artifact['id']+'.json';put(self.root,path,artifact_bytes(artifact))
        for name in ('profiles/nested/p.json','rules/r.json','mappings/m.json'):put(self.root,name,b'{"schema_version":"0.2.0"}')
        result=inventory_project(self.source)
        self.assertEqual({entry.path for entry in result.entries},{'specroad.json',path,'profiles/nested/p.json','rules/r.json','mappings/m.json'})
        self.assertEqual(next(e for e in result.entries if e.path==path).canonical_sha256,canonical_json_sha256(artifact))

    def test_inventory_automatically_verifies_evidence_attachments(self):
        item=descriptor();put(self.root,item.path,b'\x00\xffsample');name=evidence(self.root,(item,))
        result=inventory_project(self.source)
        self.assertEqual({entry.path for entry in result.entries},{'specroad.json',name,item.path})
        entry=next(entry for entry in result.entries if entry.path==item.path)
        self.assertEqual((entry.size,entry.sha256,entry.media_type),(item.size,item.sha256,item.media_type))
        self.assertIsNone(entry.canonical_sha256)

    def test_inventory_ignores_unreferenced_generated_archive_and_operational_data(self):
        expected=inventory_project(self.source).data
        for name in ('attachments/unreferenced','generated/a.json','.specroad/transactions/live','archive/objects/ab/'+'ab'*32,'src/other'):
            put(self.root,name,b'not json')
        self.assertEqual(inventory_project(self.source).data,expected)

    def test_inventory_accepts_explicit_additional_attachment_set(self):
        item=descriptor();put(self.root,item.path,b'\x00\xffsample')
        result=inventory_project(self.source,attachments=(item,))
        self.assertEqual({entry.path for entry in result.entries},{'specroad.json',item.path})

    def test_same_attachment_in_two_evidences_is_counted_once(self):
        item=descriptor();put(self.root,item.path,b'\x00\xffsample');evidence(self.root,(item,));evidence(self.root,(item,),token='1'*26)
        result=inventory_project(self.source)
        self.assertEqual(sum(entry.path==item.path for entry in result.entries),1)

    def test_conflicting_attachment_declarations_are_not_guessed(self):
        item=descriptor();evidence(self.root,(item,));evidence(self.root,(descriptor(media='text/plain'),),token='1'*26)
        with self.assertRaises(ModelError) as caught:inventory_project(self.source)
        self.assertEqual(caught.exception.reason,'conflicting_attachment_declarations')

    def test_inventory_preserves_project_and_returns_independent_values(self):
        item=descriptor();put(self.root,item.path,b'\x00\xffsample');evidence(self.root,(item,));before=files_under(self.root)
        result=inventory_project(self.source);data=result.data;data['resources'].clear()
        self.assertTrue(result.entries);self.assertEqual(files_under(self.root),before)
        with self.assertRaises(FrozenInstanceError):item.size=10
        self.assertEqual(result.sha256,inventory_project(self.source).sha256)

    def test_paths_inside_extensions_are_never_followed(self):
        value=common_artifact(extensions={'org.example.extra':{'attachments':[descriptor().data]}})
        put(self.root,'spec/goals/'+value['id']+'.json',artifact_bytes(value))
        self.assertEqual(len(inventory_project(self.source).entries),2)
