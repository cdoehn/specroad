"""Import-history binding, strict JSON and passive decision boundaries."""
from copy import deepcopy
from hashlib import sha256
import json
from unittest.mock import patch

import pytest

from specroad.exchange import ImportComparison, ImportIdentityError, NativeIdentityIndex
from specroad.graph.relations import SourceRelations
from specroad.model.canonical import canonical_json_bytes
from support.artifacts import artifact_bytes
from support.import_comparison import ADOPTING, BASE, EXTERNAL, LOCAL, STRATEGIES, compare, imported
from support.import_identities import MAPPING
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import inventory, no_write_attempts
from support.relations import artifact, edge, external


@pytest.mark.parametrize("strategy", ADOPTING)
@pytest.mark.parametrize("local,source,state,action,target,refresh", [
    (BASE, EXTERNAL, "unchanged", "noop", BASE, True),
    (BASE, BASE, "source_changed", "adopt", BASE, True),
    (EXTERNAL, EXTERNAL, "local_changed", "retain_local", None, False),
    (LOCAL, LOCAL, "converged", "adopt", LOCAL, True),
    (EXTERNAL, BASE, "diverged", "reject", None, False),
], ids=("unequal-unchanged", "equal-source-change", "equal-local-change", "converged", "diverged"))
def test_asymmetric_history_does_not_confuse_current_equality_with_change_ownership(strategy, local, source, state, action, target, refresh):
    identity = imported(imported_projection=BASE, source_projection=EXTERNAL)
    result = compare(identity=identity, strategy=strategy, local_projection=local, source_projection=source).data
    assert result["comparison"] == state and result["action"] == action
    assert result["target_projection"] == target and result["baseline_refresh_allowed"] is refresh
    assert result["identity"] == identity
    assert result["publication_authorized"] is False
    assert result["exit_code"] == (3 if state == "diverged" else 0)


@pytest.mark.parametrize("strategy", ADOPTING)
@pytest.mark.parametrize("stored,selected,equal", [
    ("rules@1.0.0-rc.1+build.7", "rules@1.0.0-rc.1+build.7", True),
    ("rules@1.0.0-rc.1", "rules@1.0.0", False),
    ("rules@1.0.0+one", "rules@1.0.0+two", False),
    ("Rules@1.0.0", "rules@1.0.0", False),
    ("rules@1.0.0 ", "rules@1.0.0", False),
    ("rules@1.0.0", "rules@1.0.1", False),
])
def test_history_mapping_binding_is_literal_including_version_case_and_build_metadata(strategy, stored, selected, equal):
    identity = imported(mapping_id=stored)
    result = compare(identity=identity, mapping_id=selected, strategy=strategy).data
    assert result["identity"] == identity and result["mapping_id"] == selected
    assert result["comparison"] == ("source_changed" if equal else "mapping_mismatch")
    assert result["target_projection"] == (EXTERNAL if equal else None)
    assert result["baseline_refresh_allowed"] is equal
    assert [d["reason"] for d in result["diagnostics"]] == ([] if equal else ["mapping_mismatch"])
    if not equal:
        assert result["local_changed"] is result["source_changed"] is None
        assert result["diagnostics"][0]["pointer"] == "/identity/mapping_id"


@pytest.mark.parametrize("strategy", STRATEGIES)
def test_legacy_extensions_and_empty_revision_never_become_active_import_history(strategy):
    history = imported()
    identity = external(external_revision="", extensions={"future.import": history})
    result = compare(identity=identity, strategy=strategy).data
    assert result["comparison"] == "history_unavailable" and result["identity"] == identity
    assert result["local_changed"] is result["source_changed"] is None
    assert result["target_projection"] is None and result["baseline_refresh_allowed"] is False
    assert result["action"] == ("skip" if strategy == "skip" else "reject")


