"""Historical AUDIT-REC-05.U process observations, not permanent defect tests.

Use the development Python with --output NEW_EXTERNAL_JSON. Sixteen cases run
through pytest-xdist with four workers. Each writer and recovery consumer is a
fresh Python process. Only owned temporary fixture projects may be supplied to
internal child modes. No preflight object is serialized or inherited.
"""
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
sys.dont_write_bytecode = True
sys.path[:0] = [str(REPO / part) for part in ("src", "tests", "tools")]

import pytest
from specroad.changes import (
    BuildingJournal, ChangePlan, LockRecord, PreparedJournal, RecoveryAuthority,
    TargetModel, TargetPolicy, begin_building_journal,
    discard_unpublished_transaction, inspect_project_lock, inspect_recovery,
    prepare_change_plan, prepare_publication_check, project_lock,
    stage_building_journal, transaction_recovery_lock,
)
from specroad.model.canonical import canonical_json_bytes
from specroad.model.model_manifest import ProjectReadBinding
from specroad.model.paths import PathClass
from specroad.profiles import ProfileResource, compose_profiles
from specroad.storage.project import ProjectSource
from specroad.storage.resource_discovery import current_json_paths
from specroad.validation import ModelDocument
from support.folds import goal
from support.publication import ALLOW, TRANSACTION, options, prepared
from support.targets import ACTOR, SCOPE

AUTHORITY = RecoveryAuthority("audit-rec-05-u-synthetic-authority", "1", lambda r: True)
PREPARATIONS = (("building", "released"), ("building", "abrupt"),
                ("prepared", "released"), ("prepared", "abrupt"),
                ("building_prefix", "abrupt"))
CASES = [(state, ending, inputs, "unchanged")
         for state, ending in PREPARATIONS for inputs in ("journal_only", "saved_plan")]
CASES += [(state, "released", "saved_plan", alteration)
          for state in ("building", "prepared")
          for alteration in ("changed_base", "additional_artifact", "wrong_plan")]


