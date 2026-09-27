"""Ordered graph edits, negative side-effect witnesses and folding invariants."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from itertools import product
import builtins
import json
import socket
import subprocess
from unittest.mock import patch
import pytest
from specroad.changes import fold_operations, fold_plan_fields, FoldError, prepare_change_plan
from specroad.model.canonical import canonical_json_sha256
from support.folds import goal, edit, create, add_relation, remove_relation
from support.change_plans import document, result, scope
from support.relations import rid, external
from support.domain import domain_value
from support.portable import build_distribution
from support.processes import run_python


def test_add_relation_then_update_observes_previous_graph_state():
    a,b=goal(),goal(1);add=add_relation(a,b);intermediate=deepcopy(a);intermediate['relations']=[add['relation']]
    out=fold_operations([a,b],[add,edit(a,'changed',expected_sha256=canonical_json_sha256(intermediate))])
    assert len(out.candidates)==1 and out.candidates[0].data['relations']==[add['relation']]
    assert out.candidates[0].operation_indices==(0,1)
    assert a['relations']==[] and out.candidates[0].data['revision']==a['revision']


def test_add_remove_reverts_one_candidate_but_retains_operation_history():
    a,b=goal(),goal(1);add=add_relation(a,b)
    out=fold_operations([a,b],[add,remove_relation(a,add['relation'])])
    assert out.candidates[0].data==a and out.candidates[0].operation_indices==(0,1)
    assert not out.candidates[0].changed and out.modified_ids==()


def test_removed_relation_id_is_not_reused_in_the_same_fold():
    a,b=goal(),goal(1);add=add_relation(a,b)
    with pytest.raises(FoldError) as e: fold_operations([a,b],[add,remove_relation(a,add['relation']),add])
    assert e.value.reason=='relation_identity_exists' and e.value.operation_index==2
    assert a['relations']==[]


def test_relation_targets_must_exist_at_the_actual_operation():
    a,b=goal(),goal(1);add=add_relation(a,b)
    with pytest.raises(FoldError) as e: fold_operations([a],[add,create(b)])
    assert e.value.reason=='missing_relation_target' and e.value.operation_index==0
    out=fold_operations([a],[create(b),add])
    assert len(out.candidates)==2 and out.candidates[0].data['relations']==[add['relation']]


def test_create_with_relations_can_use_previously_created_artifacts():
    a,b=goal(),goal(1);a['relations']=[add_relation(a,b)['relation']]
    out=fold_operations([],[create(b),create(a)])
    assert out.artifacts==[a,b] and len(out.candidates)==2
    with pytest.raises(FoldError): fold_operations([],[create(a),create(b)])


def test_new_embedded_relations_and_later_add_share_identity_inventory():
    a,b=goal(),goal(1);add=add_relation(a,b);a['relations']=[add['relation']]
    with pytest.raises(FoldError) as e: fold_operations([b],[create(a),add])
    assert e.value.reason=='relation_identity_exists'


def test_all_relation_payload_metadata_survives_folding():
    a,b=goal(),goal(1)
    add=add_relation(a,b,extensions={'acme.data':{'nested':[1,2]}},external_identities=[external()],
                     created_at=a['created_at'],created_by=a['created_by'])
    out=fold_operations([a,b],[add])
    assert out.candidates[0].data['relations']==[add['relation']]
    add['relation']['extensions']['acme.data']['nested'].append(3)
    assert out.candidates[0].data['relations'][0]['extensions']['acme.data']['nested']==[1,2]


def test_global_relation_id_collisions_are_rejected():
    a,b,c=goal(),goal(1),goal(2)
    a['relations']=[add_relation(a,b)['relation']]
    with pytest.raises(FoldError) as e: fold_operations([a,b,c],[add_relation(b,c)])
    assert e.value.reason=='relation_identity_exists'


def test_duplicate_relation_ids_in_source_inventory_fail_before_operations(monkeypatch):
    import specroad.changes.folding as module
    a,b,c=goal(),goal(1),goal(2)
    a['relations']=[add_relation(a,b)['relation']];b['relations']=[add_relation(b,c)['relation']]
    def forbidden(*args): raise AssertionError('operation executed on invalid source')
    monkeypatch.setattr(module,'_dispatch',forbidden)
    with pytest.raises(FoldError): fold_operations([a,b,c],[edit(c,'changed')])


def test_reserved_relation_ids_are_used_without_mutating_the_inventory():
    a,b=goal(),goal(1);add=add_relation(a,b);reserved=[rid()]
    with pytest.raises(FoldError) as e: fold_operations([a,b],[add],reserved_relation_ids=reserved)
    assert e.value.reason=='relation_identity_exists' and reserved==[rid()]


@pytest.mark.parametrize('bad',[None,True,7,'bogus','REL-0','REL-'+'Z'*26])
def test_invalid_reserved_relation_identity_never_reaches_execution(bad):
    with pytest.raises(FoldError): fold_operations([],[],reserved_relation_ids=[bad])


def test_wrong_source_and_missing_relation_are_not_silent_noops():
    a,b=goal(),goal(1);add=add_relation(a,b)
    for states,op,reason in [([b],add,'missing_operation_source'),
          ([a,b],remove_relation(a,add['relation']),'missing_operation_relation')]:
        with pytest.raises(FoldError) as e: fold_operations(states,[op])
        assert e.value.reason==reason


def test_relation_remove_hash_binds_all_relation_bytes_as_values():
    a,b=goal(),goal(1);add=add_relation(a,b);a['relations']=[add['relation']]
    removal=remove_relation(a,add['relation']);a['relations'][0]['extensions']={'acme.data':{'changed':True}}
    with pytest.raises(FoldError) as e: fold_operations([a,b],[removal])
    assert e.value.reason=='expected_relation_hash_mismatch' and e.value.pointer=='/operations/0/expected_sha256'
    assert len(a['relations'])==1


def test_relation_remove_and_later_artifact_guards_use_intermediate_state():
    a,b=goal(),goal(1);edge=add_relation(a,b)['relation'];a['relations']=[edge]
    after=deepcopy(a);after['relations']=[]
    out=fold_operations([a,b],[remove_relation(a,edge),edit(a,'changed',expected_sha256=canonical_json_sha256(after))])
    assert out.candidates[0].data['relations']==[] and out.candidates[0].data['statement']=='changed'


def test_self_relation_and_invalid_type_pair_remain_rejected():
    a,b=goal(),goal(1)
    for op in [add_relation(a,a),add_relation(a,b,kind='verified_by')]:
        with pytest.raises(FoldError): fold_operations([a,b],[op])


def test_symmetric_direction_is_not_rewritten_implicitly():
    a,b=goal(),goal(1)
    with pytest.raises(FoldError) as e: fold_operations([a,b],[add_relation(b,a,kind='duplicates')])
    assert e.value.reason=='noncanonical_symmetric_relation'
    out=fold_operations([a,b],[add_relation(a,b,kind='duplicates')])
    assert out.candidates[0].data['relations'][0]['target']==b['id']


def test_duplicate_symmetric_pairs_with_different_ids_fail():
    a,b=goal(),goal(1)
    with pytest.raises(FoldError) as e:
        fold_operations([a,b],[add_relation(a,b,1,'duplicates'),add_relation(a,b,2,'duplicates')])
    assert e.value.reason=='duplicate_symmetric_relation' and e.value.operation_index==1


def test_different_directed_relations_are_not_merged_by_target():
    a,b=goal(),goal(1)
    out=fold_operations([a,b],[add_relation(a,b,1),add_relation(a,b,2)])
    assert len(out.candidates)==1 and len(out.candidates[0].data['relations'])==2


def test_external_relation_ids_are_unique_across_active_relations():
    a,b,c=goal(),goal(1),goal(2)
    a['relations']=[add_relation(a,b,external_identities=[external()])['relation']]
    with pytest.raises(FoldError) as e:
        fold_operations([a,b,c],[add_relation(b,c,2,external_identities=[external()])])
    assert e.value.reason=='duplicate_external_relation_identity'


def test_relation_failure_prevents_later_updates(monkeypatch):
    import specroad.changes.folding as module
    original=module._dispatch;calls=[]
    def counted(*args):
        calls.append(args[-1]['op']);return original(*args)
    monkeypatch.setattr(module,'_dispatch',counted)
    a,b=goal(),goal(1);add=add_relation(a,b)
    with pytest.raises(FoldError):
        fold_operations([a,b],[add,remove_relation(a,add['relation'],expected_sha256='f'*64),edit(a,'never')])
    assert calls==['relation_add','relation_remove']
    assert a['relations']==[] and a['statement']!='never'


def test_valid_failure_is_not_hidden_by_later_compensating_operation():
    a=goal();bad=edit(a,'invalid');bad['patch']=[{'op':'remove','path':'/statement'}]
    with pytest.raises(FoldError) as e: fold_operations([a],[bad,edit(a,'restored')])
    assert e.value.operation_index==0


def test_subsequent_unknown_operation_is_not_semantically_dispatched(monkeypatch):
    import specroad.changes.folding as module
    original=module._dispatch;calls=[]
    def counted(*args): calls.append(args[-1]['op']);return original(*args)
    monkeypatch.setattr(module,'_dispatch',counted)
    a=goal()
    with pytest.raises(FoldError) as e: fold_operations([a],[edit(a,'x',expected_revision=99),{'op':'future'}])
    assert calls==['update'] and e.value.reason=='expected_revision_mismatch'


def test_failure_diagnostics_never_return_partial_or_secret_artifact_values():
    a=goal(statement='SECRET-INPUT-XYZ');op=edit(a,'SECRET-NEW-ABC',expected_revision=77)
    with pytest.raises(FoldError) as e: fold_operations([a],[op])
    result=e.value.diagnostic()
    assert result['partial_result_available'] is False and result['write_authorized'] is False
    assert 'SECRET-' not in json.dumps(result)


def test_create_update_sequences_match_independent_last_assignment_oracle():
    for choices in product(range(3),repeat=4):
        items=[goal(i) for i in range(3)];expected=deepcopy(items);ops=[];indices={}
        for index,target in enumerate(choices):
            ops.append(edit(items[target],str(index)));expected[target]['statement']=str(index)
            indices.setdefault(target,[]).append(index)
        out=fold_operations(items,ops)
        assert out.artifacts==expected
        assert len(out.candidates)==len(set(choices))
        for target,where in indices.items():
            candidate=next(x for x in out.candidates if x.id==items[target]['id'])
            assert candidate.operation_indices==tuple(where) and candidate.data==expected[target]


def test_final_candidate_hash_is_computed_only_for_final_artifact(monkeypatch):
    import specroad.changes.folding as module
    original=module.canonical_json_sha256;values=[]
    def observed(value):
        values.append(deepcopy(value));return original(value)
    monkeypatch.setattr(module,'canonical_json_sha256',observed)
    a=goal();ops=[edit(a,str(i)) for i in range(9)]
    out=fold_operations([a],ops)
    # Base-hash calculation is allowed. Intermediate guard/preview computations
    # are a different purpose; this observes the actual final-fold digest stage.
    finals=[value for value in values if value.get('statement')=='8']
    assert len(out.candidates)==1 and len(finals)==1
    assert not any(value.get('statement') in {str(i) for i in range(8)} for value in values)


def test_large_sequence_is_not_truncated_at_ui_or_commit_boundaries():
    a=goal();out=fold_operations([a],[edit(a,str(i)) for i in range(1100)])
    assert out.operations_applied==1100 and out.candidates[0].operation_indices==tuple(range(1100))
    assert out.candidates[0].data['statement']=='1099'


def test_many_owners_each_have_exactly_one_sorted_result():
    artifacts=[goal(i) for i in range(151)];ops=[edit(a,'one') for a in reversed(artifacts)]
    ops.extend(edit(a,'two') for a in artifacts)
    out=fold_operations(artifacts,ops)
    assert len(out.candidates)==151 and len(set(x.id for x in out.candidates))==151
    assert [x.id for x in out.candidates]==sorted(x['id'] for x in artifacts)
    assert all(x.data['statement']=='two' for x in out.candidates)


def test_operation_snapshots_cannot_run_foreign_conversion_hooks():
    class Foreign(dict):
        def items(self): raise AssertionError('foreign hook')
        def __iter__(self): raise AssertionError('foreign hook')
        def __deepcopy__(self,memo): raise AssertionError('foreign hook')
    a=goal()
    for args in [([Foreign(a)],[]),([a],[Foreign(edit(a,'x'))])]:
        with pytest.raises(FoldError): fold_operations(*args)


def test_repeated_and_concurrent_folds_do_not_share_candidate_states():
    a,b=goal(),goal(1);ops=[add_relation(a,b),edit(a,'changed')]
    with ThreadPoolExecutor(max_workers=4) as pool:
        outputs=list(pool.map(lambda _:fold_operations([a,b],ops),range(20)))
    outputs[0].artifacts[0]['relations'].clear()
    assert all(len(x.candidates[0].data['relations'])==1 for x in outputs)
    assert a['relations']==[]


def test_pure_fold_does_not_open_files_start_processes_or_network(tmp_path):
    a,b=goal(),goal(1);ops=[add_relation(a,b),edit(a,'literal /etc/passwd $(exec)')]
    with patch.object(builtins,'open',side_effect=AssertionError('file effect')), \
         patch.object(socket,'socket',side_effect=AssertionError('network effect')), \
         patch.object(subprocess,'run',side_effect=AssertionError('process effect')):
        out=fold_operations([a,b],ops)
    assert out.candidates[0].data['statement']=='literal /etc/passwd $(exec)'
    assert list(tmp_path.iterdir())==[]


def test_existing_readonly_specialized_artifact_cannot_gain_generic_relations():
    from support.records import record_value
    special=record_value('baseline');a=goal()
    with pytest.raises(FoldError): fold_operations([special,a],[add_relation(special,a)])


def test_plan_conditions_can_guard_absence_for_later_create_without_io():
    a=goal();plan=prepare_change_plan(document([create(a)],[result(a)]))
    outcome=fold_plan_fields(plan,[],observed_base_root='a'*64,observed_scope=scope())
    assert outcome.plan_sha256==plan.sha256 and outcome.candidates[0].base_sha256 is None
    assert not outcome.declared_results_verified and not outcome.expected_result_root_verified


def test_invalid_scope_reports_a_fold_error_not_a_constructor_traceback():
    a=goal();plan=prepare_change_plan(document([edit(a,'x')],[result(a)]))
    with pytest.raises(FoldError): fold_plan_fields(plan,[a],observed_base_root='a'*64,observed_scope={'kind':'nope'})


def test_missing_and_null_global_guard_fields_are_not_interchangeable():
    a=goal()
    with pytest.raises(FoldError): fold_operations([a],[],preconditions=[{'kind':'artifact','artifact_id':a['id'],'expected_revision':None}])
    with pytest.raises(FoldError): fold_operations([a],[],preconditions=[{'kind':'artifact','artifact_id':a['id']}])


def test_module_and_zipapp_execute_the_same_ordered_folding_api(tmp_path):
    module,archive=build_distribution(tmp_path/'delivery');a=goal();ops=[edit(a,'one'),edit(a,'two')]
    body="import sys;sys.path.insert(0,sys.argv[1]);from specroad.changes import fold_operations; r=fold_operations(%r,%r);assert r.candidates[0].data['statement']=='two';assert r.candidates[0].operation_indices==(0,1);assert not r.metadata_applied and not r.write_authorized"%([a],ops)
    for location in (module,archive):
        p=run_python(['-I','-S','-B','-c',body,str(location)],tmp_path,capture=True)
        assert p.returncode==0,p.stderr


def test_missing_initial_relation_target_is_not_repaired_by_a_later_creation():
    a,b=goal(),goal(1);a['relations']=[add_relation(a,b)['relation']]
    with pytest.raises(FoldError) as e: fold_operations([a],[create(b)])
    assert e.value.operation_index is None and e.value.operations_completed==0


def test_embedded_reserved_relation_id_blocks_create_before_candidate():
    a,b=goal(),goal(1);a['relations']=[add_relation(a,b)['relation']]
    with pytest.raises(FoldError) as e: fold_operations([b],[create(a)],reserved_relation_ids=[rid()])
    assert e.value.operation_index==0 and e.value.reason=='relation_identity_exists'


def test_removal_frees_external_mapping_but_not_relation_identity():
    a,b=goal(),goal(1);old=add_relation(a,b,external_identities=[external()])['relation'];a['relations']=[old]
    fresh=add_relation(a,b,number=2,external_identities=[external()])
    out=fold_operations([a,b],[remove_relation(a,old),fresh])
    assert out.candidates[0].data['relations']==[fresh['relation']]


def test_json_patch_test_can_read_a_relation_added_in_the_previous_operation():
    a,b=goal(),goal(1);add=add_relation(a,b);operation=edit(a,'verified intermediate')
    operation['patch'].insert(0,{'op':'test','path':'/relations/0/relation_id','value':rid()})
    out=fold_operations([a,b],[add,operation])
    assert out.candidates[0].data['statement']=='verified intermediate'


def test_fold_does_not_automatically_revert_or_increment_metadata_on_net_noop():
    a,b=goal(),goal(1);original=deepcopy(a);add=add_relation(a,b)
    out=fold_operations([a,b],[add,edit(a,'temporary'),remove_relation(a,add['relation']),edit(a,a['statement'])])
    assert out.candidates[0].data==original and not out.candidates[0].changed
    assert out.candidates[0].operation_indices==(0,1,2,3)
    assert not out.metadata_applied and out.operations_applied==4
