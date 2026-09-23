"""Bound project reads and policy failure edges, without presentation assertions."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

import pytest
from specroad.languages import evaluate_language, compose_language_packages, language_comparison_key
from specroad.model.canonical import canonical_json_sha256
from specroad.model.configuration import ProjectConfiguration
from specroad.model.errors import ModelError
from specroad.model.language_policy import LanguagePolicy, LanguagePolicyError
from specroad.model.language_packages import LanguagePackage, LanguagePackageError
from specroad.model.language_registry import LanguageRegistry
from specroad.profiles.composition import compose_profiles, check_composed_fields
from specroad.security import SafetyViolation
from specroad.storage.language_policy import (read_project_language_packages,
    inspect_requirement_language, effective_language_configuration)
from specroad.storage.language_registry import registry_binding
from specroad.storage.profiles import load_bundled_profile
from specroad.storage.project import ProjectSource
from support.domain import domain_value
from support.languages import load_registry, registry_bytes
from support.model import configuration_file, configuration_value, put
from support.portable import files_under, build_distribution
from test_language_policy import package, rule


def make_project(root, *, packages=(), language='en-US', **changes):
    reg=load_registry(registry_bytes(('language','en'),('region','US'),('region','IN'),('language','de'),('region','DE')))
    binding=registry_binding(reg)
    configuration_file(root,language_registry=binding,language_packages=[p.key for p in packages],**changes)
    put(root,binding['path'],reg.source_bytes)
    refs=[]
    for i,p in enumerate(packages):
        path='profiles/language-data/p'+str(i)+'.json'
        put(root,path,p.source_bytes);refs.append({**p.binding(),'path':path})
    value=domain_value('requirement',language=language)
    name='spec/requirements/'+value['id']+'.json'
    put(root,name,json.dumps(value,ensure_ascii=False).encode())
    return ProjectSource(root),name,refs,reg


def test_effective_defaults_are_not_writes_or_locale_defaults():
    for locale in ('de-DE','ja','en-US'):
        c=ProjectConfiguration(configuration_value(default_locale=locale));old=c.data
        v=effective_language_configuration(c)
        assert v['language_policy']['default_language']=='de-DE'
        assert c.data==old and 'language_policy' not in c.data
        v['language_policy']['allowed_ranges'].clear()
        assert effective_language_configuration(c)['language_policy']['allowed_ranges']==['*']


def test_project_check_preserves_requirement_and_all_files(tmp_path):
    p=package();source,path,refs,_=make_project(tmp_path,packages=[p],language='eN-uS',language_policy={'allowed_ranges':['en']})
    before=files_under(tmp_path);report=inspect_requirement_language(source,path,package_references=refs)
    assert report['language']=='eN-uS' and report['metadata']['range_allowed']
    assert report['exit_code']==0 and not report['atomic_snapshot'] and not report['approval_granted']
    assert files_under(tmp_path)==before
    assert report['language_configuration_sha256']==canonical_json_sha256(report['effective_language_configuration'])


def test_configured_threshold_changes_exit_without_changing_diagnostic(tmp_path):
    source,path,refs,_=make_project(tmp_path,language_policy={'allowed_ranges':[],'disallowed_language':'warning'},validation_policy={'fail_on':'warning'})
    a=inspect_requirement_language(source,path,package_references=refs)
    b=inspect_requirement_language(source,path,package_references=refs,fail_on='error')
    assert a['exit_code']==1 and b['exit_code']==0
    assert a['metadata']['diagnostics']==b['metadata']['diagnostics']


def test_only_matching_activated_package_payloads_are_opened(tmp_path):
    en,de,extra=package('en'),package('de',['de']),package('extra')
    source,path,refs,reg=make_project(tmp_path,packages=[en,de])
    (tmp_path/refs[1]['path']).unlink()
    refs.append({**extra.binding(),'path':'profiles/language-data/not-present.json'})
    reads=[];read=source.read_normative
    def watch(name,**kw):reads.append(name);return read(name,**kw)
    with patch.object(source,'read_normative',watch):
        value=read_project_language_packages(source,'en-US',references=refs)
    assert set(reads)=={refs[0]['path']}
    assert [p.key for p in value.packages]==[en.key]
    assert value.data['composition']['unavailable']==[]
    assert value.data['nonmatching_references']==[refs[1]]
    assert value.data['nonmatching_payloads_verified'] is False


def test_matching_declared_file_missing_has_no_distribution_fallback(tmp_path):
    p=package('en');source,path,refs,_=make_project(tmp_path,packages=[p]);(tmp_path/refs[0]['path']).unlink()
    from specroad.storage import language_packages as distributions
    with patch.object(distributions,'_read',side_effect=AssertionError('No fallback')):
        with pytest.raises((OSError,ModelError,SafetyViolation)):
            read_project_language_packages(source,'en-US',references=refs)


def test_missing_reference_reports_unavailable_without_blocking_valid_language(tmp_path):
    p=package('en');source,path,refs,_=make_project(tmp_path,packages=[p])
    report=inspect_requirement_language(source,path,package_references=[])
    assert report['exit_code']==0 and report['packages']['composition']['unavailable']==[p.key]
    assert report['packages']['composition']['capabilities']['literal_lint']=='not_available'
    assert report['packages']['composition']['lint_passed'] is None


def test_empty_activation_never_opens_any_package(tmp_path):
    source,_,_,_=make_project(tmp_path)
    p=package();refs=[{**p.binding(),'path':'profiles/language-data/absent.json'}]
    with patch.object(source,'read_normative',side_effect=AssertionError('No package read')):
        result=read_project_language_packages(source,'en-US',references=refs)
    assert result.packages==()


def test_package_hash_and_metadata_are_both_bound(tmp_path):
    p=package();source,_,refs,_=make_project(tmp_path,packages=[p])
    for field,value in [('sha256','0'*64),('language_ranges',['*']),('version','2.0.0')]:
        changed=deepcopy(refs);changed[0][field]=value
        if field=='version':
            report=read_project_language_packages(source,'en-US',references=changed)
            assert report.data['composition']['unavailable']==[p.key]
        else:
            with pytest.raises(LanguagePackageError):read_project_language_packages(source,'en-US',references=changed)


def test_package_same_length_byte_change_rejected(tmp_path):
    p=package();source,_,refs,_=make_project(tmp_path,packages=[p]);target=tmp_path/refs[0]['path']
    raw=target.read_bytes();target.write_bytes(raw.replace(b'example',b'changed'));assert target.stat().st_size==len(raw)
    with pytest.raises(LanguagePackageError):read_project_language_packages(source,'en-US',references=refs)


def test_package_change_during_read_is_rejected(tmp_path):
    p=package();source,_,refs,_=make_project(tmp_path,packages=[p]);read=source.read_normative;calls=[]
    def change(name,**kw):
        raw=read(name,**kw);calls.append(name)
        if len(calls)==1:(tmp_path/name).write_bytes(raw+b' ')
        return raw
    with patch.object(source,'read_normative',change),pytest.raises(LanguagePackageError):
        read_project_language_packages(source,'en-US',references=refs)


def test_invalid_reference_fields_are_not_ignored(tmp_path):
    p=package();source,_,refs,_=make_project(tmp_path,packages=[p])
    for value in (None,{},[None],[{}],[{**refs[0],'callback':'evil'}],[{k:v for k,v in refs[0].items() if k!='sha256'}]):
        with pytest.raises(ModelError):read_project_language_packages(source,'en',references=value)


def test_unsafe_package_paths_never_open(tmp_path):
    p=package();source,_,refs,_=make_project(tmp_path,packages=[p])
    for name in ('../foreign.json','/tmp/foreign.json','generated/p.json','specroad.json','https://example.test/p.json'):
        values=[{**refs[0],'path':name}]
        with patch.object(source,'read_normative',side_effect=AssertionError('No unsafe read')),pytest.raises((ModelError,SafetyViolation)):
            read_project_language_packages(source,'en',references=values)


def test_package_symlink_rejected_without_following(tmp_path):
    p=package();source,_,refs,_=make_project(tmp_path,packages=[p])
    target=tmp_path/refs[0]['path'];target.unlink();target.symlink_to(tmp_path/'specroad.json')
    with pytest.raises((ModelError,SafetyViolation,OSError)):
        read_project_language_packages(source,'en',references=refs)


def test_conflicting_reference_identity_or_path_is_error(tmp_path):
    p=package();source,_,refs,_=make_project(tmp_path,packages=[p]);first=refs[0]
    for other in ({**first,'sha256':'0'*64},{**first,'path':'profiles/other.json'},{**first,'package_id':'other'}):
        with pytest.raises(LanguagePackageError):read_project_language_packages(source,'en',references=[first,other])
    assert len(read_project_language_packages(source,'en',references=[first,first]).packages)==1


def test_register_bytes_are_not_updated_from_distribution(tmp_path):
    source,path,refs,reg=make_project(tmp_path)
    from specroad.storage import language_registry as storage
    before=files_under(tmp_path)
    with patch.object(storage,'bundled_language_registry',side_effect=AssertionError('No automatic upgrade')):
        report=inspect_requirement_language(source,path,package_references=refs)
    assert report['metadata']['assessment']['registry_version']==reg.version
    assert files_under(tmp_path)==before


def test_missing_registry_copy_is_hard_error_not_empty_success(tmp_path):
    source,path,refs,reg=make_project(tmp_path);(tmp_path/'profiles/language-data/registry.txt').unlink()
    with pytest.raises((ModelError,SafetyViolation,OSError)):inspect_requirement_language(source,path,package_references=refs)


def test_unknown_newer_registry_value_obeys_bound_historical_snapshot(tmp_path):
    source,path,refs,reg=make_project(tmp_path,language='qzz')
    report=inspect_requirement_language(source,path,package_references=refs)
    assert report['metadata']['assessment']['registry_state']=='unverified_registry'
    assert [d['code'] for d in report['metadata']['diagnostics']]==['SRV178']
    assert report['metadata']['assessment']['registry_version']=='2020-01-01'


def test_damaged_registry_never_degrades_to_unverified_tag(tmp_path):
    source,path,refs,reg=make_project(tmp_path);(tmp_path/'profiles/language-data/registry.txt').write_bytes(b'broken')
    with pytest.raises(ModelError):inspect_requirement_language(source,path,package_references=refs)


def test_registry_change_after_package_read_invalidates_combined_observation(tmp_path):
    p=package();source,path,refs,reg=make_project(tmp_path,packages=[p]);read=source.read_normative
    def change(name,**kw):
        raw=read(name,**kw)
        if name==refs[0]['path']:(tmp_path/'profiles/language-data/registry.txt').write_bytes(reg.source_bytes+b' ')
        return raw
    with patch.object(source,'read_normative',change),pytest.raises(ModelError):
        inspect_requirement_language(source,path,package_references=refs)


def test_configuration_change_requires_new_explicit_source(tmp_path):
    source,path,refs,reg=make_project(tmp_path);raw=(tmp_path/'specroad.json').read_bytes()
    (tmp_path/'specroad.json').write_bytes(raw+b' ')
    with pytest.raises(ModelError):inspect_requirement_language(source,path,package_references=refs)


def test_requirement_change_after_initial_read_is_rejected(tmp_path):
    p=package();source,path,refs,reg=make_project(tmp_path,packages=[p]);read=source.read_normative
    def change(name,**kw):
        raw=read(name,**kw)
        if name==refs[0]['path']:
            target=tmp_path/path;v=json.loads(target.read_bytes());v['statement']='Changed';target.write_bytes(json.dumps(v).encode())
        return raw
    with patch.object(source,'read_normative',change),pytest.raises(ModelError):
        inspect_requirement_language(source,path,package_references=refs)


def test_project_source_must_be_explicit_typed_reader(tmp_path):
    for source in (tmp_path,{},None,'/tmp'):
        with pytest.raises(ModelError):inspect_requirement_language(source,'r.json',package_references=[])
        with pytest.raises(ModelError):read_project_language_packages(source,'en',references=[])


def test_policy_conflicts_and_severity_are_not_hidden_by_star():
    registry=load_registry()
    for tag,code,key in [('qzz','SRV178','unverified_registry'),('und','SRV181','unspecified_language')]:
        for action in ('allow','warning','error'):
            p=LanguagePolicy({key:action,'unverified_registry':action})
            report=evaluate_language(tag,policy=p,registry=registry)
            assert report['range_allowed']
            assert any(d['code']==code for d in report['diagnostics']) is (action!='allow')


def test_arbitrary_objects_do_not_execute_conversions():
    calls=[]
    class Foreign:
        def __str__(self):calls.append('str');raise AssertionError
        def __fspath__(self):calls.append('path');raise AssertionError
        def __iter__(self):calls.append('iter');raise AssertionError
    for data in ({'allowed_ranges':[Foreign()]},{'mixed_languages':{'document':Foreign()}},{'default_language':Foreign()}):
        with pytest.raises(ModelError):LanguagePolicy(data)
    assert calls==[]


def test_invalid_package_reference_path_does_not_call_fspath(tmp_path):
    source,_,_,_=make_project(tmp_path);p=package();calls=[]
    class Foreign:
        def __fspath__(self):calls.append(1);return 'profiles/x.json'
    with pytest.raises(ModelError):read_project_language_packages(source,'en',references=[{**p.binding(),'path':Foreign()}])
    assert calls==[]


def test_invalid_threshold_is_rejected_even_when_strict():
    for threshold in ('info','allow',None,False,3):
        with pytest.raises(LanguagePolicyError):evaluate_language('en',policy=LanguagePolicy({}),registry=load_registry(),fail_on=threshold,strict=True)


def test_nonboolean_strict_does_not_use_truthiness():
    for strict in (1,0,'true',None,[]):
        with pytest.raises(LanguagePolicyError):evaluate_language('en',policy=LanguagePolicy({}),registry=load_registry(),strict=strict)


def test_policy_and_registry_are_explicit_values():
    with pytest.raises(ModelError):evaluate_language('en',policy={},registry=load_registry())
    with pytest.raises(ModelError):evaluate_language('en',policy=LanguagePolicy({}),registry=None)
    with pytest.raises(ModelError):effective_language_configuration({})


def test_registry_metadata_tampering_does_not_bypass_hash():
    registry=load_registry();object.__setattr__(registry,'sha256','0'*64)
    with pytest.raises(ModelError):evaluate_language('en',policy=LanguagePolicy({}),registry=registry)


def test_contradictory_duplicate_named_rules_rejected_in_package():
    with pytest.raises(LanguagePackageError):package(rules=[rule(),rule(placeholders=['OTHER'])])
    p=package(rules=[rule(),rule()]);v=compose_language_packages('en',activated=[p.key],resources=[p]).data
    assert len(v['literal_rules'])==1


def test_rule_outside_declared_package_range_rejected():
    with pytest.raises(LanguagePackageError):package(ranges=['de'],rules=[rule(language='en')])


def test_rule_language_is_preserved_not_rewritten_for_region():
    p=package(rules=[rule(language='en')]);result=compose_language_packages('en-IN',activated=[p.key],resources=[p]).data
    assert result['literal_rules'][0]['definition']['language']=='en'
    assert result['lint_passed'] is None and result['rules_executed'] is False


def test_same_rule_hash_coalesces_but_package_activation_order_is_preserved():
    a=package('a',rules=[rule()]);b=package('b',rules=[dict(reversed(list(rule().items())))])
    x=compose_language_packages('en',activated=[a.key,b.key],resources=[a,b])
    y=compose_language_packages('en',activated=[b.key,a.key],resources=[a,b])
    assert len(x.data['literal_rules'])==1 and len(y.data['literal_rules'])==1
    assert x.sha256!=y.sha256


def test_reference_input_and_result_are_independent(tmp_path):
    p=package();source,_,refs,_=make_project(tmp_path,packages=[p]);before=deepcopy(refs)
    result=read_project_language_packages(source,'en-US',references=refs)
    assert refs==before
    refs[0]['sha256']='0'*64;data=result.data;data['verified_references'].clear()
    assert result.data['verified_references']==before


def test_profiles_allow_different_declared_content_languages():
    resources=[load_bundled_profile(k) for k in ('core@0.2.0','software-de@0.2.0','software-en@0.2.0')]
    en,de=package('en'),package('de',['de'])
    result=compose_profiles(resources,core_key='core@0.2.0',project_profiles=['software-de@0.2.0','software-en@0.2.0'],language_registry=load_registry(),language_packages=[en,de])
    for language in ('en-US','en-IN','de-DE','ja','x-project'):
        observed=check_composed_fields(result,domain_value('requirement',language=language))
        assert observed['field_checks_passed'] and not observed['approval_granted']


def test_bound_register_and_package_versions_change_semantic_profile_hash():
    core=load_bundled_profile('core@0.2.0');a=package();b=package(version='1.0.1')
    one=compose_profiles([core],core_key=core.key,language_registry=load_registry(),language_packages=[a])
    two=compose_profiles([core],core_key=core.key,language_registry=load_registry(),language_packages=[b])
    assert one.sha256!=two.sha256


def test_parallel_reuse_does_not_mutate_policy_registry_or_packages():
    p=LanguagePolicy({'allowed_ranges':['en']});registry=load_registry();language_package=package()
    def run(tag):return evaluate_language(tag,policy=p,registry=registry),compose_language_packages(tag,activated=[language_package.key],resources=[language_package]).data
    tags=['en-US','de','qzz','en']*12;expected=[run(t) for t in tags]
    with ThreadPoolExecutor(max_workers=4) as pool:assert list(pool.map(run,tags))==expected


def test_long_allow_list_has_no_display_limit():
    ranges=['q'+chr(97+i//26)+chr(97+i%26) for i in range(151)]+['en']
    value=evaluate_language('en-US',policy=LanguagePolicy({'allowed_ranges':ranges}),registry=load_registry())
    assert value['matched_ranges']==['en'] and value['range_allowed']


def test_many_matching_packages_are_all_kept_without_truncation():
    packages=[package('p'+str(i)) for i in range(151)]
    report=compose_language_packages('en-US',activated=[p.key for p in packages],resources=list(reversed(packages))).data
    assert len(report['packages'])==151
    assert [p['package_id'] for p in report['packages']]==['p'+str(i) for i in range(151)]


def test_no_automatic_alias_or_macro_language_in_package_selection():
    p=package('zh',['zh'])
    report=compose_language_packages('cmn-Hans',activated=[p.key],resources=[p]).data
    assert report['packages']==[] and report['capabilities']['literal_lint']=='not_available'


def test_language_policy_hash_does_not_use_host_locale_or_environment(monkeypatch):
    p=LanguagePolicy({});reg=load_registry();old=evaluate_language('en-US',policy=p,registry=reg)
    for lang,zone in [('tr_TR.UTF-8','Asia/Tokyo'),('C','UTC'),('ja_JP.UTF-8','America/New_York')]:
        monkeypatch.setenv('LANG',lang);monkeypatch.setenv('LC_ALL',lang);monkeypatch.setenv('TZ',zone)
        assert evaluate_language('en-US',policy=p,registry=reg)==old


def test_invalid_semver_packages_are_rejected_in_configuration():
    for key in ('en@01.0.0','en@1.00.0','en@1.0.0-01','en@latest'):
        with pytest.raises(ModelError):ProjectConfiguration(configuration_value(language_packages=[key]))


def test_loaded_normative_tag_never_becomes_a_default(tmp_path):
    source,path,refs,_=make_project(tmp_path,language='ja',language_policy={'default_language':'en-US'})
    result=inspect_requirement_language(source,path,package_references=refs)
    assert result['language']=='ja' and result['metadata']['assessment']['registry_state']=='unverified_registry'


def test_missing_stored_requirement_tag_is_schema_error_not_default(tmp_path):
    source,path,refs,_=make_project(tmp_path);target=tmp_path/path;v=json.loads(target.read_bytes());del v['language'];target.write_bytes(json.dumps(v).encode())
    with pytest.raises(ModelError):inspect_requirement_language(source,path,package_references=refs)


def test_portable_module_and_zipapp_contain_policy_and_composition(tmp_path):
    original=tmp_path/'dist';build_distribution(original)
    dist=tmp_path/'moved';original.rename(dist)
    module=dist/'module';archive=dist/'specroad.pyz'
    # The generated distribution root has package plus standalone zipapp.
    snippet="""import json,sys
sys.path.insert(0, sys.argv[1])
from specroad.model.language_policy import LanguagePolicy
from specroad.storage.language_registry import bundled_language_registry
from specroad.languages import evaluate_language,compose_language_packages
from specroad.storage.language_packages import load_bundled_package
from specroad.storage.language_policy import effective_language_configuration
p=load_bundled_package('en@1.0.0')
a=evaluate_language('en-IN',policy=LanguagePolicy({'allowed_ranges':['en']}),registry=bundled_language_registry())
b=compose_language_packages('en-IN',activated=[p.key],resources=[p]).data
print(json.dumps({'allowed':a['range_allowed'],'passed':b['lint_passed'],'packages':[p['package_id'] for p in b['packages']]}))
"""
    for location in (module,archive):
        proc=subprocess.run([sys.executable,'-I','-B','-c',snippet,str(location)],cwd=tmp_path,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,check=True)
        assert json.loads(proc.stdout)=={'allowed':True,'passed':None,'packages':['en']}
