"""Races, current authority/permissions, actual native locks and live resources."""
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
import json
import os
import subprocess
import sys
import pytest
from specroad.changes import (prepare_publication_check,recheck_publication,project_lock,
    PublicationAuthority,PublicationCheckError,TargetModel)
from specroad.model.model_manifest import ProjectReadBinding
from specroad.model.canonical import canonical_json_bytes
from specroad.profiles import ProfileResource,compose_profiles
from specroad.validation import ModelDocument
from support.publication import prepared,options,invoke,files,ALLOW,TRANSACTION
from support.targets import POLICY,model,plan,gate,ACTOR,TIME
from support.folds import goal,edit,create


def test_valid_create_missing_parent_has_no_early_mkdir(tmp_path):
    a=goal();b=goal(2)
    # Another type uses a new artifact directory.
    from support.domain import domain_value
    b=domain_value('need',revision=1,created_at=TIME,updated_at=TIME,created_by=ACTOR,updated_by=ACTOR)
    m,p,c=prepared(tmp_path,operations=[create(b)])
    path=c.request.documents[0].path;parent=(tmp_path/path).parent
    assert not parent.exists()
    with project_lock(tmp_path,**options(c)) as h:
        seen=invoke(c,h,lambda r:r.documents[0].path)
        assert seen==path and not parent.exists()


def test_new_directory_after_plan_is_not_silently_adopted(tmp_path):
    from support.domain import domain_value
    m,p,c=prepared(tmp_path,operations=[create(domain_value('need',revision=1,created_at=TIME,updated_at=TIME,created_by=ACTOR,updated_by=ACTOR))])
    (tmp_path/c.request.documents[0].path).parent.mkdir()
    with project_lock(tmp_path,**options(c)) as h:
        with pytest.raises(PublicationCheckError) as e:invoke(c,h,lambda r:True)
    assert e.value.exit_code==6


def test_new_create_target_after_plan_never_overwritten(tmp_path):
    b=goal(2,revision=1,created_at=TIME,updated_at=TIME,created_by=ACTOR,updated_by=ACTOR);m,p,c=prepared(tmp_path,operations=[create(b)])
    path=tmp_path/c.request.documents[0].path;path.write_bytes(b'{}');before=path.read_bytes()
    with project_lock(tmp_path,**options(c)) as h:
        with pytest.raises(PublicationCheckError) as e:invoke(c,h,lambda r:path.write_bytes(r.documents[0].content))
    assert e.value.exit_code==6 and path.read_bytes()==before


def test_same_project_id_in_another_root_is_not_same_lock(tmp_path):
    m,p,c=prepared(tmp_path/'one');m2,p2,c2=prepared(tmp_path/'two')
    with project_lock(tmp_path/'two',**options(c2)) as h:
        with pytest.raises(PublicationCheckError) as e:invoke(c,h,lambda r:True)
    assert e.value.reason=='publication_lock_project_mismatch'


def test_root_replaced_between_plan_and_lock_is_conflict(tmp_path):
    root=tmp_path/'project';m,p,c=prepared(root);root.rename(tmp_path/'old');root.mkdir()
    for path,raw in m.source_files.items():
        f=root/path;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(raw)
    with project_lock(root,**options(c)) as h:
        with pytest.raises(PublicationCheckError) as e:invoke(c,h,lambda r:True)
    assert e.value.reason=='publication_root_changed'


@pytest.mark.parametrize('replacement',['symlink','fifo','hardlink'])
def test_unsafe_input_never_followed_or_hashed(tmp_path,replacement):
    m,p,c=prepared(tmp_path);path=tmp_path/m.documents[0].path;outside=tmp_path.parent/(tmp_path.name+'-outside')
    outside.write_bytes(path.read_bytes());path.unlink()
    try:
        if replacement=='symlink':path.symlink_to(outside)
        elif replacement=='fifo':os.mkfifo(path)
        else:os.link(outside,path)
        with project_lock(tmp_path,**options(c)) as h:
            with pytest.raises(PublicationCheckError) as e:invoke(c,h,lambda r:True)
            assert e.value.exit_code==7
    finally:outside.unlink()


