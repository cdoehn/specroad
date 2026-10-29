"""Native complete-run timing observation; no Apply selection or persistence."""
from datetime import datetime, timezone
import json
import math
import re


PHASES = ("setup", "call", "teardown")


def encoded(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False,
                       separators=(",", ":")) + "\n").encode()


def _hash(value):
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _identity(value):
    return type(value) is str and bool(value) and not any(c in value for c in "\r\n\x00")


def _timestamp(value):
    if not _identity(value):
        return False
    try:
        return datetime.fromisoformat(value).utcoffset() is not None
    except (TypeError, ValueError, OverflowError):
        return False


def validate_imports(imports, source, identities):
    if type(imports) is not list or not imports:
        raise ValueError("Missing historical measurement provenance")
    seen = set()
    for item in imports:
        fields = {"from_source_sha256", "to_source_sha256", "source_journal_sha256",
                  "input_inventory_sha256", "imported_test_ids", "changed_files"}
        if (type(item) is not dict or set(item) != fields
                or any(not _hash(item[k]) for k in fields if k.endswith("sha256"))
                or item["to_source_sha256"] != source or item["from_source_sha256"] == source
                or type(item["imported_test_ids"]) is not list
                or any(not _identity(i) for i in item["imported_test_ids"])
                or item["imported_test_ids"] != sorted(set(item["imported_test_ids"]))
                or not item["imported_test_ids"] or not set(item["imported_test_ids"]) <= set(identities)
                or seen.intersection(item["imported_test_ids"])
                or type(item["changed_files"]) is not list or not item["changed_files"]):
            raise ValueError("Invalid historical measurement provenance")
        seen.update(item["imported_test_ids"])
        paths = set()
        for change in item["changed_files"]:
            if (type(change) is not dict or set(change) != {"path", "before", "after"}
                    or not _identity(change["path"]) or change["path"].startswith("/")
                    or ".." in change["path"].split("/") or change["path"] in paths
                    or change["before"] is not None and not _hash(change["before"])
                    or not _hash(change["after"])):
                raise ValueError("Invalid instrumentation change proof")
            paths.add(change["path"])
    return imports


def validate_measurement(value):
    if type(value) is dict and value.get("format_version") == 3:
        ordinary = dict(value)
        imports = ordinary.pop("measurement_imports", None)
        if ordinary.get("kind") != "specroad-resumable-test-runtimes-v3":
            raise ValueError("Invalid historical coverage kind")
        ordinary.update(format_version=2, kind="specroad-resumable-test-runtimes-v2")
        validate_measurement(ordinary)
        validate_imports(imports, value["source_sha256"], [r["test_id"] for r in value["tests"]])
        return value
    if type(value) is dict and value.get("format_version") == 2:
        fields = {"format_version", "kind", "source_sha256", "measured_at", "workers",
                  "coverage_complete", "full_suite_passed", "attempts", "tests"}
        if (set(value) != fields or type(value["format_version"]) is not int
                or value["kind"] != "specroad-resumable-test-runtimes-v2"
                or value["coverage_complete"] is not True or value["full_suite_passed"] is not None
                or type(value["attempts"]) is not int or value["attempts"] < 1):
            raise ValueError("Incomplete resumable timing coverage")
        # Reuse identity/duration validation without claiming a real full-suite run.
        shape = {k: value[k] for k in ("source_sha256", "measured_at", "workers", "tests")}
        shape.update(format_version=1, kind="specroad-full-test-runtimes-v1", full_suite_passed=True)
        validate_measurement(shape)
        return value
    fields = {"format_version", "kind", "source_sha256", "measured_at", "workers",
              "full_suite_passed", "tests"}
    if (type(value) is not dict or set(value) != fields
            or type(value["format_version"]) is not int or value["format_version"] != 1
            or value["kind"] != "specroad-full-test-runtimes-v1"
            or not _hash(value["source_sha256"]) or not _timestamp(value["measured_at"])
            or type(value["workers"]) is not int or value["workers"] < 2
            or value["full_suite_passed"] is not True
            or type(value["tests"]) is not list or not value["tests"]):
        raise ValueError("A complete passing parallel measurement is required")
    identities, nodes = set(), set()
    for row in value["tests"]:
        if (type(row) is not dict or set(row) != {"test_id", "nodeid", "phase_ns"}
                or not _identity(row["test_id"]) or not _identity(row["nodeid"])
                or row["test_id"] in identities or row["nodeid"] in nodes
                or type(row["phase_ns"]) is not dict or set(row["phase_ns"]) != set(PHASES)
                or any(type(n) is not int or n < 0 for n in row["phase_ns"].values())):
            raise ValueError("Incomplete or ambiguous per-test timings")
        identities.add(row["test_id"]); nodes.add(row["nodeid"])
    return value


class RuntimeMeasurements:
    """Only the pytest controller accumulates completed native phase reports."""

    def __init__(self):
        self.phases = {}
        self.invalid = False

    def observe(self, nodeid, phase, duration, *, subtest=False):
        if subtest:
            return
        if (phase not in PHASES or type(duration) not in (int, float)
                or not math.isfinite(duration) or duration < 0
                or not math.isfinite(duration * 1_000_000_000)):
            self.invalid = True
            return
        phases = self.phases.setdefault(nodeid, {})
        if phase in phases:
            self.invalid = True
        phases[phase] = round(duration * 1_000_000_000)

    def finish(self, observation, source_sha256):
        aliases = observation["nodeid_to_test_id"]
        workers = observation["workers"]
        if (self.invalid or observation["suite_passed"] is not True
                or observation["pytest_exit_code"] != 0 or observation["errors"]
                or len(workers) < 2 or any(not w.startswith("gw") for w in workers)
                or set(self.phases) != set(aliases)
                or set(observation["nodeids"]) != set(aliases)
                or observation["tests_run"] != len(aliases)
                or any(result != "passed" for result in observation["test_outcomes"].values())):
            raise ValueError("Incomplete run cannot become a timing baseline")
        value = {"format_version": 1, "kind": "specroad-full-test-runtimes-v1",
                 "source_sha256": source_sha256,
                 "measured_at": datetime.now(timezone.utc).isoformat(),
                 "workers": len(workers), "full_suite_passed": True,
                 "tests": [{"nodeid": node, "test_id": identity,
                            "phase_ns": dict(self.phases[node])}
                           for node, identity in sorted(aliases.items())]}
        return validate_measurement(value)
