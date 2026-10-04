"""Historical AUDIT-REC-04.U observations, not permanent defect expectations.

Run with the project's development Python and --output NEW_EXTERNAL_JSON.
The driver runs every case through pytest-xdist with four workers. Only fresh
temporary fixture projects are mutated; no real project is accepted as input.
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
    CommittingJournal, CommittedJournal, RecoveryAuthority, RolledBackJournal,
    RollingBackJournal, complete_published_transaction, project_lock,
    rollback_interrupted_transaction,
)
from support.publication import TRANSACTION, files
from support.receipts import published
from test_transaction_recovery_rollback import partial_commit, recovery_options

AUTHORITY = RecoveryAuthority("audit-rec-04-u-synthetic-authority", "1", lambda r: True)
SITES = (
    "rollback_journal_initial", "rollback_journal_after_restore",
    "rollback_journal_terminal", "rollback_copy", "rollback_audit",
    "rollback_receipt", "completion_transaction_receipt",
    "completion_request_receipt", "completion_marker", "completion_audit",
)
MODES = ("empty", "prefix", "full_sync_response_lost", "foreign_after_prefix",
         "foreign_same_prefix")


def hashes(values):
    return {name: sha256(raw).hexdigest() for name, raw in sorted(values.items())}


def snapshot(root):
    return hashes({p.relative_to(root).as_posix(): p.read_bytes()
                   for p in root.rglob("*") if p.is_file()
                   and p.relative_to(root).as_posix() != ".specroad/locks/project.json"})


def journal_at(root, path):
    raw = (root / path).read_bytes()
    classes = {"committing": CommittingJournal, "committed": CommittedJournal,
               "rolling_back": RollingBackJournal, "rolled_back": RolledBackJournal}
    return classes[json.loads(raw)["state"]](raw)


def invoke(root, path, operation):
    # Every retry reloads only the persisted journal and acquires a fresh lock.
    journal = journal_at(root, path)
    binding = {"input_journal_sha256": journal.sha256, "input_state": journal.data["state"]}
    try:
        with project_lock(root, **recovery_options(journal)) as held:
            value = operation(TRANSACTION, held_lock=held, authority=AUTHORITY,
                              expected_journal_sha256=journal.sha256)
        return {**binding, "returned": True, "result": value.data}
    except Exception as error:
        return {**binding, "returned": False, "error_type": type(error).__name__,
                "reason": getattr(error, "reason", None),
                "exit_code": getattr(error, "exit_code", None),
                "mutation_possible": getattr(error, "mutation_possible", None),
                "reported_normative_writes": getattr(error, "normative_writes_by_recovery", None)}


class Interruption:
    def __init__(self, root, site, mode):
        self.root, self.site, self.mode = root, site, mode
        self.write, self.fsync, self.open = os.write, os.fsync, os.open
        self.seen = 0
        self.fd = None
        self.path = None
        self.expected = None
        self.prefix_written = False
        self.fired = False

    def selected(self, relative):
        name = relative.name
        if self.site.startswith("rollback_journal_"):
            if name != "journal.rollback":
                return False
            self.seen += 1
            return self.seen == {"rollback_journal_initial": 1,
                                 "rollback_journal_after_restore": 3,
                                 "rollback_journal_terminal": 4}[self.site]
        return {
            "rollback_copy": name == "0.bin" and relative.parent.name == "rollback",
            "rollback_audit": name == "rollback.json",
            "rollback_receipt": name == "transaction.json" and relative.parent.parent.as_posix() == ".specroad/transactions/receipts",
            "completion_transaction_receipt": name == "transaction.json" and relative.parent.parent.as_posix() == ".specroad/transactions/receipts",
            "completion_request_receipt": relative.parent.as_posix() == ".specroad/requests",
            "completion_marker": name == "journal.complete",
            "completion_audit": name == "complete.json",
        }[self.site]

    def opening(self, name, flags, *args, **kwargs):
        fd = self.open(name, flags, *args, **kwargs)
        if flags & os.O_EXCL and flags & os.O_CREAT:
            path = Path(os.readlink("/proc/self/fd/" + str(fd)))
            if path.is_relative_to(self.root) and self.selected(path.relative_to(self.root)):
                self.fd, self.path = fd, path
        return fd

    def writing(self, fd, raw):
        if fd != self.fd or self.fired:
            return self.write(fd, raw)
        if self.expected is None:
            self.expected = bytes(raw)
            # All selected fixture records fit in one production write block.
            assert 17 < len(raw) < 65536
        if self.mode == "full_sync_response_lost":
            return self.write(fd, raw)
        if self.mode != "empty" and not self.prefix_written:
            count = self.write(fd, raw[:17])
            assert count == 17
            self.prefix_written = True
            return count
        self.fired = True
        raise OSError(5, "AUDIT-REC-04.U controlled write interruption")

    def syncing(self, fd):
        value = self.fsync(fd)
        if fd == self.fd and self.mode == "full_sync_response_lost" and not self.fired:
            self.fired = True
            raise OSError(5, "AUDIT-REC-04.U lost successful fsync response")
        return value


@pytest.mark.parametrize("site", SITES)
@pytest.mark.parametrize("mode", MODES)
def test_observe_helper_interruption(tmp_path, site, mode, worker_id):
    output = Path(os.environ["SPECROAD_AUDIT_REC_04_OUTPUT"])
    assert output.is_dir() and output.parent.name.startswith("specroad-audit-rec-04-u-")
    root = tmp_path / "project"
    if site.startswith("rollback_"):
        model, _, journal = partial_commit(root)
        operation = rollback_interrupted_transaction
        expected = dict(model.source_files)
    else:
        with published(root) as (model, _, _, _, journal):
            expected = files(root)
        operation = complete_published_transaction
    original_images = {p: digest for p, digest in snapshot(root).items()
                       if "/before/" in p or "/staging/" in p}
    initial_normative = hashes(files(root))
    first_fault = Interruption(root, site, mode)
    native_replace = os.replace
    replacements = []

    def replacing(src, dst, **kwargs):
        source = Path(os.readlink("/proc/self/fd/" + str(kwargs["src_dir_fd"]))) / src
        target = Path(os.readlink("/proc/self/fd/" + str(kwargs["dst_dir_fd"]))) / dst
        value = native_replace(src, dst, **kwargs)
        for path in (source, target):
            relative = path.relative_to(root).as_posix()
            if relative in model.source_files:
                replacements.append(relative)
        return value

    with patch.object(os, "replace", side_effect=replacing):
        with patch.object(os, "open", side_effect=first_fault.opening), \
             patch.object(os, "write", side_effect=first_fault.writing), \
             patch.object(os, "fsync", side_effect=first_fault.syncing):
            first = invoke(root, journal.path, operation)
        assert first_fault.fired and first_fault.path is not None
        actual = first_fault.path.read_bytes()
        wanted = (first_fault.expected if mode == "full_sync_response_lost" else
                  b"" if mode == "empty" else first_fault.expected[:17])
        assert actual == wanted
        first_writes = list(replacements)
        after_fault = hashes(files(root))
        # The foreign-byte counterexample deliberately tampers only with this
        # owned fixture helper after the native interrupted attempt has ended.
        if mode == "foreign_after_prefix":
            first_fault.path.write_bytes(b"foreign-conflict!")
        original_identity = first_fault.path.stat().st_ino
        if mode == "foreign_same_prefix":
            # Retain the real writer's fragment outside the model and place an
            # independent byte-identical file at the same operational path.
            first_fault.path.rename(tmp_path / "retained-original-helper")
            first_fault.path.write_bytes(actual)
            assert first_fault.path.stat().st_ino != original_identity
        before_retry = snapshot(root)
        candidate = first_fault.path.read_bytes()
        after_first_state = journal_at(root, journal.path).data["state"]
        retries = []
        for _ in range(2):
            replacements.clear()
            before = snapshot(root)
            retry = invoke(root, journal.path, operation)
            retries.append({"attempt": retry,
                "all_file_bytes_unchanged": snapshot(root) == before,
                "observed_normative_replacements": list(replacements),
                "normative_equals_expected_result": files(root) == expected,
                "journal_state": journal_at(root, journal.path).data["state"]})
    final = snapshot(root)
    row = {"case": site + "--" + mode, "site": site, "mode": mode, "worker": worker_id,
        "binding": {key: journal.data[key] for key in ("project_id", "request_id",
            "transaction_id", "base_model_root_sha256", "target_model_root_sha256")},
        "first_attempt": first, "state_after_interruption": after_first_state,
        "observed_normative_replacements_before_interruption": first_writes,
        "initial_normative_sha256": initial_normative,
        "after_interruption_normative_sha256": after_fault,
        "expected_result_sha256": hashes(expected), "final_normative_sha256": hashes(files(root)),
        "candidate": {"path": first_fault.path.relative_to(root).as_posix(),
            "size": len(candidate), "sha256": sha256(candidate).hexdigest(),
            "expected_size": len(first_fault.expected),
            "expected_sha256": sha256(first_fault.expected).hexdigest(),
            "equals_expected": candidate == first_fault.expected,
            "is_strict_prefix": len(candidate) < len(first_fault.expected)
                                and first_fault.expected.startswith(candidate),
            "origin": "independent_replacement" if mode == "foreign_same_prefix" else
                      "externally_changed" if mode == "foreign_after_prefix" else "native_write",
            "bytes_retained_at_same_path": first_fault.path.is_file()
                                and first_fault.path.read_bytes() == candidate},
        "retries": retries, "all_retry_file_bytes_unchanged": final == before_retry,
        "original_images_preserved": all(final.get(p) == digest for p, digest in original_images.items())}
    with (output / (row["case"] + ".json")).open("x", encoding="utf-8") as stream:
        json.dump(row, stream, ensure_ascii=False, indent=2, sort_keys=True)


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    target = args.output.absolute()
    if target.is_relative_to(REPO) or target.exists():
        parser.error("Output must be a new external JSON path")
    with tempfile.TemporaryDirectory(prefix="specroad-audit-rec-04-u-") as work:
        work = Path(work)
        observations = work / "observations"
        observations.mkdir()
        environment = dict(os.environ, SPECROAD_AUDIT_REC_04_OUTPUT=str(observations))
        command = [sys.executable, "-I", "-B", "-m", "pytest", "-n", "4",
                   str(Path(__file__).resolve()), "--basetemp", str(work / "fixtures")]
        result = subprocess.run(command, cwd=REPO, env=environment,
                                stdin=subprocess.DEVNULL, check=False)
        if result.returncode:
            raise SystemExit(result.returncode)
        rows = [json.loads(p.read_text()) for p in sorted(observations.glob("*.json"))]
        assert len(rows) == len(SITES) * len(MODES)
        with target.open("x", encoding="utf-8") as stream:
            json.dump({"probe": "AUDIT-REC-04.U", "python": sys.version.split()[0],
                "synthetic_authority": True, "execution": {"engine": "pytest-xdist", "workers": 4},
                "observations": rows}, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")


if __name__ == "__main__":
    main()