@pytest.mark.parametrize("strategy", STRATEGIES)
@pytest.mark.parametrize("field", ["mapping_id", "last_imported_projection_sha256", "last_source_payload_sha256", "imported_at"])
def test_each_other_missing_history_field_is_structural_failure_before_any_strategy_result(strategy, field):
    identity = imported(); del identity[field]; before = deepcopy(identity)
    with no_write_attempts(), pytest.raises(ImportIdentityError) as caught:
        compare(identity=identity, strategy=strategy)
    assert caught.value.reason == "incomplete_import_binding" and caught.value.pointer == "/identity"
    assert caught.value.code == "SRV090" and caught.value.exit_code == 3
    assert identity == before


@pytest.mark.parametrize("strategy", STRATEGIES)
@pytest.mark.parametrize("field,value,reason", [
    ("mapping_id", None, "nonempty_string_required"),
    ("last_imported_projection_sha256", "A" * 64, "invalid_sha256"),
    ("last_source_payload_sha256", "f" * 63, "invalid_sha256"),
    ("imported_at", "2026-02-30T00:00:00Z", "invalid_utc_timestamp"),
])
def test_malformed_history_is_not_downgraded_to_a_legacy_or_mapping_mismatch_case(strategy, field, value, reason):
    identity = imported(); identity[field] = value; before = deepcopy(identity)
    with pytest.raises(ImportIdentityError) as caught: compare(identity=identity, strategy=strategy)
    assert caught.value.reason == reason and caught.value.pointer == "/identity/" + field
    assert caught.value.code == "SRV090" and identity == before


@pytest.mark.parametrize("field", ["local_projection", "source_projection"])
@pytest.mark.parametrize("value,reason,pointer", [
    ({"x/~": [float("inf")]}, "nonfinite_number", "/x~1~0/0"),
    ({"x/~": [9007199254740993]}, "number_roundtrip_loss", "/x~1~0/0"),
    ({"x/~": ["\udfff"]}, "invalid_unicode", "/x~1~0/0"),
    ({1: "not a string key"}, "string_key_required", ""),
    ({"\ud800": "not a Unicode scalar key"}, "invalid_unicode", ""),
])
def test_nested_projection_diagnostics_preserve_safe_json_pointers_and_original_values(field, value, reason, pointer):
    identity = imported(); identity_before = deepcopy(identity); projection_before = deepcopy(value)
    with no_write_attempts(), pytest.raises(ImportIdentityError) as caught:
        compare(identity=identity, **{field: value})
    diagnostic = caught.value.diagnostic()
    assert diagnostic["reason"] == reason and diagnostic["pointer"] == "/" + field + pointer
    assert diagnostic["code"] == "SRV090" and diagnostic["exit_code"] == 3
    json.dumps(diagnostic, ensure_ascii=False).encode("utf-8")
    assert identity == identity_before and value == projection_before


@pytest.mark.parametrize("field", ["strategy", "mapping_id", "identity", "source_projection"])
def test_foreign_conversion_or_container_hooks_are_never_used_to_accept_inputs(field):
    class Foreign:
        def __str__(self): raise AssertionError("string hook")
        def __float__(self): raise AssertionError("number hook")
        def __eq__(self, other): raise AssertionError("equality hook")
    class ForeignDict(dict):
        def __iter__(self): raise AssertionError("container hook")
        def items(self): raise AssertionError("member hook")
    bad = ForeignDict() if field in ("identity", "source_projection") else Foreign()
    with no_write_attempts(), pytest.raises(ImportIdentityError) as caught: compare(**{field: bad})
    assert caught.value.code == "SRV090" and caught.value.pointer.startswith("/" + field)


@pytest.mark.parametrize("field", ["identity", "source_projection"])
def test_cyclic_inputs_fail_without_running_hooks_or_replacing_a_previous_decision(field):
    cyclic = {}; cyclic["child"] = cyclic
    bad = imported(); bad["extensions"] = {"vendor.cycle": cyclic}
    if field == "source_projection": bad = cyclic
    value = compare(); before = value.data; digest = value.sha256
    arguments = dict(identity=imported(), mapping_id=MAPPING, strategy="update_if_unchanged",
                     local_projection=BASE, source_projection=EXTERNAL)
    arguments[field] = bad
    with no_write_attempts(), pytest.raises(ImportIdentityError) as caught: value.__init__(**arguments)
    assert caught.value.reason == "cyclic_json" and caught.value.pointer.startswith("/" + field)
    assert value.data == before and value.sha256 == digest


