"""Boundary completeness, project provenance, races and runtime independence."""
from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from specroad.model.configuration import ProjectConfiguration
from specroad.model.errors import ModelError
from specroad.model.model_manifest import (ManifestResource, ProjectReadBinding, assemble_model_manifest)
from specroad.model.semantic_configuration import semantic_configuration, SOFT_LIMITS
from specroad.security import SafetyViolation
from specroad.storage.model_root import capture_model_inputs, check_model_inputs_current, prepare_model_root
from specroad.storage.project import ProjectSource
from support.artifacts import artifact_bytes, common_artifact
from support.model import configuration_file, configuration_value, put
from test_model_root import scope, fixture

ROOT = Path(__file__).resolve().parents[1]


def boundary(source, *, relation="0", target="1", **overrides):
    value = {"source_id":source,"relation_id":"REL-"+relation*26,"relation_type":"conflicts_with",
             "target_id":"SR-GOAL-"+target*26,"target_type":"goal","reason":"weak_external_reference",
             "origin_target_sha256":"a"*64}
    value.update(overrides)
    return value


class ModelRootRightTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.path,self.value=fixture(self.root)
        self.source=ProjectSource(self.root)

    def build(self, *, policy="closed", boundaries=(), source=None, profile=None):
        return prepare_model_root(source or self.source,[self.path],
                                  scope_descriptor=scope([self.value["id"]],policy=policy),
                                  effective_profile={} if profile is None else profile,
                                  boundary_references=boundaries)

    def test_boundary_content_and_origin_hash_change_both_hashes(self):
        ref=boundary(self.value["id"])
        a=self.build(policy="partial",boundaries=[ref])
        b=self.build(policy="partial",boundaries=[{**ref,"origin_target_sha256":"b"*64}])
        self.assertNotEqual(a.sha256,b.sha256);self.assertNotEqual(a.scope_sha256,b.scope_sha256)
        self.assertFalse(a.boundary_relationships_verified)

    def test_boundary_order_uses_utf8_source_relation_target(self):
        a=boundary(self.value["id"],relation="1");b=boundary(self.value["id"],relation="0",target="2")
        x=self.build(policy="partial",boundaries=[a,b]);y=self.build(policy="partial",boundaries=[b,a])
        self.assertEqual(x.sha256,y.sha256);self.assertEqual(x.data['boundary_references'],[b,a])

    def test_boundary_without_relation_id_can_bind_a_non_edge_origin(self):
        ref=boundary(self.value["id"]);ref.pop('relation_id')
        self.assertEqual(self.build(policy="partial",boundaries=[ref]).data['boundary_references'],[ref])

    def test_closed_scope_rejects_boundaries(self):
        with self.assertRaises(ModelError):self.build(boundaries=[boundary(self.value["id"])])

    def test_duplicate_boundary_tuples_are_rejected(self):
        ref=boundary(self.value["id"])
        with self.assertRaises(ModelError):self.build(policy="partial",boundaries=[ref,ref])

    def test_boundary_source_must_be_included(self):
        with self.assertRaises(ModelError):self.build(policy="partial",boundaries=[boundary('SR-GOAL-'+'2'*26)])

    def test_boundary_target_must_not_be_included(self):
        with self.assertRaises(ModelError):self.build(policy="partial",boundaries=[boundary(self.value["id"],target="0")])

    def test_strong_relation_cannot_be_weakened_to_boundary(self):
        for kind in ('depends_on','refines','references','unknown',None):
            with self.subTest(kind=kind),self.assertRaises(ModelError):
                self.build(policy='partial',boundaries=[boundary(self.value['id'],relation_type=kind)])

    def test_boundary_target_type_and_id_must_agree(self):
        with self.assertRaises(ModelError):self.build(policy="partial",boundaries=[boundary(self.value["id"],target_type='requirement')])

    def test_boundary_hash_and_relation_id_require_full_identity(self):
        for values in ({'origin_target_sha256':'a'*63},{'relation_id':'REL-123'},{'relation_id':None}):
            with self.subTest(values=values),self.assertRaises(ModelError):
                self.build(policy='partial',boundaries=[boundary(self.value['id'],**values)])

    def test_boundary_unknown_fields_and_missing_metadata_rejected(self):
        ref=boundary(self.value['id'])
        for field in ref:
            if field=='relation_id':continue
            value=dict(ref);value.pop(field)
            with self.subTest(field=field),self.assertRaises(ModelError):self.build(policy='partial',boundaries=[value])
        with self.assertRaises(ModelError):self.build(policy='partial',boundaries=[{**ref,'runtime':'ignored?'}])

    def test_bad_boundary_containers_rejected_even_if_empty(self):
        for values in ('',b'',{},None):
            with self.subTest(kind=type(values).__name__),self.assertRaises(ModelError):self.build(boundaries=values)

    def test_semantic_and_hard_limits_survive_soft_projection(self):
        for field in ('artifact_file_bytes','xml_depth','json_depth','srx_depth','srx_nodes','trace_depth','query_default_limit','archive_uncompressed_bytes'):
            a=ProjectConfiguration(configuration_value(resource_limits={field:10}))
            b=ProjectConfiguration(configuration_value(resource_limits={field:11}))
            with self.subTest(field=field):self.assertNotEqual(semantic_configuration(a),semantic_configuration(b))

    def test_every_known_soft_target_is_excluded(self):
        a=ProjectConfiguration(configuration_value())
        b=ProjectConfiguration(configuration_value(resource_limits={name:1 for name in SOFT_LIMITS}))
        self.assertEqual(semantic_configuration(a),semantic_configuration(b))

    def test_semantic_policy_changes_are_included(self):
        before=self.build().sha256
        configuration_file(self.root,language_policy={'default_language':'en'})
        self.assertNotEqual(before,self.build(source=ProjectSource(self.root)).sha256)

    def test_runtime_like_extension_fields_are_not_recursively_stripped(self):
        a=ProjectConfiguration(configuration_value(extensions={'org.example':{'runtime':'a','color':'red','path':'/important'}}))
        b=ProjectConfiguration(configuration_value(extensions={'org.example':{'runtime':'b','color':'red','path':'/important'}}))
        self.assertNotEqual(semantic_configuration(a),semantic_configuration(b))

    def test_display_and_recovery_switch_leave_model_root_unchanged(self):
        before=self.build().sha256
        configuration_file(self.root,default_locale='tr',generated_path='views',transaction_policy={'auto_recover':False,'retain_receipts':True})
        self.assertEqual(before,self.build(source=ProjectSource(self.root)).sha256)

    def test_generated_cache_receipts_and_workpaths_are_not_loaded(self):
        before=self.build().sha256
        for name in ('generated/view.json','.specroad/cache/cache.json','.specroad/transactions/journal','.specroad/requests/receipt','scratch/external-work'):
            put(self.root,name,b'not even JSON')
        self.assertEqual(before,self.build().sha256)

    def test_local_provenance_is_not_in_manifest(self):
        result=self.build()
        self.assertNotIn(str(self.root),json.dumps(result.data))
        self.assertEqual(result.data['project_id'],self.source.configuration.project_id)

    def test_deleted_project_configuration_is_not_recreated(self):
        (self.root/'specroad.json').unlink()
        with self.assertRaises(FileNotFoundError):self.build()
        self.assertFalse((self.root/'specroad.json').exists())

    def test_project_relocation_requires_fresh_read_binding(self):
        before=self.build().sha256;captured=capture_model_inputs(self.source,[self.path])
        with tempfile.TemporaryDirectory() as other:
            moved=Path(other)/'moved';self.root.rename(moved)
            try:
                fresh=ProjectSource(moved)
                self.assertEqual(before,self.build(source=fresh).sha256)
                with self.assertRaises(ModelError):check_model_inputs_current(fresh,captured)
            finally:moved.rename(self.root)

    def test_selected_symlink_is_not_followed(self):
        original=(self.root/self.path).read_bytes();(self.root/self.path).unlink()
        outside=self.root/'private';outside.write_bytes(original);(self.root/self.path).symlink_to(outside)
        with self.assertRaises(SafetyViolation):self.build()
        self.assertEqual(outside.read_bytes(),original)

    def test_nested_project_is_not_merged(self):
        nested=self.root/'profiles/nested';nested.mkdir(parents=True);configuration_file(nested)
        put(nested,'r.json',b'{"schema_version":"0.2.0","profile_id":"p","profile_version":"1.0.0"}')
        with self.assertRaises(SafetyViolation):capture_model_inputs(self.source,['profiles/nested/r.json'])

    def test_modification_after_assembly_is_detected_before_return(self):
        from specroad.storage import model_root
        real=model_root.assemble_model_manifest
        def changed(*a,**kw):
            result=real(*a,**kw);put(self.root,self.path,artifact_bytes({**self.value,'title':'race'}));return result
        with patch.object(model_root,'assemble_model_manifest',side_effect=changed),self.assertRaises(ModelError):self.build()

    def test_modification_during_capture_is_detected(self):
        from specroad.storage import model_root
        real=model_root._json_resource
        def changed(*a,**kw):
            result=real(*a,**kw);put(self.root,self.path,b'{}');return result
        with patch.object(model_root,'_json_resource',side_effect=changed),self.assertRaises(ModelError):self.build()

    def test_foreign_project_id_inside_resource_rejected(self):
        put(self.root,'profiles/p.json',b'{"schema_version":"0.2.0","profile_id":"p","profile_version":"1.0.0","project_id":"foreign"}')
        with self.assertRaises(ModelError):capture_model_inputs(self.source,['profiles/p.json'])

    def test_foreign_project_profile_projection_rejected(self):
        with self.assertRaises(ModelError):self.build(profile={'project_id':'other'})

    def test_duplicate_resource_identity_in_two_files_rejected(self):
        value={'schema_version':'0.2.0','mapping_id':'csv','mapping_version':'1.0.0'}
        put(self.root,'mappings/a.json',artifact_bytes(value));put(self.root,'mappings/b.json',artifact_bytes(value))
        with self.assertRaises(ModelError):prepare_model_root(self.source,['mappings/a.json','mappings/b.json'],scope_descriptor=scope(),effective_profile={})

    def test_conflicting_resource_version_metadata_rejected(self):
        put(self.root,'rules/a.json',b'{"schema_version":"0.2.0","rule_id":"r","rule_version":"1.0.0","version":"2.0.0"}')
        with self.assertRaises(ModelError):capture_model_inputs(self.source,['rules/a.json'])

    def test_configured_registry_bytes_are_bound_and_required(self):
        from support.languages import registry_bytes
        # Test helper below uses a minimal valid explicit registry, not a bundled fallback.
        raw=registry_bytes()
        from specroad.model.language_registry import LanguageRegistry
        from specroad.storage.language_registry import registry_binding
        from hashlib import sha256
        registry=LanguageRegistry(raw, expected_sha256=sha256(raw).hexdigest(), expected_version="2020-01-01");ref=registry_binding(registry)
        configuration_file(self.root,language_registry=ref);put(self.root,ref['path'],raw)
        source=ProjectSource(self.root);result=self.build(source=source)
        self.assertTrue(any(r['kind']=='language_registry' and r['sha256']==registry.sha256 for r in result.data['resources']))
        (self.root/ref['path']).unlink()
        with self.assertRaises(ModelError):self.build(source=source)

    def test_unsupported_scope_does_not_silently_become_project(self):
        captured=capture_model_inputs(self.source,[self.path])
        for bad in (scope(kind='query'),{**scope(),'configuration_id':'SR-CFG-'+'0'*26},{**scope(),'runtime':{}}, {**scope(),'scope_kind':[]}):
            with self.assertRaises(ModelError):assemble_model_manifest(self.source.configuration,captured.binding,captured.resources,
                scope_descriptor=bad,effective_profile={})

    def test_semantic_configuration_projection_returns_owned_data(self):
        config=ProjectConfiguration(configuration_value(extensions={'org.example':{'values':[1]}}))
        value=semantic_configuration(config);value['extensions']['org.example']['values'].append(2)
        self.assertEqual(config.data['extensions']['org.example']['values'],[1])

    def test_locale_timezone_and_work_environment_do_not_change_model(self):
        script='''import sys,json,locale,time
sys.path[:0]=[sys.argv[1]+"/src",sys.argv[1]+"/tests"]
from specroad.storage.model_root import prepare_model_root
from specroad.storage.project import ProjectSource
from test_model_root import scope
locale.setlocale=lambda *a,**kw: (_ for _ in ()).throw(RuntimeError("no host locale"))
if hasattr(time,"tzset"):time.tzset()
x=prepare_model_root(ProjectSource(sys.argv[2]),[sys.argv[3]],scope_descriptor=scope(),effective_profile={})
print(json.dumps({"hash":x.sha256,"scope":x.scope_sha256,"data":x.data}))
'''
        values=[]
        for loc,tz in (('C','UTC0'),('tr_TR.not-installed','JST-9')):
            env=dict(os.environ,LANG=loc,LC_ALL=loc,TZ=tz,NO_COLOR='1',SPECROAD_WORK_DIR='/external/runtime')
            result=subprocess.run([sys.executable,'-I','-B','-c',script,str(ROOT),str(self.root),self.path],
                                  env=env,cwd=self.root,stdin=subprocess.DEVNULL,capture_output=True,check=True)
            values.append(json.loads(result.stdout))
        self.assertEqual(values[0],values[1])

    def test_manifest_services_work_in_moved_portable_distributions(self):
        from support.portable import build_distribution
        out=self.root/'distribution';build_distribution(out);moved=self.root/'moved-distribution';out.rename(moved)
        expected=self.build().sha256
        code='''import sys,json
sys.path.insert(0,sys.argv[1])
from specroad.storage.model_root import prepare_model_root
from specroad.storage.project import ProjectSource
scope=json.loads(sys.argv[4])
r=prepare_model_root(ProjectSource(sys.argv[2]),[sys.argv[3]],scope_descriptor=scope,effective_profile={})
print(json.dumps({"sha256":r.sha256,"closure_verified":r.closure_verified}))
'''
        for entry in (moved/'module',moved/'specroad.pyz'):
            result=subprocess.run([sys.executable,'-I','-S','-B','-c',code,str(entry),str(self.root),self.path,
                                   json.dumps(scope([self.value['id']]))],stdin=subprocess.DEVNULL,
                                   cwd=self.root,capture_output=True,check=True)
            self.assertEqual(json.loads(result.stdout),{'sha256':expected,'closure_verified':False})

    def test_plain_profile_projection_is_owned_and_does_not_execute_values(self):
        marker=self.root/'should-not-exist'
        data={'expressions':['write '+str(marker)]}
        result=self.build(profile=data);data['expressions'].clear()
        self.assertFalse(marker.exists())
        self.assertNotEqual(result.sha256,self.build(profile=data).sha256)

    def test_normative_configuration_array_order_is_not_silently_changed(self):
        a=ProjectConfiguration(configuration_value(profiles=['core@0.2.0','software@0.2.0']))
        b=ProjectConfiguration(configuration_value(profiles=['software@0.2.0','core@0.2.0']))
        self.assertNotEqual(semantic_configuration(a),semantic_configuration(b))

    def test_explicit_resource_ids_are_bound_and_missing_members_rejected(self):
        captured=capture_model_inputs(self.source,[self.path])
        with self.assertRaises(ModelError):assemble_model_manifest(self.source.configuration,captured.binding,captured.resources,
            scope_descriptor=scope(resources=['missing@1.0.0']),effective_profile={})

    def test_unsorted_or_duplicate_explicit_seeds_are_rejected(self):
        captured=capture_model_inputs(self.source,[self.path])
        for ids in ([self.value['id'],self.value['id']],['z','a']):
            desc=scope();desc['selector']['artifact_ids']=ids
            with self.assertRaises(ModelError):assemble_model_manifest(self.source.configuration,captured.binding,captured.resources,
                scope_descriptor=desc,effective_profile={})

    def test_explicit_generic_resource_version_is_supported(self):
        value={'schema_version':'0.2.0','profile_id':'core','version':'0.2.0'}
        put(self.root,'profiles/core.json',artifact_bytes(value))
        captured=capture_model_inputs(self.source,['profiles/core.json'])
        self.assertEqual(captured.resources[0].data['version'],'0.2.0')
