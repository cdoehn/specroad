"""Complete contract/error boundaries with no writes or presentation oracles."""
from copy import deepcopy
import json
from concurrent.futures import ThreadPoolExecutor
import builtins
import os
from pathlib import Path
import socket
import subprocess
from unittest.mock import patch
import pytest

from specroad.changes import ChangePlan, ChangeOperation, ChangePlanError, prepare_change_plan, OPERATION_TYPES
from specroad.model.canonical import canonical_json_bytes
from support.change_plans import document, operation, result
from support.domain import domain_value
from support.records import record_value, ref
from support.processes import run_python
from support.portable import build_distribution


def test_all_operation_shapes_can_coexist_without_execution():
    ops = [operation(k) for k in OPERATION_TYPES]
    results = [result(domain_value()), result(record_value('evidence')), result(record_value('relation_review')), result(record_value('proposal', proposal_status='validated', maturity='proposed', content_sha256='b'*64))]
    value = document(ops, results)
    value['preconditions'] = [{'kind':'artifact','artifact_id':ref('GOAL'),'expected_revision':1},
                              {'kind':'file','path':'attachments/a.bin','expected_byte_sha256':'f'*64},
                              {'kind':'absent','path':'spec/new.json'}]
    plan = prepare_change_plan(value)
    assert len(plan.operations) == 12
    assert ChangePlan(plan.canonical_bytes).data == plan.data
    assert not plan.execution_ready


def test_sequential_operations_preserve_order_but_do_not_execute_or_fold():
    op = operation('update')
    op['patch'] = [{'op':'remove','path':'/missing'}]  # Actual failure belongs to 5.b.
    plan = prepare_change_plan(document([operation(),op], [result(domain_value(title='Explicit final'))]))
    assert [o.op for o in plan.operations] == ['create','update']
    assert plan.data['result_artifacts'][0]['artifact']['title'] == 'Explicit final'
    assert plan.execution_ready is False


def test_missing_or_unclaimed_result_id_is_rejected():
    for data in [document(results=[]), document([], [result(domain_value())])]:
        with pytest.raises(ChangePlanError) as err: prepare_change_plan(data)
        assert err.value.reason == 'result_owner_set_mismatch'


def test_no_file_or_process_effects_for_valid_and_invalid_plans(tmp_path):
    sent = tmp_path/'sentinel'; sent.write_bytes(b'unchanged')
    data = document(); original = deepcopy(data)
    with patch.object(builtins,'open',side_effect=AssertionError('file open')), \
         patch.object(os,'open',side_effect=AssertionError('os open')), \
         patch.object(subprocess,'Popen',side_effect=AssertionError('process')), \
         patch.object(socket,'socket',side_effect=AssertionError('network')):
        assert prepare_change_plan(data).data['request_id'] == 'test:request:1'
        bad = deepcopy(data); bad['operations'][0]['op'] = 'exec'
        with pytest.raises(ChangePlanError): prepare_change_plan(bad)
    assert sent.read_bytes() == b'unchanged' and data == original
    assert list(tmp_path.iterdir()) == [sent]


def test_normalization_cannot_target_immutable_or_operational_files():
    op = operation('representation_normalize')
    for path in ['archive/objects/aa/'+'a'*64, '.specroad/cache/a.json','generated/a.json',
                 'attachments/a.json','spec/evidence/'+ref('EVD')+'.json', 'spec/baselines/'+ref('BASE')+'.json']:
        op['path'] = path
        with pytest.raises(ChangePlanError): ChangeOperation(op)


def test_declared_special_workflow_is_not_an_authorization_token():
    for k in ['evidence_record','relation_review_record','proposal_control','representation_normalize']:
        op = ChangeOperation(operation(k))
        assert op.required_workflow == k and not op.executable
    assert ChangeOperation(operation()).required_workflow == 'regular'


@pytest.mark.parametrize('kind', OPERATION_TYPES)
def test_unknown_operation_payload_member_is_not_ignored(kind):
    op = operation(kind); op['authorized'] = True
    with pytest.raises(ChangePlanError): ChangeOperation(op)


@pytest.mark.parametrize('kind', ['update','transition','retire','attachment_add','attachment_remove','relation_add','relation_remove'])
def test_all_generic_mutation_routes_reject_special_targets(kind):
    for typ in ('EVD','BASE','PROP','RREV'):
        op = operation(kind); field = 'source' if kind.startswith('relation_') else 'target'
        op[field] = ref(typ)
        with pytest.raises(ChangePlanError) as err: ChangeOperation(op)
        assert err.value.reason == 'specialized_operation_required'


def test_disguised_target_type_cannot_override_the_identity():
    op = operation('update'); op['target'] = ref('EVD'); op['artifact_type'] = 'goal'
    with pytest.raises(ChangePlanError): ChangeOperation(op)


