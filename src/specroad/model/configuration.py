"""Closed project configuration and the initial shared path contract.

Policy values remain declarations: loading never executes an adapter or resolves
an online registry. The specific policy engines belong to later plan steps.
"""

from dataclasses import dataclass
from enum import Enum
import json
import math
import re
from types import MappingProxyType

from ..security import SafetyViolation, check_project_declarations
from ..security.paths import _parts
from .errors import ModelError
from .numbers import number_from_token

SCHEMA_VERSION = "0.2.0"
REQUIRED_FIELDS = frozenset({
    "schema_version", "project_id", "project_name", "id_prefix", "default_locale",
    "managed_paths", "profiles", "generated_path", "validation_policy",
})
OPTIONAL_FIELDS = frozenset({
    "transaction_policy", "resource_limits", "language_policy", "language_packages",
    "analyzer_policy", "srx_policy", "language_registry", "extensions",
})

# Paths and ID prefixes, not the artifact schemas introduced by 2.c.
ARTIFACT_PATHS = MappingProxyType({
    "goal": ("goals", "GOAL"), "need": ("needs", "NEED"),
    "capability": ("capabilities", "CAP"), "requirement": ("requirements", "REQ"),
    "scenario": ("scenarios", "SCN"), "decision": ("decisions", "DEC"),
    "risk": ("risks", "RISK"), "assumption": ("assumptions", "ASM"),
    "component": ("components", "COMP"), "interface": ("interfaces", "IFC"),
    "source": ("sources", "SRC"), "verification": ("verifications", "VER"),
    "test": ("tests", "TEST"), "evidence": ("evidence", "EVD"),
    "release": ("releases", "REL"), "milestone": ("milestones", "MS"),
    "task": ("tasks", "TASK"), "term": ("terms", "TERM"),
    "proposal": ("proposals", "PROP"), "baseline": ("baselines", "BASE"),
    "issue": ("issues", "ISSUE"), "document": ("documents", "DOC"),
    "section": ("sections", "SEC"), "content_block": ("content-blocks", "BLOCK"),
    "view": ("views", "VIEW"), "code_ref": ("code-refs", "CODE"),
    "relation_review": ("relation-reviews", "RREV"),
    "configuration": ("configurations", "CFG"),
})


class PathClass(str, Enum):
    CONFIGURATION = "configuration"
    ARTIFACT = "artifact"
    PROFILE = "profile"
    RULE = "rule"
    MAPPING = "mapping"
    ATTACHMENT = "attachment"
    ARCHIVE_OBJECT = "archive_object"
    GENERATED = "generated"
    CACHE = "cache"
    RECOVERY = "recovery"
    RECEIPT = "receipt"
    OPERATIONAL = "operational"
    UNMANAGED = "unmanaged"


CURRENT_JSON_CLASSES = frozenset({PathClass.CONFIGURATION, PathClass.ARTIFACT,
                                 PathClass.PROFILE, PathClass.RULE, PathClass.MAPPING})
PAYLOAD_CLASSES = frozenset({PathClass.ATTACHMENT, PathClass.ARCHIVE_OBJECT})


def project_path(value):
    try:
        parts = _parts(value)
    except SafetyViolation as error:
        raise ModelError("unsafe_path") from error
    reserved = {"CON", "PRN", "AUX", "NUL"}
    reserved.update("COM" + str(number) for number in range(1, 10))
    reserved.update("LPT" + str(number) for number in range(1, 10))
    if any(part.endswith((".", " ")) or part.split(".")[0].upper() in reserved
           or any(char in part for char in '<>"|?*') for part in parts):
        raise ModelError("unsafe_path")
    if any(part.casefold() in {".git", ".patchharbor"} for part in parts):
        raise ModelError("reserved_path")
    return "/".join(parts)


def _under(path, directory):
    return path == directory or path.startswith(directory + "/")


def artifact_path(artifact_type, artifact_id, id_prefix):
    if not isinstance(artifact_type, str) or artifact_type not in ARTIFACT_PATHS:
        raise ModelError("unknown_artifact_type")
    if not isinstance(id_prefix, str) or not re.fullmatch(r"[A-Z][A-Z0-9]{1,7}", id_prefix):
        raise ModelError("invalid_id_prefix", pointer="/id_prefix")
    directory, type_prefix = ARTIFACT_PATHS[artifact_type]
    # Legacy IDs are only a read/address capability, not permission to mint them.
    token = r"(?:[0-7][0-9A-HJKMNP-TV-Z]{25}|[0-9]{4})"
    if not isinstance(artifact_id, str) or not re.fullmatch(re.escape(id_prefix + "-" + type_prefix + "-") + token, artifact_id):
        raise ModelError("artifact_identity_mismatch")
    return "spec/" + directory + "/" + artifact_id + ".json"


