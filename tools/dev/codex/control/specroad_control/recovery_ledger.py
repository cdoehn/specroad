"""Atomic, additive proof records for explicit blocked-job recovery."""
import json
import sqlite3
import time
from .config import digest
from .contracts import facts
from .errors import ControlError
from .local import decode_object


class RecoveryHistory:
    def adopt_blocked(self, patch_sha, result, completion_sha):
        """Persist the exact proof and claim transition in the same transaction."""
        digest(patch_sha)
        digest(completion_sha)
        facts(result, "result")
        try:
            with self.transaction():
                row = self.current()
                if row["stage"] != "uncertain" or row["error"] != "dev_blocked" or row["patch_sha"] is not None:
                    raise ControlError("recovery_evidence_changed", "The blocked claim changed before adoption.")
                if result["patch_sha256"] != patch_sha or result["expected"] != row["source"]["binding"] or result["run_id"] in self.known_runs():
                    raise ControlError("recovery_evidence_changed", "The Apply result no longer belongs to the unresolved claim.")
                self.db.execute('''CREATE TABLE IF NOT EXISTS blocked_recoveries (
                    source_sha TEXT PRIMARY KEY, patch_sha TEXT NOT NULL, result TEXT NOT NULL,
                    completion_sha TEXT NOT NULL)''')
                if self.db.execute("SELECT 1 FROM blocked_recoveries WHERE source_sha=?", (row["sha"],)).fetchone():
                    raise ControlError("recovery_evidence_changed", "Existing recovery evidence cannot be replaced.")
                self.db.execute("INSERT INTO blocked_recoveries VALUES(?,?,?,?)",
                                (row["sha"], patch_sha, json.dumps(result), completion_sha))
                self.db.execute("UPDATE jobs SET stage='waiting_result',patch_sha=?,error=NULL,updated=? WHERE run_id=?",
                                (patch_sha, time.time(), row["run_id"]))
        except sqlite3.Error:
            raise ControlError("recovery_persist_failed", "Recovery proof and claim were not committed; no replay is permitted.") from None

    def blocked_recovery(self):
        """Read the pinned follow-up, including after a controller restart."""
        try:
            if not self.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='blocked_recoveries'").fetchone():
                return None
            current = self.current()
            row = self.db.execute("SELECT * FROM blocked_recoveries WHERE source_sha=?", (current["sha"],)).fetchone()
            if row is None:
                return None
            digest(row["patch_sha"])
            digest(row["completion_sha"])
            result = facts(decode_object(row["result"]), "result")
            if (current["stage"] != "waiting_result" or row["patch_sha"] != current["patch_sha"]
                    or result["patch_sha256"] != row["patch_sha"] or result["expected"] != current["source"]["binding"]
                    or result["success"] is not True or result["dirty"] is not False
                    or result["operation"] != "apply" or result["dry_run"] is not False
                    or result["primary_kind"] != "success" or result["entrypoint_started"] is not True
                    or result["completed_commit"] != result["binding"]["base_commit"]):
                raise ValueError
            return result
        except (sqlite3.Error, ValueError, KeyError, TypeError, UnicodeError, IndexError):
            raise ControlError("invalid_recovery_history", "Stored recovery evidence is invalid and is preserved.") from None
