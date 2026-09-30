"""Resolve the exact dev commit to test; pass no event text to a shell."""
import json
import os
from pathlib import Path
import subprocess
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))
from verification_support.bundle_ci import commit_sha, select_ci
from ci_support.runners import commit_runner, runner_labels


def resolve_selection(environment, *, runner=None):
    runner = subprocess.run if runner is None else runner
    event, ref = environment.get("GITHUB_EVENT_NAME"), environment.get("GITHUB_REF", "")
    if event not in ("push", "workflow_dispatch"):
        raise ValueError("Unsupported workflow event")
    requested = environment.get("SR_COMMIT_SHA", "")
    if event != "workflow_dispatch" and requested:
        raise ValueError("Only a manual run accepts an explicit revision")
    sha = commit_sha(requested or environment.get("GITHUB_SHA", ""))
    def git(*args):
        return runner(["git", *args], cwd=ROOT, stdin=subprocess.DEVNULL,
                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True).stdout.decode("utf-8")
    # Full commit only, and it must belong to the published dev history.
    resolved = git("rev-parse", "--verify", sha + "^{commit}").strip()
    if resolved != sha:
        raise ValueError("Revision did not resolve exactly")
    git("merge-base", "--is-ancestor", sha, "origin/dev")
    message = git("show", "-s", "--format=%B", sha)
    selection = select_ci(event, ref, sha, message, mode=environment.get("SR_CI_MODE", "auto"))
    choice = ((environment.get("SR_CI_RUNNER") or "github-hosted")
              if event == "workflow_dispatch" else commit_runner(message))
    selection["runner_choice"] = choice
    selection["runner"] = json.dumps(runner_labels(choice), separators=(",", ":"))
    return selection


def main():
    try:
        selection = resolve_selection(os.environ)
        with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as stream:
            for key in ("commit_sha", "mode", "runner"):
                stream.write(key + "=" + selection[key] + "\n")
            stream.write("run_full=" + str(selection["run_full"]).lower() + "\n")
        print(json.dumps(selection, sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError):
        print("CI revision selection failed; no successful full gate is asserted.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