def classify_path(path, configuration):
    path = project_path(path)
    if path == "specroad.json":
        return PathClass.CONFIGURATION
    if _under(path, configuration.generated_path):
        return PathClass.GENERATED
    if _under(path, ".specroad/transactions/receipts") or _under(path, ".specroad/requests"):
        return PathClass.RECEIPT
    if _under(path, ".specroad/transactions") or _under(path, ".specroad/recovery"):
        return PathClass.RECOVERY
    if _under(path, ".specroad/cache"):
        return PathClass.CACHE
    if _under(path, ".specroad"):
        return PathClass.OPERATIONAL
    if not any(_under(path, parent) for parent in configuration.managed_paths):
        return PathClass.UNMANAGED
    pieces = path.split("/")
    if len(pieces) == 3 and pieces[0] == "spec" and pieces[-1].endswith(".json"):
        for kind, (directory, prefix) in ARTIFACT_PATHS.items():
            if directory == pieces[1]:
                artifact_path(kind, pieces[2][:-5], configuration.id_prefix)
                return PathClass.ARTIFACT
    for directory, kind in (("profiles", PathClass.PROFILE), ("rules", PathClass.RULE),
                            ("mappings", PathClass.MAPPING)):
        if len(pieces) > 1 and pieces[0] == directory and path.endswith(".json"):
            return kind
    if len(pieces) > 1 and pieces[0] == "attachments":
        return PathClass.ATTACHMENT
    if len(pieces) == 4 and pieces[:2] == ["archive", "objects"]:
        token = pieces[3]
        if re.fullmatch(r"[0-9a-f]{64}", token) and pieces[2] == token[:2]:
            return PathClass.ARCHIVE_OBJECT
    return PathClass.UNMANAGED


def _json_values(value, pointer=""):
    if value is None or type(value) is bool:
        return
    if type(value) is int:
        try:
            number_from_token(str(value), pointer=pointer)
        except ValueError as error:
            if isinstance(error, ModelError):
                raise
            raise ModelError("unsupported_number", pointer=pointer) from error
        return
    if type(value) is float:
        if not math.isfinite(value):
            raise ModelError("nonfinite_number", pointer=pointer)
        return
    if isinstance(value, str):
        try:
            value.encode("utf-8")
        except UnicodeError as error:
            raise ModelError("invalid_unicode", pointer=pointer) from error
        return
    if type(value) is list:
        for index, item in enumerate(value):
            _json_values(item, pointer + "/" + str(index))
        return
    if type(value) is dict:
        for key, item in value.items():
            if not isinstance(key, str):
                raise ModelError("nonstring_key", pointer=pointer)
            _json_values(key, pointer)
            _json_values(item, pointer + "/" + key.replace("~", "~0").replace("/", "~1"))
        return
    raise ModelError("non_json_value", pointer=pointer)


def _text(value, pointer):
    if not isinstance(value, str) or not value.strip() or "\0" in value:
        raise ModelError("invalid_text", pointer=pointer)


def validate_configuration(data):
    if type(data) is not dict:
        raise ModelError("object_required")
    _json_values(data)
    missing = REQUIRED_FIELDS - data.keys()
    if missing:
        raise ModelError("missing_field", pointer="/" + sorted(missing)[0])
    unknown = data.keys() - REQUIRED_FIELDS - OPTIONAL_FIELDS
    if unknown:
        raise ModelError("unknown_field", pointer="/" + sorted(unknown)[0])
    if data["schema_version"] != SCHEMA_VERSION:
        raise ModelError("unsupported_schema_version", pointer="/schema_version", highest_supported=SCHEMA_VERSION)
    for field in ("project_id", "project_name", "default_locale"):
        _text(data[field], "/" + field)
    if not isinstance(data["id_prefix"], str) or not re.fullmatch(r"[A-Z][A-Z0-9]{1,7}", data["id_prefix"]):
        raise ModelError("invalid_id_prefix", pointer="/id_prefix")
    for field in ("profiles", "managed_paths", "language_packages"):
        if field not in data:
            continue
        if type(data[field]) is not list:
            raise ModelError("array_required", pointer="/" + field)
        for index, value in enumerate(data[field]):
            _text(value, "/" + field + "/" + str(index))
        if len(set(data[field])) != len(data[field]):
            raise ModelError("duplicate_value", pointer="/" + field)
    for field in ("validation_policy", "transaction_policy", "resource_limits", "language_policy",
                  "analyzer_policy", "srx_policy", "language_registry", "extensions"):
        if field in data and type(data[field]) is not dict:
            raise ModelError("object_required", pointer="/" + field)
    generated = project_path(data["generated_path"])
    roots = [project_path(path) for path in data["managed_paths"]]
    protected = ("specroad.json", "spec", "profiles", "rules", "mappings", "attachments", "archive", ".specroad")
    if any(_under(generated.casefold(), path) or _under(path, generated.casefold()) for path in protected):
        raise ModelError("overlapping_path_classes", pointer="/generated_path")
    for path in roots:
        folded = path.casefold()
        if (_under(folded, ".specroad") or _under(folded, "specroad.json")
                or _under(folded, generated.casefold()) or _under(generated.casefold(), folded)):
            raise ModelError("overlapping_path_classes", pointer="/managed_paths")
    if len({path.casefold() for path in roots}) != len(roots):
        raise ModelError("duplicate_path", pointer="/managed_paths")
    try:
        check_project_declarations(data)
    except SafetyViolation as error:
        raise ModelError("unsafe_project_declaration") from error


@dataclass(frozen=True, init=False)
class ProjectConfiguration:
    """Owned immutable bytes; each data access returns an independent value tree."""
    _encoded: bytes

    def __init__(self, value):
        try:
            validate_configuration(value)
            encoded = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
        except RecursionError as error:
            raise ModelError("nesting_not_supported") from error
        object.__setattr__(self, "_encoded", encoded)

    @property
    def data(self):
        return json.loads(self._encoded)

    @property
    def id_prefix(self):
        return self.data["id_prefix"]

    @property
    def project_id(self):
        return self.data["project_id"]

    @property
    def managed_paths(self):
        return tuple(self.data["managed_paths"])

    @property
    def generated_path(self):
        return self.data["generated_path"]
