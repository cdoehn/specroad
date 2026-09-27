"""Ordered field results, not metadata policy, write receipts or formatting."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
from hashlib import sha256
import pytest
from specroad.changes import fold_operations, fold_plan_fields, prepare_change_plan, FoldError
from specroad.model.canonical import canonical_json_sha256
from support.folds import goal, edit, create
from support.change_plans import document, result, scope, operation


def test_ordered_updates_use_previous_intermediate():
    a = goal()
    first = edit(a, "First")
    second = edit(a, "Second")
    second["patch"].insert(0, {"op":"test", "path":"/statement", "value":"First"})
    out = fold_operations([a], [first, second])
    assert out.artifacts[0]["statement"] == "Second"
    assert len(out.candidates) == 1 and out.candidates[0].operation_indices == (0, 1)
    assert out.operations_applied == 2 and out.candidates[0].candidate_sha256 == canonical_json_sha256(out.artifacts[0])


def test_create_then_update_folds_to_one_final_candidate():
    a = goal()
    out = fold_operations([], [create(a), edit(a, "New")])
    assert len(out.candidates) == 1 and out.candidates[0].base_sha256 is None
    assert out.candidates[0].data["statement"] == "New" and out.candidates[0].changed


def test_updates_to_multiple_artifacts_are_not_grouped_before_evaluation():
    a,b = goal(),goal(1)
    out = fold_operations([b,a], [edit(b,"B1"),edit(a,"A1"),edit(b,"B2"),edit(a,"A2")])
    assert [x.id for x in out.candidates] == [a["id"],b["id"]]
    assert [x.operation_indices for x in out.candidates] == [(1,3),(0,2)]
    assert [x.data["statement"] for x in out.candidates] == ["A2","B2"]


def test_noop_and_reverted_changes_still_have_one_touched_candidate():
    a = goal()
    out = fold_operations([a], [edit(a,"Changed"),edit(a,a["statement"])])
    assert out.artifacts == [a] and out.modified_ids == ()
    assert len(out.candidates) == 1 and not out.candidates[0].changed


def test_no_metadata_or_lifecycle_advancement_is_claimed():
    a = goal()
    out = fold_operations([a], [edit(a,"Changed")])
    for field in ("revision","created_at","updated_at","created_by","updated_by","maturity"):
        assert out.artifacts[0][field] == a[field]
    for name in ("metadata_applied","lifecycle_checked","declared_results_verified",
                 "expected_result_root_verified","project_complete","write_authorized","execution_ready"):
        assert getattr(out,name) is False
    assert out.validation_scope == "ordered_field_candidates_only"


def test_planwide_guards_check_base_but_operation_guards_check_intermediate():
    a = goal(); h=canonical_json_sha256(a); intermediate={**a,"statement":"First"}
    out=fold_operations([a], [edit(a,"First",expected_sha256=h),
        edit(a,"Second",expected_sha256=canonical_json_sha256(intermediate))],
        preconditions=[{"kind":"artifact","artifact_id":a["id"],"expected_sha256":h}])
    assert out.preconditions_checked == 1 and out.operations_applied == 2


def test_stale_intermediate_guard_fails_at_the_right_operation():
    a=goal(); h=canonical_json_sha256(a)
    with pytest.raises(FoldError) as exc:
        fold_operations([a],[edit(a,"First"),edit(a,"Second",expected_sha256=h)])
    assert exc.value.reason == "expected_hash_mismatch"
    assert exc.value.operation_index == 1 and exc.value.operations_completed == 1
    assert exc.value.pointer == "/operations/1/expected_sha256"
    assert a["statement"] != "First" and exc.value.diagnostic()["partial_result_available"] is False


def test_failure_prevents_later_operation_execution(monkeypatch):
    import specroad.changes.folding as module
    original=module._dispatch; visits=[]
    def dispatch(*args):
        visits.append(args[-1]["op"])
        return original(*args)
    monkeypatch.setattr(module,"_dispatch",dispatch)
    a=goal()
    with pytest.raises(FoldError):
        fold_operations([a],[edit(a,"First"),edit(a,"Second",expected_revision=99),create(goal(2))])
    assert visits == ["update","update"]


def test_input_and_result_data_are_independent():
    a=goal(extensions={"test.payload":{"x":[1]}}); ops=[edit(a,"New")]
    original=deepcopy((a,ops)); out=fold_operations([a],ops)
    assert (a,ops)==original
    out.artifacts[0]["extensions"]["test.payload"]["x"].append(2)
    out.candidates[0].data["statement"]="Corrupt"
    a["statement"]="Other";ops.clear()
    assert out.artifacts[0]["statement"]=="New"
    assert out.artifacts[0]["extensions"]["test.payload"]["x"]==[1]
    with pytest.raises(FrozenInstanceError): out.operations_applied=99


def test_empty_sequence_and_untouched_artifacts_are_preserved():
    a,b=goal(),goal(1)
    out=fold_operations([b,a],[])
    assert out.artifacts == [a,b] and out.candidates==() and out.operations_applied==0
    assert fold_operations([],[]).artifacts==[]


@pytest.mark.parametrize("bad", [None,{},"value",1,True])
def test_operations_must_be_an_explicit_ordered_sequence(bad):
    with pytest.raises(FoldError): fold_operations([],bad)


@pytest.mark.parametrize("guards", [{"expected_revision":2},{"expected_sha256":"0"*64},
    {"expected_revision":1,"expected_sha256":"0"*64}])
def test_invalid_guards_block_without_changes(guards):
    a=goal(); saved=deepcopy(a)
    with pytest.raises(FoldError): fold_operations([a],[edit(a,"Changed",**guards)])
    assert a==saved


def test_missing_operation_target_is_not_created():
    with pytest.raises(FoldError) as exc: fold_operations([],[edit(goal(),"Changed")])
    assert exc.value.reason=="missing_operation_target"


@pytest.mark.parametrize("reserved", [False,True])
def test_creation_identity_collision_is_rejected(reserved):
    a=goal()
    with pytest.raises(FoldError) as exc:
        fold_operations([] if reserved else [a],[create(a)],reserved_artifact_ids=[a["id"]] if reserved else [])
    assert exc.value.reason=="creation_identity_exists"


def test_duplicate_creations_fail_after_first_without_exposing_partial_result():
    a=goal()
    with pytest.raises(FoldError) as exc: fold_operations([],[create(a),create(a)])
    assert exc.value.operation_index==1 and exc.value.operations_completed==1


def test_duplicate_input_id_is_not_silently_replaced():
    a=goal()
    with pytest.raises(FoldError) as exc: fold_operations([a,deepcopy(a)],[])
    assert exc.value.reason=="duplicate_artifact_id"


def test_mixed_project_ids_are_not_folded_together():
    a,b=goal(),goal(1);b["id"]=b["id"].replace("SR-","XX-",1)
    with pytest.raises(FoldError): fold_operations([a,b],[])
    with pytest.raises(FoldError): fold_operations([a],[create(b)])


@pytest.mark.parametrize("field", ["/id","/revision","/updated_at","/maturity","/relations"])
def test_protected_update_fields_remain_protected(field):
    a=goal();op=edit(a,"x");op["patch"]=[{"op":"remove","path":field}]
    with pytest.raises(FoldError): fold_operations([a],[op])


def test_failed_json_test_blocks_the_entire_fold():
    a=goal();op=edit(a,"Changed");op["patch"].insert(0,{"op":"test","path":"/owner","value":False})
    with pytest.raises(FoldError) as exc: fold_operations([a],[op,edit(a,"Later")])
    assert exc.value.reason=="test_failed" and exc.value.operation_index==0


def test_explicit_file_preconditions_are_hash_checked_without_file_access():
    a=goal();blob=b"binary\x00data"
    out=fold_operations([a],[edit(a,"Changed")],source_files={"attachments/a.bin":blob},
        preconditions=[{"kind":"file","path":"attachments/a.bin","expected_byte_sha256":sha256(blob).hexdigest()},
                       {"kind":"absent","path":"attachments/missing.bin"}])
    assert out.preconditions_checked==2


def test_unknown_file_inventory_is_not_an_empty_inventory():
    with pytest.raises(FoldError) as exc:
        fold_operations([],[],preconditions=[{"kind":"absent","path":"attachments/missing.bin"}])
    assert exc.value.reason=="file_snapshot_required"


@pytest.mark.parametrize("condition", [
    {"kind":"absent","path":"attachments/a.bin"},
    {"kind":"file","path":"attachments/a.bin","expected_byte_sha256":"0"*64},
    {"kind":"file","path":"attachments/missing.bin","expected_byte_sha256":"0"*64}])
def test_failed_file_guards_produce_no_operation_result(condition):
    with pytest.raises(FoldError) as exc:
        fold_operations([],[],source_files={"attachments/a.bin":b"x"},preconditions=[condition])
    assert exc.value.operations_completed==0


def test_preconditions_are_checked_before_any_operations(monkeypatch):
    import specroad.changes.folding as module
    def forbidden(*args): pytest.fail("operation executed despite failed precondition")
    monkeypatch.setattr(module,"_dispatch",forbidden)
    a=goal()
    with pytest.raises(FoldError): fold_operations([a],[edit(a,"New")],
        preconditions=[{"kind":"artifact","artifact_id":a["id"],"expected_revision":99}])


def test_duplicate_preconditions_are_errors():
    a=goal();p={"kind":"artifact","artifact_id":a["id"],"expected_revision":1}
    with pytest.raises(FoldError): fold_operations([a],[],preconditions=[p,p])


def test_change_plan_adapter_binds_the_explicit_base_and_preserves_plan():
    a=goal(); b={**a,"statement":"Changed"}; p=prepare_change_plan(document([edit(a,"Changed")],[result(b)]))
    original=p.source_bytes
    out=fold_plan_fields(p,[a],observed_base_root="a"*64,observed_scope=scope())
    assert out.plan_sha256==p.sha256 and out.artifacts==[b] and p.source_bytes==original
    assert out.declared_results_verified is False and out.expected_result_root_verified is False


def test_change_plan_adapter_rejects_wrong_root_and_scope():
    p=prepare_change_plan(document());bad=scope();bad["scope_kind"]="specification"
    with pytest.raises(FoldError): fold_plan_fields(p,[],observed_base_root="b"*64,observed_scope=scope())
    with pytest.raises(FoldError): fold_plan_fields(p,[],observed_base_root="a"*64,observed_scope=bad)


@pytest.mark.parametrize("kind", ["transition","retire","evidence_record","attachment_add","attachment_remove", "representation_normalize","relation_review_record","proposal_control"])
def test_unimplemented_specialized_workflows_are_never_successful_noops(kind):
    with pytest.raises(FoldError) as exc: fold_operations([goal()],[operation(kind)])
    assert exc.value.reason=="operation_requires_specialized_planner" and exc.value.operations_completed==0
