"""Failure, source-binding, isolation and passive-execution regressions."""
import copy
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from specroad.profiles import ProfileResource, ProfileError, resolve_profile, check_profile_fields
from specroad.storage import profiles as storage
from specroad.storage.profiles import load_bundled_profile, read_profile
from specroad.storage.project import ProjectSource
from specroad.model.errors import ModelError
from specroad.model.canonical import canonical_json_sha256
from specroad.security import SafetyViolation
from support.profiles import encoded, profile_data, selector, requirement
from support.model import configuration_file, put
from support.portable import files_under
from support.io_guards import block_imports_and_open

class ProfileRightTests(unittest.TestCase):
    def test_all_declaration_groups_are_required(self):
        for key in profile_data():
            data=profile_data();del data[key]
            with self.subTest(key=key),self.assertRaises(ProfileError): ProfileResource(encoded(data))

    def test_every_declaration_group_has_strict_type(self):
        for key in ('required_fields','forbidden_fields','allowed_values','relation_rules','lint_rules'):
            for value in (None,{},True,0,'[]'):
                with self.subTest(key=key,value=value),self.assertRaises(ProfileError):
                    ProfileResource(encoded(profile_data(**{key:value})))

    def test_invalid_field_selectors_are_controlled_errors(self):
        for key in ('artifact_types','maturities'):
            for value in (None,{},'requirement',[{}],['not-a-type'],['requirement','requirement']):
                v=selector(fields=['/statement']);v[key]=value
                with self.subTest(key=key,value=value),self.assertRaises(ProfileError):
                    ProfileResource(encoded(profile_data(required_fields=[v])))

    def test_empty_artifact_selector_is_not_global_fallback(self):
        with self.assertRaises(ProfileError):
            ProfileResource(encoded(profile_data(required_fields=[selector(artifact_types=[],fields=['/statement'])])))

    def test_bad_pointer_forms_are_not_missing_fields(self):
        for field in ('','/a/~2','/..','/a/.','$.title','#/title','relative',None,{}):
            with self.subTest(field=field),self.assertRaises(ProfileError):
                ProfileResource(encoded(profile_data(required_fields=[selector(fields=[field])])))

    def test_array_index_errors_do_not_become_optional_absence(self):
        p=ProfileResource(encoded(profile_data(required_fields=[selector(fields=['/a/01'])])))
        with self.assertRaises(ProfileError) as caught: check_profile_fields(p,requirement(a=[1,2]))
        self.assertEqual(caught.exception.reason,'profile_field_access_error')

    def test_missing_maturity_does_not_skip_conditional_rules(self):
        value=requirement();del value['maturity']
        with self.assertRaises(ProfileError): check_profile_fields(load_bundled_profile('software-en@0.2.0'),value)

    def test_incompatible_srx_version_is_rejected(self):
        v=load_bundled_profile('software-de@0.2.0').data;v['lint_rules'][0]['program']['version']='99.0'
        with self.assertRaises(ProfileError): ProfileResource(encoded(v))

    def test_unselected_lint_program_is_still_validated(self):
        v=load_bundled_profile('software-de@0.2.0').data
        rule=v['lint_rules'][0];rule['artifact_types']=['risk'];rule['program']['expression']={'op':'eval','source':'unsafe'}
        with self.assertRaises(ProfileError): ProfileResource(encoded(v))

    def test_code_like_literal_remains_passive(self):
        v=load_bundled_profile('software-de@0.2.0').data
        literal={'command':'launch','import':'some.module','callback':'f','file':'/not-read'}
        v['lint_rules'][0]['program']['expression']={'op':'literal','value':literal}
        raw=encoded(v)
        # Trusted SRX code uses fixed relative imports during AST validation.
        # Forbid external/profile-supplied imports and file access, not those
        # already-known Core dependencies (no change to the existing SRX code).
        import builtins
        original_import = builtins.__import__
        def trusted_import(name, globals=None, locals=None, fromlist=(), level=0):
            if level > 0 and (globals or {}).get("__package__", "").startswith("specroad."):
                return original_import(name, globals, locals, fromlist, level)
            raise AssertionError("Profile-supplied import attempted")
        with patch.object(builtins, "open", side_effect=AssertionError("No file access")), patch.object(builtins, "__import__", trusted_import):
            p=ProfileResource(raw)
        self.assertEqual(p.data['lint_rules'][0]['program']['expression']['value'],literal)

    def test_loading_does_not_evaluate_runtime_failures(self):
        v=load_bundled_profile('software-en@0.2.0').data
        v['lint_rules'][0]['program']['expression']={'op':'divide','args':[{'op':'literal','value':1},{'op':'literal','value':0}]}
        p=ProfileResource(encoded(v))
        result=check_profile_fields(p,requirement())
        self.assertTrue(result['field_checks_passed']);self.assertFalse(result['lint_rules_checked'])

    def test_rule_callbacks_are_not_resolved(self):
        for family in ('relation_rules','lint_rules'):
            for key in ('callback','module','imports','command','language'):
                v=load_bundled_profile('software-de@0.2.0').data;v[family][0][key]='sentinel'
                with self.subTest(family=family,key=key),self.assertRaises(ProfileError): ProfileResource(encoded(v))

    def test_rule_identity_collision_across_families(self):
        v=load_bundled_profile('software-de@0.2.0').data
        v['lint_rules'][0]['rule_id']=v['relation_rules'][0]['rule_id']
        with self.assertRaises(ProfileError): ProfileResource(encoded(v))

    def test_invalid_relation_contract_cannot_hide_in_profile(self):
        for key,value in (('minimum',True),('minimum',-1),('direction','reverse'),('relation_types',['shell']),('endpoint_types',['unknown'])):
            v=load_bundled_profile('software-de@0.2.0').data;v['relation_rules'][0][key]=value
            with self.subTest(key=key,value=value),self.assertRaises(ProfileError): ProfileResource(encoded(v))

    def test_rule_versions_and_override_severities_are_strict(self):
        for version in ('latest','1','^1.0.0',False):
            v=load_bundled_profile('software-de@0.2.0').data;v['lint_rules'][0]['version']=version
            with self.subTest(version=version),self.assertRaises(ProfileError): ProfileResource(encoded(v))
        for severity in ('off','ignore',False,{},None):
            with self.subTest(severity=severity),self.assertRaises(ProfileError):
                ProfileResource(encoded(profile_data(severity_overrides={'lint:test':severity})))

    def test_rule_bindings_and_definitions_are_detached(self):
        p=load_bundled_profile('software-de@0.2.0');a=p.rules('relation_rules');b=p.rules('lint_rules')
        old=p.source_bytes;a[0]['definition']['minimum']=99;b[0]['definition']['program']['expression']={'op':'shell'}
        self.assertEqual(p.source_bytes,old);self.assertEqual(p.minimum_relation_rules()[0].minimum,1)
        self.assertEqual(p.rules('lint_rules')[0]['sha256'],canonical_json_sha256(p.data['lint_rules'][0]))

    def test_many_field_findings_are_not_display_truncated(self):
        p=ProfileResource(encoded(profile_data(required_fields=[selector(fields=['/f'+str(i) for i in range(210)])])))
        result=check_profile_fields(p,requirement())
        self.assertEqual(len(result['diagnostics']),210);self.assertEqual(result['checked_fields'],210)

    def test_failing_results_do_not_disclose_operand_values(self):
        p=ProfileResource(encoded(profile_data(allowed_values=[selector(field='/private',values=['accepted'])])))
        result=check_profile_fields(p,requirement(private='do-not-disclose'))
        self.assertFalse(result['field_checks_passed']);self.assertNotIn('do-not-disclose',json.dumps(result))

    def test_non_json_objects_and_subclasses_never_run_hooks(self):
        class Strange(dict):
            def items(self): raise AssertionError('hook executed')
            def __iter__(self): raise AssertionError('hook executed')
        p=load_bundled_profile('core@0.2.0')
        with self.assertRaises(ModelError): check_profile_fields(p,Strange())
        with self.assertRaises(ProfileError): ProfileResource(Strange())

    def test_cyclic_and_nonfinite_input_rejected_without_mutation(self):
        p=load_bundled_profile('core@0.2.0');v=requirement();v['self']=v
        with self.assertRaises(ModelError): check_profile_fields(p,v)
        self.assertIs(v['self'],v)
        for value in (float('nan'),float('inf')):
            v=requirement(extra=value)
            with self.assertRaises(ModelError): check_profile_fields(p,v)

    def test_repeated_and_concurrent_field_checks_are_independent(self):
        p=load_bundled_profile('software-en@0.2.0');good=requirement();bad=requirement(normative_force='invalid')
        with ThreadPoolExecutor(max_workers=4) as pool:
            results=list(pool.map(lambda v:check_profile_fields(p,v)['field_checks_passed'],[good,bad]*20))
        self.assertEqual(results,[True,False]*20)

    def test_environment_does_not_set_content_language(self):
        import os
        p=load_bundled_profile('software-de@0.2.0');v=requirement(language='ja-JP');before=copy.deepcopy(v)
        with patch.dict(os.environ,{'LANG':'en_US.UTF-8','LC_ALL':'C','TZ':'Pacific/Apia'}):
            self.assertTrue(check_profile_fields(p,v)['field_checks_passed'])
        self.assertEqual(v,before)

    def test_distribution_reads_only_exact_selected_resource(self):
        read=storage._read;seen=[]
        def wrapped(name):
            seen.append(name);return read(name)
        with patch.object(storage,'_read',wrapped): load_bundled_profile('software-en@0.2.0')
        self.assertEqual(seen,['profiles.json','software-en.json'])

    def test_unknown_distribution_key_never_opens_path(self):
        with patch.object(storage,'_read',side_effect=AssertionError('No resource reads')):
            for key in ('core@0.2.1','other@1.0.0','https://host/profile','../../core@0.2.0'):
                with self.subTest(key=key),self.assertRaises(ProfileError): load_bundled_profile(key)

    def test_tampered_distribution_original_bytes_rejected(self):
        read=storage._read
        def changed(name): return read(name)+(b' ' if name=='core.json' else b'')
        with patch.object(storage,'_read',changed),self.assertRaises(ProfileError): load_bundled_profile('core@0.2.0')

    def test_tampered_index_or_wrong_identity_rejected(self):
        original=storage._read('profiles.json');read=storage._read
        for mutation in ('missing','duplicate','path','hash'):
            v=json.loads(original)
            if mutation=='missing': v['profiles'].pop()
            if mutation=='duplicate': v['profiles'].append(v['profiles'][0])
            if mutation=='path': v['profiles'][0]['filename']='../core.json'
            if mutation=='hash': v['profiles'][0]['sha256']='X'*64
            with self.subTest(mutation=mutation),patch.object(storage,'_read',lambda n:encoded(v) if n=='profiles.json' else read(n)),self.assertRaises(ProfileError):
                load_bundled_profile('core@0.2.0')

    def test_explicit_project_read_keeps_source_bytes_and_files(self):
        p=load_bundled_profile('core@0.2.0')
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);configuration_file(root);put(root,'profiles/core.json',p.source_bytes)
            before=files_under(root);observed=read_profile(ProjectSource(root),'profiles/core.json',expected_key=p.key,expected_sha256=p.sha256)
            self.assertEqual(observed.source_bytes,p.source_bytes);self.assertEqual(files_under(root),before)

    def test_wrong_project_profile_hash_or_identity_fails(self):
        p=load_bundled_profile('core@0.2.0')
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);configuration_file(root);put(root,'profiles/core.json',p.source_bytes);source=ProjectSource(root)
            for key,digest in ((p.key,'0'*64),('core@0.3.0',p.sha256),('software-en@0.2.0',p.sha256),(p.key,None)):
                with self.subTest(key=key,digest=digest),self.assertRaises(ProfileError):
                    read_profile(source,'profiles/core.json',expected_key=key,expected_sha256=digest)

    def test_missing_project_profile_does_not_fall_back_to_distribution(self):
        p=load_bundled_profile('core@0.2.0')
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);configuration_file(root);source=ProjectSource(root)
            with patch.object(storage,'_read',side_effect=AssertionError('No fallback')),self.assertRaises((ModelError,SafetyViolation,OSError)):
                read_profile(source,'profiles/core.json',expected_key=p.key,expected_sha256=p.sha256)

    def test_project_path_classes_and_links_rejected(self):
        p=load_bundled_profile('core@0.2.0')
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);configuration_file(root);put(root,'generated/p.json',p.source_bytes);put(root,'profiles/p.json',p.source_bytes)
            (root/'profiles/link.json').symlink_to(root/'profiles/p.json');source=ProjectSource(root)
            for name in ('generated/p.json','specroad.json','../p.json','profiles/link.json'):
                with self.subTest(name=name),self.assertRaises((ModelError,SafetyViolation,OSError)):
                    read_profile(source,name,expected_key=p.key,expected_sha256=p.sha256)

    def test_stale_project_configuration_is_not_repaired(self):
        p=load_bundled_profile('core@0.2.0')
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);configuration_file(root);put(root,'profiles/p.json',p.source_bytes);source=ProjectSource(root)
            configuration_file(root,project_name='Changed');before=files_under(root)
            with self.assertRaises(ModelError):read_profile(source,'profiles/p.json',expected_key=p.key,expected_sha256=p.sha256)
            self.assertEqual(files_under(root),before)

    def test_byte_change_during_project_read_rejected_even_with_same_hash(self):
        p=load_bundled_profile('core@0.2.0')
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);configuration_file(root);path=put(root,'profiles/p.json',p.source_bytes);source=ProjectSource(root);read=source.read_normative;calls=[]
            def changing(name):
                data=read(name);calls.append(name)
                if len(calls)==1:path.write_bytes(data+b' ')
                return data
            with patch.object(source,'read_normative',changing),self.assertRaises(ProfileError) as caught:
                read_profile(source,'profiles/p.json',expected_key=p.key,expected_sha256=p.sha256)
            self.assertEqual(caught.exception.reason,'profile_changed_during_read')

    def test_exact_custom_prerelease_and_build_versions(self):
        for version in ('1.0.0-rc.1','0.2.0+build.7','2.3.4-beta.0+data'):
            with self.subTest(version=version):
                p=ProfileResource(encoded(profile_data(version=version)))
                self.assertIs(resolve_profile('sample@'+version,[p]),p)

    def test_semantic_hash_ignores_key_order_not_array_order(self):
        v=profile_data(required_fields=[selector(fields=['/title','/statement'])]);p=ProfileResource(encoded(v))
        q=ProfileResource(encoded(dict(reversed(tuple(v.items())))))
        self.assertEqual(p.sha256,q.sha256)
        v['required_fields'][0]['fields'].reverse()
        self.assertNotEqual(p.sha256,ProfileResource(encoded(v)).sha256)