def test_nested_project_appears_after_plan_is_rejected(tmp_path):
    m,p,c=prepared(tmp_path);(tmp_path/'spec/specroad.json').write_bytes(b'{}')
    with project_lock(tmp_path,**options(c)) as h:
        with pytest.raises(PublicationCheckError) as e:invoke(c,h,lambda r:True)
    assert e.value.exit_code==7


def test_readonly_destination_parent_is_not_permission_from_old_preflight(tmp_path):
    m,p,c=prepared(tmp_path);parent=(tmp_path/m.documents[0].path).parent;before=files(tmp_path)
    old=parent.stat().st_mode;parent.chmod(0o500)
    try:
        with project_lock(tmp_path,**options(c)) as h:
            with pytest.raises(PublicationCheckError) as e:invoke(c,h,lambda r:True)
            assert e.value.exit_code==7
    finally:parent.chmod(old)
    assert files(tmp_path)==before


def test_readonly_permission_during_host_gate_is_rechecked(tmp_path):
    m,p,c=prepared(tmp_path);parent=(tmp_path/m.documents[0].path).parent;mode=parent.stat().st_mode;seen=[]
    def change(r):parent.chmod(0o500);return True
    try:
        with project_lock(tmp_path,**options(c)) as h:
            with pytest.raises(PublicationCheckError) as e:invoke(c,h,lambda r:seen.append(r),authority=PublicationAuthority('x','1',change))
            assert e.value.exit_code==7 and seen==[]
    finally:parent.chmod(mode)


def test_effective_permission_denied_by_kernel_is_not_mode_bit_success(tmp_path):
    m,p,c=prepared(tmp_path)
    with project_lock(tmp_path,**options(c)) as h:
        with patch.object(os,'access',return_value=False):
            with pytest.raises(PublicationCheckError) as e:invoke(c,h,lambda r:True)
    assert e.value.exit_code==7


def test_readonly_mount_refuses_despite_successful_access(tmp_path):
    m,p,c=prepared(tmp_path)
    class ReadOnly: f_flag=1
    with project_lock(tmp_path,**options(c)) as h:
        with patch.object(os,'fstatvfs',return_value=ReadOnly()):
            with pytest.raises(PublicationCheckError) as e:invoke(c,h,lambda r:True)
    assert e.value.reason=='publication_mount_read_only'


def test_no_permission_probe_support_fails_closed(tmp_path):
    import specroad.changes.publication_check as module
    m,p,c=prepared(tmp_path)
    with project_lock(tmp_path,**options(c)) as h:
        with patch.object(module,'_ACCESS_SUPPORTED',False):
            with pytest.raises(PublicationCheckError) as e:invoke(c,h,lambda r:True)
    assert e.value.reason=='effective_permission_probe_unavailable'


def test_deleting_configuration_inside_authorizer_is_conflict(tmp_path):
    m,p,c=prepared(tmp_path);f=tmp_path/'specroad.json';raw=f.read_bytes();seen=[]
    def authorizer(r):f.unlink();return True
    try:
        with project_lock(tmp_path,**options(c)) as h:
            with pytest.raises(PublicationCheckError) as e:invoke(c,h,lambda r:seen.append(r),authority=PublicationAuthority('x','1',authorizer))
            assert e.value.exit_code==6 and seen==[]
    finally:f.write_bytes(raw)


def test_invalid_configuration_after_preflight_is_conflict_before_parse(tmp_path):
    m,p,c=prepared(tmp_path);f=tmp_path/'specroad.json';raw=f.read_bytes()
    with project_lock(tmp_path,**options(c)) as h:
        try:
            f.write_bytes(b'not json')
            with pytest.raises(PublicationCheckError) as e:invoke(c,h,lambda r:True)
            assert e.value.exit_code==6
        finally:f.write_bytes(raw)


