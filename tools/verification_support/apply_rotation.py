"""Commit-bound even/odd Apply gates with persistent, append-only test numbers."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from .catalog_check import run_catalog_preflight
from .ci_reference import _load_report, _unique_object
from .identity import source_identity
from .process_environment import test_environment
from .selected_contract import new_report_directory, verify_observation

REGISTRY = "verification/apply_test_numbers.json"


def validate_registry(value, current_ids, previous=None):
    if (type(value) is not dict or set(value) != {"format_version", "anchor_commit", "test_ids"}
            or type(value["format_version"]) is not int or value["format_version"] != 1
            or type(value["anchor_commit"]) is not str
            or re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", value["anchor_commit"]) is None):
        raise ValueError("Invalid Apply numbering registry")
    ids = value["test_ids"]
    if (type(ids) is not list or not ids or any(type(i) is not str or not i for i in ids)
            or len(set(ids)) != len(ids) or not set(current_ids) <= set(ids)):
        raise ValueError("Missing or duplicate stable test numbers")
    if previous is None:
        if ids != sorted(current_ids):
            raise ValueError("Initial numbering must cover the sorted complete collection")
    else:
        validate_registry_shape(previous)
        old = previous["test_ids"]
        if (value["anchor_commit"] != previous["anchor_commit"] or ids[:len(old)] != old
                or ids[len(old):] != sorted(set(current_ids) - set(old))):
            raise ValueError("Existing test numbers must not change or be reused")
    return {name: number for number, name in enumerate(ids)}


def validate_registry_shape(value):
    # A historical registry may contain retired IDs; its old initial ordering
    # is no longer a constraint after additional tests have been appended.
    if type(value) is not dict or type(value.get("test_ids")) is not list:
        raise ValueError("Invalid historical numbering registry")
    ordered = dict(value, test_ids=sorted(value["test_ids"]))
    validate_registry(ordered, ordered["test_ids"])


def commit_context(root, registry, *, runner=None):
    """Read first-parent history only; failed attempts do not advance HEAD."""
    runner = subprocess.run if runner is None else runner

    def git(*args):
        result = runner(["git", "--no-optional-locks", *args], cwd=root,
                        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE, check=False)
        if result.returncode != 0:
            raise ValueError("Cannot bind Apply selection to committed history")
        return result.stdout.decode("utf-8")

    if Path(git("rev-parse", "--show-toplevel").strip()) != Path(root).resolve():
        raise ValueError("Apply root differs from repository root")
    history = git("rev-list", "--first-parent", "HEAD").splitlines()
    if (not history or any(re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", h) is None for h in history)
            or registry["anchor_commit"] not in history):
        raise ValueError("Apply rotation anchor is not in first-parent history")
    sequence = history.index(registry["anchor_commit"])
    previous = None
    existing = git("ls-tree", "--name-only", "HEAD", "--", REGISTRY).strip()
    if existing:
        if existing != REGISTRY:
            raise ValueError("Unexpected committed numbering path")
        previous = json.loads(git("show", history[0] + ":" + REGISTRY),
                              object_pairs_hook=_unique_object)
    elif sequence:
        raise ValueError("Committed numbering registry is missing")
    return history[0], sequence, previous


def select_partition(pairs, registry, sequence, previous=None):
    if (type(pairs) is not dict or not pairs or type(sequence) is not int or sequence < 0
            or any(type(n) is not str or not n.startswith("tests/") or "::" not in n
                   or "\n" in n or "\r" in n for n in pairs)
            or any(type(i) is not str for i in pairs.values())
            or len(set(pairs.values())) != len(pairs)):
        raise ValueError("Invalid collected identities or commit sequence")
    numbers = validate_registry(registry, pairs.values(), previous)
    selected = {n: i for n, i in sorted(pairs.items()) if numbers[i] % 2 == sequence % 2}
    if not selected:
        raise ValueError("An empty Apply partition cannot pass")
    return selected


def parallel_command(root, outdir, expected, workers):
    if type(workers) is not int or workers < 2:
        raise ValueError("Apply tests require parallel workers")
    return [sys.executable, "-I", "-B", str(root / "tools/pytest_entry.py"),
            "-o", "addopts=", "--disable-plugin-autoload", "-p", "no:cacheprovider",
            "-p", "no:doctest", "-p", "xdist.plugin", "-n", str(workers),
            "--dist", "load", "--max-worker-restart=0", "--sr-observations",
            str(outdir / "observations.json"), "--sr-expected-tests", str(expected),
            "@" + str(outdir / "nodeids.txt")]


def run_apply_partition(root, outdir, *, workers=4, runner=None):
    root = Path(root).resolve()
    if type(workers) is not int or workers < 2:
        raise ValueError("Apply tests require parallel workers")
    outdir = new_report_directory(outdir, root)
    catalog_path = outdir / "catalog.json"
    if not run_catalog_preflight(root, catalog_path):
        raise ValueError("Full collection/catalog check failed; Apply tests not started")
    catalog = _load_report(catalog_path)
    binding = catalog["source_sha256"]
    registry = _load_report(root / REGISTRY)
    validate_registry_shape(registry)
    head, sequence, previous = commit_context(root, registry)
    selected = select_partition(catalog["nodeid_to_test_id"], registry, sequence, previous)
    (outdir / "nodeids.txt").write_text("\n".join(selected) + "\n", encoding="utf-8")
    # pytest's native argument-file support avoids OS argument-length limits.
    command = parallel_command(root, outdir, len(selected), workers)
    runner = subprocess.run if runner is None else runner
    try:
        code = runner(command, cwd=root, env=test_environment(os.environ),
                      stdin=subprocess.DEVNULL, check=False).returncode
    except OSError:
        code = 4
    errors = []
    try:
        observation = _load_report(outdir / "observations.json")
        files = {n.split("::", 1)[0] for n in selected}
        verify_observation(observation, files, len(selected))
        if (observation["nodeid_to_test_id"] != selected
                or any(not name.startswith("gw") for name in observation["worker_test_counts"])
                or code != 0 or source_identity(root) != binding
                or commit_context(root, registry) != (head, sequence, previous)):
            raise ValueError("Nonpassing, changed or unbound Apply selection")
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError):
        errors.append("nonpassing_or_unbound_partition")
    result = {"format_version": 1, "purpose": "alternating_apply_tests",
              "test_scope": "stable_even_odd_partition", "full_suite_passed": None,
              "selected_passed": not errors, "source_sha256": binding,
              "base_commit": head, "anchor_commit": registry["anchor_commit"],
              "commit_sequence": sequence, "parity": "even" if sequence % 2 == 0 else "odd",
              "collected_tests": catalog["collected_tests"], "expected_tests": len(selected),
              "nodeid_to_test_id": selected, "workers": workers,
              "process_exit_code": code, "errors": errors, "exit_code": 0 if not errors else 1}
    with (outdir / "selection.json").open("x", encoding="utf-8") as stream:
        json.dump(result, stream, allow_nan=False, sort_keys=True)
        stream.write("\n")
    return result
