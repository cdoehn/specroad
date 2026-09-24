"""S.5 declared selections and machine diagnostics, never presentation wording."""
from dataclasses import FrozenInstanceError
import pytest
from specroad.languages.containers import (ContainerModel, ContainerLanguageError, project_containers,
    document_containers, evaluate_project_languages, evaluate_document_languages)
from specroad.model.errors import ModelError
from specroad.model.language_policy import LanguagePolicy
from specroad.storage.language_registry import bundled_language_registry
from specroad.storage.record_artifact import RecordArtifact
from support.artifacts import artifact_bytes
from support.containers import node, edge, model, presentation, ref_block

@pytest.fixture(scope='module')
def registry(): return bundled_language_registry()

def project(m, registry, **kwargs):
    return evaluate_project_languages(m, registry=registry, policy=LanguagePolicy(kwargs.pop('policy', {})), **kwargs)

def documents(m, root, registry, **kwargs):
    return evaluate_document_languages(m, root, registry=registry, policy=LanguagePolicy(kwargs.pop('policy', {})), **kwargs)

def test_project_membership_excludes_only_historical_requirements(registry):
    requirements = [node('requirement', i+1, maturity=s, rationale='Synthetic field rationale', language=('de' if i==0 else 'en'))
                    for i,s in enumerate(['draft','in_review','approved','retired','superseded','rejected'])]
    # Only instance-local fields are validated; this is not a provenance gate.
    m = model(*requirements)
    report = project(m, registry)
    assert report['requirement_ids'] == sorted(r['id'] for r in requirements[:3])
    assert report['mixed'] and report['action'] == 'allow'
    assert not any(d['code']=='SRV180' for d in report['diagnostics'])

@pytest.mark.parametrize('comparison,expected', [('primary_language',False),('exact_tag',True)])
def test_comparison_mode_is_explicit(registry, comparison, expected):
    m=model(node('requirement',1,language='en-US'),node('requirement',2,language='en-IN'))
    assert project(m,registry,policy={'mixed_languages':{'comparison':comparison}})['mixed'] is expected

@pytest.mark.parametrize('languages,expected', [(['x-one','x-two'],True),(['qzz-US','qzz-GB'],True),
    (['und','mul','zxx'],False),(['de','und'],False),(['EN-us','en-US'],False)])
def test_private_unregistered_unspecified_and_case_rules(registry,languages,expected):
    r=project(model(*(node('requirement',i+1,language=v) for i,v in enumerate(languages))),registry)
    assert r['mixed'] is expected
    if 'und' in languages: assert any(d['code']=='SRV181' for d in r['diagnostics'])

@pytest.mark.parametrize('kind',['project','document','section'])
def test_empty_container_is_not_mixed(registry,kind):
    m=model() if kind=='project' else model(node(kind))
    r=project(m,registry) if kind=='project' else documents(m,node(kind)['id'],registry)[0]
    assert r['requirement_ids']==[] and r['tags']==[] and r['mixed'] is False


def test_presentation_uses_references_not_trace_closure(registry):
    a=node('requirement',1,language='de'); b=node('requirement',2,language='en')
    a['relations']=[edge('depends_on',b,77)]
    plain=dict(a);plain['relations']=[]
    m,doc,section=presentation(plain)
    # The complete reference model includes B, but the document does not display B.
    values=m.values(); values[a['id']]=a; m=model(*values.values(),b)
    reports=documents(m,doc,registry)
    assert len(reports)==2 and all(r['requirement_ids']==[a['id']] and not r['mixed'] for r in reports)


def test_explicit_historical_reference_counts_in_document(registry):
    a=node('requirement',1,language='de',maturity='retired');b=node('requirement',2,language='en')
    m,doc,section=presentation(a,b)
    assert project(m,registry)['requirement_ids']==[b['id']]
    assert all(r['mixed'] for r in documents(m,doc,registry))


