"""Actual native Git commits must be accepted by the manual CI selector."""
from hashlib import sha256
import subprocess

import pytest

import select_bundle_ci
from verification_support.bundle_apply import NativeApply


@pytest.mark.parametrize("count", [1, 2, 3])
def test_actual_native_stage_commits_are_selectable_in_manual_ci(tmp_path, monkeypatch, count):
    root = tmp_path / "apply-fixture"
    root.mkdir()
    def git(*args):
        return subprocess.run(["git", *args], cwd=root, check=True,
                              capture_output=True, text=True).stdout.strip()
    git("init", "-b", "dev")
    git("config", "user.name", "Fixture")
    git("config", "user.email", "fixture@example.invalid")
    git("config", "commit.gpgsign", "false")
    (root / "sample.py").write_text("VALUE = 0\n")
    git("add", "sample.py")
    git("commit", "-m", "fixture base")
    stages = [{"commit_id": "CI-FIX." + phase} for phase in "WRC"[-count:]]
    history = []
    data = {"bundle_number": "592", "stages": stages, "branch": "dev",
            "apply_repository": str(root)}
    monkeypatch.chdir(root)
    monkeypatch.setattr(select_bundle_ci, "ROOT", root)
    backend = NativeApply(data)
    for index, stage in enumerate(stages):
        head = backend.head()
        raw = ("VALUE = " + str(index + 1) + "\n").encode()
        (root / "sample.py").write_bytes(raw)
        stage.update(message="OFF-PLAN " + stage["commit_id"] + " fixture change",
                     after={"sample.py": sha256(raw).hexdigest()})
        committed = backend.commit(stage, head, {"selection_sha256": "a" * 64})
        git("update-ref", "refs/remotes/origin/dev", committed)
        selection = select_bundle_ci.resolve_selection({
            "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_REF": "refs/heads/dev",
            "GITHUB_SHA": committed, "SR_CI_RUNNER": "github-hosted"})
        assert selection["run_full"] and selection["commit_sha"] == committed
        assert selection["bundle_number"] == 592
        assert selection["bundle_final"] is (index == len(stages) - 1)
        assert git("show", "-s", "--format=%P", committed) == head
        assert not git("status", "--porcelain")
        history.append(committed)
    # Manual CI may deliberately select a proved earlier stage of the same history.
    selection = select_bundle_ci.resolve_selection({
        "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_REF": "refs/heads/dev",
        "GITHUB_SHA": history[-1], "SR_COMMIT_SHA": history[0],
        "SR_CI_RUNNER": "github-hosted"})
    assert selection["commit_sha"] == history[0]
    assert selection["bundle_final"] is (count == 1)
