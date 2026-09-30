"""Resolve a manual full regression and a freshly checked runner alternative."""
import json
import os
from pathlib import Path
import subprocess
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))
from verification_support.bundle_ci import commit_sha, select_ci
from ci_support.runners import probe_runner, runner_labels


def resolve_selection(environment, *, runner=None, probe=None):
    runner = subprocess.run if runner is None else runner
    event, ref = environment.get("GITHUB_EVENT_NAME"), environment.get("GITHUB_REF", "")
    if event not in ("push", "workflow_dispatch"):
        raise ValueError("Unsupported workflow event")
    requested = environment.get("SR_COMMIT_SHA", "")
    if event != "workflow_dispatch" and requested:
        raise ValueError("Only a manual run accepts an explicit revision")
    workflow_sha = commit_sha(environment.get("GITHUB_SHA", ""))
    sha = commit_sha(requested or workflow_sha)
    mode = environment.get("SR_CI_MODE") or "both"
    if event == "push":
        # Defense in depth for old/default-branch push workflows: no git lookup,
        # runner probe or suite, even for a final or fifth-numbered bundle.
        return {**select_ci(event, ref, sha, "", mode=mode),
                "workflow_commit_sha": workflow_sha, "runner_choice": None,
                "runner": "[]", "runner_selection": None}
    if ref != "refs/heads/dev":
        raise ValueError("Select dev when dispatching this workflow")
    choice = environment.get("SR_CI_RUNNER") or "auto"
    if choice not in ("auto", "hetzner", "github-hosted"):
        raise ValueError("Unknown runner choice")
    def git(*args):
        return runner(["git", *args], cwd=ROOT, stdin=subprocess.DEVNULL,
                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True).stdout.decode("utf-8")
    resolved = git("rev-parse", "--verify", sha + "^{commit}").strip()
    if resolved != sha:
        raise ValueError("Revision did not resolve exactly")
    git("merge-base", "--is-ancestor", sha, "origin/dev")
    message = git("show", "-s", "--format=%B", sha)
    selection = select_ci(event, ref, sha, message, mode=mode)
    if choice == "github-hosted":
        decision = {"format_version": 1, "repository": "cdoehn/specroad",
                    "choice": "github-hosted", "runs_on": runner_labels("github-hosted"),
                    "reason": "explicit_hosted_request", "reservation": False}
    else:
        decision = (probe_runner if probe is None else probe)()
        if (type(decision) is not dict or decision.get("format_version") != 1
                or decision.get("repository") != "cdoehn/specroad"
                or decision.get("reservation") is not False
                or decision.get("choice") not in ("hetzner", "github-hosted")
                or decision.get("runs_on") != runner_labels(decision["choice"])):
            raise ValueError("Invalid runner availability evidence")
    selection.update(workflow_commit_sha=workflow_sha,
                     runner_choice=decision["choice"], runner_selection=decision,
                     runner=json.dumps(decision["runs_on"], separators=(",", ":")))
    return selection


def main():
    try:
        selection = resolve_selection(os.environ)
        with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as stream:
            for key in ("commit_sha", "mode", "runner"):
                stream.write(key + "=" + selection[key] + "\n")
            stream.write("run_full=" + str(selection["run_full"]).lower() + "\n")
        if os.environ.get("SR_SELECTION_REPORT"):
            with Path(os.environ["SR_SELECTION_REPORT"]).open("x", encoding="utf-8") as stream:
                json.dump(selection, stream, sort_keys=True, allow_nan=False)
                stream.write("\n")
        print(json.dumps(selection, sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError):
        print("CI revision selection failed; no successful full gate is asserted.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
