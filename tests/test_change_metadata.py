"""Explicit Annex-K metadata, verified by returned values rather than presentation."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
import pytest
from specroad.changes import prepare_change_metadata, MetadataError, FoldError
from specroad.model.canonical import canonical_json_sha256
from support.folds import goal, edit, create, add_relation, remove_relation

ACTOR = {"actor_type": "human", "actor_id": "bound-author"}
PLANNED = "2026-01-02T03:04:05Z"


def prepare(artifacts, operations, **kw):
    return prepare_change_metadata(artifacts, operations,
        **{"metadata_policy_version": "change-metadata-v1", "actor": ACTOR,
           "planned_at": PLANNED, **kw})


def test_existing_change_advances_revision_once_and_preserves_creation():
    a = goal(revision=7)
    out = prepare([a], [edit(a,"One"),edit(a,"Two")])
    b = out.artifacts[0]
    assert b["revision"] == 8 and b["statement"] == "Two"
    assert (b["created_at"],b["created_by"]) == (a["created_at"],a["created_by"])
    assert b["updated_at"] == PLANNED and b["updated_by"] == ACTOR
    assert out.candidates[0].operation_indices == (0,1)
    assert out.candidates[0].candidate_sha256 == canonical_json_sha256(b)


def test_new_artifact_uses_explicit_actor_and_time_not_supplied_legacy_audit():
    a = goal(revision=7)
    b = prepare([], [create(a)]).artifacts[0]
    assert b["revision"] == 1
    assert b["created_at"] == b["updated_at"] == PLANNED
    assert b["created_by"] == b["updated_by"] == ACTOR
    assert b["id"] == a["id"]


def test_create_then_modify_keeps_revision_one():
    a=goal()
    out=prepare([], [create(a),edit(a,"Changed")])
    assert len(out.candidates)==1 and out.artifacts[0]["revision"]==1
    assert out.candidates[0].disposition=="created" and out.candidates[0].base_sha256 is None


def test_noop_and_reverted_sequence_keep_all_metadata():
    a=goal(revision=19)
    for ops in [[],[edit(a,a["statement"])],[edit(a,"Different"),edit(a,a["statement"])]]:
        out=prepare([a],ops)
        assert out.artifacts == [a] and out.modified_ids == ()
        assert out.base_artifacts_sha256==out.result_artifacts_sha256
        if ops: assert out.candidates[0].disposition=="unchanged"


def test_each_changed_artifact_advances_from_its_own_base():
    a,b,c=goal(),goal(1,revision=10),goal(2,revision=20)
    out=prepare([c,b,a],[edit(a,"A"),edit(b,"B")])
    assert [v["revision"] for v in out.artifacts]==[2,11,20]
    assert out.artifacts[2]==c


def test_added_relation_advances_only_source():
    a,b=goal(),goal(1)
    out=prepare([a,b],[add_relation(a,b)])
    assert out.artifacts[0]["revision"]==2 and out.artifacts[1]==b
    assert out.modified_ids==(a["id"],)


def test_removed_relation_advances_only_source():
    a,b=goal(),goal(1); r=add_relation(a,b)["relation"];a["relations"]=[r]
    out=prepare([a,b],[remove_relation(a,r)])
    assert out.artifacts[0]["relations"]==[] and out.artifacts[0]["revision"]==2
    assert out.artifacts[1]==b


def test_add_then_remove_does_not_stamp_a_noop():
    a,b=goal(),goal(1);op=add_relation(a,b)
    out=prepare([a,b],[op,remove_relation(a,op["relation"])])
    assert out.artifacts==[a,b] and not out.candidates[0].changed


@pytest.mark.parametrize("base,planned,expected", [
    ("2026-01-01T00:00:00Z","2026-01-02T00:00:00Z","2026-01-02T00:00:00Z"),
    ("2026-01-01T00:00:00Z","2026-01-01T00:00:00Z","2026-01-01T00:00:00.000001Z"),
    ("2026-01-01T00:00:00Z","2025-01-01T00:00:00Z","2026-01-01T00:00:00.000001Z"),
    ("2026-01-01T00:00:00.999999Z","2025-01-01T00:00:00Z","2026-01-01T00:00:01Z"),
    ("2026-12-31T23:59:59.999999Z","2025-01-01T00:00:00Z","2027-01-01T00:00:00Z"),
    ("2024-02-28T23:59:59.999999Z","2024-01-01T00:00:00Z","2024-02-29T00:00:00Z"),
    ("2025-02-28T23:59:59.999999Z","2024-01-01T00:00:00Z","2025-03-01T00:00:00Z"),
    ("2026-01-01T00:00:00.123456789Z","2025-01-01T00:00:00Z","2026-01-01T00:00:00.123457789Z"),
])
def test_exact_bound_update_timestamp(base,planned,expected):
    a=goal(updated_at=base)
    assert prepare([a],[edit(a,"X")],planned_at=planned).artifacts[0]["updated_at"]==expected


def test_bound_result_does_not_follow_later_environment_or_input_changes(monkeypatch):
    a=goal();ops=[edit(a,"X")]; saved=deepcopy((a,ops));actor=deepcopy(ACTOR)
    one=prepare([a],ops,actor=actor)
    monkeypatch.setenv("TZ","Pacific/Honolulu");monkeypatch.setenv("USER","other-user")
    two=prepare([a],ops,actor=actor)
    assert one==two and (a,ops)==saved
    actor["actor_id"]="changed"; a["statement"]="Y";ops.clear()
    one.artifacts[0]["updated_by"]["actor_id"]="bad"
    one.policy["actor"]["actor_id"]="bad"
    assert one.artifacts[0]["updated_by"]==ACTOR and one.policy["actor"]==ACTOR
    with pytest.raises(FrozenInstanceError): one.plan_sha256="forged"


def test_bound_hash_changes_for_different_actor_or_planned_time():
    a=goal();ops=[edit(a,"X")]
    one=prepare([a],ops);two=prepare([a],ops,actor={"actor_type":"tool","actor_id":"other"})
    three=prepare([a],ops,planned_at="2028-01-01T00:00:00Z")
    assert len({r.policy_sha256 for r in [one,two,three]})==3
    assert len({r.result_artifacts_sha256 for r in [one,two,three]})==3


def test_repeated_preparation_does_not_advance_prepared_revision_again():
    a=goal(); ops=[edit(a,"X")]
    one=prepare([a],ops);two=prepare([a],ops)
    assert one==two and one.artifacts[0]["revision"]==2
    with pytest.raises(FoldError): prepare(one.artifacts,ops)


@pytest.mark.parametrize("version",[None,"","merge-metadata-v1","migration-metadata-v1","invented"])
def test_other_policies_cannot_trigger_regular_restamping(version):
    a=goal();saved=deepcopy(a)
    with pytest.raises(MetadataError) as exc:prepare([a],[edit(a,"X")],metadata_policy_version=version)
    assert exc.value.code=="SRV174" and exc.value.exit_code==3 and a==saved


def test_all_result_authorizations_stay_false():
    a=goal();out=prepare([a],[edit(a,"X")])
    assert out.metadata_applied and out.validation_scope=="regular_metadata_candidates_only"
    for field in ["lifecycle_checked","declared_artifacts_verified","expected_result_root_verified",
                  "project_complete","write_authorized","execution_ready"]:assert getattr(out,field) is False


def test_operation_guard_still_checks_the_unstamped_intermediate():
    a=goal();first={**a,"statement":"One"}
    out=prepare([a],[edit(a,"One"),edit(a,"Two",expected_sha256=canonical_json_sha256(first))])
    assert out.artifacts[0]["revision"]==2


def test_failing_operation_does_not_return_metadata_for_a_partial_plan():
    a=goal();saved=deepcopy(a)
    with pytest.raises(FoldError):prepare([a],[edit(a,"X"),edit(a,"Y",expected_revision=42)])
    assert a==saved