@pytest.mark.parametrize('path', ['../escape.json','/absolute.json','C:/drive.json','a\\b.json','.git/config','.patchharbor/config.json','a/../b.json','a/CON.json'])
def test_path_traversal_and_reserved_targets_are_rejected(path):
    op = operation('representation_normalize'); op['path'] = path
    with pytest.raises(ChangePlanError): ChangeOperation(op)


@pytest.mark.parametrize('name', ['expected_revision','expected_sha256'])
def test_update_accepts_each_explicit_precondition_form(name):
    op = operation('update'); op.pop('expected_revision')
    op[name] = 2 if name == 'expected_revision' else 'a'*64
    assert ChangeOperation(op).data == op


def test_update_rejects_missing_precondition():
    op = operation('update'); op.pop('expected_revision')
    with pytest.raises(ChangePlanError): ChangeOperation(op)


@pytest.mark.parametrize('value', [True,0,-1,1.5,None,'1'])
def test_invalid_expected_revision_is_rejected(value):
    op = operation('update'); op['expected_revision'] = value
    with pytest.raises(ChangePlanError): ChangeOperation(op)


@pytest.mark.parametrize('value', ['A'*64,'a'*63,'a'*65,'x'*64,None,True])
def test_invalid_expected_hash_is_rejected(value):
    op = operation('retire'); op['expected_sha256'] = value
    with pytest.raises(ChangePlanError): ChangeOperation(op)


def test_result_hash_is_checked_separately_from_plan_selfhash():
    data = document(); data['result_artifacts'][0]['sha256'] = 'f'*64
    with pytest.raises(ChangePlanError) as err: prepare_change_plan(data)
    assert err.value.reason == 'result_hash_mismatch'


def test_duplicate_result_and_creation_identities_are_rejected():
    for d in [document(results=[result(domain_value()),result(domain_value())]),document([operation(),operation()])]:
        with pytest.raises(ChangePlanError): prepare_change_plan(d)


def test_duplicate_new_relation_id_is_rejected_without_mutation():
    d = document([operation('relation_add'),operation('relation_add')]); before = deepcopy(d)
    with pytest.raises(ChangePlanError) as err: prepare_change_plan(d)
    assert err.value.reason == 'duplicate_new_relation_id' and d == before


def test_immutable_special_record_must_match_declared_result():
    evidence = record_value('evidence', title='Changed result')
    d = document([operation('evidence_record')],[result(evidence)])
    with pytest.raises(ChangePlanError) as err: prepare_change_plan(d)
    assert err.value.reason == 'immutable_record_result_mismatch'


def test_review_plan_actor_cannot_impersonate_human_origin():
    d = document([operation('relation_review_record')],[result(record_value('relation_review'))]); d['actor']['actor_type'] = 'ai'
    with pytest.raises(ChangePlanError): prepare_change_plan(d)


def test_duplicate_or_nonrequirement_review_withdrawals_rejected():
    op = operation('relation_review_record')
    withdrawal = {'target':ref(),'expected_revision':1,'reason':'Invalidated review'}
    op['approval_withdrawals'] = [withdrawal, deepcopy(withdrawal)]
    with pytest.raises(ChangePlanError): ChangeOperation(op)
    op['approval_withdrawals'] = [dict(withdrawal,target=ref('EVD'))]
    with pytest.raises(ChangePlanError): ChangeOperation(op)


def test_valid_review_withdrawals_are_bound_not_executed():
    op = operation('relation_review_record')
    op['approval_withdrawals'] = [{'target':ref(),'expected_revision':1,'reason':'Invalidated review'}]
    final = domain_value('requirement', maturity='proposed', revision=2)
    plan = prepare_change_plan(document([op], [result(op['record']), result(final)]))
    assert plan.operations[0].result_ids == (op['record']['id'], ref())
    assert plan.write_authorized is False


def test_proposal_control_rejects_unknown_or_disconnected_events():
    op = operation('proposal_control')
    for events in [[{'from':'applied','to':'draft','reason':'Cannot reopen','result_sha256':'a'*64}],
                   [op['events'][0],{'from':'checked','to':'in_review','reason':'Skipped middle','result_sha256':'b'*64}]]:
        with pytest.raises(ChangePlanError): ChangeOperation(dict(op,events=events))


def test_generic_transition_cannot_smuggle_identity_changes_in_metadata():
    op = operation('transition'); op['metadata']['id'] = ref('EVD')
    with pytest.raises(ChangePlanError): ChangeOperation(op)


def test_unknown_schema_version_and_top_level_extension_rejected():
    for d in [dict(document(),format_version='1.3.0'),dict(document(),execute='shell')]:
        with pytest.raises(ChangePlanError): prepare_change_plan(d)


