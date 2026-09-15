"""Pure path classification shared by readers, future writers and bundles."""

from enum import Enum
import re
from types import MappingProxyType

from ..security import SafetyViolation
from ..security.paths import _parts
from .errors import ModelError

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

