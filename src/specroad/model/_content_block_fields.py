"""One native registry for passive content-block payloads and local references."""
from .artifact_types import artifact_types
from .errors import ModelError
from ._field_shapes import _object, _array, _typed_reference


def _block_payload():
    text = {"$ref": "#/$defs/text"}
    # The payload remains passive. Parsing/rendering prose and queries belongs
    # to the document services, not a schema's successful read operation.
    prose = {"type": "string"}
    columns = _array({"type": "object"}, nonempty=True)
    view_source = _object({"source": {"const": "view"}})
    return {
        "prose": _object({"markdown": prose}),
        "artifact_ref": _object({"render_mode": {"enum": ["summary", "full", "link"]}}),
        "query": {"anyOf": [
            _object({"query": {"type": "object"}, "columns": columns, "empty_policy": {"enum": ["omit", "message", "error"]}}),
            _object({"source": {"const": "view"}, "columns": columns, "empty_policy": {"enum": ["omit", "message", "error"]}}),
        ]},
        "table": {"anyOf": [view_source, _object({"columns": columns, "rows": _array({"type": "array"})})]},
        "admonition": _object({"level": {"enum": ["note", "tip", "important", "warning", "caution"]},
                               "title": text, "markdown": prose}, ("level", "markdown")),
        "page_break": _object({}),
        "include_document": _object({"mode": {"enum": ["content", "section"]}}),
    }



BLOCK_KINDS = tuple(_block_payload())


def _block_reference(value):
    kind, payload = value["block_kind"], value["payload"]
    prefixes = None
    if kind == "artifact_ref":
        prefixes = tuple(t.prefix for t in artifact_types())
    elif kind in ("query", "table") and payload.get("source") == "view":
        prefixes = ("VIEW",)
    elif kind == "include_document":
        prefixes = ("DOC",) if payload["mode"] == "content" else ("SEC",)
    if prefixes is None:
        return
    relations = [(index, relation) for index, relation in enumerate(value["relations"])
                 if relation.get("type") == "references"]
    if len(relations) != 1:
        raise ModelError("block_reference_cardinality", pointer="/relations")
    index, relation = relations[0]
    try:
        _typed_reference(relation.get("target"), prefixes)
    except ModelError as error:
        raise ModelError("block_reference_type", pointer="/relations/" + str(index) + "/target") from error
