"""SRX 1.0 literal foundation with explicit context; no project execution.

Only literal evaluation is enabled in plan step 4.a. All other operators fail
closed until their own plan steps. Context values are observations supplied by
the caller, not a proof of complete graphs, resolved profiles or fresh files.
"""

from dataclasses import dataclass
from .errors import SrxError
from ._json_values import JsonSnapshot, json_type

LANGUAGE = "srx"
VERSION = "1.0"
SUPPORTED_OPERATORS = ("literal",)
CONTEXT_NAMES = ("artifact", "configuration", "project", "relations")


def _rule_id(rule_id):
    if type(rule_id) is not str or not rule_id.strip():
        raise SrxError("rule_id_required", rule_id=None, expected="nonempty string",
                       actual=json_type(rule_id))
    try:
        rule_id.encode("utf-8")
    except UnicodeError:
        raise SrxError("invalid_rule_id", rule_id=None, expected="Unicode string",
                       actual="string") from None
    return rule_id


def _exact_fields(value, names, *, rule_id, pointer, subject="expression"):
    if type(value) is not dict:
        raise SrxError("object_required", rule_id=rule_id, pointer=pointer,
                       expected="object", actual=json_type(value), subject=subject)
    if set(value) != set(names):
        raise SrxError("invalid_fields", rule_id=rule_id, pointer=pointer,
                       expected="closed object", actual="object", subject=subject)


def _validate_document(data, rule_id):
    _exact_fields(data, ("language", "version", "expression"), rule_id=rule_id, pointer="")
    if data["language"] != LANGUAGE:
        raise SrxError("unsupported_language", rule_id=rule_id, pointer="/language",
                       expected="srx", actual=json_type(data["language"]))
    if data["version"] != VERSION:
        raise SrxError("unsupported_version", rule_id=rule_id, pointer="/version",
                       expected="1.0", actual=json_type(data["version"]))
    node = data["expression"]
    if type(node) is not dict:
        raise SrxError("object_required", rule_id=rule_id, pointer="/expression",
                       expected="expression object", actual=json_type(node))
    if type(node.get("op")) is not str or node["op"] not in SUPPORTED_OPERATORS:
        raise SrxError("unsupported_operator", rule_id=rule_id, pointer="/expression/op",
                       expected="supported operator", actual=json_type(node.get("op")))
    _exact_fields(node, ("op", "value"), rule_id=rule_id, pointer="/expression")


def _validate_context(data, rule_id):
    _exact_fields(data, CONTEXT_NAMES, rule_id=rule_id, pointer="", subject="context")
    for name in ("artifact", "project"):
        if type(data[name]) is not dict:
            raise SrxError("context_object_required", rule_id=rule_id, pointer="/"+name,
                           expected="object", actual=json_type(data[name]), subject="context")
    if type(data["relations"]) not in (dict, list):
        raise SrxError("relations_view_required", rule_id=rule_id, pointer="/relations",
                       expected="object or array", actual=json_type(data["relations"]), subject="context")
    configuration = data["configuration"]
    if configuration is not None:
        _exact_fields(configuration, ("configuration_id", "effective_values"),
                      rule_id=rule_id, pointer="/configuration", subject="context")
        if type(configuration["configuration_id"]) is not str or not configuration["configuration_id"].strip():
            raise SrxError("configuration_id_required", rule_id=rule_id,
                           pointer="/configuration/configuration_id", expected="nonempty string",
                           actual=json_type(configuration["configuration_id"]), subject="context")
        if type(configuration["effective_values"]) is not dict:
            raise SrxError("effective_values_required", rule_id=rule_id,
                           pointer="/configuration/effective_values", expected="object",
                           actual=json_type(configuration["effective_values"]), subject="context")


@dataclass(frozen=True, init=False)
class EvaluationContext:
    """Only four explicit roots; profiles/statistics are passive project data.

    configuration=None explicitly means no selected configuration. No defaults
    or host environment are consulted. item is reserved for later quantifiers
    and is never accepted as an external root. Relations are precomputed data,
    never a callable resolver. No field lookup is enabled by this foundation.
    """
    _snapshot: JsonSnapshot

    def __init__(self, document, *, rule_id):
        rule_id = _rule_id(rule_id)
        snapshot = JsonSnapshot(document, rule_id=rule_id, subject="context")
        _validate_context(snapshot.data, rule_id)
        object.__setattr__(self, "_snapshot", snapshot)

    @property
    def data(self):
        return self._snapshot.data


@dataclass(frozen=True, init=False)
class SrxProgram:
    rule_id: str
    _snapshot: JsonSnapshot
    _value: JsonSnapshot
    source_bytes: bytes | None

    def __init__(self, document, *, rule_id):
        rule_id = _rule_id(rule_id)
        snapshot = JsonSnapshot(document, rule_id=rule_id)
        data = snapshot.data
        _validate_document(data, rule_id)
        object.__setattr__(self, "rule_id", rule_id)
        object.__setattr__(self, "source_bytes", None)
        object.__setattr__(self, "_snapshot", snapshot)
        object.__setattr__(self, "_value", JsonSnapshot(data["expression"]["value"],
                                                     rule_id=rule_id, pointer="/expression/value"))

    @property
    def document(self):
        return self._snapshot.data

    @property
    def value(self):
        return self._value.data


def evaluate(program, context):
    """Return a new JSON value, without Boolean coercion or external lookup."""
    if type(program) is not SrxProgram:
        raise SrxError("program_required", rule_id=None, expected="SrxProgram", actual="non_program")
    if type(context) is not EvaluationContext:
        raise SrxError("context_required", rule_id=program.rule_id,
                       expected="EvaluationContext", actual="non_context", subject="context")
    return program.value


def _decode(raw, rule_id, subject):
    """Use the existing strict reader; never interpret a string as a filename."""
    from ..model.errors import ModelError
    from ..storage.json_syntax import parse_json_object
    rule_id = _rule_id(rule_id)
    if type(raw) is not bytes:
        raise SrxError("bytes_required", rule_id=rule_id, pointer="",
                       expected="UTF-8 bytes", actual=json_type(raw), subject=subject)
    try:
        return parse_json_object(raw)
    except ModelError as error:
        raise SrxError(error.reason, rule_id=rule_id, pointer=error.pointer,
                       expected="strict JSON object", actual="invalid_json", subject=subject,
                       position=error.position, line=error.line, column=error.column) from None


def parse_program(raw, *, rule_id):
    """Parse original UTF-8 object bytes; keep them separate from JSON values."""
    program = SrxProgram(_decode(raw, rule_id, "expression"), rule_id=rule_id)
    object.__setattr__(program, "source_bytes", raw)
    return program


def parse_context(raw, *, rule_id):
    """Explicit passive context bytes, never a path, environment or live loader."""
    return EvaluationContext(_decode(raw, rule_id, "context"), rule_id=rule_id)
