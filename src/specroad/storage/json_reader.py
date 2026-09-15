"""Strict UTF-8 object reader and trusted, closed resource descriptors.

Schema descriptors are supplied by Core Python, never imported or executed from
project content. Full artifact schemas and legacy readers are separate steps.
"""

from dataclasses import dataclass
import json
import re
from typing import Callable

from ..model.errors import ModelError
from ..model.numbers import number_from_token
from ..model.configuration import (ProjectConfiguration, REQUIRED_FIELDS, OPTIONAL_FIELDS,
                                   SCHEMA_VERSION)
from ..model.paths import PathClass


class _ObjectPairs(list):
    pass


class _Number(str):
    pass


def _pointer(parent, key):
    return parent + "/" + str(key).replace("~", "~0").replace("/", "~1")


def _materialize(value, pointer=""):
    if isinstance(value, _Number):
        return number_from_token(value, pointer=pointer)
    if isinstance(value, _ObjectPairs):
        result = {}
        for key, item in value:
            child = _pointer(pointer, key)
            if key in result:
                raise ModelError("duplicate_key", pointer=child)
            _materialize(key, child)
            result[key] = _materialize(item, child)
        return result
    if isinstance(value, list):
        return [_materialize(item, _pointer(pointer, index)) for index, item in enumerate(value)]
    if isinstance(value, str):
        try:
            value.encode("utf-8")
        except UnicodeError as error:
            raise ModelError("invalid_unicode", pointer=pointer) from error
    return value


def parse_json_object(raw, *, path=None):
    """Parse exactly one object; keep original bytes and positions unchanged."""
    if not isinstance(raw, bytes):
        raise ModelError("bytes_required", path=path)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ModelError("invalid_utf8", path=path, position=error.start) from error
    try:
        value = json.loads(text, object_pairs_hook=_ObjectPairs, parse_constant=_Number,
                           parse_int=_Number, parse_float=_Number)
        if not isinstance(value, _ObjectPairs):
            raise ModelError("object_required", path=path)
        return _materialize(value)
    except json.JSONDecodeError as error:
        raise ModelError("invalid_json", path=path, position=error.pos,
                         line=error.lineno, column=error.colno) from error
    except ModelError as error:
        error.path = path
        raise
    except (ValueError, RecursionError) as error:
        raise ModelError("unsupported_json_value", path=path) from error


@dataclass(frozen=True)
class ResourceSchema:
    kind: str
    path_class: PathClass
    allowed_fields: frozenset
    required_fields: frozenset
    supported_versions: tuple = (SCHEMA_VERSION,)
    validator: Callable | None = None

    def __post_init__(self):
        if not isinstance(self.kind, str) or not self.kind or not isinstance(self.path_class, PathClass):
            raise ValueError("A trusted resource kind and path class are required")
        object.__setattr__(self, "allowed_fields", frozenset(self.allowed_fields))
        object.__setattr__(self, "required_fields", frozenset(self.required_fields) | {"schema_version"})
        object.__setattr__(self, "supported_versions", tuple(self.supported_versions))
        if (not self.required_fields <= self.allowed_fields or not self.supported_versions
                or any(not isinstance(field, str) for field in self.allowed_fields)
                or any(not isinstance(version, str) for version in self.supported_versions)):
            raise ValueError("Invalid closed resource descriptor")
        if (len(set(self.supported_versions)) != len(self.supported_versions)
                or any(not re.fullmatch(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)", version)
                       for version in self.supported_versions)):
            raise ValueError("Unsupported trusted schema version declaration")
        object.__setattr__(self, "supported_versions", tuple(sorted(
            self.supported_versions, key=lambda version: tuple(map(int, version.split("."))))))
        if self.validator is not None and not callable(self.validator):
            raise ValueError("Validator must be trusted Core code")


@dataclass(frozen=True, init=False)
class JsonResource:
    kind: str
    path: str | None
    schema_version: str
    source_bytes: bytes

    def __init__(self, raw, schema, *, path=None):
        if not isinstance(schema, ResourceSchema):
            raise TypeError("A trusted ResourceSchema is required")
        value = parse_json_object(raw, path=path)
        version = value.get("schema_version")
        highest = schema.supported_versions[-1]
        if version not in schema.supported_versions or not isinstance(version, str):
            raise ModelError("unsupported_schema_version", path=path,
                             pointer="/schema_version", highest_supported=highest)
        missing = schema.required_fields - value.keys()
        extra = value.keys() - schema.allowed_fields
        if missing:
            raise ModelError("missing_field", path=path, pointer=_pointer("", sorted(missing)[0]))
        if extra:
            raise ModelError("unknown_field", path=path, pointer=_pointer("", sorted(extra)[0]))
        if schema.validator is not None:
            try:
                schema.validator(value)
            except ModelError as error:
                error.path = path
                raise
        object.__setattr__(self, "kind", schema.kind)
        object.__setattr__(self, "path", path)
        object.__setattr__(self, "schema_version", version)
        object.__setattr__(self, "source_bytes", raw)

    @property
    def data(self):
        return parse_json_object(self.source_bytes, path=self.path)


def configuration_schema():
    return ResourceSchema("project_configuration", PathClass.CONFIGURATION,
                          REQUIRED_FIELDS | OPTIONAL_FIELDS, REQUIRED_FIELDS,
                          validator=ProjectConfiguration)


def read_resource(source, path, schema):
    if not isinstance(schema, ResourceSchema):
        raise TypeError("A trusted ResourceSchema is required")
    if source.classify(path) is not schema.path_class:
        raise ModelError("resource_path_class_mismatch", path=path)
    resource = JsonResource(source.read_normative(path), schema, path=path)
    source.check_current()
    return resource


def read_resources(source, requests):
    """No partial model is returned when any member is invalid."""
    if isinstance(requests, (str, bytes, dict)):
        raise ModelError("resource_sequence_required")
    try:
        requests = tuple(requests)
    except TypeError as error:
        raise ModelError("resource_sequence_required") from error
    if any(not isinstance(pair, (tuple, list)) or len(pair) != 2
           or not isinstance(pair[0], str) or not isinstance(pair[1], ResourceSchema)
           for pair in requests):
        raise ModelError("invalid_resource_request")
    names = tuple(path for path, schema in requests)
    if len(set(names)) != len(names):
        raise ModelError("duplicate_resource_path")
    source.check_current()
    result = tuple(read_resource(source, path, schema) for path, schema in requests)
    source.check_current()
    return result
