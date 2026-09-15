"""Development test bindings, not the future product Evidence/Release engine.

Only already discovered trusted tests may run. Manifest strings are data, never
Python import targets. Local digests bind bytes; they are not signatures.
"""

from dataclasses import dataclass
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import re
import stat
import sys
import unittest


class CatalogError(ValueError):
    """Invalid test binding or unavailable current evidence."""


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def json_bytes(value):
    # Developer report encoding, deliberately not the future model JCS contract.
    return json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False,
                      separators=(",", ":")).encode("utf-8")


def _object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise CatalogError("Duplicate JSON key")
        value[key] = item
    return value


def _reject_constant(value):
    raise CatalogError("Non-finite JSON value")


def read_object(path):
    path = Path(path)
    if not stat.S_ISREG(path.lstat().st_mode):
        raise CatalogError("Manifest must be a regular file")
    raw = path.read_bytes()
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_object,
                           parse_constant=_reject_constant)
    except (UnicodeError, ValueError, RecursionError) as error:
        raise CatalogError("Invalid manifest JSON") from error
    if not isinstance(value, dict):
        raise CatalogError("Manifest must be an object")
    return value, sha256(raw)


def _strings(value, *, nonempty=False):
    return (type(value) is list and (bool(value) or not nonempty)
            and all(type(item) is str and bool(item) for item in value)
            and len(value) == len(set(value)))