@pytest.mark.parametrize("field", ["local_projection", "source_projection"])
def test_reader_nesting_failure_is_structured_and_keeps_the_prior_complete_observation(field):
    # Beyond the shared reader's runtime capacity, without modifying a process
    # recursion limit or specifying a new product depth policy.
    nested = {}; cursor = nested
    for _ in range(2500):
        cursor["child"] = {}; cursor = cursor["child"]
    value = compare(); before = value.data; digest = value.sha256
    arguments = dict(identity=imported(), mapping_id=MAPPING, strategy="create_new_revision",
                     local_projection=BASE, source_projection=EXTERNAL)
    arguments[field] = nested
    with pytest.raises(ImportIdentityError) as caught: value.__init__(**arguments)
    assert caught.value.code == "SRV090" and caught.value.reason == "unsupported_json_value"
    assert caught.value.pointer == "/" + field
    assert value.data == before and value.sha256 == digest


@pytest.mark.parametrize("left,right", [(0, -0.0), (1, 1.0), (10**21, 1e21), (0.000001, 1e-6), (5e-324, 5e-324)])
def test_canonical_numeric_spellings_do_not_create_false_conflicts(left, right):
    identity = imported(imported_projection={"v": left}, source_projection={"v": left})
    result = compare(identity=identity, local_projection={"v": left}, source_projection={"v": right}).data
    assert result["comparison"] == "unchanged" and result["targets_equal"] is True
    assert result["local_projection_sha256"] == result["source_projection_sha256"]
    assert result["projection_changed"] is False


def test_shared_nested_inputs_and_mutated_diagnostics_cannot_change_later_observations():
    shared = {"data": [None, False, 1, "1", "e\u0301", "\0\n", "東京"]}
    source = {"a": shared, "b": shared}
    value = compare(local_projection={"a": {}}, source_projection=source)
    before = value.data; digest = value.sha256
    shared["data"].clear()
    observed = value.data; observed["source_projection"]["a"].clear()
    assert observed["source_projection"]["b"] == before["source_projection"]["b"]
    observed["identity"].clear(); observed["diagnostics"].clear()
    assert value.data == before and value.sha256 == digest
    assert digest == sha256(canonical_json_bytes(before)).hexdigest()


@pytest.mark.parametrize("strategy", STRATEGIES)
def test_real_read_only_sources_stay_byte_and_mode_identical_for_every_decision(tmp_path, monkeypatch, strategy):
    identity = imported()
    identity["source_document"] = "../../private/source.reqif"
    passive = {"url": "https://unused.invalid/next", "file": "file:///private", "script": "touch NEVER"}
    identity["extensions"]["vendor.instructions"] = passive
    native = artifact(external_identities=[identity])
    path = tmp_path / "native.json"; path.write_bytes(artifact_bytes(native)); path.chmod(0o444)
    (tmp_path / "source.bin").write_bytes(b"\0\xffexternal\r\n")
    before = inventory(tmp_path); monkeypatch.chdir(tmp_path)
    source = SourceRelations(path.read_bytes()); owner = NativeIdentityIndex([source]).lookup("artifact", "reqif", identity["source_document"], identity["external_id"])
    def forbidden(*args, **kwargs): raise AssertionError("external operation")
    with no_write_attempts(), monkeypatch.context() as guard:
        for name in ("builtins.open", "io.open", "os.open", "time.time", "socket.getaddrinfo", "secrets.token_bytes"):
            guard.setattr(name, forbidden)
        results = [compare(identity=owner["identity"], strategy=strategy,
                           local_projection=local, source_projection=incoming).data
                   for local, incoming in ((BASE, BASE), (BASE, EXTERNAL), (LOCAL, BASE), (LOCAL, EXTERNAL))]
    assert all(r["identity"] == identity and r["publication_authorized"] is False for r in results)
    assert results[-1]["diagnostics"][0]["code"] == "SRV148"
    if strategy in ("error", "skip"):
        assert all(r["target_projection"] is None for r in results)
    else:
        assert results[1]["target_projection"] == EXTERNAL
    assert source.source_bytes == artifact_bytes(native) and native["revision"] == 1
    assert inventory(tmp_path) == before


