"""One measured full run and a frozen, count-based Apply exclusion list."""
from hashlib import sha256
import os
from pathlib import Path
import stat
import tempfile

from .ci_reference import _load_report
from .runtime_measurement import (
    RuntimeMeasurements, encoded, _hash, _identity, _timestamp, validate_imports, validate_measurement,
)


BASELINE = "verification/test_runtime_baseline.json"


def make_baseline(measurement):
    value = validate_measurement(measurement)
    rows = sorted(({"test_id": row["test_id"], "nodeid": row["nodeid"],
                    "duration_ns": sum(row["phase_ns"].values())} for row in value["tests"]),
                  key=lambda row: row["test_id"])
    excluded = sorted(row["test_id"] for row in
        sorted(rows, key=lambda row: (-row["duration_ns"], row["test_id"]))[:len(rows) // 5])
    result = {"format_version": 1, "kind": "specroad-frozen-runtime-filter-v1",
            "measured_source_sha256": value["source_sha256"],
            "measurement_sha256": sha256(encoded(value)).hexdigest(),
            "measured_at": value["measured_at"], "workers": value["workers"],
            "exclude_numerator": 1, "exclude_denominator": 5,
            "tests": rows, "excluded_test_ids": excluded}

    if value.get("measurement_imports"):
        result.update(format_version=2, kind="specroad-frozen-runtime-filter-v2",
                      measurement_imports=value["measurement_imports"])
    return result


def validate_baseline(value):
    if type(value) is dict and value.get("format_version") == 2:
        ordinary = dict(value)
        imports = ordinary.pop("measurement_imports", None)
        if ordinary.get("kind") != "specroad-frozen-runtime-filter-v2":
            raise ValueError("Invalid historical baseline kind")
        ordinary.update(format_version=1, kind="specroad-frozen-runtime-filter-v1")
        validate_baseline(ordinary)
        validate_imports(imports, value["measured_source_sha256"], [r["test_id"] for r in value["tests"]])
        return value
    fields = {"format_version", "kind", "measured_source_sha256", "measurement_sha256",
              "measured_at", "workers", "exclude_numerator", "exclude_denominator",
              "tests", "excluded_test_ids"}
    if (type(value) is not dict or set(value) != fields
            or type(value["format_version"]) is not int or value["format_version"] != 1
            or value["kind"] != "specroad-frozen-runtime-filter-v1"
            or not _hash(value["measured_source_sha256"]) or not _hash(value["measurement_sha256"])
            or not _timestamp(value["measured_at"])
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
    if not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError("Timing baseline must be a regular file")
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
    if not _hash(digest):
        raise ValueError("Invalid timing baseline byte binding")
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
    if not stat.S_ISDIR(path.parent.lstat().st_mode):
        raise ValueError("Baseline directory must be a real directory")
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
