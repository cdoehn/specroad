"""Bound resolved queries, independent inclusion paths and rejected partial sets."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from concurrent.futures import ThreadPoolExecutor
import pytest
from specroad.languages.containers import (ContainerLanguageError, ResolvedRequirementScope, QueryRows,
    project_containers, document_containers, evaluate_project_languages, evaluate_document_languages)
from specroad.model.errors import ModelError
from specroad.model.canonical import canonical_json_sha256
from specroad.model.language_policy import LanguagePolicy
from specroad.storage.language_registry import bundled_language_registry
from support.containers import node,edge,model,presentation,ref_block,token
from support.records import block_value
from support.io_guards import block_imports_and_open

@pytest.fixture(scope='module')
def registry(): return bundled_language_registry()

def report(m,root,registry,**kwargs):
    return evaluate_document_languages(m,root,registry=registry,policy=LanguagePolicy(kwargs.pop('policy',{})),**kwargs)

def include(target, number=1):
    b=block_value('include_document');b['id']=b['id'][:-26]+token(number)
    b['payload']['mode']='section' if target['artifact_type']=='section' else 'content'
    b['relations']=[edge('references',target,300000+number)]
    return b

def query_graph(kind='query'):
    d,s=node('document'),node('section')
    b=node('content_block', block_kind=kind, payload=({'source':'view'} if kind=='table' else
        {'source':'view','columns':[{'field':'/title'}],'empty_policy':'omit'}))
    v=node('view');b['relations']=[edge('references',v,500)]
    d['relations']=[edge('contains',s,1)];s['relations']=[edge('contains',b,2)]
    return d,s,b,v

def rows(m,b,*ids,path=('REL-'+token(1),'REL-'+token(2)),**kwargs):
    return QueryRows(m.sha256,b['id'],path,ids,**kwargs)

def scope_for(m,cfg,*ids):
    return ResolvedRequirementScope(m.sha256,cfg['id'],canonical_json_sha256(cfg),ids)


def test_included_document_subsections_and_historical_members(registry):
    a=node('requirement',1,language='de');b=node('requirement',2,language='en',maturity='rejected')
    d,s,t,u=node('document',1),node('section',1),node('document',2),node('section',2)
    x,y=ref_block(a,1),ref_block(b,2);inc=include(t,3)
    d['relations']=[edge('contains',s,1)];s['relations']=[edge('contains',x,2),edge('contains',inc,3)]
    t['relations']=[edge('contains',u,4)];u['relations']=[edge('contains',y,5)]
    result=report(model(d,s,t,u,x,y,inc,a,b),d['id'],registry)
    assert len(result)==4 and result[0]['mixed'] and result[1]['mixed']
    assert result[2]['requirement_ids']==[b['id']] and result[3]['requirement_ids']==[b['id']]

@pytest.mark.parametrize('kind',['query','table'])
def test_query_rows_not_query_text_or_view_filter_decide_membership(registry,kind):
    d,s,b,v=query_graph(kind);a=node('requirement',1,language='de');z=node('requirement',2,language='en')
    a['relations']=[edge('depends_on',z,99)]
    m=model(d,s,b,v,a,z)
    with pytest.raises(ContainerLanguageError,match='presentation_resolver_required'): document_containers(m,d['id'])
    out=report(m,d['id'],registry,query_rows=[rows(m,b,a['id'],a['id'])])
    assert all(x['requirement_ids']==[a['id']] and not x['mixed'] for x in out)


def test_embedded_query_uses_same_explicit_result_boundary(registry):
    d,s,b,v=query_graph();b['payload']={'query':{'opaque':'not executed'},'columns':[{'field':'/id'}],'empty_policy':'omit'}
    b['relations']=[];a=node('requirement',language='ja');m=model(d,s,b,a)
    assert report(m,d['id'],registry,query_rows=[rows(m,b,a['id'])])[0]['tags']==['ja']


def test_each_inclusion_path_gets_own_query_result(registry):
    d,s,b,v=query_graph();outside,root=node('document',2),node('section',2)
    i,j=include(d,2),include(d,3)
    outside['relations']=[edge('contains',root,10)]
    root['relations']=[edge('contains',i,11),edge('contains',j,12)]
    a,z=node('requirement',1,language='de'),node('requirement',2,language='en')
    m=model(outside,root,i,j,d,s,b,v,a,z)
    prefix=('REL-'+token(10),)
    paths=[prefix+('REL-'+token(n),'REL-'+token(300000+k),'REL-'+token(1),'REL-'+token(2)) for n,k in [(11,2),(12,3)]]
    qr=[rows(m,b,x['id'],path=p) for p,x in zip(paths,[a,z])]
    out=report(m,outside['id'],registry,query_rows=qr)
    subdocs=[x for x in out if x['container_id']==d['id']]
    assert len(subdocs)==2 and all(not x['mixed'] for x in subdocs)
    assert subdocs[0]['requirement_ids']==[a['id']] and subdocs[1]['requirement_ids']==[z['id']]
    assert out[0]['mixed'] and out[1]['mixed']


def test_scope_uses_explicit_applicability_not_hidden_defaults(registry):
    a,z=node('requirement',1,language='de'),node('requirement',2,language='en')
    m,d,s=presentation(a,z);cfg=node('configuration');m=model(*m.values().values(),cfg)
    selection=scope_for(m,cfg,a['id'])
    r=evaluate_project_languages(m,registry=registry,policy=LanguagePolicy({}),scope=selection)
    assert r['requirement_ids']==[a['id']] and r['configuration']['configuration_id']==cfg['id']
    assert all(x['requirement_ids']==[a['id']] for x in report(m,d,registry,scope=selection))


def test_explicit_historical_scope_member_retained_in_doc_only(registry):
    a=node('requirement',language='en',maturity='superseded');m,d,s=presentation(a);cfg=node('configuration')
    m=model(*m.values().values(),cfg);selection=scope_for(m,cfg,a['id'])
    assert project_containers(m,scope=selection)[0]['requirement_ids']==[]
    assert document_containers(m,d,scope=selection)[0]['requirement_ids']==[a['id']]

@pytest.mark.parametrize('change',['source','configuration','type','incomplete','duplicate'])
def test_stale_or_invalid_scope_is_not_an_unfiltered_success(change):
    a=node('requirement');cfg=node('configuration');m=model(a,cfg);s=scope_for(m,cfg,a['id'])
    with pytest.raises(ModelError):
        if change=='source':
            a['statement']='Changed';project_containers(model(a,cfg),scope=s)
        elif change=='configuration': project_containers(m,scope=replace(s,configuration_sha256='0'*64))
        elif change=='type': project_containers(m,scope=replace(s,requirement_ids=(cfg['id'],)))
        elif change=='incomplete': replace(s,complete=False)
        else: replace(s,requirement_ids=(a['id'],a['id']))

@pytest.mark.parametrize('change',['stale','path','duplicate','unconsumed','missing','incomplete','configuration'])
def test_bad_query_observations_are_errors_not_empty_success(change):
    d,s,b,v=query_graph();a=node('requirement');m=model(d,s,b,v,a);r=rows(m,b,a['id'])
    with pytest.raises(ModelError):
        if change=='stale': qr=[replace(r,model_sha256='a'*64)]
        elif change=='path': qr=[replace(r,occurrence_path=('REL-'+token(13),))]
        elif change=='duplicate': qr=[r,r]
        elif change=='unconsumed': qr=[r,replace(r,occurrence_path=('REL-'+token(13),))]
        elif change=='missing': qr=[replace(r,artifact_ids=(a['id'][:-1]+'4',))]
        elif change=='incomplete': qr=[replace(r,complete=False)]
        else: qr=[replace(r,configuration_sha256='a'*64)]
        document_containers(m,d['id'],query_rows=qr)

@pytest.mark.parametrize('policy',['omit','message','error'])
def test_explicit_empty_query_selection_obeys_display_contract(registry,policy):
    d,s,b,v=query_graph();b['payload']['empty_policy']=policy;m=model(d,s,b,v)
    if policy=='error':
        with pytest.raises(ModelError,match='empty_query_display'):document_containers(m,d['id'],query_rows=[rows(m,b)])
    else: assert all(not x['mixed'] for x in report(m,d['id'],registry,query_rows=[rows(m,b)]))


def test_query_rejects_requirements_excluded_by_bound_configuration():
    d,s,b,v=query_graph();a=node('requirement');cfg=node('configuration');m=model(d,s,b,v,a,cfg)
    scope=scope_for(m,cfg)
    with pytest.raises(ModelError,match='query_scope_mismatch'):
        document_containers(m,d['id'],scope=scope,query_rows=[rows(m,b,a['id'],configuration_sha256=scope.configuration_sha256)])


def test_nonrequirement_query_rows_do_not_expand_relations(registry):
    d,s,b,v=query_graph();a=node('requirement',language='en');g=ref_block(a,3)
    m=model(d,s,b,v,a,g);out=report(m,d['id'],registry,query_rows=[rows(m,b,g['id'])])
    assert all(x['tags']==[] for x in out)

@pytest.mark.parametrize('cycle',['contains','include'])
def test_presentation_cycles_fail_without_partial_report(cycle):
    d,s,t=node('document'),node('section',1),node('section',2)
    d['relations']=[edge('contains',s,1)]
    if cycle=='contains':
        s['relations']=[edge('contains',t,2)];t['relations']=[edge('contains',s,3)];m=model(d,s,t)
    else:
        b=include(d);s['relations']=[edge('contains',b,2)];m=model(d,s,b)
    with pytest.raises(ModelError,match='presentation_cycle'): document_containers(m,d['id'])


def test_deep_inclusion_free_graph_and_complete_membership():
    d=node('document');sections=[node('section',i+1) for i in range(1100)];a=node('requirement');b=ref_block(a)
    d['relations']=[edge('contains',sections[0],1)]
    for i,s in enumerate(sections):s['relations']=[edge('contains',sections[i+1] if i+1<len(sections) else b,i+2)]
    result=document_containers(model(d,*sections,b,a),d['id'])
    assert len(result)==1101 and all(x['requirement_ids']==[a['id']] for x in result)


def test_query_result_not_cut_at_display_limit(registry):
    d,s,b,v=query_graph();rs=[node('requirement',i+1,language='de' if i%2 else 'en') for i in range(151)]
    m=model(d,s,b,v,*rs);r=report(m,d['id'],registry,query_rows=[rows(m,b,*(x['id'] for x in reversed(rs)))])[0]
    assert len(r['requirement_ids'])==151 and r['tags']==['de','en'] and r['mixed']


def test_owned_query_rows_and_simultaneous_reuse(registry):
    d,s,b,v=query_graph();a=node('requirement');m=model(d,s,b,v,a);ids=[a['id']]
    qr=QueryRows(m.sha256,b['id'],['REL-'+token(1),'REL-'+token(2)],ids);ids.clear()
    expected=report(m,d['id'],registry,query_rows=[qr])
    with ThreadPoolExecutor(max_workers=2) as pool:
        out=list(pool.map(lambda _: report(m,d['id'],registry,query_rows=[qr]),range(4)))
    assert out==[expected]*4 and qr.artifact_ids==(a['id'],)
    with pytest.raises(FrozenInstanceError):qr.complete=False


def test_empty_model_requires_real_registry_and_valid_failure_policy():
    m=model()
    for kwargs in ({'registry':None}, {'registry':bundled_language_registry(),'fail_on':'nonsense'}):
        with pytest.raises(ModelError):evaluate_project_languages(m,policy=LanguagePolicy({}),**kwargs)


def test_no_io_or_detector_needed_during_declared_evaluation(registry):
    m,d,s=presentation(node('requirement',language='de',statement='This English text must remain unchanged'))
    before=m.values()
    # Establish trusted bindings before blocking imports; mirror the 3.10-safe guard.
    with block_imports_and_open():
        out=report(m,d,registry)
    assert out[0]['tags']==['de'] and m.values()==before


def test_semantic_model_binding_is_order_and_format_independent():
    a=node('requirement');b=node('requirement',2,language='en');d,s,q,v=query_graph()
    one=model(a,b,d,s,q,v);two=model(v,q,s,d,b,a)
    assert one.sha256==two.sha256
    assert document_containers(two,d['id'],query_rows=[rows(one,q,a['id'])])[0]['requirement_ids']==[a['id']]


def test_invalid_registry_binding_rejected_even_without_requirements():
    registry=bundled_language_registry();object.__setattr__(registry,'sha256','0'*64)
    with pytest.raises(ModelError):evaluate_project_languages(model(),registry=registry,policy=LanguagePolicy({}))


def test_failed_projection_does_not_modify_model_or_later_results(registry):
    d,s,b,v=query_graph();a=node('requirement');m=model(d,s,b,v,a);before=m.values()
    with pytest.raises(ModelError):report(m,d['id'],registry)
    out=report(m,d['id'],registry,query_rows=[rows(m,b,a['id'])])
    assert m.values()==before and out[0]['requirement_ids']==[a['id']]


def test_portable_container_model_and_language_policy(tmp_path):
    import json
    import subprocess
    import sys
    from support.portable import build_distribution
    from support.artifacts import artifact_bytes
    dist=tmp_path/'dist';build_distribution(dist)
    moved=tmp_path/'relocated';dist.rename(moved)
    values=[node('requirement',1,language='en-US'),node('requirement',2,language='en-IN')]
    snippet='''import json,sys
sys.path.insert(0,sys.argv[1])
from specroad.languages.containers import ContainerModel,evaluate_project_languages
from specroad.model.language_policy import LanguagePolicy
from specroad.storage.language_registry import bundled_language_registry
m=ContainerModel([json.dumps(x).encode() for x in json.loads(sys.argv[2])])
p=LanguagePolicy({'mixed_languages':{'comparison':'exact_tag','project':'warning'}})
r=evaluate_project_languages(m,policy=p,registry=bundled_language_registry())
print(json.dumps({'mixed':r['mixed'],'tags':r['tags'],'code':r['diagnostics'][-1]['code']}))
'''
    for where in (moved/'module',moved/'specroad.pyz'):
        proc=subprocess.run([sys.executable,'-I','-B','-c',snippet,str(where),json.dumps(values)],
            cwd=tmp_path,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,check=True)
        assert json.loads(proc.stdout)=={'mixed':True,'tags':['en-IN','en-US'],'code':'SRV180'}