def test_config_mutation_inside_authorizer_returns_conflict(tmp_path):
    m,p,c=prepared(tmp_path);f=tmp_path/'specroad.json';raw=f.read_bytes();seen=[]
    def authorizer(r):f.write_bytes(raw+b' ');return True
    with project_lock(tmp_path,**options(c)) as h:
        try:
            with pytest.raises(PublicationCheckError) as e:invoke(c,h,lambda r:seen.append(r),authority=PublicationAuthority('x','1',authorizer))
            assert e.value.exit_code==6 and seen==[]
        finally:f.write_bytes(raw)


def test_journal_appears_during_authorization_is_not_waived(tmp_path):
    m,p,c=prepared(tmp_path);path=tmp_path/'.specroad/transactions/pretend-done.json';seen=[]
    def authorizer(r):path.parent.mkdir();path.write_text('{"completed":true}');return True
    with project_lock(tmp_path,**options(c)) as h:
        try:
            with pytest.raises(PublicationCheckError) as e:invoke(c,h,lambda r:seen.append(r),authority=PublicationAuthority('x','1',authorizer))
            assert e.value.reason=='publication_recovery_required' and seen==[]
        finally:path.unlink()


def test_foreign_lock_record_cannot_be_cleared_or_used(tmp_path):
    m,p,c=prepared(tmp_path);path=tmp_path/'.specroad/locks/project.json';seen=[]
    with project_lock(tmp_path,**options(c)) as h:
        raw=path.read_bytes();v=json.loads(raw);v['request_id']='Other'
        try:
            path.write_bytes(canonical_json_bytes(v))
            with pytest.raises(PublicationCheckError) as e:invoke(c,h,lambda r:seen.append(r))
            assert e.value.reason=='lock_owner_changed' and seen==[] and path.exists()
        finally:path.write_bytes(raw)


def test_gate_that_was_green_is_rerun_under_lock(tmp_path):
    m,p,c=prepared(tmp_path);calls=[];state={'deny':False}
    def check(ctx):
        calls.append(state['deny'])
        return ctx.result([{'reason':'revoked','severity':'error'}] if state['deny'] else [])
    g=gate(check=check);c=prepare_publication_check(p,m,policy=POLICY,gates=[g]);state['deny']=True
    with project_lock(tmp_path,**options(c)) as h:
        with pytest.raises(PublicationCheckError) as e:invoke(c,h,lambda r:True,gates=[g])
    assert e.value.reason=='publication_target_not_validated' and calls==[False,True]


def test_mutation_by_target_gate_is_caught_after_gate(tmp_path):
    m,p,c=prepared(tmp_path);path=tmp_path/m.documents[0].path;state={'mutate':False};seen=[]
    def check(ctx):
        if state['mutate']:path.write_bytes(path.read_bytes()+b' ')
        return ctx.result()
    g=gate(check=check);c=prepare_publication_check(p,m,policy=POLICY,gates=[g]);state['mutate']=True
    with project_lock(tmp_path,**options(c)) as h:
        with pytest.raises(PublicationCheckError) as e:invoke(c,h,lambda r:seen.append(r),gates=[g])
    assert e.value.exit_code==6 and seen==[]


def test_authority_exception_does_not_invoke_writer_or_leak_false_success(tmp_path):
    m,p,c=prepared(tmp_path);seen=[]
    def bad(r):raise RuntimeError('auth failure')
    with project_lock(tmp_path,**options(c)) as h:
        with pytest.raises(PublicationCheckError) as e:invoke(c,h,lambda r:seen.append(r),authority=PublicationAuthority('x','1',bad))
    assert e.value.reason=='publication_authority_failed' and seen==[]


def test_authority_tampered_handoff_is_rejected(tmp_path):
    m,p,c=prepared(tmp_path)
    def bad(r):object.__setattr__(r,'documents',());return True
    with project_lock(tmp_path,**options(c)) as h:
        with pytest.raises(PublicationCheckError) as e:invoke(c,h,lambda r:True,authority=PublicationAuthority('x','1',bad))
    assert e.value.reason=='publication_request_changed'


def test_actual_other_process_cannot_enter_during_publication(tmp_path):
    from support.project_locks import attempt
    m,p,c=prepared(tmp_path)
    with project_lock(tmp_path,**options(c)) as h:
        result=invoke(c,h,lambda r:attempt(tmp_path))
    assert result['acquired'] is False and result['reason']=='project_lock_busy'