@pytest.mark.parametrize("strategy", STRATEGIES)
@pytest.mark.parametrize("kind", ["artifact", "relation"])
def test_ambiguous_native_owners_are_not_accepted_by_a_policy_choice(strategy, kind):
    identity = imported(); other = imported(mapping_id="other@2.0.0")
    values = [artifact(number=i, external_identities=[v] if kind == "artifact" else [],
                       relations=[edge(number=i, external_identities=[v])] if kind == "relation" else [])
              for i, v in enumerate((identity, other), 1)]
    raw = [artifact_bytes(value) for value in values]
    with no_write_attempts(), pytest.raises(ImportIdentityError) as caught:
        owner = NativeIdentityIndex([SourceRelations(b) for b in raw]).lookup(kind, "reqif", "supplier.reqif", "_req-10")
        compare(identity=owner["identity"], strategy=strategy)
    assert caught.value.code == "SRV147" and caught.value.exit_code == 3
    assert [artifact_bytes(value) for value in values] == raw


@pytest.mark.parametrize("mode", ["core", "pyz"])
def test_isolated_rejections_keep_conflicts_visible_and_passive_data_unexecuted(tmp_path, mode):
    identity = imported(); identity["extensions"]["vendor.passive"] = {"command": "touch NEVER", "url": "file:///private"}
    body = '''import json, os, sys
from specroad.exchange import ImportComparison, ImportIdentityError
def guard(event, args):
    if event.startswith(('socket.', 'subprocess.')) or event in ('os.system', 'os.mkdir', 'os.remove', 'os.rename'):
        raise AssertionError(event)
    if event == 'open':
        mode, flags = args[1], args[2]
        if (isinstance(mode, str) and any(c in mode for c in 'wax+')) or (isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)):
            raise AssertionError(event)
sys.addaudithook(guard)
'''
    body += 'identity=' + repr(identity) + '\nvalues=[]\n'
    body += 'for strategy in ' + repr(STRATEGIES) + ':\n'
    body += '    values.append(ImportComparison(identity,mapping_id=' + repr(MAPPING) + ',strategy=strategy,local_projection=' + repr(LOCAL) + ',source_projection=' + repr(EXTERNAL) + ').data)\n'
    body += 'identity["last_source_projection_sha256"]=None\n'
    body += 'try:\n    ImportComparison(identity,mapping_id=' + repr(MAPPING) + ',strategy="skip",local_projection={},source_projection={})\n'
    body += 'except ImportIdentityError as error:\n    invalid=error.diagnostic()\n'
    body += 'print(json.dumps({"values":values,"invalid":invalid}))\n'
    if mode == "core": result = run_core(body, tmp_path, capture=True)
    else:
        _, package = build_distribution(tmp_path / "distribution")
        result = run_python(["-I", "-S", "-B", "-c", "import sys;sys.path.insert(0," + repr(str(package)) + ")\n" + body], tmp_path, capture=True)
    assert result.returncode == 0, result.stderr
    result = json.loads(result.stdout)
    assert result["invalid"]["code"] == "SRV090" and result["invalid"]["pointer"] == "/identity/last_source_projection_sha256"
    for value in result["values"]:
        assert value["comparison"] == "diverged" and value["diagnostics"][0]["code"] == "SRV148"
        assert value["target_projection"] is None and value["baseline_refresh_allowed"] is False
        assert value["identity"]["extensions"] == identity["extensions"]
