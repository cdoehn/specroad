"""Developer verification: catalog responsibilities."""

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import stat
from .common import CatalogError, _hash, _strings, json_bytes, read_object, sha256


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
    if value["oracle"]["kind"] != "behavior" and value["test_ids"]:
        raise CatalogError("Human presentation or pending oracles cannot have automated pass tests")
    if value["implementation_status"] == "open" and value["test_ids"]:
        raise CatalogError("An open case cannot pretend to have an executable implementation")
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


@dataclass(frozen=True, init=False)
class Case:
    _encoded: bytes
    manifest_sha256: str

    def __init__(self, data, manifest_sha256):
        if not _hash(manifest_sha256):
            raise CatalogError("Invalid manifest hash")
        checked = validate_manifest(data, data.get("specification_sha256"))
        object.__setattr__(self, "_encoded", json_bytes(checked))
        object.__setattr__(self, "manifest_sha256", manifest_sha256)

    @property
    def data(self):
        return json.loads(self._encoded)


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
    required_ids = index.get("required_test_case_ids", ids)
    if not _strings(required_ids, nonempty=True) or any(
        not re.fullmatch(r"SR-TC-[0-9]{4}", name) for name in required_ids
    ):
        raise CatalogError("Invalid required case inventory")
    if not set(ids) <= set(required_ids) or (index["complete"] and set(ids) != set(required_ids)):
        raise CatalogError("A complete catalog must contain every required primary case")
    fixtures, fixture_hash = read_object(directory / "fixtures.json")
    fixture_ids = fixtures.get("fixture_ids")
    if type(fixtures.get("fixture_format_version")) is not int or fixtures["fixture_format_version"] != 1 or not _strings(fixture_ids, nonempty=True):
        raise CatalogError("Invalid fixture registry")
    cases = []
    hashes = {"catalog.json": index_hash, "fixtures.json": fixture_hash}
    case_root = directory / "requirements"
    if not stat.S_ISDIR(case_root.lstat().st_mode):
        raise CatalogError("Requirement directory must not be linked")
    with os.scandir(case_root) as entries:
        actual_names = {entry.name for entry in entries}
    if actual_names != {case_id + ".json" for case_id in ids}:
        raise CatalogError("Requirement directory differs from the declared catalog")
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


