"""Ordinary Change Plans and honest read-only reports for artifact imports."""
from copy import deepcopy
from hashlib import sha256
import json

import pytest

from specroad.changes import ChangePlan, TargetModel, TargetPolicy, assess_change_target
from specroad.exchange import ExternalIdentity, ImportIdentityError, ImportPlan
from specroad.mappings import ExchangeMapping
from specroad.model.attachments import AttachmentDescriptor
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.model.errors import ModelError
from specroad.validation import ModelDocument
from support.folds import goal, add_relation
from support.import_planning import BASE, EXTERNAL, LOCAL, PAYLOAD, candidate, identity, imported, mapping, prepare
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import no_write_attempts, inventory
from support.targets import ACTOR, TIME, POLICY, SCOPE, gate, model


def targets(result):
    return {v["artifact"]["id"]: v["artifact"] for v in result.plan.data["result_artifacts"]}


@pytest.mark.parametrize("input_format", ["csv", "ndjson", "reqif", "reqifz"])
def test_new_artifact_plan_binds_real_input_mapping_ids_operations_and_whole_target(input_format):
    resource = mapping(source_format="reqif" if input_format == "reqifz" else input_format)
    c = candidate(new=True); m = model([])
    r = prepare(m, [c], resource=resource, input_format=input_format)
    assert r.plan_valid and r.require_valid() is r and type(r.plan) is ChangePlan
    data = r.data; binding = data["binding"]; value = targets(r)[c["new_artifact"]["id"]]
    assert data["input_sha256"] == sha256(PAYLOAD).hexdigest() == binding["input_sha256"]
    assert data["mapping_sha256"] == resource.sha256 == binding["mapping"]["sha256"]
    assert binding["mapping_source_sha256"] == sha256(resource.source_bytes).hexdigest()
    assert binding["candidates_sha256"] == canonical_json_sha256([c])
    assert binding["base_model_root_sha256"] == m.manifest([], SCOPE).sha256
    assert binding["change_plan_sha256"] == r.plan.sha256
    assert data["change_plan_id"] == r.plan.data["change_plan_id"] == "CP-import-explicit"
    assert data["operations"] == r.plan.data["operations"] and data["operations"][0]["op"] == "create"
    assert data["created_ids"] == [value["id"]] and data["updated_ids"] == []
    assert data["skipped"] == data["conflicts"] == data["losses"] == data["attachments"] == []
    assert value["statement"] == EXTERNAL and value["revision"] == 1
    assert value["created_at"] == value["updated_at"] == TIME
    assert value["created_by"] == value["updated_by"] == ACTOR
    h = value["external_identities"][0]
    expected = canonical_json_sha256({"artifact_type": "goal", "statement": EXTERNAL})
    assert h["last_imported_projection_sha256"] == h["last_source_projection_sha256"] == expected
    assert h["last_source_payload_sha256"] == sha256(PAYLOAD).hexdigest() and h["imported_at"] == TIME
    saved = assess_change_target(r.plan, m, policy=POLICY)
    assert saved.target_validated and saved.artifacts == [value]
    assert data["target_model_root_sha256"] == m.manifest([value], SCOPE).sha256
    assert data["target_model_root_sha256"] == saved.data["binding"]["target_model_root"]
    assert data["exit_code"] == 0
    assert not any(data[k] for k in ("input_parsed", "import_completed", "execution_ready", "write_authorized"))
    assert not r.write_authorized and not r.plan.write_authorized
    with pytest.raises(TypeError): bool(r)