def write_json(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")


def hashes(root, *, normative=False):
    return {p.relative_to(root).as_posix(): sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()
            and (not normative or ".specroad" not in p.relative_to(root).parts)}


def describe_error(error):
    return {"returned": False, "error_type": type(error).__name__,
            "reason": getattr(error, "reason", None),
            "exit_code": getattr(error, "exit_code", None),
            "mutation_possible": getattr(error, "mutation_possible", None)}


def owned_case(control):
    control = control.resolve()
    assert any(p.name.startswith("specroad-audit-rec-05-u-") for p in control.parents)
    assert control.name == "case.json" and control.is_file()
    return json.loads(control.read_text()), control.parent / "project"


def writer(control):
    case, root = owned_case(control)
    assert not root.exists(), "Fixture creation never overwrites an existing project"
    model, plan, preflight = prepared(root)
    if case["inputs"] == "saved_plan":
        original = plan
        if case["alteration"] == "wrong_plan":
            value = plan.data
            value.pop("change_plan_sha256")
            value["request_id"] = "different-request"
            original = prepare_change_plan(value)
        (control.parent / "caller-plan.json").write_bytes(original.source_bytes)
    # This oracle is read by the parent only, never by the recovery consumer.
    write_json(control.parent / "writer-oracle.json", {
        "pid": os.getpid(), "base_files": hashes(root, normative=True),
        "base_model_root_sha256": model.manifest(model.artifacts, SCOPE).sha256,
        "plan_sha256": plan.sha256, "plan_bytes_sha256": sha256(plan.source_bytes).hexdigest(),
        "target_model_root_sha256": preflight.request.data["target_root_sha256"]})
    with project_lock(root, **options(preflight)) as held:
        journal = begin_building_journal(preflight, held_lock=held,
            transaction_id=TRANSACTION, authority=ALLOW)
        if case["preparation"] == "building_prefix":
            native_write, native_sync = os.write, os.fsync
            def stop_after_prefix(fd, raw):
                target = Path(os.readlink("/proc/self/fd/" + str(fd)))
                if target.is_relative_to(root) and target.parent.name == "staging" and target.name == "0.bin":
                    assert len(raw) > 17
                    assert native_write(fd, raw[:17]) == 17
                    native_sync(fd)
                    os._exit(23)
                return native_write(fd, raw)
            with patch.object(os, "write", side_effect=stop_after_prefix):
                stage_building_journal(preflight, journal, held_lock=held, authority=ALLOW)
            raise AssertionError("Fixture interruption did not occur")
        if case["preparation"] == "prepared":
            stage_building_journal(preflight, journal, held_lock=held, authority=ALLOW)
        if case["ending"] == "abrupt":
            os._exit(23)


def reconstruct_fixture_preflight(root, plan_path, observation):
    """Counterexample using public constructors plus an EXTRA original plan.

    This is a test-only adapter for the small Goal/core-profile fixture. It is
    neither a product recovery entrypoint nor a general live-project loader.
    Its inventory is enumerated from live project files, not copied from the
    writer oracle or the journal's claimed inventory. Policy is host-registered.
    """
    source = ProjectSource(root, expected_project_id="sample")
    documents, resources, profiles = [], [], []
    names = current_json_paths(source)
    for name in names:
        kind = source.classify(name)
        raw = source.read_normative(name)
        if kind is PathClass.ARTIFACT:
            documents.append(ModelDocument(name, raw))
        elif kind is PathClass.PROFILE:
            resources.append(ModelDocument(name, raw))
            profiles.append(ProfileResource(raw))
        else:
            assert kind is PathClass.CONFIGURATION, "Fixture reader has no general-resource claim"
    assert len(profiles) == 1 and profiles[0].profile_id == "core"
    info = root.stat()
    model = TargetModel(source.configuration_bytes,
        ProjectReadBinding("sample", str(root), (info.st_dev, info.st_ino)),
        documents, profile=compose_profiles(profiles, core_key=profiles[0].key),
        resource_files=resources)
    observation.update(inventory=list(names),
        independent_model_root_sha256=model.manifest(model.artifacts, SCOPE).sha256)
    plan = ChangePlan(plan_path.read_bytes())
    observation["plan_sha256"] = plan.sha256
    return prepare_publication_check(plan, model, policy=TargetPolicy("ordinary-change", "1", ()))


def recover(control):
    case, root = owned_case(control)
    raw = (root / ".specroad/transactions" / TRANSACTION / "journal.json").read_bytes()
    value = json.loads(raw)
    cls = PreparedJournal if value["state"] == "prepared" else BuildingJournal
    journal = cls(raw)
    result = {"pid": os.getpid(), "input_journal_sha256": journal.sha256,
              "input_state": value["state"], "published_count": value["published_count"]}
    before = hashes(root)
    result["status_without_preflight"] = inspect_recovery(root).data["transactions"][0]
    result["status_read_only"] = hashes(root) == before
    preflight = None
    if case["inputs"] == "saved_plan":
        rebuilt = {}
        try:
            preflight = reconstruct_fixture_preflight(root, control.parent / "caller-plan.json", rebuilt)
            rebuilt.update(returned=True, preflight=preflight.data)
        except Exception as error:
            rebuilt.update(describe_error(error))
            result.update(reconstruction=rebuilt, phase="reconstruction",
                          all_file_bytes_unchanged=hashes(root) == before)
            return result
        result["reconstruction"] = rebuilt
        result["status_with_reconstructed_preflight"] = inspect_recovery(root, preflight=preflight).data["transactions"][0]
    else:
        result["reconstruction"] = {"attempted": False, "original_plan_supplied": False}
    result["preparation_read_only"] = hashes(root) == before
    lock_path = root / ".specroad/locks/project.json"
    result["owner_state_before_lock"] = inspect_project_lock(root).data["owner_state"]
    common = dict(project_id=value["project_id"], request_id=value["request_id"], command="recover discard")
    if lock_path.exists():
        lock = LockRecord(lock_path.read_bytes())
        context = transaction_recovery_lock(root, TRANSACTION, **common,
            expected_lock_sha256=lock.sha256, expected_journal_sha256=journal.sha256,
            authority=AUTHORITY, actor=ACTOR, reason="Explicit stopped fixture writer recovery", force=True)
        result["lock_mode"] = "audited_native_takeover"
    else:
        context = project_lock(root, kind="recovery", transaction_id=TRANSACTION, **common)
        result["lock_mode"] = "new_native_recovery_lock"
    result["phase"] = "lock"
    try:
        with context as held:
            result["phase"] = "discard"
            locked_before = hashes(root)
            try:
                value = discard_unpublished_transaction(preflight, TRANSACTION,
                    held_lock=held, authority=AUTHORITY, actor=ACTOR,
                    reason="Explicit restart fixture discard", expected_journal_sha256=journal.sha256)
                result["discard"] = {"returned": True, "result": value.data}
            except Exception as error:
                result["discard"] = describe_error(error)
            result["discard_file_bytes_unchanged"] = hashes(root) == locked_before
    except Exception as error:
        result["lock_error"] = describe_error(error)
    result["all_file_bytes_unchanged"] = hashes(root) == before
    try:
        with project_lock(root, kind="writer", command="change apply", project_id="sample",
                          request_id="next-request", transaction_id="next-transaction"):
            pass
        result["new_writer_allowed"] = True
    except Exception as error:
        result["new_writer_allowed"] = False
        result["new_writer_error"] = describe_error(error)
    return result


def child(control, mode):
    return subprocess.run([sys.executable, "-I", "-B", str(Path(__file__).resolve()),
        "--child", mode, "--control", str(control)], stdin=subprocess.DEVNULL,
        text=True, capture_output=True, check=False)


@pytest.mark.parametrize("preparation,ending,inputs,alteration", CASES)
def test_observe_restart(tmp_path, preparation, ending, inputs, alteration, worker_id):
    output = Path(os.environ["SPECROAD_AUDIT_REC_05_OUTPUT"])
    assert output.is_dir() and output.parent.name.startswith("specroad-audit-rec-05-u-")
    control = tmp_path / "case.json"
    case = dict(preparation=preparation, ending=ending, inputs=inputs, alteration=alteration)
    write_json(control, case)
    created = child(control, "writer")
    assert created.returncode == (23 if ending == "abrupt" else 0), created.stderr
    root = tmp_path / "project"
    oracle = json.loads((tmp_path / "writer-oracle.json").read_text())
    assert hashes(root, normative=True) == oracle["base_files"]
    journal_path = root / ".specroad/transactions" / TRANSACTION / "journal.json"
    journal = json.loads(journal_path.read_bytes())
    assert journal["state"] == ("prepared" if preparation == "prepared" else "building")
    assert journal["published_count"] == 0
    original_work = hashes(journal_path.parent)
    if preparation == "building_prefix":
        assert (journal_path.parent / "staging/0.bin").stat().st_size == 17
    if alteration in ("changed_base", "additional_artifact"):
        artifact = next(root.glob("spec/goals/*.json"))
        value = json.loads(artifact.read_bytes())
        if alteration == "changed_base":
            value["title"] = "Independent change after writer exit"
        else:
            value = goal(2)
            artifact = artifact.with_name(value["id"] + ".json")
            assert not artifact.exists()
        artifact.write_bytes(canonical_json_bytes(value))
    normative_before = hashes(root, normative=True)
    observed = child(control, "recover")
    assert observed.returncode == 0, observed.stderr
    outcome = json.loads(observed.stdout)
    assert outcome.pop("pid") != oracle.pop("pid")
    assert hashes(root, normative=True) == normative_before
    discard = outcome.get("discard", {})
    if discard.get("returned"):
        archive = root / discard["result"]["audit_path"]
        preserved = all((sha256((archive / "journal.before.json").read_bytes()).hexdigest()
                         if p == "journal.json" else sha256((archive / "work" / p).read_bytes()).hexdigest())
                        == digest for p, digest in original_work.items())
    else:
        preserved = hashes(journal_path.parent) == original_work
    row = {"case": "--".join(case.values()), **case, "worker": worker_id,
           "writer_exit_code": created.returncode, "separate_fresh_processes": True,
           "oracle": oracle, "outcome": outcome, "original_work_preserved": preserved,
           "normative_bytes_unchanged_by_recovery": hashes(root, normative=True) == normative_before,
           "original_basis_retained": hashes(root, normative=True) == oracle["base_files"]}
    assert preserved
    write_json(output / (row["case"] + ".json"), row)


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--child", choices=("writer", "recover"))
    parser.add_argument("--control", type=Path)
    args = parser.parse_args()
    if args.child:
        assert args.control is not None and args.output is None
        if args.child == "writer":
            writer(args.control)
        else:
            print(json.dumps(recover(args.control), sort_keys=True))
        return
    if args.output is None:
        parser.error("--output NEW_EXTERNAL_JSON is required")
    target = args.output.absolute()
    if target.is_relative_to(REPO) or target.exists():
        parser.error("Output must be a new external JSON path")
    with tempfile.TemporaryDirectory(prefix="specroad-audit-rec-05-u-") as directory:
        directory = Path(directory)
        output = directory / "observations"
        output.mkdir()
        environment = dict(os.environ, SPECROAD_AUDIT_REC_05_OUTPUT=str(output))
        run = subprocess.run([sys.executable, "-I", "-B", "-m", "pytest", "-n", "4",
            str(Path(__file__).resolve()), "--basetemp", str(directory / "fixtures")],
            cwd=REPO, env=environment, stdin=subprocess.DEVNULL, check=False)
        if run.returncode:
            raise SystemExit(run.returncode)
        rows = [json.loads(p.read_text()) for p in sorted(output.glob("*.json"))]
        assert len(rows) == len(CASES)
        write_json(target, {"probe": "AUDIT-REC-05.U", "python": sys.version.split()[0],
            "synthetic_authority": True, "execution": {"engine": "pytest-xdist", "workers": 4},
            "probe_sha256": sha256(Path(__file__).read_bytes()).hexdigest(), "observations": rows})


if __name__ == "__main__":
    main()