def test_empty_plan_does_not_hide_revoked_source_or_recovery(tmp_path):
    m,p,c=prepared(tmp_path,operations=[]);f=tmp_path/m.documents[0].path;f.write_bytes(f.read_bytes()+b' ')
    with project_lock(tmp_path,**options(c)) as h:
        with pytest.raises(PublicationCheckError):invoke(c,h,lambda r:True)


def test_large_model_verifies_unchanged_resources_too(tmp_path):
    artifacts=[goal(i) for i in range(1,42)];m,p,c=prepared(tmp_path,artifacts=artifacts)
    f=tmp_path/m.documents[-1].path;f.write_bytes(f.read_bytes()+b' ')
    with project_lock(tmp_path,**options(c)) as h:
        with pytest.raises(PublicationCheckError) as e:invoke(c,h,lambda r:True)
    assert e.value.exit_code==6


def package_model(tmp_path):
    from importlib.resources import files as resources
    from specroad.model.language_package_values import LanguagePackage
    m,p,c=prepared(tmp_path)
    package=LanguagePackage(resources('specroad.language_data').joinpath('packages/de.json').read_bytes())
    profiles=[ProfileResource(d.content) for d in m.resource_files]
    profile=compose_profiles(profiles,core_key=profiles[0].key,language_packages=[package])
    m=TargetModel(m.configuration_bytes,m.binding,m.documents,profile=profile,
                  resource_files=m.resource_files,language_packages=[package])
    extra=ModelDocument('profiles/language-data/packages/de.json',package.source_bytes)
    f=tmp_path/extra.path;f.parent.mkdir(parents=True);f.write_bytes(extra.content)
    p=plan(m,[edit(m.artifacts[0],'Changed')])
    return m,p,extra


def test_actual_language_package_bytes_have_explicit_live_path(tmp_path):
    m,p,extra=package_model(tmp_path);c=prepare_publication_check(p,m,policy=POLICY,package_files=[extra])
    with project_lock(tmp_path,**options(c)) as h:assert invoke(c,h,lambda r:True)
    assert extra.path in c.data['observed_paths']


def test_detached_package_metadata_without_live_binding_is_not_enough(tmp_path):
    m,p,extra=package_model(tmp_path)
    with pytest.raises(PublicationCheckError) as e:prepare_publication_check(p,m,policy=POLICY)
    assert e.value.reason=='live_language_package_bindings_required'


def test_language_package_changed_after_preflight_stops_writer(tmp_path):
    m,p,extra=package_model(tmp_path);c=prepare_publication_check(p,m,policy=POLICY,package_files=[extra])
    (tmp_path/extra.path).write_bytes(extra.content+b' ')
    with project_lock(tmp_path,**options(c)) as h:
        with pytest.raises(PublicationCheckError) as e:invoke(c,h,lambda r:True)
    assert e.value.exit_code==6


def test_redundant_package_path_binding_is_not_a_fallback(tmp_path):
    m,p,extra=package_model(tmp_path)
    with pytest.raises(PublicationCheckError):prepare_publication_check(p,m,policy=POLICY,package_files=[extra,extra])


def test_unknown_extra_files_cannot_be_added_to_canonical_inventory(tmp_path):
    m,p,c=prepared(tmp_path)
    with pytest.raises(PublicationCheckError):prepare_publication_check(p,m,policy=POLICY,package_files=[ModelDocument('rules/x.json',b'{}')])


def test_only_timestamp_changes_are_not_semantic_rebase(tmp_path):
    m,p,c=prepared(tmp_path);f=tmp_path/m.documents[0].path;i=f.stat();os.utime(f,ns=(i.st_atime_ns,i.st_mtime_ns+1000000))
    with project_lock(tmp_path,**options(c)) as h:assert invoke(c,h,lambda r:True)