def test_nested_section_sets_and_parent_are_separate(registry):
    a=node('requirement',1,language='de'); b=node('requirement',2,language='en')
    d,s,t=node('document'),node('section',1),node('section',2)
    x,y=ref_block(a,1),ref_block(b,2)
    d['relations']=[edge('contains',s,1)];s['relations']=[edge('contains',x,2),edge('contains',t,3)]
    t['relations']=[edge('contains',y,4)]
    out=documents(model(d,s,t,x,y,a,b),d['id'],registry)
    byid={r['container_id']:r for r in out}
    assert byid[d['id']]['mixed'] and byid[s['id']]['mixed']
    assert not byid[t['id']]['mixed']


def test_duplicate_rendered_reference_counts_once(registry):
    a=node('requirement',1,language='de')
    d,s=node('document'),node('section'); x,y=ref_block(a,1),ref_block(a,2)
    d['relations']=[edge('contains',s,1)];s['relations']=[edge('contains',x,2),edge('contains',y,3)]
    for r in documents(model(d,s,x,y,a),d['id'],registry):
        assert r['requirement_ids']==[a['id']] and len(r['declarations'])==1

@pytest.mark.parametrize('action,severity,exitcode',[('allow',None,0),('warning','warning',0),('error','error',1)])
def test_container_override_has_only_own_mixing_effect(registry,action,severity,exitcode):
    a=node('requirement',1,language='de');b=node('requirement',2,language='en')
    m,d,s=presentation(a,b)
    v=m.values();v[s]['language_policy_override']={'mixed_languages':action}
    r=documents(model(*v.values()),d,registry)
    section=next(x for x in r if x['container_id']==s); doc=next(x for x in r if x['container_id']==d)
    assert doc['action']=='warning' and doc['mixed']
    assert section['exit_code']==exitcode
    assert [x['severity'] for x in section['diagnostics'] if x['code']=='SRV180']==([] if severity is None else [severity])


def test_override_does_not_change_project_allowlist(registry):
    a=node('requirement',1,language='en');m,d,s=presentation(a,language_policy_override={'mixed_languages':'allow'})
    r=documents(m,d,registry,policy={'allowed_ranges':['de']})[0]
    assert any(x['code']=='SRV179' and x['severity']=='error' for x in r['diagnostics'])

@pytest.mark.parametrize('options', [{'strict':True},{'fail_on':'warning'}])
def test_threshold_changes_exit_not_warning(registry,options):
    m,d,s=presentation(node('requirement',1,language='de'),node('requirement',2,language='en'))
    r=documents(m,d,registry,**options)[0]
    assert r['exit_code']==1 and [x['severity'] for x in r['diagnostics'] if x['code']=='SRV180']==['warning']

@pytest.mark.parametrize('bad',[None,True,{'mixed_languages':'info'},{'other':'allow'},{'mixed_languages':None}])
def test_record_reader_rejects_invalid_overrides(bad):
    for kind in ('document','section'):
        with pytest.raises(ModelError): RecordArtifact(artifact_bytes(node(kind,language_policy_override=bad)))


def test_original_and_returned_values_are_independent(registry):
    a=node('requirement',language='de');m=model(a);digest=m.sha256
    a['language']='en';values=m.values();values[a['id']]['language']='ja'
    result=project(m,registry);result['tags'].clear()
    assert project(m,registry)['tags']==['de'] and m.sha256==digest
    with pytest.raises(FrozenInstanceError): m.sha256='a'*64


def test_trace_text_ids_and_nonrequirement_reference_are_not_languages(registry):
    d,s,b=node('document'),node('section'),node('content_block',payload={'markdown':'de-DE en-US SR-REQ-00000000000000000000000001'})
    d['relations']=[edge('contains',s,1)];s['relations']=[edge('contains',b,2)]
    r=documents(model(d,s,b),d['id'],registry)
    assert all(x['tags']==[] and not x['language_detection_performed'] for x in r)


def test_full_lists_are_sorted_not_limited(registry):
    rs=[node('requirement',i+1,language='de' if i%2 else 'en') for i in range(151)]
    m=model(*reversed(rs));r=project(m,registry,policy={'mixed_languages':{'project':'error'}})
    assert r['tags']==['de','en'] and len(r['requirement_ids'])==151
    assert r['diagnostics'][-1]['requirement_ids']==r['requirement_ids']
    assert not r['approval_granted'] and not r['project_complete'] and not r['atomic_snapshot']
