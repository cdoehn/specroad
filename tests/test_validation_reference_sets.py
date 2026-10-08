"""Independent reference findings, identity barriers and selection boundaries."""

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
from support.records import record_value
from support.relations import external


CASES = ("missing_and_wrong_type", "mixed_same_source", "missing_and_self",
         "same_target_two_sources", "same_target_two_edges", "relations_and_fields",
         "mixed_relations_and_fields", "two_wrong_types", "missing_review", "unresolved_review")


def path(value):
    return artifact_path(value["artifact_type"], value["id"], "SR")


def reference_case(case):
    a, b, missing, unrelated = (artifact(number=n) for n in (1, 2, 11, 99))
    component, other_component = (artifact("component", number=n) for n in (11, 12))
    a["relations"] = [edge(missing, number=1)]
    b["relations"] = [edge(component, number=2)]
    values = [a, b, component]
    expected = [(a, "SRV020", "/relations/0/target"), (b, "SRV021", "/relations/0/target")]
    if case == "mixed_same_source":
        a["relations"].append(edge(component, number=2))
        values = [a, component]
        expected[1] = (a, "SRV021", "/relations/1/target")
    elif case == "missing_and_self":
        b["relations"] = [edge(b, number=2)]
        values = [a, b]
    elif case == "same_target_two_sources":
        b["relations"] = [edge(missing, number=2)]
        values = [a, b]
        expected[1] = (b, "SRV020", "/relations/0/target")
    elif case == "same_target_two_edges":
        a["relations"].append(edge(missing, "duplicates", number=2))
        values = [a]
        expected[1] = (a, "SRV020", "/relations/1/target")
    elif case in ("relations_and_fields", "mixed_relations_and_fields", "missing_review"):
        interface = artifact("interface", number=1,
            source_component=component["id"], target_component=other_component["id"])
        if case == "mixed_relations_and_fields":
            values.append(interface)
            expected.append((interface, "SRV020", "/target_component"))
        else:
            values = [a, interface]
            expected = [expected[0], (interface, "SRV020", "/source_component"),
                        (interface, "SRV020", "/target_component")]
            if case == "missing_review":
                review = record_value("relation_review", relation_id="REL-" + "0" * 24 + "99")
                values.append(review)
                expected.append((review, "MODEL_VALIDATION", "/relation_id"))
    elif case == "two_wrong_types":
        a["relations"] = [edge(other_component, number=1)]
        values.append(other_component)
        expected[0] = (a, "SRV021", "/relations/0/target")
    elif case == "unresolved_review":
        review = record_value("relation_review", relation_id=a["relations"][0]["relation_id"])
        values = [a, review]
        expected = [expected[0]]
    return (*values, unrelated), expected, unrelated


@pytest.mark.parametrize("selection", ("project", "source", "unrelated"))
@pytest.mark.parametrize("case", CASES)
def test_reference_set_is_complete_in_project_and_selected_validation(tmp_path, case, selection):
    values, expected, unrelated = reference_case(case)
    selected = None if selection == "project" else (
        unrelated["id"] if selection == "unrelated" else values[0]["id"],)
    core = load_bundled_profile("core@0.2.0")
    effective = compose_profiles((core,), core_key=core.key)
    make_project(tmp_path, *values)
    documents = tuple(doc(value, path(value)) for value in values)
    before = inventory(tmp_path)
    with no_write_attempts():
        report = validate_model(documents, profile=effective, selected_ids=selected)
        direct = assess_validation(report, documents=documents)
        reverse = assess_validation(validate_model(documents[::-1], profile=effective,
            selected_ids=selected), documents=documents[::-1])
        public = validate_project_read_only(tmp_path, profile_resources=(core,), core_key=core.key,
            selected_ids=selected)
        with pytest.raises(ModelError):
            RelationReferences(tuple(SourceRelations(d.content, path=d.path) for d in documents))
    assert inventory(tmp_path) == before
    assert direct.as_dict() == reverse.as_dict()
    expected_locations = {(code, value["id"], path(value), pointer) for value, code, pointer in expected}
    assert {(d.code, d.artifact_id, d.path, d.location["pointer"]) for d in direct.diagnostics} == expected_locations
    assert len(direct.diagnostics) == len(expected)
    for key in ("diagnostics", "summary", "checks_complete", "approval_granted", "write_authorized"):
        assert public.data["validation"][key] == direct.as_dict()[key]
    assert public.data["validation"]["source_report"]["stages"] == report.data["stages"]
    assert direct.summary["checked_artifacts"] == len(values)
    assert direct.summary["diagnostic_count"] == len(expected)
    assert direct.exit_code == public.exit_code == 3
    assert report.data["checked_ids"] == []
    assert report.data["model_valid"] is False
    assert report.data["stages"][-1] == {
        "stage": "graph_and_semantics", "status": "blocked", "checked_ids": [], "diagnostics": []}
    assert report.complete is False
    assert report.data["approval_granted"] is False
    assert report.data["write_authorized"] is False


