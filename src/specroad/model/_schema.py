"""Small interpreter for the vocabulary used by trusted built-in schemas only.

This is not a user-supplied-schema loader. Unknown assertions and nonlocal
references fail closed; there is no network resolver or plugin mechanism.
"""

import math
from datetime import date
import re

from .errors import ModelError


_KEYWORDS = frozenset({
    "$schema", "$id", "$defs", "$ref", "$comment", "description", "title",
    "x-specroad-validation-scope", "type", "const", "enum", "required",
    "properties", "additionalProperties", "items", "minLength", "minItems",
    "minimum", "maximum", "pattern", "anyOf", "allOf", "not", "format",
})


def _pointer(parent, key):
    return parent + "/" + str(key).replace("~", "~0").replace("/", "~1")


def _type_matches(value, kind):
    number = type(value) in (int, float) and (type(value) is int or math.isfinite(value))
    return {
        "object": type(value) is dict, "array": type(value) is list,
        "string": type(value) is str, "boolean": type(value) is bool,
        "null": value is None, "number": number,
        "integer": number and (type(value) is int or value.is_integer()),
    }[kind]


def _json_equal(left, right):
    # Python considers True == 1; JSON Schema does not.
    if type(left) is bool or type(right) is bool:
        return type(left) is type(right) and left == right
    if type(left) is dict and type(right) is dict:
        return left.keys() == right.keys() and all(_json_equal(left[k], right[k]) for k in left)
    if type(left) is list and type(right) is list:
        return len(left) == len(right) and all(_json_equal(a, b) for a, b in zip(left, right))
    return left == right



def _date(value):
    if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value) is None:
        return False
    try:
        date(*map(int, value.split("-")))
    except ValueError:
        return False
    return True


def _datetime_utc(value):
    # RFC 3339 UTC only: -00:00 explicitly means an unknown local offset.
    match = re.fullmatch(r"([0-9]{4})-([0-9]{2})-([0-9]{2})[Tt]([0-9]{2}):([0-9]{2}):([0-9]{2})(?:\.[0-9]+)?(?:[Zz]|\+00:00)", value)
    if match is None:
        return False
    year, month, day, hour, minute, second = map(int, match.groups())
    try:
        date(year, month, day)
    except ValueError:
        return False
    if hour > 23 or minute > 59 or second > 60:
        return False
    # Syntax supports a UTC leap-second candidate; this is not an IERS registry
    # lookup and makes no assertion that a future leap second was announced.
    return second != 60 or (hour == 23 and minute == 59 and (month, day) in ((6, 30), (12, 31)))


def _check_vocabulary(schema):
    """Check all trusted branches, including those not selected by an instance."""
    def check(node, active=()):
        if type(node) is bool:
            return
        if type(node) is not dict or node.keys() - _KEYWORDS:
            raise ValueError("Unsupported built-in schema vocabulary")
        if "type" in node and node["type"] not in (
                "object", "array", "string", "boolean", "null", "number", "integer"):
            raise ValueError("Unsupported built-in schema type")
        if "format" in node and node["format"] not in ("date-time", "date"):
            raise ValueError("Unknown built-in format assertion")
        if "$ref" in node:
            ref = node["$ref"]
            if type(ref) is not str or not ref.startswith("#/$defs/") or ref in active:
                raise ValueError("Only acyclic local built-in references are supported")
            name = ref[len("#/$defs/"):].replace("~1", "/").replace("~0", "~")
            try:
                target = schema["$defs"][name]
            except (KeyError, TypeError) as error:
                raise ValueError("Unknown built-in schema reference") from error
            check(target, (*active, ref))
        for key in ("$defs", "properties"):
            for child in node.get(key, {}).values():
                check(child, active)
        for key in ("anyOf", "allOf"):
            for child in node.get(key, ()):
                check(child, active)
        for key in ("not", "items", "additionalProperties"):
            if key in node:
                check(node[key], active)
    check(schema)


def validate_builtin(instance, schema):
    """Assert a built-in JSON Schema subset, reporting instance JSON Pointers."""
    _check_vocabulary(schema)
    def visit(value, node, pointer="", references=()):
        if node is True:
            return
        if node is False:
            raise ModelError("schema_rejected", pointer=pointer)
        if type(node) is not dict or node.keys() - _KEYWORDS:
            raise ValueError("Unsupported built-in schema vocabulary")
        if "$ref" in node:
            reference = node["$ref"]
            if (not isinstance(reference, str) or not reference.startswith("#/$defs/")
                    or reference in references):
                raise ValueError("Only acyclic local built-in references are supported")
            name = reference[len("#/$defs/"):].replace("~1", "/").replace("~0", "~")
            try:
                target = schema["$defs"][name]
            except KeyError as error:
                raise ValueError("Unknown built-in schema reference") from error
            visit(value, target, pointer, (*references, reference))
        if "type" in node and not _type_matches(value, node["type"]):
            raise ModelError("schema_type", pointer=pointer)
        if "const" in node and not _json_equal(value, node["const"]):
            raise ModelError("schema_const", pointer=pointer)
        if "enum" in node and not any(_json_equal(value, item) for item in node["enum"]):
            raise ModelError("schema_enum", pointer=pointer)
        if "anyOf" in node:
            for candidate in node["anyOf"]:
                try:
                    visit(value, candidate, pointer, references)
                    break
                except ModelError:
                    continue
            else:
                raise ModelError("schema_any_of", pointer=pointer)
        if "not" in node:
            try:
                visit(value, node["not"], pointer, references)
            except ModelError:
                pass
            else:
                raise ModelError("schema_not", pointer=pointer)
        for candidate in node.get("allOf", ()):
            visit(value, candidate, pointer, references)
        if type(value) is str:
            if len(value) < node.get("minLength", 0):
                raise ModelError("schema_min_length", pointer=pointer)
            if "pattern" in node and re.search(node["pattern"], value) is None:
                raise ModelError("schema_pattern", pointer=pointer)
        if "format" in node:
            if node["format"] not in ("date-time", "date"):
                raise ValueError("Unknown built-in format assertion")
            if type(value) is str and not (_date(value) if node["format"] == "date" else _datetime_utc(value)):
                raise ModelError("schema_format", pointer=pointer)
        if type(value) in (int, float):
            if "minimum" in node and value < node["minimum"]:
                raise ModelError("schema_minimum", pointer=pointer)
            if "maximum" in node and value > node["maximum"]:
                raise ModelError("schema_maximum", pointer=pointer)
        if type(value) is list:
            if len(value) < node.get("minItems", 0):
                raise ModelError("schema_min_items", pointer=pointer)
            for index, item in enumerate(value):
                visit(item, node.get("items", True), _pointer(pointer, index), references)
        if type(value) is dict:
            for field in node.get("required", ()):
                if field not in value:
                    raise ModelError("missing_field", pointer=_pointer(pointer, field))
            properties = node.get("properties", {})
            for field, item in value.items():
                if field not in properties and node.get("additionalProperties", True) is False:
                    raise ModelError("unknown_field", pointer=_pointer(pointer, field))
                visit(item, properties.get(field, node.get("additionalProperties", True)),
                      _pointer(pointer, field), references)
    visit(instance, schema)