@pytest.mark.parametrize("strategy", ["update_if_unchanged", "create_new_revision"])
@pytest.mark.parametrize("local,source,state,action,expected,changed", [
    (BASE, BASE, "unchanged", "noop", BASE, False),
    (BASE, EXTERNAL, "source_changed", "adopt", EXTERNAL, True),
    (LOCAL, BASE, "local_changed", "retain_local", LOCAL, False),
    (EXTERNAL, EXTERNAL, "converged", "adopt", EXTERNAL, True),
    (LOCAL, EXTERNAL, "diverged", "reject", LOCAL, False),
], ids=["unchanged", "source-only", "local-only", "converged", "diverged"])
def test_same_native_identity_follows_comparison_and_regular_revision_rules(strategy, local, source, state, action, expected, changed):
    a = imported(local=local); m = model([a]); c = candidate(source)
    r = prepare(m, [c], strategy=strategy); data = r.data
    assert data["objects"][0]["comparison"] == state and data["objects"][0]["action"] == action
    assert data["strategy"] == strategy and data["created_ids"] == []
    assert data["updated_ids"] == ([a["id"]] if changed else [])
    assert r.plan_valid is (state != "diverged")
    if state == "diverged":
        assert data["conflicts"][0]["code"] == "SRV148" and not data["conflicts"][0]["resolved"]
        assert data["exit_code"] == 3
        with pytest.raises(ImportIdentityError): r.plan
    else:
        target = assess_change_target(r.plan, m, policy=POLICY).artifacts[0]
        assert target["id"] == a["id"] and target["statement"] == expected
        assert target["revision"] == a["revision"] + int(changed)
        assert target["created_at"] == a["created_at"] and target["created_by"] == a["created_by"]
        if changed:
            assert target["updated_by"] == ACTOR and target["updated_at"] == TIME
            assert target["external_identities"][0]["imported_at"] == TIME
        else:
            assert target == a and data["operations"] == []
    assert m.artifacts == [a]


def test_adoption_preserves_nonmapped_content_relations_and_other_identities():
    a = imported(owner="local owner", extensions={"example.local": {"value": "retained"}})
    b = goal(1); a["relations"] = [add_relation(a, b)["relation"]]
    a["external_identities"].append(identity("another-key"))
    old_identity = a["external_identities"][0]
    old_identity["extensions"] = {"example.local": "identity metadata"}
    c = candidate(); c["identity"]["external_revision"] = "2"
    m = model([a, b]); r = prepare(m, [c]); target = targets(r)[a["id"]]
    assert target["owner"] == a["owner"] and target["extensions"] == a["extensions"]
    assert target["relations"] == a["relations"] and target["external_identities"][1] == a["external_identities"][1]
    assert target["external_identities"][0]["extensions"] == old_identity["extensions"]
    assert target["external_identities"][0]["external_revision"] == "2"


@pytest.mark.parametrize("strategy", ["error", "skip", "update_if_unchanged", "create_new_revision"])
def test_no_strategy_can_turn_a_divergent_object_into_an_executable_plan(strategy):
    a = imported(local=LOCAL); r = prepare(model([a]), [candidate()], strategy=strategy)
    assert not r.plan_valid and r.data["conflicts"][0]["artifact_id"] == a["id"]
    assert r.data["operations"] == [] and any(d["code"] == "SRV148" for d in r.data["diagnostics"])
    assert bool(r.data["skipped"]) is (strategy == "skip")
    with pytest.raises(ImportIdentityError): r.require_valid()


@pytest.mark.parametrize("strategy,valid", [("error", False), ("skip", True),
    ("update_if_unchanged", False), ("create_new_revision", False)])
def test_legacy_identity_has_no_invented_history_or_unsafe_update(strategy, valid):
    a = goal(external_identities=[identity()]); r = prepare(model([a]), [candidate()], strategy=strategy)
    assert r.plan_valid is valid and r.data["operations"] == []
    assert not r.data["conflicts"] and not r.data["updated_ids"]
    if valid:
        assert r.plan.data["operations"] == [] and r.data["skipped"][0]["artifact_id"] == a["id"]
    else:
        assert r.data["diagnostics"][0]["code"] == "SRV090"


def test_unmapped_values_are_individually_preserved_in_loss_report_and_block_plan():
    c = candidate(new=True); c["fields"].update({"slash/~": [None, True, 1, "1"], "other": {"x": False}})
    r = prepare(model([]), [c]); d = r.data
    assert not r.plan_valid and d["exit_code"] == 3
    assert {v["pointer"]: v["value"] for v in d["losses"]} == {
        "/candidates/0/fields/other": {"x": False}, "/candidates/0/fields/slash~1~0": [None, True, 1, "1"]}
    assert all(v["accepted"] is False for v in d["losses"])
    with pytest.raises(ImportIdentityError): r.plan


def test_unmodified_artifact_is_checked_and_can_block_import_target():
    a, b = imported(), goal(1); seen = []
    def check(c):
        seen.append(c.subjects)
        return c.result([{"reason": "dependent_contract_failed", "severity": "error", "artifact_id": b["id"]}])
    r = prepare(model([a, b]), [candidate()], gates=[gate(check=check)])
    assert seen == [(a["id"], b["id"])] and not r.plan_valid
    assert b["id"] in r.data["target_assessment"]["validation"]["source_report"]["checked_ids"]
    with pytest.raises(ImportIdentityError): r.plan