def test_mode_change_is_bound_even_if_still_writable(tmp_path):
    m,p,c=prepared(tmp_path);f=tmp_path/m.documents[0].path;f.chmod(0o640)
    with project_lock(tmp_path,**options(c)) as h:
        with pytest.raises(PublicationCheckError) as e:invoke(c,h,lambda r:True)
    assert e.value.exit_code==6


def test_saved_preflight_is_not_shared_by_copy_mutation(tmp_path):
    m,p,c=prepared(tmp_path);before=c.data;returned=c.request.data
    returned['changed_paths'].clear()
    observed=c.data;observed['observed_paths'].clear()
    with project_lock(tmp_path,**options(c)) as h:assert invoke(c,h,lambda r:bool(r.documents))
    assert c.data==before


def test_gate_cannot_change_bound_package_during_final_checks(tmp_path):
    m,p,extra=package_model(tmp_path);state={'change':False};seen=[]
    def check(ctx):
        if state['change']:(tmp_path/extra.path).write_bytes(extra.content+b' ')
        return ctx.result()
    g=gate(check=check)
    c=prepare_publication_check(p,m,policy=POLICY,gates=[g],package_files=[extra])
    state['change']=True
    with project_lock(tmp_path,**options(c)) as h:
        with pytest.raises(PublicationCheckError) as e:invoke(c,h,lambda r:seen.append(r),gates=[g])
    assert e.value.exit_code==6 and seen==[]


def test_wrong_expected_hash_is_never_rebased_to_live_content(tmp_path):
    from support.targets import resign
    m,p,c=prepared(tmp_path)
    changed=resign(p,lambda v:v['operations'][0].update(expected_sha256='0'*64))
    with pytest.raises(PublicationCheckError):prepare_publication_check(changed,m,policy=POLICY)
    assert not (tmp_path/'.specroad').exists()


def test_request_id_from_other_plan_never_uses_successful_preflight(tmp_path):
    m,p,c=prepared(tmp_path)
    other=plan(m,[edit(m.artifacts[0],'Changed')],request_id='Other')
    other_check=prepare_publication_check(other,m,policy=POLICY)
    with project_lock(tmp_path,**options(c)) as h:
        with pytest.raises(PublicationCheckError) as e:
            recheck_publication(c,other_check.request,held_lock=h,transaction_id=TRANSACTION,authority=ALLOW)
    assert e.value.reason=='publication_request_changed'


def test_inode_replacement_during_authorizer_does_not_gain_fresh_permission(tmp_path):
    m,p,c=prepared(tmp_path);f=tmp_path/m.documents[0].path;seen=[]
    def check(r):
        new=f.with_suffix('.tmp');new.write_bytes(f.read_bytes());new.replace(f);return True
    with project_lock(tmp_path,**options(c)) as h:
        with pytest.raises(PublicationCheckError) as e:invoke(c,h,lambda r:seen.append(r),authority=PublicationAuthority('x','1',check))
    assert e.value.exit_code==6 and seen==[]


def test_gate_failure_cannot_be_skipped_using_previous_report(tmp_path):
    from specroad.changes import TargetPolicy
    m,p,c=prepared(tmp_path);g=gate('extension:required');policy=TargetPolicy('ordinary-change','1',('extension:required',))
    c=prepare_publication_check(p,m,policy=policy,gates=[g])
    with project_lock(tmp_path,**options(c)) as h:
        with pytest.raises(PublicationCheckError) as e:invoke(c,h,lambda r:True,gates=[])
    assert e.value.reason=='publication_target_not_validated'


