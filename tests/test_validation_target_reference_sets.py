"""Reference findings survive whole-target assessment without authorizing writes."""

import pytest

from specroad.changes import assess_change_target, dry_run_change
from specroad.model.errors import ModelError
from specroad.storage.read_only import validate_project_read_only
from specroad.validation import assess_validation, validate_model
from support.folds import edit
from support.model_validation import artifact, edge
from support.production_validation import inputs, target_model, write_project
from support.read_only import inventory, no_write_attempts
from support.targets import POLICY, plan


@pytest.mark.parametrize("present,same_target", [(0, False), (1, False), (2, False), (0, True)])
def test_complete_field_findings_agree_for_project_target_and_dry_run(tmp_path, present, same_target):
    changed = artifact("goal", number=1)
    components = [artifact("component", number=n) for n in (11, 12)]
    interface = artifact("interface", number=1,
        source_component=components[0]["id"],
        target_component=components[0 if same_target else 1]["id"])
    data = inputs([changed, interface, *components[:present]])
    model = target_model(data)
    change = plan(model, [edit(changed, "Changed statement.")])
    write_project(tmp_path, data)
    before = inventory(tmp_path)
    original_documents = model.documents

    with no_write_attempts():
        direct = assess_validation(validate_model(data.documents, profile=data.profile,
            resources=data.resources), documents=data.documents)
        public = validate_project_read_only(tmp_path, profile_resources=data.profiles,
            core_key=data.profiles[0].key)
        target = assess_change_target(change, model, policy=POLICY)
        dry = dry_run_change(change, model, policy=POLICY)

    assert inventory(tmp_path) == before
    assert model.documents == original_documents
    assert target.data == dry.data["assessment"]
    observations = (direct.as_dict(), public.data["validation"], target.data["validation"])
    for result in observations:
        for key in ("diagnostics", "summary", "checks_complete", "exit_code",
                    "approval_granted", "write_authorized"):
            assert result[key] == observations[0][key]
    expected_pointers = ({"/source_component", "/target_component"} if present == 0
                         else {"/target_component"} if present == 1 else set())
    interface_path = next(d.path for d in data.documents if interface["id"] in d.path)
    assert {(d.code, d.artifact_id, d.path, d.location["pointer"])
            for d in direct.diagnostics} == {
        ("SRV020", interface["id"], interface_path, pointer) for pointer in expected_pointers}
    assert direct.summary["diagnostic_count"] == len(expected_pointers)
    assert direct.exit_code == public.exit_code == (3 if expected_pointers else 0)
    assert target.target_validated is (not expected_pointers)
    assert target.data["approval_granted"] is False
    assert target.data["transaction_prepared"] is False
    assert target.data["write_authorized"] is False
    assert all(value["write_authorized"] is False for value in observations)
    if expected_pointers:
        assert target.data["validation"]["source_report"]["stages"][-1]["status"] == "blocked"
        assert target.data["validation"]["source_report"]["checked_ids"] == []


@pytest.mark.parametrize("two_sources", [False, True])
def test_invalid_stored_relations_keep_strict_plan_boundary(two_sources):
    first, second = (artifact("goal", number=n) for n in (1, 2))
    first["relations"] = [edge(artifact("goal", number=11), number=1)]
    relation = edge(artifact("goal", number=12), number=2)
    (second if two_sources else first).setdefault("relations", []).append(relation)
    data = inputs([first, second])
    model = target_model(data)
    original_documents = model.documents
    with no_write_attempts():
        report = assess_validation(validate_model(data.documents, profile=data.profile,
            resources=data.resources), documents=data.documents)
        with pytest.raises(ModelError) as caught:
            plan(model, [edit(second, "Changed statement.")])
    assert caught.value.reason == "missing_relation_target"
    assert len(report.diagnostics) == report.summary["diagnostic_count"] == 2
    assert report.exit_code == 3
    assert report.as_dict()["approval_granted"] is False
    assert report.as_dict()["write_authorized"] is False
    assert model.documents == original_documents