def test_missing_trusted_gate_cannot_be_replaced_by_a_valid_mapping():
    r = prepare(model([]), [candidate(new=True)], policy=TargetPolicy("import", "1", ("extension:import",)))
    assert not r.plan_valid and r.data["target_assessment"]["missing_command_gates"] == ["extension:import"]


@pytest.mark.parametrize("field", ["revision", "maturity", "relations", "external_identities"])
def test_mapping_cannot_bypass_controlled_fields_or_forge_import_history(field):
    resource = mapping(); data = resource.data; data["fields"][0]["target_field"] = field
    resource = ExchangeMapping(canonical_json_bytes(data))
    with pytest.raises(ModelError): prepare(model([]), [candidate(new=True)], resource=resource)


def test_mapping_hash_and_format_are_verified_from_supplied_resource_bytes():
    with pytest.raises(ModelError): prepare(model([]), [], mapping_sha256="a" * 64)
    with pytest.raises(ImportIdentityError) as caught: prepare(model([]), [], input_format="csv")
    assert caught.value.reason == "import_mapping_format_mismatch"


def test_duplicate_native_external_identity_is_not_masked_by_skip():
    a, b = imported(), imported(number=1)
    with pytest.raises(ImportIdentityError) as caught: prepare(model([a, b]), [candidate()], strategy="skip")
    assert caught.value.code == "SRV147"


def test_duplicate_candidate_key_and_two_keys_for_one_owner_are_rejected():
    a = imported(); a["external_identities"].append(identity("second")); m = model([a])
    with pytest.raises(ImportIdentityError) as caught: prepare(m, [candidate(), candidate()])
    assert caught.value.code == "SRV147"
    with pytest.raises(ImportIdentityError) as caught: prepare(m, [candidate(), candidate(key="second")])
    assert caught.value.reason == "import_duplicate_native_candidate"


@pytest.mark.parametrize("case", ["missing-template", "known-template", "wrong-type", "source-history", "unknown-member"])
def test_malformed_candidates_do_not_become_implicit_creates_or_authorities(case):
    m = model([]); c = candidate(new=True)
    if case == "missing-template": c["new_artifact"] = None
    elif case == "known-template": m = model([imported()])
    elif case == "wrong-type": c["new_artifact"]["artifact_type"] = "requirement"
    elif case == "source-history": c["identity"] = imported()["external_identities"][0]
    else: c["accepted_losses"] = True
    with pytest.raises(ImportIdentityError): prepare(m, [c])


def test_attachment_report_uses_verified_existing_bytes_and_reference_in_target():
    raw = b"bound attachment bytes"
    descriptor = AttachmentDescriptor("attachments/import.dat", "application/octet-stream", len(raw), sha256(raw).hexdigest())
    from support.records import record_value
    resource = mapping(); data = resource.data
    data["types"][0].update(external_type="Source", artifact_type="source")
    data["fields"][0].update(external_type="Source", target_field="locator")
    resource = ExchangeMapping(canonical_json_bytes(data))
    c = candidate(new=True); c["external_type"] = "Source"; c["fields"]["Text"] = descriptor.path
    c["new_artifact"] = record_value("source", created_at=TIME, updated_at=TIME, created_by=ACTOR, updated_by=ACTOR,
                                      content_sha256=descriptor.sha256)
    m = model([], attachments=[descriptor], resource_files=[ModelDocument(descriptor.path, raw)])
    missing = prepare(m, [c], resource=resource)
    assert not missing.plan_valid
    assert any(s["stage"] == "external_resources" and s["status"] == "unavailable"
               for s in missing.data["target_assessment"]["validation"]["source_report"]["stages"])
    aid = c["new_artifact"]["id"]; checked = []
    def check(context):
        value = context.artifact(aid); actual = m.source_files[value["locator"]]
        checked.append(value["id"])
        valid = value["content_sha256"] == sha256(actual).hexdigest() and len(actual) == descriptor.size
        return context.result([] if valid else [{"reason": "source_integrity_failed", "severity": "error"}])
    r = prepare(m, [c], resource=resource, gates=[gate("external_resources", check=check)])
    assert checked == [aid]
    assert r.plan_valid and r.data["attachments"] == [{"kind": "attachment", **descriptor.data}]
    assert r.data["attachment_scope"] == "complete_supplied_target"
    assert targets(r)[aid]["locator"] == descriptor.path
    assert targets(r)[aid]["content_sha256"] == descriptor.sha256
    assert r.data["target_assessment"]["target_manifest"]["attachments"] == r.data["attachments"]
    with pytest.raises(ModelError): model([], attachments=[descriptor])
    with pytest.raises(ModelError): model([], attachments=[descriptor], resource_files=[ModelDocument(descriptor.path, b"altered")])


