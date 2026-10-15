"""Observe execution/data contracts, not CLI text or workflow formatting."""
import json
import subprocess
import sys
import uuid
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

import pytest
import run_tests
from run_ci_tests import run_reference


def evidence():
    return {
        "report_format_version": 2, "purpose": "development_behavior_evidence",
        "suite_passed": True, "tests_run": 1,
        "test_outcomes": {"stable.a": "passed"}, "run_id": str(uuid.uuid4()),
        **{name: "a" * 64 for name in ("tool_build_sha256", "specification_sha256", "catalog_sha256", "platform_sha256")},
        "observation": {
            "nodeids": ["test.py::test_a"], "nodeid_to_test_id": {"test.py::test_a": "stable.a"},
            "test_outcomes": {"stable.a": "passed"}, "suite_passed": True, "errors": [],
            "pytest_exit_code": 0, "tests_run": 1, "worker_test_counts": {"main": 1},
        },
    }


def fake_runner(calls, codes=(0, 0), write=True):
    def execute(command, **kwargs):
        index = len(calls)
        calls.append((command, kwargs))
        if write:
            data = evidence()
            if index == 0:
                data["observation"]["worker_test_counts"] = {"gw0": 1}
            Path(command[command.index("--evidence") + 1]).write_text(json.dumps(data), encoding="utf-8")
        return SimpleNamespace(returncode=codes[index])
    return execute


def test_local_default_is_one_four_worker_run():
    with patch.object(run_tests.subprocess, "run", return_value=SimpleNamespace(returncode=0)) as start:
        assert run_tests.main([]) == 0
    assert start.call_count == 1
    command = start.call_args.args[0]
    assert command[command.index("-n") + 1] == "4"
    assert "timeout" not in start.call_args.kwargs
    assert start.call_args.kwargs["stdin"] == subprocess.DEVNULL


def test_explicit_parallel_override_is_preserved():
    with patch.object(run_tests.subprocess, "run", return_value=SimpleNamespace(returncode=0)) as start:
        assert run_tests.main(["--workers", "2"]) == 0
    command = start.call_args.args[0]
    assert command[command.index("-n") + 1] == "2"


def test_local_runner_propagates_failure_without_retry():
    with patch.object(run_tests.subprocess, "run", return_value=SimpleNamespace(returncode=1)) as start:
        assert run_tests.main([]) == 1
    assert start.call_count == 1


def test_ci_refuses_accidental_local_invocation(tmp_path):
    calls = []
    target = tmp_path / "new"
    with pytest.raises(ValueError):
        run_reference(target, environment={}, runner=fake_runner(calls))
    assert not calls and not target.exists()


def test_ci_runs_only_parallel_with_owned_evidence(tmp_path):
    calls = []
    result = run_reference(tmp_path / "run", environment={"GITHUB_ACTIONS": "true"}, runner=fake_runner(calls))
    assert result["suite_passed"] is True and result["exit_code"] == 0
    assert result["comparison"] is None
    assert [c[c.index("--workers")+1] for c, kw in calls] == ["4"]
    assert len({kw["env"]["PYTHONHASHSEED"] for c, kw in calls}) == 1
    assert all("timeout" not in kw and "shell" not in kw for c, kw in calls)


def test_parallel_failure_is_not_retried(tmp_path):
    calls = []
    result = run_reference(tmp_path / "run", environment={"GITHUB_ACTIONS": "true"},
                           runner=fake_runner(calls, codes=(1, 0)))
    assert len(calls) == 1 and result["exit_code"] != 0
    assert result["suite_passed"] is False and result["comparison"] is None


def test_nonzero_parallel_exit_prevents_ci_success(tmp_path):
    result = run_reference(tmp_path / "run", environment={"GITHUB_ACTIONS": "true"},
                           runner=fake_runner([], codes=(2,)))
    assert result["exit_code"] != 0 and result["suite_passed"] is False


def test_passing_exit_codes_without_evidence_are_not_success(tmp_path):
    result = run_reference(tmp_path / "run", environment={"GITHUB_ACTIONS": "true"},
                           runner=fake_runner([], write=False))
    assert result["exit_code"] != 0 and result["suite_passed"] is False


def test_existing_ci_directory_is_not_reused(tmp_path):
    target = tmp_path / "old"
    target.mkdir(); saved = target / "parallel-evidence.json"; saved.write_bytes(b"preserve")
    calls = []
    with pytest.raises(FileExistsError):
        run_reference(target, environment={"GITHUB_ACTIONS": "true"}, runner=fake_runner(calls))
    assert saved.read_bytes() == b"preserve" and not calls