def _hash(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def validate_manifest(value, specification_sha256):
    """Validate executable data contracts, never wording, Markdown or layout."""
    required = {
        "test_case_format_version", "test_case_id", "requirement_id", "specification_sha256",
        "primary_verification_id", "implementation_status", "method", "fixture_ids",
        "preconditions", "steps", "oracle", "expected_diagnostics", "expected_exit_codes",
        "json_pointers", "required_environment", "resources", "evidence_kind", "test_ids", "open_items",
    }
    if not isinstance(value, dict) or not required <= value.keys():
        raise CatalogError("Missing required test binding")
    if type(value["test_case_format_version"]) is not int or value["test_case_format_version"] != 1:
        raise CatalogError("Unsupported test-case format")
    case_id = value["test_case_id"]
    if not isinstance(case_id, str) or not re.fullmatch(r"SR-TC-[0-9]{4}", case_id):
        raise CatalogError("Invalid primary test-case identity")
    if value["requirement_id"] != case_id.replace("SR-TC-", "SR-REQ-"):
        raise CatalogError("Primary test and requirement numbers differ")
    if not _hash(specification_sha256) or value["specification_sha256"] != specification_sha256:
        raise CatalogError("Wrong specification binding")
    if not isinstance(value["primary_verification_id"], str) or not re.fullmatch(
            r"SR-VER-[0-9]{4}", value["primary_verification_id"]):
        raise CatalogError("Invalid primary verification identity")
    if value["implementation_status"] not in ("open", "partial", "implemented"):
        raise CatalogError("Unknown implementation status")
    if value["method"] not in ("automated_behavior", "pending", "manual_presentation"):
        raise CatalogError("Unknown verification method")
    for field in ("fixture_ids", "preconditions", "steps", "expected_diagnostics", "json_pointers",
                  "test_ids", "open_items"):
        if not _strings(value[field]):
            raise CatalogError("Invalid sequence field: " + field)
    if (not isinstance(value["oracle"], dict)
            or value["oracle"].get("kind") not in ("behavior", "pending", "manual_presentation")):
        raise CatalogError("Invalid behavior oracle")
    if (type(value["expected_exit_codes"]) is not list
            or any(type(code) is not int or not 0 <= code <= 255 for code in value["expected_exit_codes"])
            or len(set(value["expected_exit_codes"])) != len(value["expected_exit_codes"])):
        raise CatalogError("Invalid exit-code contract")
    if not isinstance(value["required_environment"], dict) or not isinstance(value["resources"], dict):
        raise CatalogError("Missing environment/resource contract")
    if value["evidence_kind"] != "specroad-dev-unittest-v1":
        raise CatalogError("Unknown developer evidence format")
    if value["implementation_status"] != "open" and (
        not value["test_ids"] or not value["fixture_ids"] or not value["steps"]
        or not value["preconditions"] or value["method"] != "automated_behavior"
        or value["oracle"]["kind"] != "behavior"
    ):
        raise CatalogError("Implemented scope needs real behavior tests and fixtures")
    if value["implementation_status"] != "implemented" and not value["open_items"]:
        raise CatalogError("Incomplete requirements must declare their remaining work")
    if value["implementation_status"] == "implemented" and value["open_items"]:
        raise CatalogError("Open work cannot be declared implemented")
    for pointer in value["json_pointers"]:
        if not pointer.startswith("/"):
            raise CatalogError("Invalid JSON pointer")
    return json.loads(json_bytes(value))


@dataclass(frozen=True)
class Case:
    data: dict
    manifest_sha256: str


@dataclass(frozen=True)
class Catalog:
    cases: tuple
    specification_sha256: str
    catalog_sha256: str
    complete: bool


def load_catalog(directory):
    directory = Path(directory)
    if not stat.S_ISDIR(directory.lstat().st_mode):
        raise CatalogError("Catalog root must be a real directory")
    index, index_hash = read_object(directory / "catalog.json")
    if type(index.get("catalog_format_version")) is not int or index["catalog_format_version"] != 1:
        raise CatalogError("Unsupported catalog version")
    spec = index.get("specification_sha256")
    ids = index.get("test_case_ids")
    if not _hash(spec) or not _strings(ids, nonempty=True) or type(index.get("complete")) is not bool:
        raise CatalogError("Invalid catalog identity or scope")
    fixtures, fixture_hash = read_object(directory / "fixtures.json")
    fixture_ids = fixtures.get("fixture_ids")
    if fixtures.get("fixture_format_version") != 1 or not _strings(fixture_ids, nonempty=True):
        raise CatalogError("Invalid fixture registry")
    cases = []
    hashes = {"catalog.json": index_hash, "fixtures.json": fixture_hash}
    case_root = directory / "requirements"
    if not stat.S_ISDIR(case_root.lstat().st_mode):
        raise CatalogError("Requirement directory must not be linked")
    for case_id in ids:
        if not re.fullmatch(r"SR-TC-[0-9]{4}", case_id):
            raise CatalogError("Unsafe catalog entry")
        value, file_hash = read_object(case_root / (case_id + ".json"))
        value = validate_manifest(value, spec)
        if value["test_case_id"] != case_id or not set(value["fixture_ids"]) <= set(fixture_ids):
            raise CatalogError("Manifest identity or fixture registry mismatch")
        cases.append(Case(value, file_hash))
        hashes["requirements/" + case_id + ".json"] = file_hash
    return Catalog(tuple(cases), spec, sha256(json_bytes(hashes)), index["complete"])


def flatten_suite(suite):
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            yield from flatten_suite(test)
        else:
            yield test


def bind_tests(catalog, suite):
    tests = list(flatten_suite(suite))
    ids = [test.id() for test in tests]
    if not ids or len(ids) != len(set(ids)):
        raise CatalogError("Test discovery is empty or ambiguous")
    available = set(ids)
    for case in catalog.cases:
        if not set(case.data["test_ids"]) <= available:
            raise CatalogError("Manifest names an unavailable real test: " + case.data["test_case_id"])
    return tuple(ids)


class ObservedResult(unittest.TextTestResult):
    """Record actual unittest callbacks, including non-passing subtests."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.outcomes = {}

    def startTest(self, test):
        super().startTest(test)
        self.outcomes[test.id()] = "running"

    def _record(self, test, state):
        key = getattr(test, "test_case", test).id()
        rank = {"running": 0, "passed": 1, "expected_failure": 2, "skipped": 3,
                "unexpected_success": 4, "failed": 5, "error": 6}
        previous = self.outcomes.get(key, "running")
        if rank[state] > rank[previous]:
            self.outcomes[key] = state

    def addSuccess(self, test):
        super().addSuccess(test)
        self._record(test, "passed")

    def addError(self, test, error):
        super().addError(test, error)
        self._record(test, "error")

    def addFailure(self, test, error):
        super().addFailure(test, error)
        self._record(test, "failed")

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self._record(test, "skipped")

    def addExpectedFailure(self, test, error):
        super().addExpectedFailure(test, error)
        self._record(test, "expected_failure")

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self._record(test, "unexpected_success")

    def addSubTest(self, test, subtest, error):
        super().addSubTest(test, subtest, error)
        if error is not None:
            self._record(test, "failed" if issubclass(error[0], test.failureException) else "error")


def observe_suite(suite, *, stream=None, verbosity=2):
    return unittest.TextTestRunner(stream=stream, verbosity=verbosity,
                                  resultclass=ObservedResult).run(suite)


def case_evidence(case, binding, outcomes):
    data = case.data
    statuses = {name: outcomes.get(name, "not_run") for name in data["test_ids"]}
    if any(value in ("failed", "error", "unexpected_success") for value in statuses.values()):
        status = "failed"
    elif not statuses or any(value != "passed" for value in statuses.values()):
        status = "open"
    elif data["implementation_status"] != "implemented":
        status = "partial"
    else:
        status = "passed"
    return {
        "evidence_kind": data["evidence_kind"], "test_case_id": data["test_case_id"],
        "requirement_id": data["requirement_id"], "specification_sha256": data["specification_sha256"],
        "manifest_sha256": case.manifest_sha256, **binding,
        "test_outcomes": statuses, "status": status,
    }


def source_identity(root):
    """Hash current developer inputs, not repository docs or ignored build output."""
    root = Path(root)
    entries = {}
    def visit(path):
        mode = path.lstat().st_mode
        if stat.S_ISREG(mode):
            entries[path.relative_to(root).as_posix()] = sha256(path.read_bytes())
        elif stat.S_ISDIR(mode):
            with os.scandir(path) as scan:
                names = sorted(entry.name for entry in scan)
            for name in names:
                if name == "__pycache__" or name.endswith((".pyc", ".pyo", ".egg-info")):
                    continue
                visit(path / name)
        else:
            raise CatalogError("Linked or special source input")
    # Limit the source tree to the package, not local editable-install siblings.
    for relative in ("src/specroad", "tests", "tools", "verification", "pyproject.toml"):
        visit(root / relative)
    return sha256(json_bytes(entries))


def platform_identity():
    return {"implementation": sys.implementation.name, "python": platform.python_version(),
            "system": platform.system(), "machine": platform.machine()}


def make_report(catalog, binding, result, discovered_ids):
    cases = [case_evidence(case, binding, result.outcomes) for case in catalog.cases]
    suite_passed = (result.wasSuccessful() and result.testsRun == len(discovered_ids)
                    and set(result.outcomes) == set(discovered_ids)
                    and all(value == "passed" for value in result.outcomes.values()))
    counts = {name: sum(case["status"] == name for case in cases)
              for name in ("open", "partial", "failed", "passed")}
    return {
        "report_format_version": 1, "purpose": "development_behavior_evidence", **binding,
        "catalog_sha256": catalog.catalog_sha256, "specification_sha256": catalog.specification_sha256,
        "catalog_complete": catalog.complete, "tests_run": result.testsRun,
        "suite_passed": suite_passed, "test_outcomes": dict(result.outcomes),
        "requirement_counts": counts, "cases": cases,
        "release_approved": False, "release_gate": "not_evaluated",
    }
