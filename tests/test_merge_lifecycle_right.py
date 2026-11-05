"""17.f.R: retirement, immutable originals and bound source safety."""
from hashlib import sha256
import json
from unittest.mock import patch

import pytest

from specroad.authoring._inspection_snapshot import InspectionSnapshot
from specroad.merge import inspect_merge_lifecycle, SourceRequest, load_merge_sources
from specroad.model.canonical import canonical_json_bytes as jcs
from specroad.model.errors import ModelError
from specroad.model.paths import artifact_path
from support.merge_lifecycle import artifact, bound_records, changed, decision, with_successors
from support.merge_relations import history_for
from support.model import put
from support.read_only import inventory
from support.records import record_value
from support.relations import aid, edge
from test_merge_inventory import bind_files
from test_merge_lifecycle import original
from test_merge_sources import read_only_sources, sources as source_kinds, KINDS
from test_project_bundle import baseline_project


@pytest.mark.parametrize('side', ['ours','theirs'])
@pytest.mark.parametrize('field,content', [('title','Changed'), ('statement','Changed statement'),
    ('owner','Another owner'), ('relations',[edge(kind='conflicts_with', target=aid(number=0))]),
    ('extensions',{'vendor.merge':{'x':1}})])
def test_retirement_against_any_normative_content_change_is_blocked(tmp_path, original, side, field, content):
    path, old = artifact(original)
    retired = changed(old, maturity='retired')
    edited = changed(old, **{field:content})
    variants = [old, retired, edited] if side=='ours' else [old, edited, retired]
    sources, history = bound_records(tmp_path, original, path, variants)
    before = inventory(tmp_path)
    with read_only_sources(): result = inspect_merge_lifecycle(sources, history=history)
    conflict, = result.conflicts
    assert conflict['kind'] == 'retirement_content_conflict'
    assert conflict['original_values'] == dict(zip(('base','ours','theirs'),variants))
    assert inventory(tmp_path) == before and not result.approval_granted


@pytest.mark.parametrize('representation', [False,True])
def test_audit_and_representation_changes_are_not_invented_content_changes(tmp_path, original, representation):
    path, old = artifact(original)
    edited = changed(old, revision=2, updated_at='2026-01-02T00:00:00Z',
                     updated_by={'actor_type':'tool','actor_id':'synthetic'})
    if representation: edited = json.dumps(old, indent=3).encode() + b'\n'
    sources, history = bound_records(tmp_path, original, path, [old, changed(old, maturity='retired'), edited])
    assert inspect_merge_lifecycle(sources, history=history).compatible


def test_typed_json_content_is_not_collapsed_by_python_boolean_numeric_equality(tmp_path, original):
    path, old = artifact(original)
    old['extensions'] = {'vendor.merge':False}
    sources, history = bound_records(tmp_path, original, path,
        [old, changed(old,maturity='retired'), changed(old,extensions={'vendor.merge':0})])
    assert inspect_merge_lifecycle(sources, history=history).conflicts[0]['kind'] == 'retirement_content_conflict'


@pytest.mark.parametrize('state', ['draft','proposed','approved'])
def test_retired_identity_cannot_be_reactivated_by_one_branch(tmp_path, original, state):
    path, old = artifact(original)
    old.update(maturity='retired', success_criterion=['Synthetic stored field, not review authority.'])
    sources, history = bound_records(tmp_path, original, path, [old, old, changed(old,maturity=state)])
    assert inspect_merge_lifecycle(sources, history=history).conflicts[0]['kind'] == 'lifecycle_reactivation'


@pytest.fixture(scope='module')
def protected_samples(tmp_path_factory, original):
    root = tmp_path_factory.mktemp('lifecycle-baseline')/'project'
    baseline_project(root)
    baseline_files = InspectionSnapshot(root, None, include_archive_objects=True).raw
    path, value = artifact(baseline_files, 'baseline')
    result = {'baseline':(baseline_files,path,value)}
    for kind, status, maturity in [('evidence',None,None), ('relation_review',None,None),
        ('proposal','applied','approved'), ('proposal','rejected','rejected'), ('proposal','stale','retired')]:
        if kind=='evidence':
            path,value=artifact(original,kind)
        else:
            value=record_value(kind, **({} if status is None else {'proposal_status':status,'maturity':maturity}))
            path=artifact_path(kind,value['id'],'SR')
        result[status or kind]=(original,path,value)
    return result


