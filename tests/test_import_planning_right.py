"""Saved import envelopes cannot substitute stale inputs or declared success."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from hashlib import sha256
import json

import pytest

from specroad.changes import TargetModel, TargetPolicy
from specroad.exchange import ImportIdentityError, assess_import_plan
from specroad.mappings import ExchangeMapping
from specroad.model.attachments import AttachmentDescriptor
from specroad.model.canonical import canonical_json_bytes
from specroad.model.errors import ModelError
from specroad.model.model_manifest import ProjectReadBinding
from specroad.validation import ModelDocument
from support.folds import goal
from support.import_planning import BASE, EXTERNAL, LOCAL, PAYLOAD, candidate, imported, mapping, prepare
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import inventory, no_write_attempts
from support.targets import ACTOR, TIME, POLICY, SCOPE, gate, model


def arguments(resource=None, **changes):
    resource = resource or mapping()
    args = dict(input_format="reqif", input_bytes=PAYLOAD, mapping_resources=[resource],
        mapping_key=resource.key, mapping_sha256=resource.sha256, strategy="update_if_unchanged",
        change_plan_id="CP-import-explicit", request_id="import-request-explicit", actor=ACTOR,
        planned_at=TIME, scope_descriptor=SCOPE, metadata_policy_version="change-metadata-v1", policy=POLICY)
    args.update(changes)
    return args


def assess(raw, m, candidates, *, resource=None, **changes):
    return assess_import_plan(raw, m, candidates, **arguments(resource, **changes))


def copied(m, **changes):
    args = dict(configuration_bytes=m.configuration_bytes, binding=m.binding, documents=m.documents,
        profile=m.profile, resource_files=m.resource_files, attachments=m.attachment_descriptors,
        language_packages=m.language_packages, **m.reservations)
    args.update(changes)
    return TargetModel(**args)


@pytest.mark.parametrize("input_format", ["csv", "ndjson", "reqif", "reqifz"])
def test_saved_envelope_recreates_the_same_regular_target_without_authority(input_format):
    resource = mapping(source_format="reqif" if input_format == "reqifz" else input_format)
    m = model([]); candidates = [candidate(new=True)]
    first = prepare(m, candidates, resource=resource, input_format=input_format)
    raw = first.canonical_bytes
    again = assess(raw, m, candidates, resource=resource, input_format=input_format)
    assert again is not first and again.plan_valid
    assert again.canonical_bytes == raw and again.sha256 == sha256(raw).hexdigest()
    assert again.plan.canonical_bytes == first.plan.canonical_bytes
    assert again.data["created_ids"] == [candidates[0]["new_artifact"]["id"]]
    assert again.data["updated_ids"] == [] and again.data["exit_code"] == 0
    for name in ("write_authorized", "execution_ready", "import_completed", "input_parsed"):
        assert again.data[name] is False
    assert not again.write_authorized and not again.plan.write_authorized


@pytest.mark.parametrize("local,source,strategy,action,valid", [
    (BASE, EXTERNAL, "update_if_unchanged", "adopt", True),
    (BASE, EXTERNAL, "create_new_revision", "adopt", True),
    (BASE, BASE, "update_if_unchanged", "noop", True),
    (LOCAL, BASE, "update_if_unchanged", "retain_local", True),
    (BASE, EXTERNAL, "skip", "skip", True),
    (BASE, EXTERNAL, "error", "reject", False),
    (LOCAL, EXTERNAL, "update_if_unchanged", "reject", False),
    (LOCAL, EXTERNAL, "skip", "skip", False),
], ids=["update", "revision", "noop", "local", "skip", "error", "conflict", "skipped-conflict"])
def test_reuse_preserves_history_decisions_and_never_promotes_invalid_reports(local, source, strategy, action, valid):
    a = imported(local=local); m = model([a]); candidates = [candidate(source)]
    first = prepare(m, candidates, strategy=strategy)
    again = assess(first.canonical_bytes, m, candidates, strategy=strategy)
    assert again.data == first.data and again.plan_valid is valid
    assert again.data["objects"][0]["action"] == action
    if action == "adopt":
        target = again.plan.data["result_artifacts"][0]["artifact"]
        assert target["id"] == a["id"] and target["revision"] == a["revision"] + 1
        assert target["external_identities"][0]["last_source_payload_sha256"] == sha256(PAYLOAD).hexdigest()
    else:
        assert again.data["operations"] == []
        assert m.artifacts == [a]
    if not valid:
        with pytest.raises(ImportIdentityError): again.plan


def test_saved_unaccepted_losses_cannot_be_hidden_or_marked_accepted():
    m = model([imported()]); c = candidate(); c["fields"]["a/b~c"] = {"unknown": [None, 1, True]}
    first = prepare(m, [c]); assert not first.plan_valid
    again = assess(first.canonical_bytes, m, [c])
    assert again.data["losses"] == first.data["losses"]
    for edited in ({"losses": []}, {"losses": [{**first.data["losses"][0], "accepted": True}]},
                   {"plan_valid": True, "exit_code": 0, "diagnostics": []}):
        with pytest.raises(ImportIdentityError):
            assess(canonical_json_bytes({**first.data, **edited}), m, [c])
    with pytest.raises(ImportIdentityError): again.require_valid()


@pytest.mark.parametrize("replacement", [b"explicit supplier PAYLOAD\r\n", PAYLOAD + b" ",
                                        PAYLOAD.replace(b"\r\n", b"\n"), b""])
def test_different_exact_input_bytes_are_rejected_even_when_candidates_are_unchanged(replacement):
    m = model([imported()]); c = [candidate(BASE)]  # No-op still binds original bytes.
    first = prepare(m, c); assert first.data["operations"] == []
    with pytest.raises(ImportIdentityError) as caught:
        assess(first.canonical_bytes, m, c, input_bytes=replacement)
    assert caught.value.reason == "import_plan_binding_mismatch"


@pytest.mark.parametrize("change", ["format", "fields", "identity", "revision", "envelope", "order"])
def test_explicit_candidate_origin_and_format_cannot_be_replaced(change):
    m = model([]); candidates = [candidate(new=True), candidate(number=1, new=True, key="external-2")]
    first = prepare(m, candidates); other = deepcopy(candidates); args = {}
    if change == "format": args["input_format"] = "reqifz"
    if change == "fields": other[0]["fields"]["Text"] = "Different supplier value."
    if change == "identity": other[0]["identity"]["source_document"] = "other document"
    if change == "revision": other[0]["identity"]["external_revision"] = "2"
    if change == "envelope": other[0]["new_artifact"]["owner"] = "other owner"
    if change == "order": other.reverse()
    with pytest.raises(ImportIdentityError): assess(first.canonical_bytes, m, other, **args)


@pytest.mark.parametrize("change", ["bytes", "content", "version", "identity"])
def test_selected_mapping_is_bound_by_actual_bytes_and_full_versioned_content(change):
    m = model([]); resource = mapping(); first = prepare(m, [], resource=resource)
    value = resource.data
    if change == "content": value["extensions"]["example.note"] = "different rule resource"
    if change == "version": value["mapping_version"] = "1.0.1"
    if change == "identity": value["mapping_id"] = "example:other"
    raw = json.dumps(value, indent=3).encode() if change == "bytes" else canonical_json_bytes(value)
    other = ExchangeMapping(raw)
    if change == "bytes": assert other.sha256 == resource.sha256
    with pytest.raises(ImportIdentityError): assess(first.canonical_bytes, m, [], resource=other)


@pytest.mark.parametrize("change", ["changed-object", "unchanged-object", "config", "artifact-bytes",
                                  "config-bytes", "profile-bytes", "history", "reserved-id"])
def test_current_basis_includes_untouched_objects_configuration_raw_files_and_reservations(change):
    a, b = imported(), goal(1); m = model([a, b]); candidates = [candidate()]
    first = prepare(m, candidates)
    if change == "changed-object":
        other = model([{**a, "owner": "changed locally"}, b])
    elif change == "unchanged-object":
        other = model([a, {**b, "statement": "A changed unrelated goal."}])
    elif change == "config":
        conf = m.configuration.data; conf["validation_policy"]["fail_on"] = "warning"
        other = model([a, b], config=conf)
    elif change == "artifact-bytes":
        other = copied(m, documents=[ModelDocument(d.path, json.dumps(json.loads(d.content), indent=4).encode())
                                     for d in m.documents])
    elif change == "config-bytes":
        other = copied(m, configuration_bytes=json.dumps(m.configuration.data, indent=4).encode())
    elif change == "profile-bytes":
        other = copied(m, resource_files=[ModelDocument(d.path, json.dumps(json.loads(d.content), indent=4).encode())
                                          for d in m.resource_files])
    elif change == "history":
        other = copied(m, previously_approved_ids=[goal(99)["id"]])
    else:
        other = copied(m, reserved_artifact_ids=[goal(99)["id"]])
    if change.endswith("bytes") or change in ("history", "reserved-id"):
        assert other.manifest(other.artifacts, SCOPE).sha256 == m.manifest(m.artifacts, SCOPE).sha256
    with pytest.raises(ImportIdentityError): assess(first.canonical_bytes, other, candidates)


@pytest.mark.parametrize("change", ["attachment-bytes", "attachment-metadata", "resource-bytes"])
def test_attachment_and_companion_resource_bindings_are_not_just_artifact_roots(change):
    a = imported(); raw = b"one"; other_raw = b"two" if change == "attachment-bytes" else raw
    desc = AttachmentDescriptor("attachments/a.bin", "application/octet-stream", 3, sha256(raw).hexdigest())
    other_desc = AttachmentDescriptor(desc.path, "text/plain" if change == "attachment-metadata" else desc.media_type,
                                      3, sha256(other_raw).hexdigest())
    rule = {"schema_version": "0.2.0", "rule_id": "example", "version": "1.0.0", "payload": 1}
    f = ModelDocument("rules/one.json", canonical_json_bytes(rule))
    second = ModelDocument(f.path, json.dumps(rule, indent=5).encode()) if change == "resource-bytes" else f
    m = model([a], resource_files=[ModelDocument(desc.path, raw), f], attachments=[desc])
    other = model([a], resource_files=[ModelDocument(desc.path, other_raw), second], attachments=[other_desc])
    checks = [gate("extension:target-resources")]
    first = prepare(m, [candidate()], gates=checks); assert first.plan_valid
    with pytest.raises(ImportIdentityError): assess(first.canonical_bytes, other, [candidate()], gates=checks)


@pytest.mark.parametrize("key,value", [("strategy", "create_new_revision"), ("change_plan_id", "CP-other"),
    ("request_id", "other-request"), ("actor", {"actor_type": "human", "actor_id": "other"}),
    ("planned_at", "2026-07-02T00:00:00Z"), ("strict", True),
    ("policy", TargetPolicy("other-command", "1", ()))])
def test_request_metadata_and_trusted_policy_are_not_inferred_from_the_saved_plan(key, value):
    m = model([imported()]); c = [candidate(BASE)]; first = prepare(m, c)
    with pytest.raises(ImportIdentityError): assess(first.canonical_bytes, m, c, **{key: value})


def test_saved_target_success_does_not_replace_fresh_whole_target_gate_execution():
    a, b = imported(), goal(1); m = model([a, b]); candidates = [candidate()]
    seen = []; blocked = []
    def check(context):
        seen.append(set(context.subjects))
        return context.result([{"reason": "current_external_check_failed", "severity": "error",
                                "artifact_id": b["id"]}] if blocked else [])
    checks = [gate(check=check)]
    first = prepare(m, candidates, gates=checks)
    assert first.plan_valid and seen == [{a["id"], b["id"]}]
    again = assess(first.canonical_bytes, m, candidates, gates=checks)
    assert again.plan_valid and seen == [{a["id"], b["id"]}] * 2
    blocked.append(True)
    with pytest.raises(ImportIdentityError): assess(first.canonical_bytes, m, candidates, gates=checks)
    assert seen == [{a["id"], b["id"]}] * 3
    assert not prepare(m, candidates, gates=checks).plan_valid


@pytest.mark.parametrize("change", ["missing", "version", "additional"])
def test_saved_gate_registration_cannot_be_reused_with_different_current_services(change):
    m = model([imported()]); c = [candidate()]
    policy = TargetPolicy("import", "1", ("extension:required",))
    first = prepare(m, c, policy=policy, gates=[gate("extension:required")])
    assert first.plan_valid
    checks = [] if change == "missing" else [gate("extension:required", version="2" if change == "version" else "1")]
    if change == "additional": checks.append(gate("extension:additional"))
    with pytest.raises(ImportIdentityError): assess(first.canonical_bytes, m, c, policy=policy, gates=checks)


def test_a_previously_invalid_plan_needs_new_preparation_when_gates_become_available():
    m = model([imported()]); c = [candidate()]
    policy = TargetPolicy("import", "1", ("extension:required",))
    first = prepare(m, c, policy=policy); assert not first.plan_valid
    again = assess(first.canonical_bytes, m, c, policy=policy)
    assert not again.plan_valid and again.data == first.data
    with pytest.raises(ImportIdentityError):
        assess(first.canonical_bytes, m, c, policy=policy, gates=[gate("extension:required")])
    assert prepare(m, c, policy=policy, gates=[gate("extension:required")]).plan_valid


@pytest.mark.parametrize("key,value", [("operations", []), ("created_ids", ["invented"]), ("updated_ids", []),
    ("objects", []), ("skipped", [{"action": "skip"}]), ("conflicts", [{"resolved": True}]),
    ("losses", [{"accepted": True}]), ("diagnostics", [{"reason": "fabricated"}]),
    ("attachments", [{"path": "elsewhere"}]), ("attachment_scope", "changed_only"),
    ("target_model_root_sha256", "0" * 64), ("input_sha256", "0" * 64), ("mapping_sha256", "0" * 64),
    ("input_parsed", True), ("import_completed", True), ("execution_ready", True), ("write_authorized", True),
    ("plan_valid", 1), ("exit_code", False), ("candidate_origin", "trusted_without_parsing")])
def test_saved_reports_do_not_supply_their_own_operations_results_or_success(key, value):
    m = model([imported()]); c = [candidate()]; first = prepare(m, c)
    tampered = first.data; tampered[key] = value
    with pytest.raises(ImportIdentityError): assess(canonical_json_bytes(tampered), m, c)


def test_resigned_regular_plan_and_rewritten_bindings_do_not_bypass_candidate_recomputation():
    m = model([imported()]); c = [candidate()]
    first = prepare(m, c); second = prepare(m, [candidate("A different but valid target.")])
    assert first.plan_valid and second.plan_valid and first.plan.sha256 != second.plan.sha256
    forged = first.data; forged["change_plan"] = second.plan.data
    forged["binding"]["change_plan_sha256"] = second.plan.sha256
    with pytest.raises(ImportIdentityError): assess(canonical_json_bytes(forged), m, c)
    with pytest.raises(ImportIdentityError): assess(second.canonical_bytes, m, c)
    forged = first.data; forged["target_assessment"]["write_authorized"] = True
    with pytest.raises(ImportIdentityError): assess(canonical_json_bytes(forged), m, c)


@pytest.mark.parametrize("change", ["extra", "missing", "version", "binding-type", "binding-extra"])
def test_saved_envelopes_have_no_unchecked_control_fields(change):
    m = model([]); first = prepare(m, []); value = first.data
    if change == "extra": value["accept_losses"] = True
    if change == "missing": value.pop("write_authorized")
    if change == "version": value["format_version"] = "artifact-import-plan-v2"
    if change == "binding-type": value["binding"] = []
    if change == "binding-extra": value["binding"]["approved"] = True
    with pytest.raises(ImportIdentityError): assess(canonical_json_bytes(value), m, [])


@pytest.mark.parametrize("raw", [b"[]", b"null", b'{"format_version":1,"format_version":2}', b'{}\xff',
    b'{"format_version":"artifact-import-plan-v1","x":NaN}', b'{"x":"\\ud800"}',
    b'{"x":' + b'[' * 1200 + b']' * 1200 + b'}'])
def test_saved_plan_reader_uses_strict_json_and_structured_errors(raw):
    with pytest.raises(ImportIdentityError) as caught: assess(raw, model([]), [])
    diagnostic = caught.value.diagnostic()
    assert diagnostic["code"] == "SRV090" and diagnostic["exit_code"] == 3
    canonical_json_bytes(diagnostic)


def test_file_names_objects_and_foreign_byte_callbacks_are_not_plan_read_instructions(tmp_path):
    class Foreign(bytes):
        def decode(self, *a, **kw): raise AssertionError("foreign callback")
    m = model([]); first = prepare(m, []); path = tmp_path / "plan.json"
    path.write_bytes(first.canonical_bytes)
    for raw in (path, str(path), first, first.data, bytearray(first.canonical_bytes), Foreign(first.canonical_bytes)):
        with no_write_attempts(), pytest.raises(ImportIdentityError) as caught: assess(raw, m, [])
        assert caught.value.reason == "import_plan_bytes_required"


def test_plan_json_layout_is_irrelevant_but_source_layout_is_not():
    m = model([imported()]); c = [candidate()]; first = prepare(m, c)
    raw = json.dumps(dict(reversed(list(first.data.items()))), indent=4).encode()
    assert raw != first.canonical_bytes
    assert assess(raw, m, c).sha256 == first.sha256
    with pytest.raises(ImportIdentityError): assess(raw, m, c, input_bytes=PAYLOAD + b"\n")


def test_portable_host_location_does_not_fake_live_inventory_or_expand_project_scope():
    m = model([imported()]); c = [candidate()]; first = prepare(m, c)
    shifted = copied(m, binding=ProjectReadBinding("sample", "/different/provider", (9, 10)))
    again = assess(first.canonical_bytes, shifted, c)
    assert again.plan_valid and again.sha256 == first.sha256
    assert again.data["target_assessment"]["project_files_verified"] is False
    scope = {**SCOPE, "boundary_policy": "open"}
    with pytest.raises(ModelError): assess(first.canonical_bytes, m, c, scope_descriptor=scope)


def test_reassessment_is_detached_and_preserves_project_and_operational_inventory(tmp_path):
    m = model([imported()]); c = [candidate("Passive text: /etc/private $(run) https://invalid.example")]
    first = prepare(m, c); snapshot = deepcopy(c)
    (tmp_path / "input.reqif").write_bytes(PAYLOAD)
    (tmp_path / "plan.json").write_bytes(first.canonical_bytes)
    (tmp_path / ".specroad").mkdir(); (tmp_path / ".specroad" / "state").write_bytes(b"unchanged")
    for path, raw in m.source_files.items():
        dest = tmp_path / "project" / path; dest.parent.mkdir(parents=True, exist_ok=True); dest.write_bytes(raw)
    before = inventory(tmp_path)
    with no_write_attempts():
        again = assess(first.canonical_bytes, m, c)
        with pytest.raises(ImportIdentityError): assess(first.canonical_bytes, m, c, input_bytes=b"changed")
    assert inventory(tmp_path) == before and c == snapshot
    report = again.data; report["binding"].clear(); report["change_plan"]["operations"].clear()
    c[0]["fields"].clear()
    assert again.canonical_bytes == first.canonical_bytes and again.plan_valid


def test_parallel_reassessments_do_not_share_mutable_reports_or_history():
    m = model([imported()]); c = [candidate()]; first = prepare(m, c)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: assess(first.canonical_bytes, m, c), range(8)))
    assert all(r.sha256 == first.sha256 and r.plan_valid for r in results)
    results[0].data["objects"].clear()
    assert all(r.data["objects"] == first.data["objects"] for r in results)


@pytest.mark.parametrize("mode", ["core", "pyz"])
def test_saved_import_reassessment_is_available_in_isolated_runtimes(tmp_path, mode):
    m = model([]); resource = mapping(); c = [candidate(new=True)]; first = prepare(m, c, resource=resource)
    plain = arguments(resource); plain.pop("mapping_resources"); plain.pop("policy")
    body = "from specroad.exchange import assess_import_plan\nfrom specroad.changes import TargetModel,TargetPolicy\n"
    body += "from specroad.profiles import ProfileResource,compose_profiles\nfrom specroad.validation import ModelDocument\n"
    body += "from specroad.model.model_manifest import ProjectReadBinding\nfrom specroad.mappings import ExchangeMapping\nimport json\n"
    body += "p=ProfileResource(" + repr(m.profile_resources[0].source_bytes) + ")\n"
    body += "m=TargetModel(" + repr(m.configuration_bytes) + ",ProjectReadBinding('sample','/explicit/provider',(1,2)),[],profile=compose_profiles([p],core_key=p.key),resource_files=[ModelDocument('profiles/core.json',p.source_bytes)])\n"
    body += "r=assess_import_plan(" + repr(first.canonical_bytes) + ",m," + repr(c)
    body += ",mapping_resources=[ExchangeMapping(" + repr(resource.source_bytes) + ")],policy=TargetPolicy('ordinary-change','1',()),**" + repr(plain) + ")\n"
    body += "print(json.dumps({'valid':r.plan_valid,'hash':r.sha256,'authorized':r.write_authorized}))\n"
    if mode == "core":
        result = run_core(body, cwd=tmp_path, capture=True)
    else:
        _, package = build_distribution(tmp_path / "dist")
        body = "import sys\nsys.path.insert(0," + repr(str(package)) + ")\n" + body
        result = run_python(["-I", "-S", "-B", "-c", body], cwd=tmp_path, capture=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"valid": True, "hash": first.sha256, "authorized": False}
