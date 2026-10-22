"""Explicit byte-bound v1 resources and pure projection of already parsed values.

This first exchange layer neither discovers files nor parses exchange formats.
Native artifact validation, import history and loss decisions belong downstream.
"""
from dataclasses import dataclass
from hashlib import sha256
import re

from ..graph.relation_types import CORE_RELATION_TYPES
from ..model.artifact_types import artifact_types
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
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


@dataclass(frozen=True, init=False)
class ExchangeMapping:
    """Owned original bytes; a parsed resource alone is not a selection."""
    source_bytes: bytes
    mapping_id: str
    mapping_version: str
    sha256: str
    source_sha256: str

    def __init__(self, raw):
        value = _parse(raw, _MAPPING)
        self._initialize(raw, value)

    def _initialize(self, raw, value):
        for name, item in (("source_bytes", raw), ("mapping_id", value["mapping_id"]),
                           ("mapping_version", value["mapping_version"]),
                           ("sha256", canonical_json_sha256(value)),
                           ("source_sha256", sha256(raw).hexdigest())):
            object.__setattr__(self, name, item)

    @property
    def data(self):
        return parse_json_object(self.source_bytes)

    @property
    def key(self):
        return self.mapping_id + "@" + self.mapping_version

    def binding(self):
        return {"mapping_id": self.mapping_id, "mapping_version": self.mapping_version,
                "sha256": self.sha256}


@dataclass(frozen=True, init=False)
class ExternalIdentityRegistry(ExchangeMapping):
    """Passive registry bytes; binding to actual rules occurs at selection."""
    def __init__(self, raw):
        self._initialize(raw, _parse(raw, _REGISTRY))


def _index(resources, resource_type):
    if type(resources) not in (list, tuple):
        _fail("mapping_resource_sequence_required")
    indexed = {}
    for i, resource in enumerate(resources):
        if type(resource) is not resource_type:
            _fail("mapping_resource_type_required", "/resources/" + str(i))
        owned = resource_type(resource.source_bytes)
        if owned.key in indexed:
            _fail("mapping_duplicate_resource", "/resources/" + str(i))
        indexed[owned.key] = owned
    return indexed


def _select(indexed, key, expected_sha256):
    if type(key) is not str or key.count("@") != 1:
        _fail("mapping_exact_key_required")
    name, version = key.split("@")
    _identity({"mapping_id": name, "mapping_version": version})
    _hash(expected_sha256)
    if key not in indexed:
        _fail("mapping_resource_missing", "/resources")
    resource = indexed[key]
    if resource.sha256 != expected_sha256:
        raise MappingError("mapping_hash_mismatch", path=key, pointer="/sha256")
    return resource


@dataclass(frozen=True, init=False)
class _SelectedMapping:
    _source_bytes: bytes

    def __init__(self, resource):
        object.__setattr__(self, "_source_bytes", resource.source_bytes)

    @property
    def resource(self):
        # Exposed resource objects are observations, not the selection's state.
        # Reinitializing a returned object cannot replace the chosen binding.
        return ExchangeMapping(self._source_bytes)

    def artifact(self, external_type, fields):
        row = self._row("types", external_type)
        try:
            # Own and validate nested values before producing any projection.
            fields = parse_json_object(canonical_json_bytes(fields))
        except ModelError as error:
            raise MappingError(error.reason, path=self.resource.key, pointer=error.pointer) from error
        result = {"artifact_type": row["artifact_type"]}
        used = set()
        for i, field in enumerate(self.resource.data["fields"]):
            if field["external_type"] != external_type:
                continue
            at = "/fields/" + str(i)
            source = field["external_field"]
            if source not in fields:
                raise MappingError("mapping_source_field_missing", path=self.resource.key, pointer=at)
            target = fields[source]
            if field["value_map"] is not None:
                candidates = [entry["target_value"] for entry in field["value_map"]
                              if canonical_json_bytes(entry["external_value"]) == canonical_json_bytes(target)]
                if not candidates:
                    raise MappingError("mapping_value_unmapped", path=self.resource.key,
                                       pointer=at + "/value_map")
                target = candidates[0]
            result[field["target_field"]] = target
            used.add(source)
        return {"mapping": self.resource.binding(), "artifact": result,
                "unmapped": {k: v for k, v in fields.items() if k not in used}}

    def _row(self, family, external_type):
        _text(external_type, "/external_type")
        for row in self.resource.data[family]:
            if row["external_type"] == external_type:
                return row
        raise MappingError("mapping_type_unmapped", path=self.resource.key, pointer="/" + family)

    def _edge(self, family, external_type, first, second):
        row = self._row(family, external_type)
        _text(first, "/endpoints/0")
        _text(second, "/endpoints/1")
        if row["direction"] in ("reverse", "child_to_parent"):
            first, second = second, first
        return {"mapping": self.resource.binding(), "relation_type": row["relation_type"],
                "source": first, "target": second}

    def relation(self, external_type, source, target):
        return self._edge("relations", external_type, source, target)

    def hierarchy(self, external_type, parent, child):
        return self._edge("hierarchies", external_type, parent, child)


def select_mapping(resources, *, key, expected_sha256):
    """Select exactly one supplied resource; no highest-version or path lookup."""
    return _SelectedMapping(_select(_index(resources, ExchangeMapping), key, expected_sha256))


@dataclass(frozen=True, init=False)
class _SelectedRegistries:
    _source_bytes: tuple

    def __init__(self, resources):
        object.__setattr__(self, "_source_bytes", tuple(r.source_bytes for r in resources))

    @property
    def resources(self):
        return tuple(ExternalIdentityRegistry(raw) for raw in self._source_bytes)

    def lookup(self, object_class, source_system, source_document, external_id):
        key = (object_class, source_system, source_document, external_id)
        _member(object_class, _CLASSES, "/object_class")
        for name, value in zip(_IDENTITY_FIELDS[1:], key[1:]):
            _text(value, "/" + name)
        for resource in self.resources:
            for entry in resource.data["entries"]:
                if tuple(entry[k] for k in _IDENTITY_FIELDS) == key:
                    return {"registry": resource.binding(), "mapping": resource.data["mapping"],
                            "entry": entry}
        return None


def select_registries(resources, *, bindings, mappings):
    """Bind selected registries and all their entries to actual supplied rules."""
    registries = _index(resources, ExternalIdentityRegistry)
    rules = _index(mappings, ExchangeMapping)
    if registries.keys() & rules.keys():
        _fail("mapping_duplicate_resource", "/resources")
    _array(bindings, "/bindings")
    selected, keys, entries = [], set(), set()
    for i, value in enumerate(bindings):
        at = "/bindings/" + str(i)
        key = _binding(value, at)
        _unique(keys, key, at)
        registry = _select(registries, key, value["sha256"])
        bound = registry.data["mapping"]
        _select(rules, _binding(bound), bound["sha256"])
        for j, entry in enumerate(registry.data["entries"]):
            identity = tuple(entry[k] for k in _IDENTITY_FIELDS)
            if identity in entries:
                raise MappingError("mapping_duplicate_registry_entry", path=registry.key,
                                   pointer="/entries/" + str(j))
            entries.add(identity)
        selected.append(registry)
    return _SelectedRegistries(tuple(selected))