def test_inputs_and_reports_are_detached_and_planning_does_not_touch_owned_files(tmp_path):
    a = imported(); m = model([a]); c = candidate(); before = deepcopy((a, c))
    (tmp_path / "source.reqif").write_bytes(PAYLOAD)
    for path, raw in m.source_files.items():
        dest = tmp_path / "project" / path; dest.parent.mkdir(parents=True, exist_ok=True); dest.write_bytes(raw)
    snapshot = inventory(tmp_path)
    with no_write_attempts(): r = prepare(m, [c])
    assert inventory(tmp_path) == snapshot and (a, c) == before and m.artifacts == [a]
    report = r.data; report["plan_valid"] = False; report["change_plan"]["operations"].clear()
    c["fields"]["Text"] = "tampered"
    assert r.plan_valid and targets(r)[a["id"]]["statement"] == EXTERNAL
    with pytest.raises(TypeError): ImportPlan(report)


def test_input_byte_mapping_representation_and_base_bindings_are_independent():
    a = imported(); m = model([a]); c = candidate(); resource = mapping()
    original = prepare(m, [c], resource=resource)
    other_input = prepare(m, [c], input_bytes=PAYLOAD + b" ")
    resource = ExchangeMapping(json.dumps(resource.data, indent=4).encode())
    other_mapping = prepare(m, [c], resource=resource)
    other_base = prepare(model([a, goal(1)]), [c])
    bindings = [r.data["binding"] for r in (original, other_input, other_mapping, other_base)]
    assert bindings[0]["input_sha256"] != bindings[1]["input_sha256"]
    assert bindings[0]["mapping"] == bindings[2]["mapping"]
    assert bindings[0]["mapping_source_sha256"] != bindings[2]["mapping_source_sha256"]
    assert bindings[0]["base_model_root_sha256"] != bindings[3]["base_model_root_sha256"]
    assert len({r.sha256 for r in (original, other_input, other_mapping, other_base)}) == 4


@pytest.mark.parametrize("mode", ["core", "pyz"])
def test_import_plan_is_available_in_isolated_runtimes(tmp_path, mode):
    m = model([]); resource = mapping(); c = candidate(new=True)
    body = "from specroad.exchange import prepare_import_plan\nfrom specroad.changes import TargetModel,TargetPolicy\n"
    body += "from specroad.profiles import ProfileResource,compose_profiles\nfrom specroad.validation import ModelDocument\n"
    body += "from specroad.model.model_manifest import ProjectReadBinding\nimport json\n"
    body += "from specroad.mappings import ExchangeMapping\n"
    body += "p=ProfileResource(" + repr(m.profile_resources[0].source_bytes) + ")\n"
    body += "m=TargetModel(" + repr(m.configuration_bytes) + ",ProjectReadBinding('sample','/explicit/provider',(1,2)),[],profile=compose_profiles([p],core_key=p.key),resource_files=[ModelDocument('profiles/core.json',p.source_bytes)])\n"
    body += "mapping=ExchangeMapping(" + repr(resource.source_bytes) + ")\n"
    body += "r=prepare_import_plan(m," + repr([c]) + ",input_format='reqif',input_bytes=" + repr(PAYLOAD)
    body += ",mapping_resources=[mapping],mapping_key=mapping.key,mapping_sha256=mapping.sha256,strategy='update_if_unchanged',change_plan_id='CP-explicit',request_id='request-explicit',actor=" + repr(ACTOR)
    body += ",planned_at=" + repr(TIME) + ",scope_descriptor=" + repr(SCOPE) + ",metadata_policy_version='change-metadata-v1',policy=TargetPolicy('import','1',()))\n"
    body += "print(json.dumps({'valid':r.plan_valid,'created':r.data['created_ids'],'write':r.write_authorized}))\n"
    if mode == "core": result = run_core(body, tmp_path, capture=True)
    else:
        _, package = build_distribution(tmp_path / "distribution")
        result = run_python(["-I", "-S", "-B", "-c", "import sys;sys.path.insert(0," + repr(str(package)) + ")\n" + body], tmp_path, capture=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"valid": True, "created": [c["new_artifact"]["id"]], "write": False}