def test_empty_plan_requires_unchanged_model_root():
    d = document([],[])
    with pytest.raises(ChangePlanError): prepare_change_plan(d)
    d['expected_result'] = dict(model_root_sha256=d['base']['model_root_sha256'])
    assert prepare_change_plan(d).operations == ()


def test_duplicate_preconditions_are_not_collapsed_or_overwritten():
    d = document(); c = {'kind':'artifact','artifact_id':ref('GOAL'),'expected_revision':1}
    d['preconditions'] = [c,dict(c,expected_revision=2)]
    with pytest.raises(ChangePlanError): prepare_change_plan(d)


def test_precondition_arrays_accept_neither_predicate_code_nor_paths_to_load():
    for c in [{'kind':'exec','expression':'shell'}, {'kind':'file','path':'/outside','expected_byte_sha256':'a'*64}]:
        with pytest.raises(ChangePlanError): prepare_change_plan(dict(document(),preconditions=[c]))


def test_ordinary_nested_metadata_named_like_identity_remains_data():
    op = operation('update'); op['patch'] = [{'op':'replace','path':'/extensions/acme/id','value':'data'}]
    assert ChangeOperation(op).data == op


def test_operation_order_and_literal_array_order_change_plan_hash():
    a,b = operation('update'),operation('retire')
    assert prepare_change_plan(document([a,b])).sha256 != prepare_change_plan(document([b,a])).sha256


def test_invalid_escaped_pointer_reports_exact_operation_position():
    op = operation('update'); op['patch'][0]['path']='/a~2b'
    with pytest.raises(ChangePlanError) as err: prepare_change_plan(document([op]))
    assert err.value.pointer == '/operations/0/patch/0/path'


def test_foreign_objects_and_subclasses_cannot_run_conversion_hooks():
    class Bad(dict):
        def items(self): raise AssertionError('Executed a hook')
        def __iter__(self): raise AssertionError('Executed a hook')
    for d in [Bad(document()), dict(document(), operations=[Bad(operation())])]:
        with pytest.raises(ChangePlanError): prepare_change_plan(d)


def test_cyclic_inputs_are_rejected_without_mutating_them():
    d=document(); d['operations'].append(d)
    with pytest.raises(ChangePlanError): prepare_change_plan(d)
    assert d['operations'][-1] is d


def test_same_owned_plan_is_safe_for_concurrent_readers():
    p = prepare_change_plan(document()); original = p.canonical_bytes
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(lambda _: ChangePlan(p.canonical_bytes).data,range(12)))
    assert all(v==p.data for v in results) and p.canonical_bytes==original


def test_large_operation_sequence_is_not_truncated():
    ops=[dict(operation('update'),patch=[{'op':'test','path':'/revision','value':1}]) for _ in range(151)]
    p=prepare_change_plan(document(ops))
    assert len(p.operations)==151 and p.data['operations']==ops


def test_module_and_zipapp_include_change_plan_contracts_without_dependencies(tmp_path):
    module, archive=build_distribution(tmp_path/'distribution')
    raw=prepare_change_plan(document()).canonical_bytes
    body="import sys;sys.path.insert(0,sys.argv[1]);from specroad.changes import ChangePlan,ChangeOperation; p=ChangePlan(%r);assert p.sha256==%r;assert not p.write_authorized;assert p.operations[0].op=='create'" % (raw,ChangePlan(raw).sha256)
    for location in (module,archive):
        done=run_python(['-I','-S','-B','-c',body,str(location)],tmp_path,capture=True)
        assert done.returncode==0,done.stderr


def test_single_create_cannot_claim_unrelated_final_artifact_values():
    d = document(results=[result(domain_value(title='Other'))])
    with pytest.raises(ChangePlanError) as err: prepare_change_plan(d)
    assert err.value.reason == 'creation_result_mismatch'


def test_proposal_control_cannot_change_the_approved_content_binding():
    op=operation('proposal_control')
    d=document([op],[result(record_value('proposal'))])
    with pytest.raises(ChangePlanError) as err: prepare_change_plan(d)
    assert err.value.reason == 'proposal_control_result_mismatch'


def test_unknown_operation_has_its_own_exact_pointer_in_a_full_plan():
    with pytest.raises(ChangePlanError) as err: prepare_change_plan(document([{'op':'exec'}]))
    assert err.value.reason == 'unknown_operation'
    assert err.value.pointer == '/operations/0/op'


def test_extra_from_members_of_nonmove_patches_remain_passive_bound_data():
    for kind in ("add", "remove", "replace", "test"):
        op = operation("update")
        item = {"op": kind, "path": "/title", "from": {"not": "a pointer"}}
        if kind in ("add", "replace", "test"):
            item["value"] = "explicit"
        op["patch"] = [item]
        observed = ChangeOperation(op)
        assert observed.data["patch"] == [item]
        assert observed.executable is False