@pytest.mark.parametrize("conflict", ("artifact", "relation", "external", "prefix"))
def test_identity_conflicts_block_target_lookup_even_after_an_earlier_missing_target(conflict):
    values = [artifact(number=n) for n in (1, 2, 3)]
    missing = artifact(number=11)
    for number, value in enumerate(values, 1):
        value["relations"] = [edge(missing, number=number)]
    if conflict == "artifact":
        for value in values[1:]:
            value["id"] = values[0]["id"]
        reason, code, pointer = "duplicate_artifact_id", "SRV010", "/id"
    elif conflict == "relation":
        for value in values[1:]:
            value["relations"][0]["relation_id"] = values[0]["relations"][0]["relation_id"]
        reason, code, pointer = "duplicate_relation_id", "SRV013", "/relations/0/relation_id"
    elif conflict == "external":
        for value in values:
            value["relations"][0]["external_identities"] = [external()]
        reason, code, pointer = "duplicate_external_relation_identity", "SRV147", "/relations/0/external_identities/0"
    else:
        for value, prefix in zip(values[1:], ("XX", "ZZ")):
            value["id"] = prefix + value["id"][2:]
        reason, code, pointer = "mixed_project_prefix", "MODEL_VALIDATION", ""
    documents = tuple(doc(value, name + ".json") for value, name in zip(values, ("a", "b", "c")))
    report = validate_model(documents, profile=profile())
    reverse = validate_model(documents[::-1], profile=profile())
    assert report.data == reverse.data
    assert [(d["reason"], d["path"], d["pointer"]) for d in report.diagnostics] == [
        (reason, "b.json", pointer), (reason, "c.json", pointer)]
    assessment = assess_validation(report, documents=documents)
    assert [d.code for d in assessment.diagnostics] == [code, code]
    assert assessment.exit_code == 3
    assert report.data["stages"][-1]["status"] == "blocked"


@pytest.mark.parametrize("invalid", ("json", "schema", "typed_field"))
def test_selected_public_validation_does_not_infer_targets_from_invalid_inventory(tmp_path, invalid):
    a, target, unrelated = (artifact(number=n) for n in (1, 11, 99))
    a["relations"] = [edge(target, number=1)]
    values = [a, target, unrelated]
    if invalid == "schema":
        del target["title"]
    elif invalid == "typed_field":
        values.append(artifact("interface", source_component=a["id"]))
    make_project(tmp_path, *values)
    if invalid == "json":
        (tmp_path / path(target)).write_bytes(b"{unreadable")
    documents = tuple(ModelDocument(path(value), (tmp_path / path(value)).read_bytes()) for value in values)
    core = load_bundled_profile("core@0.2.0")
    before = inventory(tmp_path)
    with no_write_attempts():
        public = validate_project_read_only(tmp_path, profile_resources=(core,), core_key=core.key,
            selected_ids=(unrelated["id"],))
        direct = assess_validation(validate_model(documents, profile=compose_profiles((core,), core_key=core.key),
            selected_ids=(unrelated["id"],)), documents=documents)
    assert inventory(tmp_path) == before
    assert public.exit_code == direct.exit_code == 3
    assert public.data["validation"]["diagnostics"] == direct.as_dict()["diagnostics"]
    assert all(d.code != "SRV020" for d in direct.diagnostics)
    assert direct.as_dict()["source_report"]["stages"][-1]["stage"] == "model_dependencies"
    assert direct.as_dict()["source_report"]["stages"][-1]["status"] == "blocked"