@pytest.mark.parametrize('kind', ['evidence','baseline','relation_review','applied','rejected','stale'])
@pytest.mark.parametrize('change', ['same','format','revision','content'])
def test_all_protected_kinds_use_original_bytes_before_any_equality_shortcut(tmp_path, protected_samples, kind, change):
    original,path,value=protected_samples[kind]
    raw=jcs(value)
    altered={'same':raw, 'format':json.dumps(value,indent=2).encode()+b'\n',
        'revision':jcs(changed(value,revision=value['revision']+1)),
        'content':jcs(changed(value,title='A rewritten original'))}[change]
    sources,history=bound_records(tmp_path,original,path,[raw,raw,altered])
    before=inventory(tmp_path)
    with read_only_sources(): result=inspect_merge_lifecycle(sources,history=history)
    assert inventory(tmp_path)==before
    assert not result.ready and not result.approval_granted
    if change=='same':
        assert result.originals[path]==raw and decision(result,value['id'])['protected']
    else:
        conflict,=result.conflicts
        assert conflict['kind']=='immutable_original_change'
        assert conflict['base']['byte_sha256']==sha256(raw).hexdigest()
        assert conflict['theirs']['byte_sha256']==sha256(altered).hexdigest()
        with pytest.raises(ModelError): _=result.originals


@pytest.mark.parametrize('state,maturity', [('draft','draft'), ('validated','proposed'),
    ('checked','proposed'), ('in_review','in_review'), ('approved','approved')])
def test_active_proposal_is_not_misclassified_as_an_immutable_original(tmp_path, original, state, maturity):
    path,old=artifact(original,'proposal');old.update(proposal_status=state,maturity=maturity)
    sources,history=bound_records(tmp_path,original,path,[old,old,changed(old,title='Changed active proposal')])
    result=inspect_merge_lifecycle(sources,history=history)
    assert result.compatible and not decision(result,old['id'])['protected']
    assert path not in result.originals and not result.approval_granted


def test_specialist_status_conflicts_even_when_maturity_is_identical(tmp_path, original):
    path,old=artifact(original,'proposal')
    variants=[old,changed(old,proposal_status='validated',maturity='proposed'),
              changed(old,proposal_status='checked',maturity='proposed')]
    sources,history=bound_records(tmp_path,original,path,variants)
    assert inspect_merge_lifecycle(sources,history=history).conflicts[0]['kind']=='lifecycle_transition_conflict'


@pytest.mark.parametrize('presence', [(True,False,True),(True,True,False),(True,False,False)])
@pytest.mark.parametrize('kind', ['goal','evidence'])
def test_missing_original_or_artifact_does_not_prove_deletion(tmp_path,original,presence,kind):
    path,old=artifact(original,kind)
    sources,history=bound_records(tmp_path,original,path,[old if p else None for p in presence])
    conflict,=inspect_merge_lifecycle(sources,history=history).conflicts
    assert conflict['kind']=='artifact_absence_unproven'
    for role,present in zip(('base','ours','theirs'),presence):
        assert conflict[role]['state']==('present' if present else 'absent')


def test_new_shared_identity_without_base_still_has_conflicting_lifecycle_states(tmp_path,original):
    path,old=artifact(original)
    sources,history=bound_records(tmp_path,original,path,[None,old,changed(old,maturity='proposed')])
    assert inspect_merge_lifecycle(sources,history=history).conflicts[0]['kind']=='lifecycle_transition_conflict'


