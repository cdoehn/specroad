"""Complete missing-target locations without accepting an unresolved graph."""

import pytest

from specroad.graph.references import RelationReferences
from specroad.graph.relations import SourceRelations
from specroad.model.errors import ModelError
from specroad.model.paths import artifact_path
from specroad.profiles import compose_profiles
from specroad.storage.profiles import load_bundled_profile
from specroad.storage.read_only import validate_project_read_only
from specroad.validation import ModelDocument, assess_validation, validate_model
from support.model_validation import artifact, doc, edge, profile
from support.read_only import inventory, make_project, no_write_attempts


def source_path(value):
    return artifact_path(value["artifact_type"], value["id"], "SR")


def missing_case(case):
    a, b, c, d = (artifact(number=n) for n in (1, 2, 11, 12))
    a["relations"] = [edge(c, number=1)]
    b["relations"] = [edge(d, number=2)]
    if case == "two_sources":
        return (a, b), ((a, "/relations/0/target"), (b, "/relations/0/target"))
    if case == "two_edges":
        a["relations"].append(edge(d, number=2))
        return (a,), ((a, "/relations/0/target"), (a, "/relations/1/target"))
    interface = artifact("interface", number=1,
        source_component=artifact("component", number=11)["id"],
        target_component=artifact("component", number=12)["id"])
    return (interface,), ((interface, "/source_component"), (interface, "/target_component"))


@pytest.mark.parametrize("case", ("two_sources", "two_edges", "interface_fields"))
def test_every_independent_missing_target_has_its_own_location(tmp_path, case):
    values, expected = missing_case(case)
    core = load_bundled_profile("core@0.2.0")
    effective = compose_profiles((core,), core_key=core.key)
    make_project(tmp_path, *values)
    before = inventory(tmp_path)
    documents = tuple(doc(value, source_path(value)) for value in values)
    with no_write_attempts():
        report = validate_model(documents, profile=effective)
        assessment = assess_validation(report, documents=documents)
        reversed_result = assess_validation(
            validate_model(documents[::-1], profile=effective), documents=documents[::-1])
        public = validate_project_read_only(tmp_path, profile_resources=(core,), core_key=core.key)
        if case != "interface_fields":
            with pytest.raises(ModelError) as caught:
                RelationReferences(tuple(SourceRelations(d.content, path=d.path) for d in documents))
            assert caught.value.reason == "missing_relation_target"
    assert inventory(tmp_path) == before
    assert assessment.as_dict() == reversed_result.as_dict()
    # Public reads also bind their observed production resources. Those input
    # hashes may differ; the complete findings and decisions must agree.
    for key in ("diagnostics", "summary", "checks_complete", "approval_granted", "write_authorized"):
        assert public.data["validation"][key] == assessment.as_dict()[key]
    assert public.data["validation"]["source_report"]["stages"] == report.data["stages"]
    assert {(d.code, d.artifact_id, d.path, d.location["pointer"]) for d in assessment.diagnostics} == {
        ("SRV020", value["id"], source_path(value), pointer) for value, pointer in expected}
    assert len(assessment.diagnostics) == assessment.summary["diagnostic_count"] == 2
    assert assessment.exit_code == public.exit_code == 3
    assert report.data["model_valid"] is False
    assert report.complete is False
    assert report.data["checked_ids"] == []
    assert [(stage["stage"], stage["status"]) for stage in report.data["stages"]] == [
        ("parsing", "passed"), ("schema_types_identity_fields", "passed"),
        ("identities_references", "failed"), ("graph_and_semantics", "blocked")]
    assert report.data["approval_granted"] is False
    assert report.data["write_authorized"] is False


@pytest.mark.parametrize("invalid", ("json", "schema"))
def test_unreadable_or_invalid_target_inventory_cannot_prove_absence(invalid):
    values, _ = missing_case("two_sources")
    possible_target = artifact(number=11)
    if invalid == "schema":
        del possible_target["title"]
        uncertain = doc(possible_target)
    else:
        uncertain = ModelDocument(source_path(possible_target), b"{broken")
    report = validate_model((*map(doc, values), uncertain), profile=profile())
    assert report.data["stages"][-1] == {
        "stage": "model_dependencies", "status": "blocked", "checked_ids": [], "diagnostics": []}
    assert all(d["reason"] not in ("missing_relation_target", "validation_field_target_missing")
               for d in report.diagnostics)
    assert report.passed is False


@pytest.mark.parametrize("conflict", ("duplicate", "prefix"))
def test_ambiguous_source_index_retains_its_strict_boundary(conflict):
    values, _ = missing_case("two_sources")
    additional = artifact(number=1) if conflict == "duplicate" else artifact(
        number=99, id="XX-GOAL-" + "0" * 26)
    documents = (*map(doc, values), doc(additional, "conflict.json"))
    report = validate_model(documents, profile=profile())
    assert [d["reason"] for d in report.diagnostics] == [
        "duplicate_artifact_id" if conflict == "duplicate" else "mixed_project_prefix"]
    assert report.data["stages"][-1]["stage"] == "graph_and_semantics"
    assert report.data["stages"][-1]["status"] == "blocked"


def test_loading_all_real_targets_restores_complete_valid_graph():
    values, _ = missing_case("two_sources")
    fields, _ = missing_case("interface_fields")
    values = (*values, artifact(number=11), artifact(number=12), *fields,
              artifact("component", number=11), artifact("component", number=12))
    documents = tuple(map(doc, values))
    references = RelationReferences(tuple(SourceRelations(d.content, path=d.path) for d in documents))
    assert len(references.relations) == 2
    report = validate_model(documents, profile=profile())
    assert report.passed is True
    assert report.complete is True
    assert report.diagnostics == ()
    assert report.data["approval_granted"] is False