def test_forked_handle_is_not_publication_authority(tmp_path):
    # Keep fork out of the threaded xdist worker. The isolated interpreter owns
    # no worker transport thread and proves that the parent lock survives.
    from support.processes import run_python,SOURCE
    body="""import sys,os,json
sys.path[:0]=[sys.argv[1],sys.argv[2]]
from pathlib import Path
from support.publication import prepared,options,invoke
from specroad.changes import project_lock,PublicationCheckError
m,p,c=prepared(Path(sys.argv[3]))
with project_lock(sys.argv[3],**options(c)) as h:
 reader,writer=os.pipe();pid=os.fork()
 if pid==0:
  os.close(reader)
  try:invoke(c,h,lambda r:True)
  except PublicationCheckError as e:os.write(writer,json.dumps({'blocked':True,'reason':e.reason}).encode())
  except BaseException:os.write(writer,b'{"unexpected":true}')
  else:os.write(writer,b'{"blocked":false}')
  os.close(writer);os._exit(0)
 os.close(writer)
 try:result=json.loads(os.read(reader,4096))
 finally:os.close(reader);os.waitpid(pid,0)
 assert result['blocked'] and h.check()
 assert invoke(c,h,lambda r:True)
"""
    run=run_python(['-I','-S','-B','-c',body,str(SOURCE),str(Path(__file__).parent),str(tmp_path/'project')],tmp_path,capture=True)
    assert run.returncode==0,run.stderr


def test_strict_invalid_option_does_not_create_lock(tmp_path):
    m,p,c=prepared(tmp_path)
    with pytest.raises(PublicationCheckError) as e:prepare_publication_check(p,m,policy=POLICY,strict=1)
    assert e.value.exit_code==2 and not (tmp_path/'.specroad').exists()


def test_permission_check_does_not_rewrite_read_only_files_to_fix_them(tmp_path):
    m,p,c=prepared(tmp_path);f=tmp_path/m.documents[0].path;f.chmod(0o400);raw=f.read_bytes()
    with project_lock(tmp_path,**options(c)) as h:
        with pytest.raises(PublicationCheckError):invoke(c,h,lambda r:True)
    assert f.stat().st_mode&0o777==0o400 and f.read_bytes()==raw


def test_shifted_module_and_zipapp_retain_live_publication_guard(tmp_path):
    from support.portable import build_distribution
    from support.processes import run_python
    m,p,c=prepared(tmp_path/'project')
    values={'root':m.binding.source_root,'plan':p.source_bytes.decode(),
        'config':m.configuration_bytes.decode(),
        'artifacts':[{'path':d.path,'data':d.content.decode()} for d in m.documents],
        'resources':[{'path':d.path,'data':d.content.decode()} for d in m.resource_files]}
    incoming=tmp_path/'input.json';incoming.write_bytes(canonical_json_bytes(values))
    module,archive=build_distribution(tmp_path/'delivery')
    moved=tmp_path/'moved';module.rename(moved);pyz=tmp_path/'moved.pyz';archive.rename(pyz)
    body='''import sys,json
sys.path.insert(0,sys.argv[1])
from pathlib import Path
from specroad.changes import (TargetModel,TargetPolicy,ChangePlan,prepare_publication_check,
    recheck_publication,project_lock,PublicationAuthority)
from specroad.model.model_manifest import ProjectReadBinding
from specroad.profiles import ProfileResource,compose_profiles
from specroad.validation import ModelDocument
v=json.loads(Path(sys.argv[2]).read_bytes());root=Path(v['root']);st=root.stat()
resources=[ModelDocument(d['path'],d['data'].encode()) for d in v['resources']]
profiles=[ProfileResource(d.content) for d in resources]
profile=compose_profiles(profiles,core_key=profiles[0].key)
m=TargetModel(v['config'].encode(),ProjectReadBinding('sample',str(root),(st.st_dev,st.st_ino)),
    [ModelDocument(d['path'],d['data'].encode()) for d in v['artifacts']],profile=profile,resource_files=resources)
p=ChangePlan(v['plan'].encode());c=prepare_publication_check(p,m,policy=TargetPolicy('ordinary-change','1',()))
with project_lock(root,kind='writer',command='change apply',project_id='sample',request_id=p.data['request_id'],transaction_id='portable') as h:
 r=recheck_publication(c,c.request,held_lock=h,transaction_id='portable',authority=PublicationAuthority('explicit-host','1',lambda request:True))
 assert r.data['ready_for_backend'] and r.data['normative_writes']==0 and h.check()
'''
    for location in (moved,pyz):
        run=run_python(['-I','-S','-B','-c',body,str(location),str(incoming)],tmp_path,capture=True)
        assert run.returncode==0,run.stderr