def test_different_outgoing_supersession_targets_are_not_merged_as_independent_edges(tmp_path,original):
    _,old=artifact(original)
    variants=with_successors(original,old)
    owner_path=artifact_path('goal',aid('goal',1),'SR')
    for files,target in zip(variants[1:],(old['id'],aid('goal',2))):
        owner=json.loads(files[owner_path]);owner['relations']=[edge(kind='supersedes',target=target)]
        files[owner_path]=jcs(owner)
    sources=bind_files(tmp_path,variants)
    conflict,=inspect_merge_lifecycle(sources,history=history_for(sources)).conflicts
    assert conflict['kind']=='supersession_target_conflict'
    assert conflict['identity']['id']==aid('goal',1)
    assert conflict['supersedes_ids']=={'base':[],'ours':[old['id']],'theirs':[aid('goal',2)]}


def test_superseded_state_requires_an_actual_inverse_successor(tmp_path,original):
    path,old=artifact(original)
    sources,history=bound_records(tmp_path,original,path,[old,old,changed(old,maturity='superseded')])
    assert inspect_merge_lifecycle(sources,history=history).conflicts[0]['kind']=='supersession_target_missing'


@pytest.mark.parametrize('kind',KINDS)
def test_guard_uses_all_native_source_kinds_without_a_new_loader(tmp_path,kind):
    requests,_,_,_=source_kinds(tmp_path)
    sources=load_merge_sources(requests['local'],requests[kind],requests['local'])
    history=history_for(sources);before=inventory(tmp_path)
    with read_only_sources(): result=inspect_merge_lifecycle(sources,history=history)
    assert result.compatible and inventory(tmp_path)==before


def test_real_legacy_originals_keep_their_registered_bytes(tmp_path):
    from support.legacy_manifest import migrated,write_files,MANIFEST
    _,files,_=migrated();root=tmp_path/'project';write_files(root,files)
    sources=load_merge_sources(*(SourceRequest(root) for _ in range(3)))
    history=history_for(sources);before=inventory(root)
    with read_only_sources(): result=inspect_merge_lifecycle(sources,history=history)
    paths={row['path'] for row in json.loads(files[MANIFEST])['entries'] if row['path'].startswith('spec/')}
    assert paths and paths<=set(result.originals)
    assert {path:result.originals[path] for path in paths}=={path:files[path] for path in paths}
    assert inventory(root)==before and not result.approval_granted


@pytest.mark.parametrize('when',['before','during'])
def test_current_sources_are_rechecked_before_and_after_calculation(tmp_path,original,when):
    path,old=artifact(original)
    sources,history=bound_records(tmp_path,original,path,[old]*3)
    def mutate(): put(tmp_path/'ours',path,jcs(changed(old,title='Late source mutation')))
    if when=='before':
        mutate()
        with pytest.raises(ModelError): inspect_merge_lifecycle(sources,history=history)
    else:
        from specroad.merge.lifecycle import _successors
        def mutate_during(*args,**kwargs):
            mutate();return _successors(*args,**kwargs)
        with patch('specroad.merge.lifecycle._successors',side_effect=mutate_during),pytest.raises(ModelError):
            inspect_merge_lifecycle(sources,history=history)


def test_known_collision_precedes_even_identical_or_protected_content(tmp_path,original):
    path,old=artifact(original,'evidence')
    sources,history=bound_records(tmp_path,original,path,[old]*3)
    row=next(row for row in history['observations'] if row['role']=='theirs' and row['identity']['id']==old['id'])
    row['origin']['creation_event']='different-known-event'
    with read_only_sources(),patch('os.urandom',side_effect=AssertionError('random rename')):
        result=inspect_merge_lifecycle(sources,history=history)
    conflict,=result.conflicts
    assert conflict['kind']=='identity_collision' and conflict['diagnostic_code']=='SRV101'
    with pytest.raises(ModelError): _=result.originals


def test_stale_history_binding_cannot_be_used_as_a_guard_input(tmp_path,original):
    path,old=artifact(original)
    sources,history=bound_records(tmp_path,original,path,[old]*3)
    history['source_bindings_sha256']='0'*64
    with pytest.raises(ModelError) as error:
        inspect_merge_lifecycle(sources,history=history)
    assert error.value.reason=='merge_history_source_mismatch'
