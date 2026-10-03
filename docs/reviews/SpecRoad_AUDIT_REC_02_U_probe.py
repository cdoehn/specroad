"""Historical AUDIT-REC-02.U probe; all writes stay in owned temporary projects.

Use a repository path as the only argument. This observes behavior; it does not
turn the observed defects into regression expectations or claim release gates.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

REPO = Path(sys.argv[1]).resolve()
sys.dont_write_bytecode = True
sys.path[:0] = [str(REPO / "src"), str(REPO / "tests")]

from specroad.changes import (
    CommittingJournal, CommittedJournal, CommitPublicationError,
    RecoveryAuthority, cleanup_completed_transaction,
    complete_published_transaction, inspect_project_lock, project_lock,
    recover_project_lock, rollback_interrupted_transaction,
)
from specroad.storage.read_only import validate_project_read_only
from specroad.profiles import ProfileResource
from specroad.model.canonical import canonical_json_bytes
from support.profiles import profile_data
from support.publication import ALLOW, TRANSACTION, files, options, prepared
from support.receipts import published, finish
from support.committing import staged, publish
from support.recovery import pending, discard, recovery_options as discard_options
from support.targets import ACTOR
from support.folds import goal, edit

RECOVER = RecoveryAuthority("audit-rec-02-u-synthetic-authority", "1", lambda r: True)


def hashes(root, *, normative=False):
    data = files(root) if normative else {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in root.rglob("*") if p.is_file()
    }
    return {name: hashlib.sha256(raw).hexdigest() for name, raw in sorted(data.items())}


def observe(call):
    try:
        value = call()
        return {"returned": True, "result": getattr(value, "data", value)}
    except Exception as error:
        return {"returned": False, "error_type": type(error).__name__,
                "reason": getattr(error, "reason", str(error)),
                "exit_code": getattr(error, "exit_code", None)}


def recovery_options(journal):
    d = journal.data
    return dict(kind="recovery", command="recover run", project_id=d["project_id"],
                request_id=d["request_id"], transaction_id=d["transaction_id"])


def acquire(root, opts):
    with project_lock(root, **opts):
        return {"acquired": True}


def followup(root):
    profile = ProfileResource(canonical_json_bytes(profile_data(profile_id="core")))
    read = validate_project_read_only(root, profile_resources=[profile], core_key=profile.key).data
    writer = observe(lambda: acquire(root, dict(kind="writer", command="change apply",
        project_id="sample", request_id="following-request", transaction_id="following-txn")))
    return {"reader": {k: read[k] for k in
        ("exit_code", "model_loaded", "normal_operation_started", "status")}, "writer": writer}


def evidence(root):
    return {"transaction_receipts": sorted(
        p.relative_to(root).as_posix() for p in (root / ".specroad/transactions/receipts").rglob("*") if p.is_file()),
        "recovery_audits": sorted(
        p.relative_to(root).as_posix() for p in (root / ".specroad/recovery").rglob("*") if p.is_file())}


def child(root, mode, sidecar):
    # Internal fixture process: never write to an existing or real project.
    if (root.exists() or not root.parent.name.startswith("specroad-audit-rec-02-u-")
            or sidecar.parent != root.parent
            or mode not in {"target", "committed", "partial", "abrupt", "orphan_no_journal"}):
        raise RuntimeError("Child requires a fresh owned audit fixture")
    if mode == "orphan_no_journal":
        _, _, preflight = prepared(root)
        with project_lock(root, **options(preflight)):
            os._exit(23)
    if mode == "partial":
        a, b = goal(1), goal(2)
        with staged(root, operations=[edit(a, "A"), edit(b, "B")], artifacts=[a, b]) as (model, _, c, held, j):
            sidecar.write_text(json.dumps({p: hashlib.sha256(b).hexdigest()
                                          for p, b in model.source_files.items()}))
            original = os.replace
            targets = []
            def interrupt(src, dst, **kw):
                if dst != "journal.json" and targets:
                    raise OSError(5, "controlled stop before second target")
                result = original(src, dst, **kw)
                if dst != "journal.json":
                    targets.append(dst)
                return result
            with patch.object(os, "replace", side_effect=interrupt):
                try:
                    publish(c, j, held)
                except CommitPublicationError:
                    pass
                else:
                    raise RuntimeError("Partial publication fixture was not interrupted")
    else:
        with published(root) as (_, _, c, held, j):
            if mode == "abrupt":
                os._exit(23)
            if mode == "committed":
                finish(c, held, j)


def spawn(root, mode):
    sidecar = root.parent / (root.name + "-basis.json")
    run = subprocess.run([sys.executable, "-I", "-B", str(Path(__file__).resolve()),
        str(REPO), "--child", str(root), mode, str(sidecar)],
        stdin=subprocess.DEVNULL, capture_output=True, text=True, check=False)
    expected = 23 if mode in ("abrupt", "orphan_no_journal") else 0
    if run.returncode != expected:
        raise RuntimeError(f"Child fixture failed: {run.returncode}: {run.stderr}")
    return run.returncode, sidecar


def run_all(work):
    out = {}
    root = work / "ordinary"
    with published(root) as (_, _, c, held, j):
        finish(c, held, j)
        result = cleanup_completed_transaction(c, TRANSACTION, held_lock=held, authority=ALLOW)
    out["ordinary_cleanup_control"] = {"cleanup_completed": result.data["cleanup_completed"],
        "followup": followup(root), **evidence(root)}

    root = work / "target"
    code, _ = spawn(root, "target")
    j = CommittingJournal((root / ".specroad/transactions" / TRANSACTION / "journal.json").read_bytes())
    before = hashes(root, normative=True)
    with project_lock(root, **recovery_options(j)) as held:
        result = complete_published_transaction(TRANSACTION, held_lock=held,
            authority=RECOVER, expected_journal_sha256=j.sha256)
    out["target_after_writer_exit"] = {"child_returncode": code,
        "completion": result.data, "normative_bytes_unchanged": hashes(root, normative=True) == before,
        "active_journal_present": (root / j.path).is_file(), "followup": followup(root), **evidence(root)}

    root = work / "cleanup_access"
    with published(root) as (_, _, c, _, j):
        pass
    with project_lock(root, **recovery_options(j)) as held:
        complete_published_transaction(TRANSACTION, held_lock=held,
            authority=RECOVER, expected_journal_sha256=j.sha256)
        before = hashes(root)
        attempt = observe(lambda: cleanup_completed_transaction(c, TRANSACTION,
            held_lock=held, authority=ALLOW))
        unchanged = before == hashes(root)
    out["cleanup_with_recovery_lock_and_retained_preflight"] = {
        "attempt": attempt, "all_file_bytes_unchanged": unchanged}

    root = work / "rollback"
    code, sidecar = spawn(root, "partial")
    j = CommittingJournal((root / ".specroad/transactions" / TRANSACTION / "journal.json").read_bytes())
    with project_lock(root, **recovery_options(j)) as held:
        result = rollback_interrupted_transaction(TRANSACTION, held_lock=held,
            authority=RECOVER, expected_journal_sha256=j.sha256)
        current_hash = hashlib.sha256((root / j.path).read_bytes()).hexdigest()
        before = hashes(root)
        repeat = rollback_interrupted_transaction(TRANSACTION, held_lock=held,
            authority=RECOVER, expected_journal_sha256=current_hash)
        unchanged = before == hashes(root)
    out["rollback_after_writer_exit"] = {"child_returncode": code,
        "completion": result.data, "basis_bytes_restored": hashes(root, normative=True) == json.loads(sidecar.read_text()),
        "retry_normative_writes": repeat.data["normative_writes"], "retry_all_file_bytes_unchanged": unchanged,
        "active_journal_present": (root / j.path).is_file(), "followup": followup(root), **evidence(root)}

    root = work / "discard"
    _, _, c, j = pending(root, state="prepared")
    before = hashes(root, normative=True)
    with project_lock(root, **discard_options(c)) as held:
        result = discard(c, j, held, authority=RECOVER)
    out["discard_with_retained_preflight"] = {"completion": result.data,
        "normative_bytes_unchanged": hashes(root, normative=True) == before,
        "active_journal_present": (root / j.path).is_file(), "followup": followup(root), **evidence(root)}

    root = work / "committed"
    code, _ = spawn(root, "committed")
    j = CommittedJournal((root / ".specroad/transactions" / TRANSACTION / "journal.json").read_bytes())
    out["ordinary_commit_after_writer_exit"] = {"child_returncode": code,
        "state": j.data["state"], "followup": followup(root), **evidence(root)}

    for mode in ("abrupt", "orphan_no_journal"):
        root = work / mode
        code, _ = spawn(root, mode)
        status = inspect_project_lock(root, expected_project_id="sample").data
        before = hashes(root)
        recovery_lock = observe(lambda: acquire(root, dict(kind="recovery", command="recover run",
            project_id="sample", request_id="request-1", transaction_id=TRANSACTION)))
        recovery = observe(lambda: recover_project_lock(root, project_id="sample",
            expected_lock_sha256=status["record_sha256"], actor=ACTOR,
            reason="Synthetic AUDIT-REC-02.U process-exit observation", force=True))
        if recovery["returned"]:
            recovery["result"] = {k: recovery["result"][k] for k in
                ("record_removed", "observed_owner_state", "journal_recovery_performed", "new_lock_acquired")}
        out[mode] = {"child_returncode": code, "owner_state": status["owner_state"],
            "journal_paths": status["journal_paths"], "recovery_lock": recovery_lock,
            "lock_recovery": recovery, "all_file_bytes_unchanged": hashes(root) == before,
            "followup": followup(root)}
    return out


if "--child" in sys.argv:
    child(Path(sys.argv[3]), sys.argv[4], Path(sys.argv[5]))
else:
    with tempfile.TemporaryDirectory(prefix="specroad-audit-rec-02-u-") as directory:
        output = run_all(Path(directory))
    print(json.dumps({"probe": "AUDIT-REC-02.U", "python": sys.version.split()[0],
        "synthetic_authority": True, "observations": output}, ensure_ascii=False, indent=2, sort_keys=True))
