"""One measured full run and a frozen, count-based Apply exclusion list."""
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import re
import tempfile

from .ci_reference import _load_report


BASELINE = "verification/test_runtime_baseline.json"
PHASES = ("setup", "call", "teardown")


def encoded(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False,
                       separators=(",", ":")) + "\n").encode()


def _hash(value):
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _identity(value):
    return type(value) is str and bool(value) and not any(c in value for c in "\r\n\x00")


def validate_measurement(value):
    fields = {"format_version", "kind", "source_sha256", "measured_at", "workers",
              "full_suite_passed", "tests"}
    if (type(value) is not dict or set(value) != fields
            or type(value["format_version"]) is not int or value["format_version"] != 1
            or value["kind"] != "specroad-full-test-runtimes-v1"
            or not _hash(value["source_sha256"]) or not _identity(value["measured_at"])
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
                or not math.isfinite(duration) or duration < 0):
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


def make_baseline(measurement):
    value = validate_measurement(measurement)
    rows = sorted(({"test_id": row["test_id"], "nodeid": row["nodeid"],
                    "duration_ns": sum(row["phase_ns"].values())} for row in value["tests"]),
                  key=lambda row: row["test_id"])
    excluded = sorted(row["test_id"] for row in
        sorted(rows, key=lambda row: (-row["duration_ns"], row["test_id"]))[:len(rows) // 5])
    return {"format_version": 1, "kind": "specroad-frozen-runtime-filter-v1",
            "measured_source_sha256": value["source_sha256"],
            "measurement_sha256": sha256(encoded(value)).hexdigest(),
            "measured_at": value["measured_at"], "workers": value["workers"],
            "exclude_numerator": 1, "exclude_denominator": 5,
            "tests": rows, "excluded_test_ids": excluded}


def validate_baseline(value):
    fields = {"format_version", "kind", "measured_source_sha256", "measurement_sha256",
              "measured_at", "workers", "exclude_numerator", "exclude_denominator",
              "tests", "excluded_test_ids"}
    if (type(value) is not dict or set(value) != fields
            or type(value["format_version"]) is not int or value["format_version"] != 1
            or value["kind"] != "specroad-frozen-runtime-filter-v1"
            or not _hash(value["measured_source_sha256"]) or not _hash(value["measurement_sha256"])
            or not _identity(value["measured_at"])
            or type(value["workers"]) is not int or value["workers"] < 2
            or type(value["exclude_numerator"]) is not int or value["exclude_numerator"] != 1
            or type(value["exclude_denominator"]) is not int or value["exclude_denominator"] != 5
            or type(value["tests"]) is not list or not value["tests"]
            or type(value["excluded_test_ids"]) is not list):
        raise ValueError("Invalid frozen runtime baseline")
    identities, nodes = set(), set()
    for row in value["tests"]:
        if (type(row) is not dict or set(row) != {"test_id", "nodeid", "duration_ns"}
                or not _identity(row["test_id"]) or not _identity(row["nodeid"])
                or row["test_id"] in identities or row["nodeid"] in nodes
                or type(row["duration_ns"]) is not int or row["duration_ns"] < 0):
            raise ValueError("Invalid frozen test duration")
        identities.add(row["test_id"]); nodes.add(row["nodeid"])
    expected = sorted(row["test_id"] for row in sorted(value["tests"],
        key=lambda row: (-row["duration_ns"], row["test_id"]))[:len(value["tests"]) // 5])
    if value["excluded_test_ids"] != expected:
        raise ValueError("Exclusions differ from the measured slowest fifth")
    return value


def load_baseline(root):
    path = Path(root) / BASELINE
    if not os.path.lexists(path):
        return None
    raw = path.read_bytes()
    value = validate_baseline(_load_report(path))
    if path.read_bytes() != raw:
        raise ValueError("Timing baseline changed while reading")
    return sha256(raw).hexdigest(), value


def filter_partition(selected, baseline):
    if baseline is None:
        return dict(selected), None
    digest, value = baseline
    validate_baseline(value)
    excluded = set(value["excluded_test_ids"])
    retained = {n: i for n, i in selected.items() if i not in excluded}
    if not retained:
        raise ValueError("A completely excluded Apply group cannot claim a pass")
    receipt = {"format_version": 1, "baseline_sha256": digest,
               "measured_tests": len(value["tests"]),
               "baseline_excluded_tests": len(excluded),
               "partition_tests": len(selected),
               "excluded_test_ids": sorted(set(selected.values()) & excluded)}
    return retained, receipt


def freeze(measurement_path, root):
    """Explicit one-time publication; never overwrite or silently recalibrate."""
    path = Path(root) / BASELINE
    value = make_baseline(_load_report(Path(measurement_path)))
    raw = encoded(value)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".runtime-baseline-",
                                     delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
            os.chmod(temporary, 0o644)
            os.link(temporary, path)
        finally:
            temporary.unlink()
    return value
