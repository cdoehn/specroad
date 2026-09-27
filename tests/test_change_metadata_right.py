"""Bound saved plans, byte preservation, precision, isolation and failure cases."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from decimal import localcontext, ROUND_UP
import json
import pytest
from specroad.changes import (prepare_plan_metadata, prepare_change_metadata_bytes,
    prepare_change_metadata, prepare_change_plan, MetadataError, ChangePlanError)
from specroad.model.canonical import canonical_json_sha256
from specroad.changes.metadata_time import next_update_time
from support.change_plans import document, result, scope
from support.folds import goal, edit, create, add_relation
from support.records import record_value
from test_change_metadata import prepare, ACTOR, PLANNED


def saved(a,ops,results,**overrides):
    value=document(ops,[result(x) for x in results]);value.update(actor=deepcopy(ACTOR),planned_at=PLANNED)
    value.update(overrides)
    return prepare_change_plan(value)


def check(plan,artifacts,**overrides):
    return prepare_plan_metadata(plan,artifacts,**{"observed_base_root":"a"*64,"observed_scope":scope(),**overrides})


def raw_prepare(sources,ops,**overrides):
    return prepare_change_metadata_bytes(sources,ops,**{"metadata_policy_version":"change-metadata-v1",
        "actor":ACTOR,"planned_at":PLANNED,**overrides})


def test_saved_plan_binding_is_preserved_and_declared_results_are_checked():
    a=goal();ops=[edit(a,"New")];candidate=prepare([a],ops).artifacts[0]
    p=saved(a,ops,[candidate]);before=p.source_bytes
    out=check(p,[a]);again=check(p,[a])
    assert out==again and out.plan_sha256==p.sha256 and p.source_bytes==before
    assert out.declared_artifacts_verified and out.artifacts==[candidate]
    assert not out.expected_result_root_verified and not out.lifecycle_checked and not out.execution_ready


def test_declared_revision_time_actor_or_hash_mismatch_is_rejected():
    a=goal();ops=[edit(a,"New")];expected=prepare([a],ops).artifacts[0]
    for field,value in [("revision",99),("updated_at","2099-01-01T00:00:00Z"),
        ("updated_by",{"actor_type":"tool","actor_id":"unexpected"}),("statement","different"),
        ("created_by",{"actor_type":"human","actor_id":"forged-origin"})]:
        bad={**expected,field:value};p=saved(a,ops,[bad])
        with pytest.raises(MetadataError) as exc:check(p,[a])
        assert exc.value.reason=="declared_metadata_result_mismatch" and exc.value.pointer=="/result_artifacts/0"
        assert exc.value.diagnostic()["partial_result_available"] is False


def test_saved_creation_plan_cannot_override_bound_metadata():
    a=goal(revision=7)
    p=saved(a,[create(a)],[a])
    with pytest.raises(MetadataError):check(p,[])
    proper=prepare([], [create(a)]).artifacts[0]
    out=check(saved(proper,[create(proper)],[proper]),[])
    assert out.artifacts[0]["revision"]==1 and out.declared_artifacts_verified


def test_planwide_preconditions_check_base_not_the_resulting_revision():
    a=goal();ops=[edit(a,"New")];target=prepare([a],ops).artifacts[0]
    p=saved(a,ops,[target],preconditions=[{"kind":"artifact","artifact_id":a["id"],"expected_revision":1}])
    assert check(p,[a]).preconditions_checked==1
    with pytest.raises(ChangePlanError):check(p,[target])


def test_missing_or_wrong_base_observations_fail_instead_of_using_current_state():
    a=goal();ops=[edit(a,"New")];p=saved(a,ops,prepare([a],ops).artifacts)
    for root in [None,"","b"*64]:
        with pytest.raises(ChangePlanError):check(p,[a],observed_base_root=root)
    with pytest.raises(ChangePlanError):check(p,[a],observed_scope={**scope(),"scope_kind":"specification"})


def test_raw_noop_preserves_original_bytes_and_all_historical_values():
    a=goal(revision=17);raw=json.dumps(a,indent=3,ensure_ascii=False).encode()+b'\n'
    out=raw_prepare([raw],[edit(a,a["statement"])])
    assert out.candidates[0].original_bytes==raw and out.artifacts==[a]
    assert out.candidates[0].disposition=="unchanged"


def test_raw_changed_candidate_keeps_source_bytes_separate():
    a=goal();raw=json.dumps(a,indent=5).encode();out=raw_prepare([raw],[edit(a,"New")])
    assert out.candidates[0].original_bytes==raw
    assert out.candidates[0].candidate_sha256==canonical_json_sha256(out.artifacts[0])
    assert json.loads(raw)==a and out.artifacts[0]["revision"]==2


@pytest.mark.parametrize("bad", [b'{"a":1,"a":2}',b'{} false',b'\xff',b'{}',"/tmp/model.json",bytearray(b'{}')])
def test_invalid_raw_inputs_are_not_paths_or_partially_successful_results(bad):
    with pytest.raises(MetadataError):raw_prepare([bad],[])


def test_duplicate_raw_id_is_rejected_even_with_different_formatting():
    a=goal()
    with pytest.raises(MetadataError):raw_prepare([json.dumps(a).encode(),json.dumps(a,indent=2).encode()],[])


def test_unchanged_historical_special_records_are_not_recreated():
    for kind in ["evidence","baseline","relation_review","proposal"]:
        a=record_value(kind)
        # No operations: readable historical values are left alone, never
        # mistaken for ordinary newly generated identities.
        out=prepare([a],[])
        assert out.artifacts==[a] and out.modified_ids==()


def test_changed_specialized_source_cannot_use_regular_metadata_policy():
    a=record_value("evidence");b=goal()
    # Evidence -> goal is permitted by traces_to matrix, but it is not an
    # ordinary mutable artifact. A generic metadata pass must still refuse it.
    op=add_relation(a,b,kind="traces_to")
    with pytest.raises(ChangePlanError):prepare([a,b],[op])


def test_saved_plan_object_is_required_not_an_unchecked_mapping():
    with pytest.raises(MetadataError):check({},[])


def test_unknown_and_historical_policies_cannot_apply_even_to_empty_inputs():
    for version in ["latest","change-metadata-v2","merge-metadata-v1","migration-metadata-v1",True,{},None]:
        with pytest.raises(MetadataError) as exc:prepare([],[],metadata_policy_version=version)
        assert exc.value.code=="SRV174"


@pytest.mark.parametrize("actor", [None,{}, {"actor_type":"human","actor_id":""},
    {"actor_type":"robot","actor_id":"x"}, {"actor_type":"human","actor_id":"x","auth":True}])
def test_actor_is_required_and_closed(actor):
    with pytest.raises(MetadataError):prepare([],[],actor=actor)


@pytest.mark.parametrize("value", [None,"2026-01-01T00:00:00+00:00","2026-02-30T00:00:00Z",True])
def test_planning_time_is_explicit_and_valid(value):
    with pytest.raises(MetadataError):prepare([],[],planned_at=value)


def test_fractional_seconds_beyond_datetime_precision_are_not_truncated():
    # Exact digit arithmetic remains safe even beyond Python's integer-string
    # conversion limit. No change to that global limit is required.
    tail="1"*5000
    base="2026-01-01T00:00:00.123456"+tail+"Z"
    assert next_update_time("2025-01-01T00:00:00Z",base)=="2026-01-01T00:00:00.123457"+tail+"Z"
    assert next_update_time("2026-01-01T00:00:00.1234572Z",base)=="2026-01-01T00:00:00.1234572Z"


def test_fractional_carry_retains_the_submicrosecond_remainder():
    assert next_update_time("2020-01-01T00:00:00Z","2026-01-01T23:59:59.9999997Z")=="2026-01-02T00:00:00.0000007Z"


def test_equal_maximum_preserves_the_bound_planned_spelling():
    bound="2026-01-01t00:00:00.00000100Z"
    assert next_update_time(bound,"2026-01-01T00:00:00Z")==bound


def test_explicit_leap_spelling_is_calculated_not_authenticated():
    assert next_update_time("2010-01-01T00:00:00Z","2016-12-31T23:59:60.1Z")=="2016-12-31T23:59:60.100001Z"
    assert next_update_time("2010-01-01T00:00:00Z","2016-12-31T23:59:60.999999Z")=="2017-01-01T00:00:00Z"


def test_out_of_range_timestamp_fails_without_overflowing_into_another_year():
    a=goal(updated_at="9999-12-31T23:59:59.999999Z")
    with pytest.raises(MetadataError) as exc:prepare([a],[edit(a,"X")])
    assert exc.value.reason=="timestamp_overflow"
    assert prepare([a],[edit(a,a["statement"])]).artifacts==[a]


def test_revision_that_would_lose_json_precision_fails():
    a=goal(revision=9007199254740992)
    with pytest.raises(MetadataError):prepare([a],[edit(a,"X")])
    assert prepare([a],[edit(a,a["statement"])]).artifacts==[a]


def test_new_metadata_is_independent_of_decimal_context():
    a=goal(updated_at="2028-01-01T00:00:00.123456789Z")
    normal=prepare([a],[edit(a,"X")])
    with localcontext() as ctx:
        ctx.prec=1;ctx.rounding=ROUND_UP
        assert prepare([a],[edit(a,"X")])==normal


def test_parallel_reuse_does_not_mix_actor_bindings():
    a=goal();ops=[edit(a,"X")]
    def invoke(n):return prepare([a],ops,actor={"actor_type":"tool","actor_id":str(n)})
    with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(invoke,range(25)))
    assert [r.artifacts[0]["updated_by"]["actor_id"] for r in results]==[str(n) for n in range(25)]
    assert a["revision"]==1 and all(r.artifacts[0]["revision"]==2 for r in results)


def test_many_updates_keep_exactly_one_revision_per_owner():
    base=[goal(n,revision=n+1) for n in range(151)]
    ops=[edit(a,"Once") for a in base]+[edit(a,"Twice") for a in reversed(base)]
    out=prepare(base,ops)
    assert len(out.candidates)==151 and out.operations_applied==302
    assert [v["revision"] for v in out.artifacts]==list(range(2,153))
    assert all(len(v.operation_indices)==2 for v in out.candidates)


def test_retired_and_approved_status_are_not_silently_decided_by_metadata():
    from support.domain import approved_value
    a=approved_value("goal")
    out=prepare([a],[edit(a,"X")])
    assert out.artifacts[0]["maturity"]=="approved" and out.lifecycle_checked is False
    # It is a pre-lifecycle candidate, not an executable or approved write.
    assert out.execution_ready is False and out.write_authorized is False


def test_no_hidden_io_clock_or_identity_generation(monkeypatch):
    import builtins,time,os,uuid
    a=goal();ops=[edit(a,"X")]
    def blocked(*args,**kw):raise AssertionError("unexpected external operation")
    monkeypatch.setattr(builtins,"open",blocked);monkeypatch.setattr(time,"time",blocked)
    monkeypatch.setattr(uuid,"uuid4",blocked);monkeypatch.setattr(os,"getlogin",blocked)
    assert prepare([a],ops).artifacts[0]["updated_at"]==PLANNED


def test_foreign_input_methods_are_not_executed():
    class Hostile(dict):
        def items(self):raise AssertionError("custom method")
        def __iter__(self):raise AssertionError("custom iteration")
    with pytest.raises(ChangePlanError):prepare([Hostile(goal())],[])
    with pytest.raises(MetadataError):prepare([],[],actor=Hostile(ACTOR))


def test_whole_microsecond_clock_matches_an_independent_calendar_oracle():
    from datetime import datetime, timedelta
    for stamp in ["0001-01-01T00:00:00.000000", "2024-02-28T23:59:59.999999",
                  "2024-02-29T23:59:59.999999", "2025-12-31T23:59:59.999999",
                  "2026-07-31T12:59:59.123456"]:
        d=datetime.fromisoformat(stamp)+timedelta(microseconds=1)
        expected=f"{d.year:04d}-{d.month:02d}-{d.day:02d}T{d.hour:02d}:{d.minute:02d}:{d.second:02d}"
        if d.microsecond:expected+='.'+f'{d.microsecond:06d}'.rstrip('0')
        assert next_update_time("0001-01-01T00:00:00Z",stamp+"Z")==expected+"Z"


def test_nested_fields_named_like_audit_are_still_content():
    a=goal(extensions={"test.audit":{"revision":1,"updated_at":"plain content"}})
    op=edit(a,"X");op["patch"]=[{"op":"replace","path":"/extensions/test.audit/revision","value":2}]
    out=prepare([a],[op])
    assert out.artifacts[0]["revision"]==2 and out.artifacts[0]["extensions"]["test.audit"]["revision"]==2


def test_ordinary_new_identity_is_not_reused_from_a_reserved_history():
    a=goal(revision=99)
    with pytest.raises(ChangePlanError):prepare([], [create(a)], reserved_artifact_ids=[a["id"]])


def test_shifted_module_and_zipapp_expose_same_metadata_policy(tmp_path):
    from support.portable import build_distribution
    from support.processes import run_python
    module,archive=build_distribution(tmp_path/'delivery')
    a=goal();ops=[edit(a,"New")]
    body=("import sys;sys.path.insert(0,sys.argv[1]);"
          "from specroad.changes import prepare_change_metadata;"
          "r=prepare_change_metadata(%r,%r,metadata_policy_version='change-metadata-v1',actor=%r,planned_at=%r);"
          "assert r.artifacts[0]['revision']==2;assert r.artifacts[0]['updated_at']==%r;"
          "assert not r.write_authorized")%([a],ops,ACTOR,PLANNED,PLANNED)
    for location in (module,archive):
        proc=run_python(['-I','-S','-B','-c',body,str(location)],tmp_path,capture=True)
        assert proc.returncode==0,proc.stderr
