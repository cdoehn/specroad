"""Immutable ReqIF source values and diagnostics, without parsing or mapping."""
from dataclasses import dataclass, fields, replace

from ..model.errors import ModelError

REQIF_NAMESPACE = "http://www.omg.org/spec/ReqIF/20110401/reqif.xsd"
_XML = "http://www.w3.org/XML/1998/namespace"
_SEP = "\x1f"


class ReqIFError(ModelError):
    """Machine-readable format, source conflict or safety failure; no payload."""

    def __init__(self, reason, *, exit_code=3, object_id=None, definition_id=None, **location):
        super().__init__(reason, **location)
        self.exit_code = exit_code
        self.object_id = object_id
        self.definition_id = definition_id

    def diagnostic(self):
        return {**super().diagnostic(), "exit_code": self.exit_code,
                "object_id": self.object_id, "definition_id": self.definition_id}


@dataclass(frozen=True)
class ReqIFLimits:
    """Explicit positive per-document safety bounds, not a total job budget.

    No JUnit-specific file cap is silently imposed on ReqIF. Callers bind all
    seven bounds before parsing; the shared XML reader enforces them throughout.
    """
    max_bytes: int
    max_depth: int
    max_elements: int
    max_text_chars: int
    max_attributes_per_element: int
    max_name_chars: int
    max_expanded_name_chars: int

    def __post_init__(self):
        if any(type(getattr(self, f.name)) is not int or getattr(self, f.name) < 1
               for f in fields(self)):
            raise ReqIFError("invalid_xml_limits", exit_code=2)


@dataclass(frozen=True)
class _Node:
    name: str
    attributes: tuple
    content: tuple
    pointer: str = ""

    @property
    def tag(self):
        namespace, _, local = self.name.rpartition(_SEP)
        return local if namespace == REQIF_NAMESPACE else None

    @property
    def attrs(self):
        return dict(self.attributes)

    @property
    def children(self):
        return tuple(x for x in self.content if type(x) is _Node)


def _error(reason, node, **context):
    return ReqIFError(reason, pointer=node.pointer, **context)


@dataclass(frozen=True)
class ReqIFValue:
    family: str
    definition_id: str
    lexical: object
    element: _Node


@dataclass(frozen=True)
class ReqIFDatatype:
    identifier: str
    family: str
    element: _Node
    enum_ids: tuple = ()


@dataclass(frozen=True)
class ReqIFDefinition:
    identifier: str
    family: str
    datatype_id: str
    default: object
    element: _Node


@dataclass(frozen=True)
class ReqIFType:
    identifier: str
    definitions: tuple
    element: _Node


@dataclass(frozen=True)
class ReqIFObject:
    identifier: str
    type_id: str
    values: tuple
    element: _Node


def _replace_node(root, before, after):
    if root is before:
        return after
    return replace(root, content=tuple(_replace_node(v, before, after) if type(v) is _Node else v
                                       for v in root.content))
