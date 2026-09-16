"""Resource races, failure completeness and read-only portability regressions."""

from dataclasses import FrozenInstanceError
import errno
from hashlib import sha256
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from specroad.model.attachments import AttachmentDescriptor
from specroad.model.errors import ModelError
from specroad.security import SafetyViolation
from specroad.storage.attachments import inspect_attachment, verify_attachments, fingerprint_file
from specroad.storage.inventory import inventory_project, check_inventory_current
from specroad.storage.project import ProjectSource
from support.artifacts import artifact_bytes, common_artifact
from support.model import configuration_file, put
from support.portable import build_distribution, files_under
from test_resource_inventory import descriptor, evidence

RAW=b'{"schema_version":"0.2.0","value":1}'


class ResourceRightTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name);configuration_file(self.root);self.source=ProjectSource(self.root)

    def test_inventory_recheck_accepts_the_same_observation(self):
        put(self.root,'profiles/p.json',RAW);result=inventory_project(self.source)
        self.assertIsNone(check_inventory_current(self.source,result))

    def test_inventory_recheck_detects_added_json_resource(self):
        result=inventory_project(self.source);put(self.root,'rules/new.json',RAW)
        with self.assertRaises(ModelError) as caught:check_inventory_current(self.source,result)
        self.assertEqual(caught.exception.reason,'inventory_changed')

    def test_inventory_recheck_detects_removed_resource(self):
        path=put(self.root,'rules/r.json',RAW);result=inventory_project(self.source);path.unlink()
        with self.assertRaises(ModelError):check_inventory_current(self.source,result)

    def test_byte_sensitive_inventory_is_not_confused_with_canonical_model_hash(self):
        path=put(self.root,'rules/r.json',RAW);old=inventory_project(self.source)
        path.write_bytes(b'{ "value": 1, "schema_version": "0.2.0" }\n');new=inventory_project(self.source)
        a=next(e for e in old.entries if e.path=='rules/r.json');b=next(e for e in new.entries if e.path=='rules/r.json')
        self.assertEqual(a.canonical_sha256,b.canonical_sha256);self.assertNotEqual(a.sha256,b.sha256)
        self.assertNotEqual(old.sha256,new.sha256)
        with self.assertRaises(ModelError):check_inventory_current(self.source,old)

    def test_recheck_rejects_same_project_id_on_a_different_root(self):
        result=inventory_project(self.source)
        other=self.root/'other';other.mkdir();configuration_file(other)
        self.assertEqual(inventory_project(ProjectSource(other)).sha256,result.sha256)
        with self.assertRaises(ModelError):check_inventory_current(ProjectSource(other),result)

    def test_changed_project_configuration_invalidates_source(self):
        result=inventory_project(self.source);configuration_file(self.root,project_id='changed')
        with self.assertRaises(ModelError) as caught:check_inventory_current(self.source,result)
        self.assertEqual(caught.exception.reason,'configuration_changed')

    def test_replaced_root_does_not_silently_rebind(self):
        result=inventory_project(self.source)
        parent=self.root/'source';parent.mkdir();configuration_file(parent);source=ProjectSource(parent)
        before=inventory_project(source);parent.rename(self.root/'saved');parent.mkdir();configuration_file(parent)
        with self.assertRaises(SafetyViolation):check_inventory_current(source,before)
        self.assertEqual(result.project_id,'sample')

    def test_explicit_attachment_declarations_remain_part_of_recheck(self):
        item=descriptor(content=b'a');put(self.root,item.path,b'a');result=inventory_project(self.source,attachments=(item,))
        self.assertIsNone(check_inventory_current(self.source,result));(self.root/item.path).write_bytes(b'b')
        with self.assertRaises(ModelError):check_inventory_current(self.source,result)

    def test_unreferenced_changes_do_not_invalidate_current_inventory(self):
        result=inventory_project(self.source)
        for name in ('generated/x','.specroad/recovery/live','attachments/unused','archive/objects/ab/'+'ab'*32):put(self.root,name,b'x')
        self.assertIsNone(check_inventory_current(self.source,result))

    def test_managed_subtree_restriction_and_overlaps_are_complete(self):
        configuration_file(self.root,managed_paths=['profiles/a','profiles/a/sub','attachments'])
        put(self.root,'profiles/a/p.json',RAW);put(self.root,'profiles/a/sub/q.json',RAW);put(self.root,'profiles/other.json',b'bad')
        result=inventory_project(ProjectSource(self.root))
        self.assertEqual({e.path for e in result.entries},{'specroad.json','profiles/a/p.json','profiles/a/sub/q.json'})

    def test_managed_single_file_must_actually_exist(self):
        configuration_file(self.root,managed_paths=['rules/missing.json'])
        with self.assertRaises(FileNotFoundError):inventory_project(ProjectSource(self.root))

    def test_empty_and_missing_optional_trees_are_supported(self):
        (self.root/'rules').mkdir()
        self.assertEqual(len(inventory_project(self.source).entries),1)

    def test_duplicate_explicit_declarations_are_rejected(self):
        item=descriptor()
        with self.assertRaises(ModelError):inventory_project(self.source,attachments=(item,item))

    def test_bad_attachment_sequences_do_not_become_empty_success(self):
        for value in (None,'attachments/file',{},[{}]):
            with self.subTest(value=value),self.assertRaises(ModelError):inventory_project(self.source,attachments=value)
            with self.subTest(batch=value),self.assertRaises(ModelError):verify_attachments(self.source,value)

    def test_duplicate_evidence_attachment_paths_are_rejected(self):
        item=descriptor();evidence(self.root,(item,item))
        with self.assertRaises(ModelError):inventory_project(self.source)

    def test_unknown_attachment_descriptor_fields_are_not_ignored(self):
        value=common_artifact('evidence','EVD',attachments=[dict(descriptor().data,other=True)])
        put(self.root,'spec/evidence/'+value['id']+'.json',artifact_bytes(value))
        with self.assertRaises(ModelError):inventory_project(self.source)

    def test_case_colliding_payload_paths_are_rejected(self):
        a=descriptor('attachments/a',b'a');b=descriptor('attachments/A',b'a')
        for item in (a,b):put(self.root,item.path,b'a')
        with self.assertRaises(ModelError):verify_attachments(self.source,(a,b))
        with self.assertRaises(ModelError):inventory_project(self.source,attachments=(a,b))

    def test_case_colliding_normative_paths_are_rejected(self):
        put(self.root,'rules/a.json',RAW);put(self.root,'rules/A.json',RAW)
        with self.assertRaises(SafetyViolation):inventory_project(self.source)

    def test_deep_malformed_artifact_path_does_not_disappear_from_inventory(self):
        put(self.root,'spec/goals/nested/not-an-artifact.json',RAW)
        with self.assertRaises(ModelError) as caught:inventory_project(self.source)
        self.assertEqual(caught.exception.reason,'unclassified_normative_json')

    def test_artifact_path_and_identity_must_match(self):
        value=common_artifact();value['id']='SR-GOAL-'+'1'*26
        put(self.root,'spec/goals/SR-GOAL-'+'0'*26+'.json',artifact_bytes(value))
        with self.assertRaises(ModelError):inventory_project(self.source)

    def test_json_syntax_and_version_errors_abort_the_inventory(self):
        for raw in (b'[]',b'{"x":1,"x":2}',b'{}',b'{"schema_version":"99.0.0"}'):
            put(self.root,'rules/r.json',raw)
            with self.subTest(raw=raw.decode()),self.assertRaises(ModelError):inventory_project(self.source)

    def test_nested_project_under_normative_tree_is_rejected(self):
        nested=self.root/'profiles/nested';nested.mkdir(parents=True);configuration_file(nested)
        with self.assertRaises(SafetyViolation):inventory_project(self.source)

    def test_nested_project_under_attachments_is_rejected(self):
        nested=self.root/'attachments';nested.mkdir();configuration_file(nested);(nested/'a').write_bytes(b'a')
        with self.assertRaises(SafetyViolation):inspect_attachment(self.source,'attachments/a','text/plain')

    def test_linked_managed_directory_is_not_traversed(self):
        outside=self.root/'outside';outside.mkdir();put(outside,'a.json',RAW);(self.root/'rules').symlink_to(outside,target_is_directory=True)
        with self.assertRaises(SafetyViolation):inventory_project(self.source)

    def test_dangling_link_is_not_treated_as_missing_optional_directory(self):
        (self.root/'rules').symlink_to('missing')
        with self.assertRaises(SafetyViolation):inventory_project(self.source)

    def test_special_payload_is_rejected_without_blocking(self):
        (self.root/'attachments').mkdir();os.mkfifo(self.root/'attachments/pipe')
        with self.assertRaises(SafetyViolation):inspect_attachment(self.source,'attachments/pipe','application/octet-stream')

    def test_payload_replaced_during_read_is_rejected(self):
        path=put(self.root,'attachments/a',b'abc');real_read=os.read;done=False
        def reading(fd,size):
            nonlocal done
            result=real_read(fd,size)
            if not done:
                done=True;path.rename(self.root/'attachments/saved');path.write_bytes(b'abc')
            return result
        with patch.object(os,'read',side_effect=reading),self.assertRaises(SafetyViolation):
            inspect_attachment(self.source,'attachments/a','text/plain')

    def test_payload_changed_in_place_during_read_is_rejected(self):
        path=put(self.root,'attachments/a',b'abc');real_read=os.read;done=False
        def reading(fd,size):
            nonlocal done
            result=real_read(fd,size)
            if not done:done=True;path.write_bytes(b'abcdef')
            return result
        with patch.object(os,'read',side_effect=reading),self.assertRaises(SafetyViolation):inspect_attachment(self.source,'attachments/a','text/plain')

    def test_continuous_growth_is_detected_without_unbounded_reads(self):
        put(self.root,'attachments/a',b'abc');calls=[]
        def reading(fd,size):calls.append(size);return b'x'*4
        with patch.object(os,'read',side_effect=reading),self.assertRaises(SafetyViolation):inspect_attachment(self.source,'attachments/a','text/plain')
        self.assertEqual(len(calls),1)

    def test_nested_root_added_during_payload_read_is_detected(self):
        put(self.root,'attachments/a',b'abc');real_read=os.read;done=False
        def reading(fd,size):
            nonlocal done
            value=real_read(fd,size)
            if not done:done=True;configuration_file(self.root/'attachments')
            return value
        with patch.object(os,'read',side_effect=reading),self.assertRaises(SafetyViolation):inspect_attachment(self.source,'attachments/a','text/plain')

    def test_read_error_closes_all_owned_descriptors(self):
        put(self.root,'attachments/a',b'a');opened=[];real_open=os.open
        def opening(*args,**kwargs):fd=real_open(*args,**kwargs);opened.append(fd);return fd
        with patch.object(os,'open',side_effect=opening),patch.object(os,'read',side_effect=OSError(errno.EIO,'injected')):
            with self.assertRaises(OSError):fingerprint_file(self.source.boundary,'attachments/a')
        for fd in opened:
            with self.assertRaises(OSError):os.fstat(fd)

    def test_invalid_block_size_is_rejected_before_file_io(self):
        for size in (0,-1,True,1.5,1048577):
            with self.subTest(size=size),self.assertRaises(ValueError):fingerprint_file(self.source.boundary,'attachments/missing',block_size=size)

    def test_json_change_after_read_is_detected_on_final_recheck(self):
        from specroad.storage import inventory
        path=put(self.root,'rules/r.json',RAW);read=inventory._read_json_entry
        def loading(source,name):
            result=read(source,name)
            if name=='rules/r.json':path.write_bytes(b'{"schema_version":"0.2.0","value":2}')
            return result
        with patch.object(inventory,'_read_json_entry',side_effect=loading),self.assertRaises(ModelError) as caught:inventory_project(self.source)
        self.assertEqual(caught.exception.reason,'inventory_resource_changed')

    def test_resource_added_after_scan_is_detected(self):
        from specroad.storage import inventory
        scan=inventory._scan_json_paths;calls=0
        def scanning(source):
            nonlocal calls
            result=scan(source);calls+=1
            if calls==1:put(self.root,'rules/new.json',RAW)
            return result
        with patch.object(inventory,'_scan_json_paths',side_effect=scanning),self.assertRaises(ModelError) as caught:inventory_project(self.source)
        self.assertEqual(caught.exception.reason,'inventory_membership_changed')

    def test_disappearing_entry_during_listing_is_not_silently_omitted(self):
        from specroad.security import resource_access
        path=put(self.root,'rules/a.json',RAW);listing=os.listdir;done=False
        def names(fd):
            nonlocal done
            result=listing(fd)
            if 'a.json' in result and not done:done=True;path.unlink()
            return result
        with patch.object(resource_access.os,'listdir',side_effect=names),self.assertRaises(FileNotFoundError):inventory_project(self.source)

    def test_permission_error_during_enumeration_is_not_an_empty_tree(self):
        from specroad.security import resource_access
        (self.root/'rules').mkdir()
        with patch.object(resource_access.os,'listdir',side_effect=PermissionError(errno.EACCES,'injected')):
            with self.assertRaises(PermissionError):inventory_project(self.source)

    def test_missing_secure_open_support_fails_closed(self):
        from specroad.security import paths
        put(self.root,'attachments/a',b'a')
        with patch.object(paths,'_HAS_SAFE_OPEN',False),self.assertRaises(OSError):fingerprint_file(self.source.boundary,'attachments/a')

    def test_configured_registry_bytes_are_included_and_hash_verified(self):
        content=b'registry fixture\n';name='profiles/language-data/registry.txt';put(self.root,name,content)
        registry={'registry_id':'iana-language-subtags','registry_version':'2026-01-01','path':name,'sha256':sha256(content).hexdigest()}
        configuration_file(self.root,language_registry=registry);source=ProjectSource(self.root);result=inventory_project(source)
        entry=next(e for e in result.entries if e.path==name);self.assertEqual(entry.kind,'language_registry');self.assertEqual(entry.size,len(content))
        self.assertIsNone(entry.canonical_sha256)
        (self.root/name).write_bytes(b'changed')
        with self.assertRaises(ModelError) as caught:inventory_project(source)
        self.assertEqual(caught.exception.reason,'registry_hash_mismatch')

    def test_missing_configured_registry_is_not_ignored(self):
        registry={'registry_id':'iana-language-subtags','registry_version':'2026-01-01','path':'profiles/language-data/missing.txt','sha256':'a'*64}
        configuration_file(self.root,language_registry=registry)
        with self.assertRaises(FileNotFoundError):inventory_project(ProjectSource(self.root))

    def test_reference_changes_are_bound_even_with_unchanged_payload_bytes(self):
        item=descriptor();put(self.root,item.path,b'\x00\xffsample');path=evidence(self.root,(item,));old=inventory_project(self.source)
        value=json.loads((self.root/path).read_bytes());value['attachments'][0]['media_type']='text/plain';(self.root/path).write_bytes(artifact_bytes(value))
        with self.assertRaises(ModelError):check_inventory_current(self.source,old)

    def test_no_network_shell_subprocess_or_project_write(self):
        item=descriptor();put(self.root,item.path,b'\x00\xffsample');evidence(self.root,(item,));before=files_under(self.root)
        with patch.object(socket,'getaddrinfo',side_effect=AssertionError('DNS')),patch.object(socket,'create_connection',side_effect=AssertionError('network')),patch.object(subprocess,'Popen',side_effect=AssertionError('process')),patch.object(os,'system',side_effect=AssertionError('shell')):
            result=inventory_project(self.source);self.assertEqual(len(result.entries),3)
        self.assertEqual(before,files_under(self.root))

    def test_moved_module_and_zipapp_use_same_read_only_inventory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);build=root/'build';build_distribution(build);moved=root/'moved';build.rename(moved)
            project=root/'project';project.mkdir();configuration_file(project);put(project,'attachments/a',b'abc');before=files_under(project)
            code=("import sys;sys.path.insert(0,sys.argv[1]);from specroad.storage.project import ProjectSource; "
                  "from specroad.storage.attachments import inspect_attachment; "
                  "from specroad.storage.inventory import inventory_project,check_inventory_current; "
                  "s=ProjectSource(sys.argv[2]);a=inspect_attachment(s,'attachments/a','text/plain'); "
                  "i=inventory_project(s,attachments=(a,));assert len(i.entries)==2 and a.size==3; "
                  "assert not i.atomic_snapshot;check_inventory_current(s,i)")
            for path in (moved/'module',moved/'specroad.pyz'):
                process=subprocess.run([sys.executable,'-I','-S','-B','-c',code,str(path),str(project)],cwd=root,stdin=subprocess.DEVNULL,capture_output=True)
                self.assertEqual(process.returncode,0,process.stderr)
            self.assertEqual(files_under(project),before)

    def test_symlink_to_bytes_outside_the_project_never_reads_payload(self):
        with tempfile.TemporaryDirectory() as outside:
            secret=Path(outside)/'secret';secret.write_bytes(b'outside secret')
            (self.root/'attachments').mkdir();(self.root/'attachments/link').symlink_to(secret)
            with patch.object(os,'read',side_effect=AssertionError('payload read')),self.assertRaises(SafetyViolation):
                inspect_attachment(self.source,'attachments/link','text/plain')
            self.assertEqual(secret.read_bytes(),b'outside secret')

    def test_directory_with_json_suffix_is_still_traversed(self):
        put(self.root,'profiles/directory.json/p.json',RAW)
        self.assertIn('profiles/directory.json/p.json',{e.path for e in inventory_project(self.source).entries})

    def test_configured_directory_with_json_suffix_is_not_opened_as_file(self):
        configuration_file(self.root,managed_paths=['profiles/directory.json'])
        put(self.root,'profiles/directory.json/p.json',RAW)
        self.assertEqual({e.path for e in inventory_project(ProjectSource(self.root)).entries},
                         {'specroad.json','profiles/directory.json/p.json'})

    def test_configured_single_json_file_is_included(self):
        configuration_file(self.root,managed_paths=['profiles/p.json']);put(self.root,'profiles/p.json',RAW)
        self.assertEqual({e.path for e in inventory_project(ProjectSource(self.root)).entries},
                         {'specroad.json','profiles/p.json'})

    def test_directory_disappearing_after_classification_is_an_error(self):
        from specroad.storage import resource_discovery
        put(self.root,'rules/a.json',RAW);classify=resource_discovery.resource_is_directory
        def inspecting(boundary,path,**kwargs):
            result=classify(boundary,path,**kwargs)
            if path=='rules':(self.root/'rules').rename(self.root/'saved-rules')
            return result
        with patch.object(resource_discovery,'resource_is_directory',side_effect=inspecting),self.assertRaises(FileNotFoundError):
            inventory_project(self.source)
