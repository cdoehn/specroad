"""One immutable type registry for schema lookup and canonical artifact paths."""

from dataclasses import dataclass
from types import MappingProxyType

from .errors import ModelError
from .versions import SCHEMA_VERSION, PLAN_SCHEMA_VERSION, PLAN_TYPES

# These are data, never dynamic plugin registrations or imported project code.
_TYPE_PATHS = MappingProxyType({
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
    "implementation_plan": ("implementation-plans", "IPLAN"),
    "plan_entry": ("implementation-plans", "PENTRY"),
})


@dataclass(frozen=True)
class ArtifactType:
    artifact_type: str
    prefix: str
    directory: str
    schema_version: str
    schema_id: str


_TYPES = tuple(ArtifactType(kind, prefix, directory, version,
                           "urn:specroad:schema:" + version + ":artifact-common:" + kind)
               for kind, (directory, prefix) in _TYPE_PATHS.items()
               for version in (PLAN_SCHEMA_VERSION if kind in PLAN_TYPES else SCHEMA_VERSION,))
_BY_TYPE = MappingProxyType({item.artifact_type: item for item in _TYPES})


def artifact_types():
    """Stable immutable enumeration; modifying a result cannot alter the registry."""
    return _TYPES


def artifact_type(kind):
    if type(kind) is not str or kind not in _BY_TYPE:
        raise ModelError("unknown_artifact_type", pointer="/artifact_type")
    return _BY_TYPE[kind]

