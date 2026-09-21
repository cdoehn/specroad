"""Faults never turn a CI reference into a passed full-suite observation."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from run_ci_tests import run_reference
from test_ci_policy import evidence, fake_runner


@pytest.mark.parametrize("value", [0, -1, True, 1.5, "4", "auto", None])
def test_invalid_parallel_worker_selection_has_no_effect(tmp_path, value):
    calls = []
    target = tmp_path / "run"
    with pytest.raises(ValueError):
        run_reference(target, workers=value, environment={"GITHUB_ACTIONS": "true"}, runner=fake_runner(calls))
    assert not calls and not target.exists()


@pytest.mark.parametrize("value", [None, "false", "TRUE", True, "1"])
def test_ci_guard_is_explicit(tmp_path, value):
    with pytest.raises(ValueError):
        run_reference(tmp_path / "run", environment={"GITHUB_ACTIONS": value}, runner=fake_runner([]))
    assert not (tmp_path / "run").exists()


@pytest.mark.parametrize("fault", ["missing", "invalid_json", "duplicate_key", "nonfinite", "nonobject", "different_source", "different_ids", "repeated_run"])
def test_invalid_current_evidence_fails_comparison(tmp_path, fault):
    first = evidence(); calls = []
    def execute(command, **kwargs):
        path = Path(command[command.index("--evidence") + 1])
        data = first if not calls else evidence()
        if calls:
            if fault == "missing":
                calls.append(command); return SimpleNamespace(returncode=0)
            if fault == "different_source": data["tool_build_sha256"] = "b" * 64
            if fault == "different_ids": data["observation"]["nodeids"] = ["other"]
            if fault == "repeated_run": data["run_id"] = first["run_id"]
            if fault == "nonobject": data = None
        raw = json.dumps(data)
        if calls:
            if fault == "invalid_json": raw = "{"
            if fault == "duplicate_key": raw = raw[:-1] + ', "suite_passed": true}'
            if fault == "nonfinite": raw = raw[:-1] + ', "unsafe": NaN}'
        path.write_text(raw, encoding="utf-8"); calls.append(command)
        return SimpleNamespace(returncode=0)
    target = tmp_path / "run"
    result = run_reference(target, environment={"GITHUB_ACTIONS": "true"}, runner=execute)
    assert not result["suite_passed"] and result["exit_code"] != 0
    assert result["errors"] == ["invalid_or_non_equivalent_evidence"]
    assert json.loads((target/"summary.json").read_text()) == result


def test_interpreter_launch_error_is_not_a_green_run(tmp_path):
    calls = []
    def execute(command, **kwargs):
        calls.append(command)
        raise OSError("interpreter unavailable")
    result = run_reference(tmp_path / "run", environment={"GITHUB_ACTIONS": "true"}, runner=execute)
    assert len(calls) == 2 and not result["suite_passed"]
    assert [check["exit_code"] for check in result["checks"]] == [4, 4]


def test_signal_exit_remains_a_failure_even_if_serial_passes(tmp_path):
    result = run_reference(tmp_path / "run", environment={"GITHUB_ACTIONS": "true"}, runner=fake_runner([], codes=(-9, 0)))
    assert result["exit_code"] == 1 and result["checks"][0]["exit_code"] == -9


def test_interruption_stops_instead_of_claiming_success(tmp_path):
    calls = []
    def execute(command, **kwargs):
        calls.append(command)
        raise KeyboardInterrupt
    with pytest.raises(KeyboardInterrupt):
        run_reference(tmp_path / "run", environment={"GITHUB_ACTIONS": "true"}, runner=execute)
    assert len(calls) == 1 and not (tmp_path/"run/summary.json").exists()


def test_symlink_report_is_not_followed(tmp_path):
    elsewhere = tmp_path/"untouched.json"; elsewhere.write_text(json.dumps(evidence()))
    def execute(command, **kwargs):
        Path(command[command.index("--evidence")+1]).symlink_to(elsewhere)
        return SimpleNamespace(returncode=0)
    before = elsewhere.read_bytes()
    result = run_reference(tmp_path / "run", environment={"GITHUB_ACTIONS": "true"}, runner=execute)
    assert not result["suite_passed"] and elsewhere.read_bytes() == before


def test_existing_summary_is_not_overwritten(tmp_path):
    target = tmp_path/"run"; calls=[];delegate=fake_runner(calls)
    def execute(command, **kwargs):
        value=delegate(command, **kwargs)
        if len(calls)==2: (target/"summary.json").write_bytes(b"keep")
        return value
    with pytest.raises(FileExistsError):
        run_reference(target, environment={"GITHUB_ACTIONS":"true"},runner=execute)
    assert (target/"summary.json").read_bytes()==b"keep"


def test_two_ci_invocations_never_share_evidence(tmp_path):
    for name in ("one","two"):
        result=run_reference(tmp_path/name,environment={"GITHUB_ACTIONS":"true"},runner=fake_runner([]))
        assert result["suite_passed"]
    first=json.loads((tmp_path/"one/serial-evidence.json").read_text())
    second=json.loads((tmp_path/"two/serial-evidence.json").read_text())
    assert first["run_id"]!=second["run_id"]