def test_ci_processes_do_not_inherit_worker_identity_or_pytest_addopts(tmp_path):
    source = {"GITHUB_ACTIONS": "true", "PYTEST_XDIST_WORKER": "gw8", "PYTEST_ADDOPTS": "-n 0"}
    before = dict(source); calls = []
    run_reference(tmp_path / "run", environment=source, runner=fake_runner(calls))
    assert source == before
    for c, kw in calls:
        assert "PYTEST_XDIST_WORKER" not in kw["env"] and "PYTEST_ADDOPTS" not in kw["env"]


def test_serial_option_is_preserved_for_laptop_gate():
    with patch.object(run_tests.subprocess, "run", return_value=SimpleNamespace(returncode=0)) as start:
        assert run_tests.main(["--workers", "0"]) == 0
    command = start.call_args.args[0]
    assert "-n" not in command and "xdist.plugin" not in command


def _assert_apply_partition(args, code, capsys, tmp_path):
    """The historical test IDs stay stable; the approved gate now selects a half."""
    import run_apply_tests
    calls = []
    report = {"purpose": "alternating_apply_tests", "workers": 4, "parity": "odd",
              "commit_sequence": 3, "test_scope": "stable_even_odd_partition",
              "selected_passed": code == 0, "full_suite_passed": None,
              "process_exit_code": code, "exit_code": 0 if code == 0 else 1,
              "nodeid_to_test_id": {"tests/test_sample.py::test_one": "sample.one"}}
    def execute(root, outdir):
        calls.append((root, outdir))
        return report
    outdir = tmp_path / "apply-report"
    with patch.object(run_apply_tests, "run_apply_partition", side_effect=execute):
        assert run_apply_tests.main([*args, "--outdir", str(outdir)]) == (0 if code == 0 else 1)
    assert len(calls) == 1
    assert calls[0] == (run_apply_tests.ROOT, outdir)
    assert json.loads(capsys.readouterr().out) == {
        **{k: v for k, v in report.items() if k != "nodeid_to_test_id"},
        "report_directory": str(outdir)}


@pytest.mark.parametrize("code", [0, 1, 2, 4])
def test_intermediate_apply_runs_only_full_parallel_without_retry(code, capsys, tmp_path):
    _assert_apply_partition([], code, capsys, tmp_path)


@pytest.mark.parametrize("code", [0, 1, 2, 4])
def test_final_apply_runs_only_full_parallel_without_retry(code, capsys, tmp_path):
    _assert_apply_partition(["--final-bundle-state"], code, capsys, tmp_path)


@pytest.mark.parametrize("final", [False, True])
def test_apply_start_failure_does_not_retry_or_fall_back(final, capsys, tmp_path):
    import run_apply_tests
    calls = []
    def execute(root, outdir):
        calls.append((root, outdir))
        raise OSError('cannot start')
    outdir = tmp_path / "failed-report"
    args = (["--final-bundle-state"] if final else []) + ["--outdir", str(outdir)]
    with patch.object(run_apply_tests, "run_apply_partition", side_effect=execute):
        assert run_apply_tests.main(args) == 4
    assert calls == [(run_apply_tests.ROOT, outdir)]
    assert json.loads(capsys.readouterr().out) == {
        "purpose": "alternating_apply_tests", "selected_passed": False,
        "full_suite_passed": None, "exit_code": 4, "error": "apply_partition_rejected",
        "report_directory": str(outdir)}


def test_apply_rejects_unknown_gate_options_before_starting_tests():
    import run_apply_tests
    with patch.object(run_apply_tests, "run_apply_partition") as start:
        with pytest.raises(SystemExit) as failure:
            run_apply_tests.main(["--workers", "0"])
    assert failure.value.code == 2
    start.assert_not_called()


@pytest.mark.parametrize("code,write", [(0, True), (1, True), (0, False)])
def test_current_github_gate_runs_only_parallel_and_requires_complete_evidence(tmp_path, code, write):
    calls = []
    result = run_reference(tmp_path / "parallel", environment={"GITHUB_ACTIONS": "true"}, runner=fake_runner(calls, codes=(code,), write=write))
    assert len(calls) == 1
    assert calls[0][0][calls[0][0].index("--workers") + 1] == "4"
    assert result["suite_passed"] is (code == 0 and write)
    assert result["comparison"] is None
    assert not (tmp_path / "parallel" / "serial-evidence.json").exists()
