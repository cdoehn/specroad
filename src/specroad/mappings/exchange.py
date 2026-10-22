"""Pure mapping projections and registry lookup over explicitly bound resources.

Inputs are already parsed external values. Format parsers, import policy and
project writers remain outside this layer and supply their own authority.
"""
from dataclasses import dataclass

from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..storage.json_syntax import parse_json_object
from ._contract import (MappingError, _CLASSES, _IDENTITY_FIELDS,
                        _array, _binding, _fail, _member, _text, _unique)
from ._resources import ExchangeMapping, ExternalIdentityRegistry, _index, _select


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
