"""Machine diagnostics preserve failure, existing evidence and private data."""
import json
import subprocess

import pytest
import select_bundle_ci


@pytest.mark.parametrize("error,code", [
    (ValueError("Missing or ambiguous bundle trailers"), "invalid_bundle_metadata"),
    (ValueError("Invalid bundle number"), "invalid_bundle_metadata"),
    (ValueError("Invalid completion trailer"), "invalid_bundle_metadata"),
    (ValueError("private-input"), "invalid_selection"),
    (KeyError("private-input"), "missing_environment"),
    (OSError("private-input"), "selection_io_failed"),
    (subprocess.CalledProcessError(1, ["git", "private-input"], stderr=b"private-input"), "revision_git_failed"),
])
def test_selection_failure_records_bounded_reason_without_a_success(tmp_path, monkeypatch, error, code):
    report = tmp_path / "selection.json"
    output = tmp_path / "output"
    monkeypatch.setenv("SR_SELECTION_REPORT", str(report))
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    def fail(environment):
        raise error
    monkeypatch.setattr(select_bundle_ci, "resolve_selection", fail)
    assert select_bundle_ci.main() == 2
    value = json.loads(report.read_bytes())
    assert value == {"format_version": 1, "kind": "specroad-ci-selection-failure-v1",
                     "error": code, "run_full": False, "tests_run": 0, "full_suite_passed": None}
    assert not output.exists()


@pytest.mark.parametrize("existing", [False, True])
def test_failed_diagnostic_write_does_not_replace_evidence_or_original_error(tmp_path, existing):
    report = tmp_path / "existing" if existing else tmp_path / "absent/selection.json"
    if existing:
        report.write_bytes(b"retained evidence")
    assert select_bundle_ci.selection_failure(ValueError("private-input"), {
        "SR_SELECTION_REPORT": str(report)}) == "invalid_selection"
    if existing:
        assert report.read_bytes() == b"retained evidence"
    else:
        assert not report.exists()
