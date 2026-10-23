"""Observable policy outcomes from the specified five-case comparison table."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
from hashlib import sha256
import json
from unittest.mock import patch

import pytest

from specroad.exchange import ExternalIdentity, ImportComparison, ImportIdentityError, NativeIdentityIndex
from specroad.graph.relations import SourceRelations
from specroad.model.canonical import canonical_json_bytes
from support.artifacts import artifact_bytes
from support.exchange_mappings import selected, fields_value
from support.import_comparison import ADOPTING, BASE, EXTERNAL, LOCAL, STRATEGIES, compare, imported
from support.import_identities import MAPPING, TIME
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import no_write_attempts
from support.relations import aid, artifact, edge, external


@pytest.mark.parametrize("strategy", ADOPTING)
@pytest.mark.parametrize("local,source,state,action,target,refresh,changed", [
    (BASE, BASE, "unchanged", "noop", BASE, True, False),
    (BASE, EXTERNAL, "source_changed", "adopt", EXTERNAL, True, True),
    (LOCAL, BASE, "local_changed", "retain_local", None, False, False),
    (EXTERNAL, EXTERNAL, "converged", "adopt", EXTERNAL, True, False),
    (LOCAL, EXTERNAL, "diverged", "reject", None, False, False),
], ids=("unchanged", "source-only", "local-only", "converged", "diverged"))
def test_both_adopting_strategies_follow_the_five_normative_cases(strategy, local, source, state,
                                                                action, target, refresh, changed):
    identity = imported(); before = deepcopy(identity)
    with no_write_attempts():
        result = compare(identity=identity, strategy=strategy,
                         local_projection=local, source_projection=source).data
    assert result["strategy"] == strategy and result["comparison"] == state
    assert result["action"] == action and result["target_projection"] == target
    assert result["baseline_refresh_allowed"] is refresh and result["projection_changed"] is changed
    assert result["local_changed"] is (local != BASE)
    assert result["source_changed"] is (source != BASE)
    assert result["identity"] == identity == before
    assert result["local_projection"] == local and result["source_projection"] == source
    assert result["publication_authorized"] is False
    assert result["exit_code"] == (3 if state == "diverged" else 0)
    assert [d["code"] for d in result["diagnostics"]] == (["SRV148"] if state == "diverged" else [])


@pytest.mark.parametrize("strategy,action", [("error", "reject"), ("skip", "skip")])
@pytest.mark.parametrize("local,source,state", [
    (BASE, BASE, "unchanged"), (BASE, EXTERNAL, "source_changed"),
    (LOCAL, BASE, "local_changed"), (EXTERNAL, EXTERNAL, "converged"),
    (LOCAL, EXTERNAL, "diverged"),
], ids=("unchanged", "source-only", "local-only", "converged", "diverged"))
def test_error_and_skip_never_adopt_or_hide_a_divergent_conflict(strategy, action, local, source, state):
    result = compare(strategy=strategy, local_projection=local, source_projection=source).data
    assert result["action"] == action and result["comparison"] == state
    assert result["target_projection"] is None and result["baseline_refresh_allowed"] is False
    assert result["identity"] == imported() and result["local_projection"] == local
    diagnostics = result["diagnostics"]
    if state == "diverged":
        assert [(d["code"], d["reason"]) for d in diagnostics] == [("SRV148", "divergent_changes")]
    elif strategy == "error":
        assert [(d["code"], d["reason"]) for d in diagnostics] == [("SRV090", "known_identity")]
    else:
        assert diagnostics == []
    assert result["exit_code"] == (3 if diagnostics else 0)


@pytest.mark.parametrize("strategy", STRATEGIES)
def test_missing_legacy_history_remains_missing_and_cannot_become_an_import_baseline(strategy):
    identity = external(external_revision="007"); before = deepcopy(identity)
    result = compare(identity=identity, strategy=strategy).data
    assert result["identity"] == identity == before and result["comparison"] == "history_unavailable"
    assert result["local_changed"] is result["source_changed"] is None
    assert result["target_projection"] is None and result["baseline_refresh_allowed"] is False
    assert result["action"] == ("skip" if strategy == "skip" else "reject")
    reason = "known_identity" if strategy == "error" else "history_unavailable"
    assert [d["reason"] for d in result["diagnostics"]] == ([] if strategy == "skip" else [reason])


@pytest.mark.parametrize("strategy", STRATEGIES)
def test_wrong_mapping_is_not_compared_as_unchanged_or_silently_rebound(strategy):
    identity = imported(mapping_id="legacy-label")
    result = compare(identity=identity, strategy=strategy).data
    assert result["comparison"] == "mapping_mismatch" and result["local_changed"] is None
    assert result["source_changed"] is None and result["target_projection"] is None
    assert result["identity"] == identity and result["baseline_refresh_allowed"] is False
    reason = "known_identity" if strategy == "error" else "mapping_mismatch"
    assert [d["reason"] for d in result["diagnostics"]] == ([] if strategy == "skip" else [reason])


@pytest.mark.parametrize("strategy", STRATEGIES)
def test_unmatched_lookup_is_not_a_collision_or_an_authorized_new_object(strategy):
    index = NativeIdentityIndex([SourceRelations(artifact_bytes(artifact()))])
    match = index.lookup("artifact", "reqif", "source", "missing")
    assert match is None
    with no_write_attempts(): result = compare(identity=match, strategy=strategy).data
    assert result["comparison"] == result["action"] == "unmatched"
    assert result["identity"] is result["target_projection"] is None
    assert result["local_changed"] is result["source_changed"] is None
    assert result["diagnostics"] == [] and result["exit_code"] == 0
    assert result["publication_authorized"] is result["baseline_refresh_allowed"] is False


@pytest.mark.parametrize("strategy", ADOPTING)
def test_different_historical_projection_hashes_are_compared_to_their_own_side(strategy):
    identity = imported(imported_projection=LOCAL, source_projection=BASE)
    unchanged = compare(identity=identity, strategy=strategy, local_projection=LOCAL, source_projection=BASE).data
    assert unchanged["comparison"] == "unchanged" and unchanged["target_projection"] == LOCAL
    assert unchanged["targets_equal"] is False
    adopted = compare(identity=identity, strategy=strategy, local_projection=LOCAL).data
    assert adopted["comparison"] == "source_changed" and adopted["target_projection"] == EXTERNAL
    local = compare(identity=identity, strategy=strategy, local_projection=BASE, source_projection=BASE).data
    assert local["comparison"] == "local_changed" and local["targets_equal"] is True
    assert local["target_projection"] is None and local["baseline_refresh_allowed"] is False


def test_payload_external_revision_and_audit_changes_do_not_change_projected_comparison():
    identity = imported(); changed = imported(source_payload=b"different raw syntax", imported_at="2026-09-02T00:00:00Z")
    changed["external_revision"] = "999"
    changed["extensions"]["vendor.opaque"]["original"].append("provenance only")
    with patch("time.time", side_effect=AssertionError("clock")), no_write_attempts():
        a = compare(identity=identity, source_projection=BASE).data
        b = compare(identity=changed, source_projection=BASE).data
    assert a["comparison"] == b["comparison"] == "unchanged"
    for key in ("local_projection_sha256", "source_projection_sha256", "local_changed", "source_changed"):
        assert a[key] == b[key]
    assert a["identity"] == identity and b["identity"] == changed


@pytest.mark.parametrize("value", [None, True, 1, "1", [], {}])
def test_json_value_types_are_not_conflated_with_missing_fields(value):
    identity = imported(imported_projection={}, source_projection={})
    result = compare(identity=identity, local_projection={}, source_projection={"value": value}).data
    assert result["comparison"] == "source_changed" and result["target_projection"] == {"value": value}
    raw = json.dumps({"value": value}, separators=(",", ":")).encode()
    assert result["source_projection_sha256"] == sha256(raw).hexdigest()


def test_canonical_object_order_and_equivalent_numbers_are_equal_without_python_boolean_equality():
    identity = imported(imported_projection={"n": 1, "label": "e\u0301"}, source_projection={"n": 1, "label": "e\u0301"})
    result = compare(identity=identity, local_projection={"label": "e\u0301", "n": 1.0}, source_projection={"n": 1, "label": "e\u0301"}).data
    assert result["comparison"] == "unchanged" and result["targets_equal"] is True
    boolean = compare(identity=identity, local_projection={"n": True, "label": "e\u0301"}, source_projection={"n": 1, "label": "é"}).data
    assert boolean["comparison"] == "diverged" and boolean["targets_equal"] is False


def test_inputs_and_nested_observations_do_not_change_other_observations_or_hashes():
    identity = imported(); local = deepcopy(BASE); source = deepcopy(EXTERNAL)
    value = compare(identity=identity, local_projection=local, source_projection=source)
    before = value.data; digest = value.sha256
    identity["extensions"].clear(); local["value"].clear(); source["value"].append("changed")
    observed = value.data; observed["target_projection"]["value"].clear(); observed["identity"].clear()
    assert value.data == before and value.sha256 == digest
    assert digest == sha256(canonical_json_bytes(before)).hexdigest()
    with pytest.raises(FrozenInstanceError): value._encoded = b"{}"


@pytest.mark.parametrize("strategy", [None, "", "force", "SKIP", [], True])
def test_strategy_is_required_and_never_coerced_or_defaulted(strategy):
    with pytest.raises(ImportIdentityError) as caught: compare(strategy=strategy)
    assert caught.value.reason == "explicit_import_strategy_required"
    assert caught.value.pointer == "/strategy" and caught.value.code == "SRV090"


@pytest.mark.parametrize("key", [None, "legacy-label", "rules@latest", "rules@1", "rules@v1.0.0", "rules@01.0.0"])
def test_selected_mapping_requires_an_exact_versioned_key(key):
    with pytest.raises(ImportIdentityError) as caught: compare(mapping_id=key)
    assert caught.value.reason == "mapping_exact_key_required" and caught.value.pointer == "/mapping_id"


@pytest.mark.parametrize("strategy", STRATEGIES)
def test_structurally_incomplete_history_is_invalid_even_for_skip_or_error(strategy):
    identity = imported(); del identity["last_source_projection_sha256"]
    with pytest.raises(ImportIdentityError) as caught: compare(identity=identity, strategy=strategy)
    assert caught.value.reason == "incomplete_import_binding"
    assert caught.value.pointer.startswith("/identity") and caught.value.exit_code == 3


@pytest.mark.parametrize("field,bad", [("local_projection", []), ("source_projection", None),
    ("local_projection", {"value": float("nan")}), ("source_projection", {"value": "\ud800"}),
    ("local_projection", {"value": object()})])
def test_invalid_projection_fails_without_mutating_identity(field, bad):
    identity = imported(); before = deepcopy(identity)
    with no_write_attempts(), pytest.raises(ImportIdentityError) as caught:
        compare(identity=identity, **{field: bad})
    assert caught.value.pointer.startswith("/" + field) and caught.value.code == "SRV090"
    json.dumps(caught.value.diagnostic(), ensure_ascii=False).encode("utf-8")
    assert identity == before


@pytest.mark.parametrize("kind", ["artifact", "relation"])
def test_real_mapping_and_native_lookup_keep_owner_identity_and_original_revision(kind):
    mapper = selected()
    if kind == "artifact":
        old = mapper.artifact("Requirement", fields_value())["artifact"]
        incoming = {**old, "statement": "supplier changes the existing requirement"}
    else:
        old = mapper.relation("Derivation", aid(number=1), aid(number=2))
        incoming = mapper.relation("Derivation", aid(number=1), aid(number=3))
        old = {k: v for k, v in old.items() if k != "mapping"}
        incoming = {k: v for k, v in incoming.items() if k != "mapping"}
    identity = ExternalIdentity(external()).with_import_history(mapping_id=mapper.resource.key,
        imported_projection=old, source_projection=old, source_payload=b"source", imported_at=TIME)
    if kind == "artifact":
        native = artifact(external_identities=[identity.data], **old)
    else:
        native = artifact(relations=[edge(kind=old["relation_type"], target=old["target"],
                                          external_identities=[identity.data])])
    raw = artifact_bytes(native); index = NativeIdentityIndex([SourceRelations(raw)])
    owner = index.lookup(kind, *identity.key); before = deepcopy(owner)
    with no_write_attempts():
        result = ImportComparison(owner["identity"], mapping_id=mapper.resource.key,
            strategy="create_new_revision", local_projection=old, source_projection=incoming).data
    assert result["comparison"] == "source_changed" and result["target_projection"] == incoming
    assert index.lookup(kind, *identity.key) == owner == before
    assert native["revision"] == 1 and artifact_bytes(native) == raw
    assert result["identity"] == identity.data and result["publication_authorized"] is False


@pytest.mark.parametrize("mode", ["core", "pyz"])
def test_comparison_is_available_in_isolated_runtimes_with_no_false_write_authority(tmp_path, mode):
    body = "from specroad.exchange import ImportComparison\nimport json\n"
    body += "value=ImportComparison(" + repr(imported()) + ", mapping_id=" + repr(MAPPING)
    body += ",strategy='create_new_revision',local_projection=" + repr(BASE) + ",source_projection=" + repr(EXTERNAL) + ")\n"
    body += "print(json.dumps(value.data))\n"
    if mode == "core": result = run_core(body, tmp_path, capture=True)
    else:
        _, package = build_distribution(tmp_path / "distribution")
        result = run_python(["-I", "-S", "-B", "-c", "import sys;sys.path.insert(0," + repr(str(package)) + ")\n" + body], tmp_path, capture=True)
    assert result.returncode == 0, result.stderr
    value = json.loads(result.stdout)
    assert value["target_projection"] == EXTERNAL and value["comparison"] == "source_changed"
    assert value["strategy"] == "create_new_revision" and value["publication_authorized"] is False
