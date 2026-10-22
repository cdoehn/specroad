"""Closed v1 resource grammar, strict JSON validation and mapping diagnostics.

This layer validates passive declarations; it never parses an exchange format
or grants permission to import, publish or resolve external data.
"""
from hashlib import sha256
import re

from ..graph.relation_types import CORE_RELATION_TYPES
from ..model.artifact_types import artifact_types
from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..model.metadata import validate_extensions
from ..model.versions import SCHEMA_VERSION
from ..profiles._contract import IDENTITY, SEMVER
from ..storage.json_syntax import parse_json_object

_MAPPING = "exchange-mapping-v1"
_REGISTRY = "external-identity-registry-v1"
_COMMON = {"schema_version", "mapping_format_version", "mapping_id", "mapping_version", "extensions"}
_KINDS = frozenset(t.artifact_type for t in artifact_types())
_CLASSES = ("type", "hierarchy", "relation", "metadata")
_IDENTITY_FIELDS = ("object_class", "source_system", "source_document", "external_id")


class MappingError(ModelError):
    """A failed mapping is never a partial import or an approval."""
    code = "SRV090"
    exit_code = 3

    def diagnostic(self):
        return {**super().diagnostic(), "code": self.code, "exit_code": self.exit_code}


def _fail(reason, at=""):
    raise MappingError(reason, pointer=at)


def _shape(value, fields, at):
    if type(value) is not dict:
        _fail("mapping_object_required", at)
    if any(type(key) is not str for key in value):
        _fail("mapping_string_key_required", at)
    # Bindings can arrive as Python values, without the strict byte reader.
    # Never echo a non-scalar Unicode key into a machine-readable pointer.
    for key in value:
        try:
            key.encode("utf-8")
        except UnicodeError:
            _fail("mapping_invalid_unicode", at)
    missing = fields - value.keys()
    extra = value.keys() - fields
    if missing:
        _fail("mapping_missing_field", at + "/" + sorted(missing)[0])
    if extra:
        key = sorted(extra)[0].replace("~", "~0").replace("/", "~1")
        _fail("mapping_unknown_field", at + "/" + key)


def _text(value, at):
    if type(value) is not str or not value:
        _fail("mapping_nonempty_string_required", at)
    try:
        value.encode("utf-8")
    except UnicodeError:
        _fail("mapping_invalid_unicode", at)
    return value


def _member(value, choices, at):
    if type(value) is not str or value not in choices:
        _fail("mapping_invalid_choice", at)


def _array(value, at):
    if type(value) is not list:
        _fail("mapping_array_required", at)
    return value


def _identity(value, at=""):
    for field, pattern in (("mapping_id", IDENTITY), ("mapping_version", SEMVER)):
        if type(value[field]) is not str or pattern.fullmatch(value[field]) is None:
            _fail("mapping_exact_identity_required", at + "/" + field)
    return value["mapping_id"] + "@" + value["mapping_version"]


def _hash(value, at="/sha256"):
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        _fail("mapping_sha256_required", at)


def _binding(value, at=""):
    _shape(value, {"mapping_id", "mapping_version", "sha256"}, at)
    key = _identity(value, at)
    _hash(value["sha256"], at + "/sha256")
    return key


def _unique(seen, key, at):
    if key in seen:
        _fail("mapping_duplicate_key", at)
    seen.add(key)


def _rules(value):
    _member(value["source_format"], ("reqif", "reqifz", "csv", "ndjson"), "/source_format")
    types = set()
    for i, row in enumerate(_array(value["types"], "/types")):
        at = "/types/" + str(i)
        _shape(row, {"external_type", "artifact_type"}, at)
        _unique(types, _text(row["external_type"], at + "/external_type"), at)
        _member(row["artifact_type"], _KINDS, at + "/artifact_type")
    sources, targets = set(), set()
    for i, row in enumerate(_array(value["fields"], "/fields")):
        at = "/fields/" + str(i)
        _shape(row, {"external_type", "external_field", "target_field", "value_map"}, at)
        _member(row["external_type"], types, at + "/external_type")
        source = _text(row["external_field"], at + "/external_field")
        target = _text(row["target_field"], at + "/target_field")
        if target == "artifact_type":
            _fail("mapping_reserved_target", at + "/target_field")
        _unique(sources, (row["external_type"], source), at + "/external_field")
        _unique(targets, (row["external_type"], target), at + "/target_field")
        if row["value_map"] is not None:
            entries = _array(row["value_map"], at + "/value_map")
            if not entries:
                _fail("mapping_empty_value_table", at + "/value_map")
            seen = set()
            for j, entry in enumerate(entries):
                here = at + "/value_map/" + str(j)
                _shape(entry, {"external_value", "target_value"}, here)
                _unique(seen, canonical_json_bytes(entry["external_value"]), here)
    for family, directions in (("relations", ("forward", "reverse")),
                               ("hierarchies", ("parent_to_child", "child_to_parent"))):
        seen = set()
        for i, row in enumerate(_array(value[family], "/" + family)):
            at = "/" + family + "/" + str(i)
            _shape(row, {"external_type", "relation_type", "direction"}, at)
            _unique(seen, _text(row["external_type"], at + "/external_type"), at)
            _member(row["relation_type"], CORE_RELATION_TYPES, at + "/relation_type")
            _member(row["direction"], directions, at + "/direction")


def _entries(value):
    bound_key = _binding(value["mapping"], "/mapping")
    if bound_key == _identity(value):
        _fail("mapping_registry_identity_collision", "/mapping")
    seen = set()
    for i, row in enumerate(_array(value["entries"], "/entries")):
        at = "/entries/" + str(i)
        _shape(row, {*_IDENTITY_FIELDS, "external_revision", "data", "extensions"}, at)
        _member(row["object_class"], _CLASSES, at + "/object_class")
        for field in (*_IDENTITY_FIELDS[1:], "external_revision"):
            if field != "external_revision" or row[field] is not None:
                _text(row[field], at + "/" + field)
        if type(row["data"]) is not dict:
            _fail("mapping_object_required", at + "/data")
        validate_extensions(row["extensions"], pointer=at + "/extensions")
        _unique(seen, tuple(row[k] for k in _IDENTITY_FIELDS), at)


def _parse(raw, format_version):
    if type(raw) is not bytes:
        _fail("mapping_bytes_required")
    try:
        value = parse_json_object(raw)
        fields = ({"source_format", "types", "fields", "relations", "hierarchies"}
                  if format_version == _MAPPING else {"mapping", "entries"})
        _shape(value, _COMMON | fields, "")
        if value["schema_version"] != SCHEMA_VERSION:
            _fail("mapping_unsupported_schema", "/schema_version")
        if value["mapping_format_version"] != format_version:
            _fail("mapping_unsupported_format", "/mapping_format_version")
        _identity(value)
        validate_extensions(value["extensions"])
        (_rules if format_version == _MAPPING else _entries)(value)
        return value
    except ModelError as error:
        # The byte identity locates even malformed or unnamed resources safely.
        raise MappingError(error.reason, path="sha256:" + sha256(raw).hexdigest(),
                           pointer=error.pointer, position=error.position,
                           line=error.line, column=error.column) from error
