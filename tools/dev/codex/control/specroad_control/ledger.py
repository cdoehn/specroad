"""Transactional claims; corruption and ambiguous work never reset the history."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import sqlite3
import stat
import time
from .errors import ControlError
from .retry_ledger import RetryHistory
from .recovery_ledger import RecoveryHistory
from .wait_ledger import WaitHistory
from .config import digest
from .contracts import facts
from .local import decode_object, outside, private_dir, write_private
from .decision_history import DecisionHistory
from .handover_evidence import validate_chain

STAGES = {"ready", "running", "waiting_result", "done", "uncertain", "no_work", "retry_wait", "overload_wait"}
TRANSITIONS = {"ready": {"ready", "running", "waiting_result", "uncertain"},
               "running": {"waiting_result", "uncertain", "no_work"},
               "uncertain": {"waiting_result", "uncertain", "no_work"},
               "retry_wait": {"running", "uncertain", "waiting_result"},
               "overload_wait": {"uncertain", "waiting_result"},
               "waiting_result": {"waiting_result"}, "done": set(), "no_work": set()}


class Ledger(RetryHistory, RecoveryHistory, WaitHistory, DecisionHistory):
    def __init__(self, path: Path, scope: str, *, initial: dict | None = None, allow_empty: bool = False):
        # An explicit initial source creates the runtime state. Ordinary opens
        # never create/reseed history merely because a file disappeared.
        if initial is not None:
            try:
                facts(initial, "result")
                if initial["dry_run"]:
                    raise ValueError
            except (KeyError, ValueError, TypeError):
                raise ControlError("invalid_seed", "Bootstrap needs a validated non-dry-run Result.") from None
        outside(path)
        private_dir(path.parent)
        if not os.path.lexists(path):
            if initial is None:
                raise ControlError("state_not_initialized", "Initialize runtime state once with configure --result; no automatic seed guess.")
            # Build a complete initial database away from the published path.
            # The existing private-file writer fsyncs and publishes exclusively:
            # no empty/half-built ledger can become the authoritative state.
            memory = sqlite3.connect(":memory:")
            try:
                memory.execute("CREATE TABLE meta (id INTEGER PRIMARY KEY CHECK(id=1), version INTEGER, scope TEXT, seed TEXT, current TEXT)")
                memory.execute("CREATE TABLE jobs (run_id TEXT PRIMARY KEY, sha TEXT UNIQUE NOT NULL, source TEXT NOT NULL, stage TEXT NOT NULL, patch_sha TEXT, error TEXT, updated REAL NOT NULL)")
                memory.execute("INSERT INTO meta VALUES(1,1,?,?,?)", (scope, initial["sha256"], initial["run_id"]))
                memory.execute("INSERT INTO jobs VALUES(?,?,?,'ready',NULL,NULL,?)",
                               (initial["run_id"], initial["sha256"], json.dumps(initial), time.time()))
                memory.commit()
                data = memory.serialize()
            except (sqlite3.Error, AttributeError):
                raise ControlError("state_initialization_failed", "Initial state could not be built; no history was replaced.") from None
            finally:
                memory.close()
            try:
                write_private(path, data, exclusive=True)
            except FileExistsError:
                pass  # Never replace a competing published history; validate it below.
        s = path.lstat()
        if not stat.S_ISREG(s.st_mode) or s.st_uid != os.getuid() or s.st_mode & 0o077 or s.st_nlink != 1:
            raise ControlError("unsafe_ledger", "Ledger must be a private regular file.")
        try:
            self.db = sqlite3.connect(path, timeout=2, isolation_level=None)
            self.db.row_factory = sqlite3.Row
            self.db.execute("PRAGMA synchronous=FULL")
            self.db.execute("PRAGMA trusted_schema=OFF")
            row = self.db.execute("SELECT * FROM meta WHERE id=1").fetchone()
            if row is None or row["version"] != 1 or self.db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise ValueError
            self.seed_sha = digest(row["seed"])
            if row["scope"] != scope:
                raise ControlError("ledger_scope_mismatch", "Existing history belongs to different settings; it is not reset.")
            validate_chain(self.db, scope)
            if initial is not None and self.seed_sha != initial["sha256"]:
                raise ControlError("bootstrap_conflict", "Runtime history already has a different initial Result; it is never reset.")
            current = self.current()
            if current is None and initial is not None:
                # An old format-1 ledger may have a seed but no first job, e.g.
                # before the old worker's first enqueue. It must match exactly;
                # this does not repair/reset any running or uncertain job.
                self.enqueue(initial)
                current = self.current()
            if current is None:
                if not allow_empty:
                    raise ControlError("state_not_initialized", "Existing empty history requires explicit reviewed initialization.")
            else:
                origin = self.db.execute("SELECT run_id, source FROM jobs WHERE sha=?", (self.seed_sha,)).fetchone()
                if origin is None or (initial is not None and origin["run_id"] != initial["run_id"]):
                    raise ValueError
                original = facts(decode_object(origin["source"]), "result")
                if original["sha256"] != self.seed_sha or original["run_id"] != origin["run_id"]:
                    raise ValueError
            from .apply_reconcile_history import validate_history
            validate_history(self)
            from .clarification_authorization_history import validate_history as validate_authorizations
            validate_authorizations(self)
        except (sqlite3.Error, ValueError, KeyError, TypeError, UnicodeError, ControlError) as exc:
            if hasattr(self, "db"):
                self.db.close()
            if isinstance(exc, ControlError):
                raise
            raise ControlError("invalid_ledger", "Ledger is unreadable and is preserved for review.") from None

    @contextmanager
    def transaction(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.db.execute("COMMIT")
        except BaseException:
            if self.db.in_transaction:
                self.db.execute("ROLLBACK")
            raise

    def current(self):
        try:
            meta = self.db.execute("SELECT current FROM meta WHERE id=1").fetchone()
            if meta is None:
                raise ValueError
            if meta["current"] is None:
                if self.db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]:
                    raise ValueError
                return None
            row = self.db.execute("SELECT * FROM jobs WHERE run_id=?", (meta["current"],)).fetchone()
            if row is None:
                raise ValueError
            result = dict(row)
            result["source"] = facts(decode_object(result["source"]), "result")
            if result["stage"] not in STAGES or result["stage"] == "done":
                raise ValueError
            if result["source"]["run_id"] != result["run_id"] or result["source"]["sha256"] != result["sha"]:
                raise ValueError
            if result["stage"] == "waiting_result" and (not isinstance(result["patch_sha"], str) or len(result["patch_sha"]) != 64):
                raise ValueError
            return result
        except (sqlite3.Error, ValueError, KeyError, TypeError, UnicodeError):
            raise ControlError("invalid_ledger", "Stored job facts are invalid; no replay.") from None

    def enqueue(self, source: dict, *, decision_evidence=None):
        with self.transaction():
            self._enqueue(source, decision_evidence=decision_evidence)

    def _enqueue(self, source: dict, *, decision_evidence=None):
        existing = self.db.execute("SELECT sha FROM jobs WHERE run_id=? OR sha=?", (source["run_id"], source["sha256"])).fetchone()
        if existing is not None:
            raise ControlError("result_already_claimed", "No Result is scheduled twice.")
        old = self.current()
        inherited = None
        if old is not None:
            if old["stage"] != "waiting_result":
                raise ControlError("invalid_transition", "Only a bound follow-up can advance the ledger.")
            inherited = self.inherit_contract(source, old, decision_evidence=decision_evidence)
            self.db.execute("UPDATE jobs SET stage='done', updated=? WHERE run_id=?", (time.time(), old["run_id"]))
        elif source["sha256"] != self.seed_sha:
            raise ControlError("bootstrap_conflict", "Empty history is already bound to a different initial Result.")
        self.db.execute("INSERT INTO jobs VALUES(?,?,?,'ready',NULL,NULL,?)",
                        (source["run_id"], source["sha256"], json.dumps(source), time.time()))
        self.db.execute("UPDATE meta SET current=? WHERE id=1", (source["run_id"],))
        if inherited is not None:
            self._insert_contract(source['sha256'], inherited)

    def published_hashes(self):
        return {row[0] for row in self.db.execute("SELECT patch_sha FROM jobs WHERE patch_sha IS NOT NULL")}

    def known_runs(self):
        return {row[0] for row in self.db.execute("SELECT run_id FROM jobs")}

    def change(self, stage: str, *, patch_sha=None, error=None, output_kind=None):
        with self.transaction():
            row = self.current()
            selected_contract = self.request_contract()
            if row is None or stage not in TRANSITIONS[row["stage"]]:
                raise ControlError("invalid_transition", "An invalid transition cannot requeue previous work.")
            selected = patch_sha or row["patch_sha"]
            if stage == "waiting_result" and (not isinstance(selected, str) or len(selected) != 64 or any(c not in "0123456789abcdef" for c in selected)):
                raise ControlError("invalid_transition", "A pending Apply needs an exact patch SHA-256.")
            if selected_contract and row['patch_sha'] and patch_sha and row['patch_sha'] != patch_sha:
                raise ControlError('request_contract_changed', 'A classified handoff cannot change its package.')
            self.db.execute("UPDATE jobs SET stage=?,patch_sha=COALESCE(?,patch_sha),error=?,updated=? WHERE run_id=?",
                            (stage, patch_sha, error, time.time(), row["run_id"]))
            if stage == 'waiting_result' and selected_contract is not None:
                self.record_output_contract(selected_contract, row, output_kind)

    def close(self):
        self.db.close()
