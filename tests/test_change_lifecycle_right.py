"""Full lifecycle postconditions and hostile inputs; no CLI/doc snapshots."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
import json
import pytest
from specroad.changes import (prepare_change_lifecycle_bytes, prepare_plan_lifecycle,
    prepare_change_plan, lifecycle_content_sha256, LifecycleError, ChangePlanError)
from specroad.model.canonical import canonical_json_sha256
from specroad.model.errors import ModelError
from support.folds import goal, edit, create, add_relation, remove_relation
from support.change_plans import document, result, scope, operation
from test_change_lifecycle import approved, prepare, transition, retire, ACTOR, TIME


def test_all_49_matrix_pairs_match_independent_contract_or_explicit_gate():
    rows = {'draft': {'proposed','rejected','retired'},
        'proposed': {'draft','in_review','rejected','retired'},
        'in_review': {'draft','proposed','approved','rejected'},
        'approved': {'proposed','superseded','retired'}, 'rejected': {'draft','retired'},
        'superseded': {'retired'}, 'retired': set()}
    for source in rows:
        for dest in rows:
            a = approved() if source == 'approved' else goal(maturity=source)
            b = goal(1); b['relations'] = [add_relation(b,a)['relation']]
            if dest not in rows[source] or dest == 'approved':
                with pytest.raises(LifecycleError): prepare([a,b], [transition(a,dest)])
            else:
                out = prepare([a,b], [transition(a,dest)])
                assert out.artifacts[0]['maturity'] == dest and out.artifacts[0]['revision'] == 2


def test_complete_content_projection_includes_metadata_named_nested_fields():
    a = approved(extensions={'test.audit': {'revision': 1, 'maturity': 'draft'}})
    for field in ('title','owner','statement','language','display_id','tags','extensions'):
        b = deepcopy(a)
        b[field] = {'title': 'Other', 'owner': 'other', 'statement': 'X', 'language': 'en',
            'display_id': 'Display-42', 'tags': ['extra'],
            'extensions': {'test.audit': {'revision': 2, 'maturity': 'draft'}}}[field]
        assert lifecycle_content_sha256(a) != lifecycle_content_sha256(b)
        op = edit(a, 'unused'); op['patch'] = [{'op': 'add','path': '/'+field,'value': b[field]}]
        assert prepare([a],[op]).artifacts[0]['maturity'] == 'proposed'


def test_only_six_top_level_fields_are_excluded():
    a = approved(); b = deepcopy(a)
    b.update(maturity='proposed', revision=100, created_at='2025-01-01T00:00:00Z',
             updated_at='2027-01-01T00:00:00Z', created_by=ACTOR, updated_by=ACTOR)
    assert lifecycle_content_sha256(a) == lifecycle_content_sha256(b)


def test_changed_approved_cannot_transition_back_to_approved_in_same_plan():
    a = approved(); proposed = {**a,'maturity':'proposed'}; review={**a,'maturity':'in_review'}
    ops=[edit(a,'Changed'),transition(a,'proposed'),transition(proposed,'in_review'),transition(review,'approved')]
    with pytest.raises(LifecycleError) as err: prepare([a],ops)
    assert err.value.reason == 'content_lifecycle_conflict' and err.value.exit_code == 2


def test_unchanged_approved_explicit_same_status_is_not_forged_approval():
    a=approved()
    with pytest.raises(LifecycleError) as err:prepare([a],[edit(a,'X'),transition(a,'approved')])
    assert err.value.exit_code == 2


def test_retirement_then_content_change_cannot_evade_final_conflict():
    a=approved()
    with pytest.raises(LifecycleError) as err:prepare([a],[retire(a),edit(a,'X')])
    assert err.value.reason=='content_lifecycle_conflict'


def test_multiple_lifecycle_steps_increment_only_once():
    a=goal(); b={**a,'maturity':'proposed'}
    out=prepare([a],[transition(a,'proposed'),transition(b,'in_review')])
    assert (out.artifacts[0]['maturity'],out.artifacts[0]['revision'])==('in_review',2)
    assert len(out.transition_events)==2


def test_status_roundtrip_is_noop_without_new_revision():
    a=goal();b={**a,'maturity':'proposed'}
    out=prepare([a],[transition(a,'proposed'),transition(b,'draft')])
    assert out.artifacts==[a] and not out.modified_ids and len(out.transition_events)==2


def test_guarded_repeated_retire_is_noop():
    a=goal(maturity='retired',revision=12)
    out=prepare([a],[retire(a)])
    assert out.artifacts==[a] and out.transition_events==[]
    bad=retire(a);bad['expected_revision']=11
    with pytest.raises(LifecycleError):prepare([a],[bad])


def test_transition_from_is_checked_against_immediate_intermediate_state():
    a=goal()
    with pytest.raises(LifecycleError) as err:
        prepare([a],[transition(a,'proposed'),transition(a,'rejected')])
    assert err.value.reason=='expected_maturity_mismatch' and err.value.operation_index==1


def test_hash_guard_sees_lifecycle_change_before_metadata_stamp():
    a=goal();b={**a,'maturity':'proposed'}
    ops=[transition(a,'proposed'),edit(a,'X',expected_sha256=canonical_json_sha256(b))]
    out=prepare([a],ops)
    assert out.artifacts[0]['maturity']=='proposed' and out.artifacts[0]['revision']==2
    ops[1]['expected_sha256']=canonical_json_sha256(a)
    with pytest.raises(LifecycleError):prepare([a],ops)


def test_retire_hash_and_revision_must_both_match():
    a=approved();op=retire(a);op['expected_sha256']='0'*64
    with pytest.raises(LifecycleError) as err:prepare([a],[op])
    assert err.value.reason=='expected_hash_mismatch'


def test_removed_final_successor_is_not_enough():
    a,b=approved(),goal(1);edge=add_relation(b,a)['relation'];b['relations']=[edge]
    with pytest.raises(LifecycleError) as err:
        prepare([a,b],[transition(a,'superseded'),remove_relation(b,edge)])
    assert err.value.reason=='successor_required_in_final_model'


def test_outgoing_supersedes_is_not_a_successor_of_the_source():
    a,b=approved(),goal(1);a['relations']=[add_relation(a,b)['relation']]
    with pytest.raises(LifecycleError):prepare([a,b],[transition(a,'superseded')])


def test_cyclic_successors_cannot_legitimize_supersession():
    a,b=approved(),approved(1)
    a['relations']=[add_relation(a,b,1)['relation']];b['relations']=[add_relation(b,a,2)['relation']]
    with pytest.raises(LifecycleError) as err:prepare([a,b],[transition(a,'superseded')])
    assert err.value.reason=='relation_hierarchy_cycle'


@pytest.mark.parametrize('kind',['proposal','evidence','baseline','relation_review'])
def test_special_artifact_lifecycle_cannot_use_general_path(kind):
    from support.records import record_value
    a=record_value(kind)
    with pytest.raises(ModelError):prepare([a],[retire(a)])


def test_lifecycle_reason_is_kept_in_audit_not_normative_content():
    a=goal();op=transition(a,'rejected',metadata={'reason':'Not needed', 'extra': {'text':'passive'}})
    out=prepare([a],[op]); assert out.artifacts[0]['maturity']=='rejected'
    assert out.transition_events[0]['metadata']==op['metadata']
    assert 'extra' not in out.artifacts[0] and out.artifacts[0]['updated_by']==ACTOR


def test_history_known_ids_remain_reserved_even_if_absent_from_current_scope():
    a=goal();b=goal(1)
    with pytest.raises(LifecycleError) as err:prepare([a],[create(b)],previously_approved_ids=[b['id']])
    assert err.value.reason=='creation_identity_exists'
    out=prepare([a],[edit(a,'X')],previously_approved_ids=[b['id']])
    assert out.previously_approved_ids==[b['id']] and not out.history_complete


def test_observed_approved_identity_survives_retirement_and_content_change():
    a=approved()
    for ops in [[retire(a)],[edit(a,'X')]]:
        out=prepare([a],ops)
        assert out.previously_approved_ids==[a['id']] and out.artifacts[0]['id']==a['id']
        assert out.candidates[0].base_sha256==canonical_json_sha256(a)


def test_history_is_not_claimed_authenticated_or_complete():
    a=goal();out=prepare([a],[],previously_approved_ids=[a['id']])
    out.previously_approved_ids.clear()
    assert out.previously_approved_ids==[a['id']] and out.history_complete is False
    with pytest.raises(LifecycleError):prepare([a],[],previously_approved_ids=[a['id'],a['id']])


def test_delete_not_a_regular_operation_even_for_unapproved_artifacts():
    a=goal()
    with pytest.raises(LifecycleError):prepare([a],[{'op':'delete','target':a['id']}])


def test_plain_field_patch_never_sets_maturity_even_if_reverted_later():
    a=approved();op=edit(a,'X');op['patch']=[{'op':'replace','path':'/maturity','value':'retired'},
                                        {'op':'replace','path':'/maturity','value':'approved'}]
    with pytest.raises(LifecycleError) as err:prepare([a],[op])
    assert err.value.reason=='controlled_field_mutation'


def test_first_operation_failure_stops_following_reducers(monkeypatch):
    import specroad.changes.lifecycle as module
    a=goal();called=[]
    monkeypatch.setattr(module,'_dispatch',lambda *args:called.append(args))
    with pytest.raises(LifecycleError):prepare([a],[transition(a,'approved'),edit(a,'X')])
    assert called==[]


def test_time_and_revision_policy_runs_after_derived_downgrade_once():
    a=approved(revision=8,updated_at='2030-01-01T00:00:00.123456789Z')
    out=prepare([a],[edit(a,'One'),edit(a,'Two')])
    b=out.artifacts[0]
    assert b['updated_at']=='2030-01-01T00:00:00.123457789Z' and b['revision']==9
    assert b['maturity']=='proposed'


def test_owned_model_history_operations_actor_and_events_cannot_alias():
    a=approved();op=retire(a);actor=deepcopy(ACTOR);history=[a['id']]
    saved=deepcopy((a,op,actor,history))
    out=prepare([a],[op],actor=actor,previously_approved_ids=history)
    assert (a,op,actor,history)==saved
    actor['actor_id']='evil';op['reason']='evil';history.clear()
    out.transition_events[0]['actor']['actor_id']='evil'
    assert out.transition_events[0]['actor']==ACTOR
    with pytest.raises(FrozenInstanceError):out.plan_sha256='forged'


def test_actual_bytes_and_noop_representation_are_preserved():
    a=approved();raw=json.dumps(a,ensure_ascii=False,indent=3).encode()
    out=prepare_change_lifecycle_bytes([raw],[edit(a,a['statement'])],
        actor=ACTOR,planned_at=TIME,metadata_policy_version='change-metadata-v1')
    assert out.artifacts==[a] and out.candidates[0].original_bytes==raw and not out.modified_ids


@pytest.mark.parametrize('raw',[b'{"id":1,"id":2}',b'{}{}',b'\xff', '/not/a/readable/path'])
def test_raw_sources_reject_duplicates_trailing_invalid_or_path_input(raw):
    with pytest.raises(ModelError):prepare_change_lifecycle_bytes([raw],[],
        actor=ACTOR,planned_at=TIME,metadata_policy_version='change-metadata-v1')


def saved(a,ops,candidates):
    d=document(ops,[result(v) for v in candidates]);d.update(actor=ACTOR,planned_at=TIME)
    return prepare_change_plan(d)


def verify(plan,a,**kw):
    return prepare_plan_lifecycle(plan,[a],observed_base_root='a'*64,observed_scope=scope(),**kw)


def test_saved_plan_verifies_final_lifecycle_metadata_and_hash():
    a=approved();ops=[edit(a,'New')];out=prepare([a],ops);p=saved(a,ops,[v.data for v in out.candidates])
    verified=verify(p,a)
    assert verified.declared_artifacts_verified and verified.plan_sha256==p.sha256
    assert verified.artifacts==out.artifacts and not verified.expected_result_root_verified


def test_saved_plan_without_declared_downgrade_is_rejected():
    a=approved();ops=[edit(a,'New')];out=prepare([a],ops)
    wrong=out.artifacts[0];wrong['maturity']='approved'
    with pytest.raises(LifecycleError) as err:verify(saved(a,ops,[wrong]),a)
    assert err.value.reason=='declared_lifecycle_result_mismatch'


def test_saved_conflict_is_model_error_even_with_self_consistent_sha():
    a=approved();ops=[edit(a,'New'),retire(a)]
    wrong={**a,'statement':'New','maturity':'retired','revision':2,'updated_at':TIME,'updated_by':ACTOR}
    with pytest.raises(LifecycleError) as err:verify(saved(a,ops,[wrong]),a)
    assert err.value.reason=='content_lifecycle_conflict' and err.value.exit_code==3


def test_wrong_base_root_or_scope_cannot_be_verified():
    a=approved();ops=[retire(a)];out=prepare([a],ops);p=saved(a,ops,out.artifacts)
    with pytest.raises(LifecycleError):prepare_plan_lifecycle(p,[a],observed_base_root='b'*64,observed_scope=scope())
    other=scope();other['boundary_policy']='partial'
    with pytest.raises(LifecycleError):prepare_plan_lifecycle(p,[a],observed_base_root='a'*64,observed_scope=other)


def test_noop_saved_plan_keeps_original_artifact_and_metadata():
    a=approved();ops=[edit(a,a['statement'])]
    out=verify(saved(a,ops,[a]),a)
    assert out.artifacts==[a] and not out.modified_ids


def test_undeclared_actor_or_time_changes_fail_saved_result_verification():
    a=approved();ops=[retire(a)];out=prepare([a],ops)
    for field,new in [('revision',8),('updated_at','2040-01-01T00:00:00Z'),('updated_by',{'actor_type':'ci','actor_id':'fake'})]:
        wrong=out.artifacts[0];wrong[field]=new
        with pytest.raises(ModelError):verify(saved(a,ops,[wrong]),a)


def test_repeated_and_parallel_preparation_is_deterministic():
    a=approved();ops=[edit(a,'New')]
    def run(_):return prepare([a],ops)
    with ThreadPoolExecutor(max_workers=4) as executor: rows=list(executor.map(run,range(16)))
    assert all(v==rows[0] for v in rows) and a['maturity']=='approved'


def test_many_owners_and_repeated_operations_each_stamp_once():
    values=[approved(n,revision=n+1) for n in range(151)]
    ops=[edit(a,'One') for a in values]+[edit(a,'Two') for a in reversed(values)]
    out=prepare(values,ops)
    assert len(out.candidates)==151 and out.operations_applied==302
    assert all(v['maturity']=='proposed' for v in out.artifacts)
    assert [v['revision'] for v in out.artifacts]==list(range(2,153))


def test_lifecycle_planning_does_not_access_io_clock_or_identity_source(monkeypatch):
    import builtins,time,uuid,os
    a=approved();ops=[retire(a)]
    def blocked(*args,**kw):raise AssertionError('unexpected external access')
    for module,name in [(builtins,'open'),(time,'time'),(uuid,'uuid4'),(os,'getlogin')]:monkeypatch.setattr(module,name,blocked)
    assert prepare([a],ops).artifacts[0]['updated_at']==TIME


def test_custom_input_hooks_are_not_executed():
    class Evil(dict):
        def items(self):raise AssertionError('hook ran')
    with pytest.raises(ModelError):prepare([Evil(approved())],[])
    with pytest.raises(ModelError):prepare([],[],actor=Evil(ACTOR))


def test_shifted_module_and_zipapp_expose_same_lifecycle_candidate(tmp_path):
    from support.portable import build_distribution
    from support.processes import run_python
    module,archive=build_distribution(tmp_path/'delivery')
    a=approved(revision=8);ops=[edit(a,'New')]
    body=("import sys;sys.path.insert(0,sys.argv[1]);"
          "from specroad.changes import prepare_change_lifecycle;"
          "r=prepare_change_lifecycle(%r,%r,metadata_policy_version='change-metadata-v1',actor=%r,planned_at=%r);"
          "assert r.artifacts[0]['revision']==9;assert r.artifacts[0]['maturity']=='proposed';"
          "assert r.decisions[0]['approval_withdrawn'];assert not r.write_authorized")%([a],ops,ACTOR,TIME)
    for location in (module,archive):
        proc=run_python(['-I','-S','-B','-c',body,str(location)],tmp_path,capture=True)
        assert proc.returncode==0,proc.stderr


def test_approved_only_fields_can_be_removed_before_derived_downgrade():
    a=approved();op=edit(a,'X');op['patch']=[{'op':'remove','path':'/success_criterion'}]
    out=prepare([a],[op])
    assert out.artifacts[0]['maturity']=='proposed' and 'success_criterion' not in out.artifacts[0]
    assert out.artifacts[0]['revision']==2


def test_intermediate_hash_is_not_computed_using_projected_maturity():
    a=approved();op=edit(a,'X');op['patch']=[{'op':'remove','path':'/success_criterion'}]
    interim=deepcopy(a);interim.pop('success_criterion')
    second=edit(a,'Final',expected_sha256=canonical_json_sha256(interim))
    out=prepare([a],[op,second,transition(a,'proposed')])
    assert out.artifacts[0]['maturity']=='proposed' and out.artifacts[0]['statement']=='Final'


def test_relation_reducers_can_follow_pending_approved_field_removal():
    a,b=approved(),goal(1);op=edit(a,'X');op['patch']=[{'op':'remove','path':'/success_criterion'}]
    add=add_relation(a,b)
    out=prepare([a,b],[op,add,remove_relation(a,add['relation'])])
    assert out.artifacts[0]['maturity']=='proposed' and out.artifacts[0]['relations']==[]
    assert out.artifacts[1]==b


def test_derived_status_does_not_relax_common_field_contracts():
    a=approved();op=edit(a,'X');op['patch']=[{'op':'replace','path':'/statement','value':1}]
    with pytest.raises(LifecycleError):prepare([a],[op])
